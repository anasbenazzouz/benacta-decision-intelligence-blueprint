"""Shared machinery of the Odoo seed executors: external identifiers, adoption of twins, batching and reporting.

Every record a seeder creates receives the external identifier `benacta_demo.<model>__<fixture key>`, so a replay
creates nothing twice. Records created just before an interruption are adopted by a unique business reference
instead of being duplicated. Existing records of the company are never modified by these helpers.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from app.connectors.odoo import OdooReader, OdooWriter
from app.fixtures.demo_dataset import FixtureDataset

XMLID_MODULE = "benacta_demo"
BATCH = 200


def xmlid_name(model: str, key: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", f"{model.replace('.', '_')}__{key}")


def m2o_id(value: Any) -> int | None:
    return value[0] if isinstance(value, list | tuple) and value else None


def batched(items: list[Any], size: int) -> Iterable[list[Any]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


@dataclass
class Step:
    model: str
    planned: int = 0
    existing: int = 0
    adopted: int = 0
    created: int = 0


@dataclass
class SeedReport:
    steps: dict[str, Step] = field(default_factory=dict)
    mismatches: list[str] = field(default_factory=list)
    configuration: list[str] = field(default_factory=list)  # shared settings the executor changes on the owner's decision

    def step(self, model: str) -> Step:
        return self.steps.setdefault(model, Step(model))


def print_report(report: SeedReport, *, dry_run: bool) -> None:
    print(f"{'model':28} {'planned':>8} {'present':>8} {'adopted':>8} {'to create' if dry_run else 'created':>9}")
    for step in report.steps.values():
        print(f"{step.model:28} {step.planned:8} {step.existing:8} {step.adopted:8} {step.created:9}")
    for change in report.configuration:
        print(f"  {'CONFIGURATION' if dry_run else 'CONFIGURED':13} {change}")
    for mismatch in report.mismatches:
        print(f"  MISMATCH {mismatch}")


class OdooSeeder:
    """Base of the seeders: maps fixture ids to Odoo ids through the external identifier registry."""

    def __init__(self, reader: OdooReader, writer: OdooWriter | None, company_name: str, dataset: FixtureDataset):
        self.r, self.w = reader, writer
        self.ds = dataset
        self.company_name = company_name
        self.ids: dict[str, dict[int, int]] = defaultdict(dict)
        self.report = SeedReport()
        self.fixture = {m: {row["id"]: row for row in rows} for m, rows in dataset.records.items()}
        self.existing = {row["name"]: row["res_id"] for row in reader.iter_search_read(
            "ir.model.data", [["module", "=", XMLID_MODULE]], ["name", "res_id"])}

    @property
    def dry_run(self) -> bool:
        return self.w is None

    def key(self, model: str, fixture_id: int) -> str:
        return xmlid_name(model, self.ds.keys[model][fixture_id])

    def ref(self, model: str, value: Any) -> int | bool:
        fixture_id = m2o_id(value) if not isinstance(value, int) else value
        if fixture_id is None:
            return False
        return self.ids[model][fixture_id]

    def _register(self, model: str, rows: list[dict[str, Any]], odoo_ids: list[int]) -> None:
        names = [self.key(model, row["id"]) for row in rows]
        self.w.create("ir.model.data", [{"module": XMLID_MODULE, "name": n, "model": model, "res_id": i, "noupdate": True}
                                        for n, i in zip(names, odoo_ids, strict=True)])
        for row, name, odoo_id in zip(rows, names, odoo_ids, strict=True):
            self.existing[name] = odoo_id
            self.ids[model][row["id"]] = odoo_id

    def register_one(self, model: str, row: dict[str, Any], odoo_id: int) -> None:
        self._register(model, [row], [odoo_id])

    def ensure(
        self,
        model: str,
        rows: list[dict[str, Any]],
        vals: Callable[[dict[str, Any]], dict[str, Any]],
        *,
        adopt: tuple[str, Callable[[dict[str, Any]], Any]] | None = None,
        batch: int = BATCH,
    ) -> list[int]:
        """Map rows already in Odoo, adopt unregistered twins by a unique reference, create the rest."""
        step = self.report.step(model)
        step.planned += len(rows)
        todo = []
        for row in rows:
            name = self.key(model, row["id"])
            if name in self.existing:
                self.ids[model][row["id"]] = self.existing[name]
                step.existing += 1
            else:
                todo.append(row)
        if adopt and todo:
            field_name, value_of = adopt
            wanted = {value_of(row): row for row in todo}
            found = self.r.search_read(model, [[field_name, "in", list(wanted)]], [field_name])
            twins = [(wanted[rec[field_name]], rec["id"]) for rec in found if rec.get(field_name) in wanted]
            if twins and not self.dry_run:
                self._register(model, [t[0] for t in twins], [t[1] for t in twins])
            step.adopted += len(twins)
            adopted = {id(t[0]) for t in twins}
            todo = [row for row in todo if id(row) not in adopted]
        if self.dry_run:
            step.created += len(todo)
            return []
        created: list[int] = []
        for chunk in batched(todo, batch):
            odoo_ids = self.w.create(model, [vals(row) for row in chunk])
            self._register(model, chunk, odoo_ids)
            created.extend(odoo_ids)
        step.created += len(created)
        return created

    def map_by_name(self, model: str, rows: list[dict[str, Any]], extra: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
                    domain: list | None = None) -> None:
        """Reference data: reuse a record with the same name, create the missing ones."""
        names = {row["name"] for row in rows}
        found = {rec["name"]: rec["id"] for rec in self.r.search_read(model, [["name", "in", list(names)], *(domain or [])], ["name"])
                 if rec.get("name")}
        missing = []
        for row in rows:
            if row["name"] in found and self.key(model, row["id"]) not in self.existing:
                self.ids[model][row["id"]] = found[row["name"]]
                self.report.step(model).planned += 1
                self.report.step(model).existing += 1
            else:
                missing.append(row)
        self.ensure(model, missing, lambda row: {"name": row["name"], **(extra(row) if extra else {})})

    def lookup_one(self, model: str, domain: list, what: str, context: dict[str, Any] | None = None) -> int:
        rows = self.r.search_read(model, domain, ["id"], limit=1, context=context)
        if not rows:
            raise RuntimeError(f"{what} not found in Odoo ({model} {domain})")
        return rows[0]["id"]

    def _map_lines(self, parent_model: str, o2m: str, line_model: str, parents: list[dict[str, Any]]) -> None:
        """Register the lines Odoo created with the parents, in order, under the fixture line keys."""
        odoo = {p["id"]: p[o2m] for p in self.r.search_read(parent_model, [["id", "in", [self.ids[parent_model][p["id"]] for p in parents]]], [o2m])}
        rows, ids = [], []
        for parent in parents:
            fixture_lines = parent[o2m] if parent_model == "sale.order" else [
                line["id"] for line in self.ds.records[line_model] if line["order_id"][0] == parent["id"]]
            created = sorted(odoo[self.ids[parent_model][parent["id"]]])
            if len(created) != len(fixture_lines):
                raise RuntimeError(f"{parent_model} {parent['name']}: {len(created)} lines in Odoo, {len(fixture_lines)} expected")
            for fixture_id, odoo_id in zip(fixture_lines, created, strict=True):
                if self.key(line_model, fixture_id) in self.existing:
                    self.ids[line_model][fixture_id] = self.existing[self.key(line_model, fixture_id)]
                else:
                    rows.append(self.fixture[line_model][fixture_id])
                    ids.append(odoo_id)
        if rows:
            self._register(line_model, rows, ids)
