"""Extraction sources with one contract for Odoo and fixtures.

A source yields records changed after a watermark in (write_date, id) order,
lists every existing id (deletions are reconciled against it, never inferred
from a watermark), and computes server-side sums used as reconciliation
control totals.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from app.connectors.odoo import OdooReader
from app.fixtures.demo_dataset import FixtureDataset

ODOO_DATETIME = "%Y-%m-%d %H:%M:%S"
# Archived records still exist: they must not be mistaken for deletions.
ALL_RECORDS_CONTEXT = {"active_test": False}


@dataclass(frozen=True, order=True)
class Watermark:
    write_date: str
    record_id: int


class Source(Protocol):
    source_instance: str
    source_kind: str
    independence: str

    def available_fields(self, model: str) -> set[str]: ...

    def iter_changed(
        self, model: str, fields: list[str], after: Watermark | None, page_size: int = 500
    ) -> Iterator[dict[str, Any]]: ...

    def all_ids(self, model: str) -> set[int]: ...

    def sum_by_company(self, model: str, domain: list, field: str) -> dict[int, Decimal]: ...


def parse_odoo_datetime(value: str) -> datetime:
    return datetime.strptime(value, ODOO_DATETIME)


class OdooSource:
    source_kind = "odoo"
    independence = "SERVER_AGGREGATE"

    def __init__(self, reader: OdooReader, source_instance: str):
        self.reader = reader
        self.source_instance = source_instance
        self._fields: dict[str, set[str]] = {}

    def available_fields(self, model: str) -> set[str]:
        if model not in self._fields:
            self._fields[model] = set(self.reader.fields_get(model, ["type"]))
        return self._fields[model]

    def iter_changed(self, model, fields, after, page_size=500):
        cursor = after
        while True:
            domain: list = []
            if cursor is not None:
                domain = [
                    "|",
                    ["write_date", ">", cursor.write_date],
                    "&",
                    ["write_date", "=", cursor.write_date],
                    ["id", ">", cursor.record_id],
                ]
            page = self.reader.search_read(
                model, domain, fields, order="write_date asc, id asc", limit=page_size, context=ALL_RECORDS_CONTEXT
            )
            yield from page
            if len(page) < page_size:
                return
            cursor = Watermark(page[-1]["write_date"], page[-1]["id"])

    def all_ids(self, model):
        ids: set[int] = set()
        last = 0
        while True:
            page = self.reader.search_read(
                model, [["id", ">", last]], ["id"], order="id asc", limit=5000, context=ALL_RECORDS_CONTEXT
            )
            ids.update(row["id"] for row in page)
            if len(page) < 5000:
                return ids
            last = page[-1]["id"]

    def sum_by_company(self, model, domain, field):
        rows = self.reader.call(
            model, "formatted_read_group", domain=domain, groupby=["company_id"], aggregates=[f"{field}:sum"]
        )
        return {row["company_id"][0]: Decimal(str(row[f"{field}:sum"] or 0)) for row in rows if row["company_id"]}


class FixtureSource:
    """Serves a generated dataset with the same semantics as the Odoo API."""

    source_kind = "fixture"
    independence = "FIXTURE_CONTROL_TOTAL"

    def __init__(self, dataset: FixtureDataset, source_instance: str | None = None):
        self.dataset = dataset
        self.source_instance = source_instance or dataset.source_instance
        self._index: dict[str, dict[int, dict[str, Any]]] = {}

    def available_fields(self, model):
        rows = self.dataset.records.get(model, [])
        return set().union(*(r.keys() for r in rows)) if rows else set()

    def iter_changed(self, model, fields, after, page_size=500):
        rows = sorted(self.dataset.records.get(model, []), key=lambda r: (r["write_date"], r["id"]))
        for row in rows:
            if after is None or (row["write_date"], row["id"]) > (after.write_date, after.record_id):
                yield {name: row[name] for name in fields if name in row}

    def all_ids(self, model):
        return {row["id"] for row in self.dataset.records.get(model, [])}

    def sum_by_company(self, model, domain, field):
        self._index = {m: {r["id"]: r for r in rows} for m, rows in self.dataset.records.items()}
        totals: dict[int, Decimal] = {}
        for row in self.dataset.records.get(model, []):
            if all(self._match(model, row, leaf) for leaf in domain):
                company = row["company_id"][0]
                totals[company] = totals.get(company, Decimal(0)) + Decimal(str(row[field]))
        return totals

    def _resolve(self, model: str, row: dict[str, Any], path: str) -> Any:
        head, _, rest = path.partition(".")
        value = row.get(head)
        if not rest:
            return value
        target_model = {"move_id": "account.move", "account_id": "account.account"}[head]
        return self._resolve(target_model, self._index[target_model][value[0]], rest)

    def _match(self, model: str, row: dict[str, Any], leaf: list) -> bool:
        path, operator, expected = leaf
        value = self._resolve(model, row, path)
        if operator == "=":
            return value == expected
        if operator == "in":
            return value in expected
        if operator == ">=":
            return value >= expected
        if operator == "<":
            return value < expected
        raise ValueError(f"operator {operator} is not supported by the fixture source")
