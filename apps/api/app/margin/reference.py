"""Governed reference data: the commercial terms the margin rules read.

Two loaders write the same `semantic` tables: the fixture dataset's terms (development profile) and the policy
register file of a connected instance. Rows are keyed by business references (partner `ref`, product
`default_code`), never by Odoo ids, so rules stay portable across systems of record. A load is idempotent:
the same content replaces the previous rows of the same instance and company and records its provenance.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import sqlalchemy as sa
import yaml
from sqlalchemy.engine import Connection

from app.audit.log import append_event, content_hash
from app.config import REPO_ROOT

REGISTER_PATH = REPO_ROOT / "data" / "policies" / "margin_policy_register.yml"
TABLES = ("customer_segment", "discount_policy", "discount_derogation", "freight_contract", "contract_price", "cost_reference")


class ReferenceDataError(ValueError):
    pass


def _d(value: Any) -> date | None:
    if value in (None, "", False):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _dec(value: Any) -> Decimal:
    return Decimal(str(value))


@dataclass
class ReferenceRows:
    customer_segments: list[dict[str, Any]]
    discount_policies: list[dict[str, Any]]
    discount_derogations: list[dict[str, Any]]
    freight_contracts: list[dict[str, Any]]
    contract_prices: list[dict[str, Any]]
    cost_references: list[dict[str, Any]]

    def counts(self) -> dict[str, int]:
        return {name: len(getattr(self, name)) for name in self.__dataclass_fields__}

    def validate(self) -> None:
        for name, rows in (
            ("discount_policies", self.discount_policies),
            ("discount_derogations", self.discount_derogations),
            ("freight_contracts", self.freight_contracts),
            ("contract_prices", self.contract_prices),
            ("cost_references", self.cost_references),
            ("customer_segments", self.customer_segments),
        ):
            for row in rows:
                if not row.get("owner") or not row.get("source"):
                    raise ReferenceDataError(f"{name}: every row needs an owner and a source ({row})")
                if row["valid_to"] is not None and row["valid_to"] < row["valid_from"]:
                    raise ReferenceDataError(f"{name}: valid_to before valid_from ({row})")
        for row in self.discount_policies:
            if row["scope_segment"] is None and row["scope_customer_ref"] is None:
                raise ReferenceDataError(f"discount policy {row['policy_id']} needs a segment or a customer scope")


def rows_from_terms(terms: dict[str, Any], *, owner: str, source: str) -> ReferenceRows:
    """Rows from a terms document: the fixture dataset's `terms` or a parsed policy register."""
    segments = terms.get("customer_segments", {})
    if isinstance(segments, dict):
        segment_rows = [
            {"customer_ref": ref, "segment": segment, "valid_from": date(2000, 1, 1), "valid_to": None, "owner": owner, "source": source}
            for ref, segment in sorted(segments.items())
        ]
    else:
        segment_rows = [
            {"customer_ref": s["customer_ref"], "segment": s["segment"], "valid_from": _d(s["valid_from"]), "valid_to": _d(s.get("valid_to")),
             "owner": s.get("owner", owner), "source": s.get("source", source)}
            for s in segments
        ]
    policies = [
        {"policy_id": p["policy_id"], "version": int(p.get("version", 1)), "scope_segment": p.get("scope", {}).get("segment"),
         "scope_customer_ref": p.get("scope", {}).get("customer"), "max_discount_pct": _dec(p["max_discount_pct"]),
         "priority": int(p["priority"]), "valid_from": _d(p["valid_from"]), "valid_to": _d(p.get("valid_to")),
         "owner": p.get("owner", owner), "source": p.get("source", source)}
        for p in terms.get("discount_policies", [])
    ]
    derogations = [
        {"derogation_id": d["derogation_id"], "order_ref": d["order"], "max_discount_pct": _dec(d["max_discount_pct"]),
         "approved_by_role": d["approved_by_role"], "approved_on": _d(d["approved_on"]), "valid_from": _d(d["valid_from"]),
         "valid_to": _d(d.get("valid_to")), "evidence_ref": d.get("evidence_ref"), "owner": d.get("owner", owner),
         "source": d.get("source", source)}
        for d in terms.get("discount_derogations", [])
    ]
    freight = [
        {"contract_id": c["contract_id"], "customer_ref": c["customer"] if "customer" in c else c["customer_ref"], "terms": c["terms"],
         "amount": _dec(c.get("amount") or 0), "currency": c.get("currency", "EUR"), "trigger": c.get("trigger"),
         "valid_from": _d(c["valid_from"]), "valid_to": _d(c.get("valid_to")), "owner": c.get("owner", owner),
         "source": c.get("source", source)}
        for c in terms.get("freight_contracts", [])
    ]
    prices = [
        {"contract_id": c["contract_id"], "customer_ref": c["customer"] if "customer" in c else c["customer_ref"],
         "product_code": c.get("product") or c["product_code"], "unit_price": _dec(c["unit_price"]), "currency": c.get("currency", "EUR"),
         "min_quantity": _dec(c.get("min_quantity") or 0), "valid_from": _d(c["valid_from"]), "valid_to": _d(c.get("valid_to")),
         "owner": c.get("owner", owner), "source": c.get("source", source)}
        for c in terms.get("contract_prices", [])
    ]
    costs = [
        {"reference_id": r["reference_id"], "product_code": r.get("product") or r["product_code"], "unit_cost": _dec(r["unit_cost"]),
         "currency": r.get("currency", "EUR"), "frozen_on": _d(r["frozen_on"]), "valid_from": _d(r["valid_from"]),
         "valid_to": _d(r.get("valid_to")), "owner": r.get("owner", owner), "source": r.get("source", source)}
        for r in terms.get("cost_references", [])
    ]
    rows = ReferenceRows(segment_rows, policies, derogations, freight, prices, costs)
    rows.validate()
    return rows


def load_register(path: Path = REGISTER_PATH) -> tuple[dict[str, Any], ReferenceRows]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    owner = raw.get("owner") or "unspecified"
    return raw, rows_from_terms(raw, owner=owner, source=f"policy register {path.name} v{raw.get('register_version', 1)}")


def store_reference(
    conn: Connection,
    rows: ReferenceRows,
    *,
    source_instance: str,
    company_id: int,
    source_kind: str,
    source_ref: str,
    actor: str = "service:reference",
) -> uuid.UUID:
    """Replace the reference rows of one instance and company. Returns the load id."""
    load_id = uuid.uuid4()
    digest = content_hash({name: rows_ for name, rows_ in rows.__dict__.items()})
    conn.execute(
        sa.text(
            "insert into semantic.reference_load (load_id, source_instance, company_id, source_kind, source_ref, content_hash,"
            " actor, row_counts) values (:l, :i, :c, :k, :r, :h, :a, cast(:n as jsonb))"
        ),
        {"l": load_id, "i": source_instance, "c": company_id, "k": source_kind, "r": source_ref, "h": digest, "a": actor,
         "n": json.dumps(rows.counts())},
    )
    for table in TABLES:
        conn.execute(
            sa.text(f"delete from semantic.{table} where source_instance = :i and company_id = :c"),  # noqa: S608 table from TABLES
            {"i": source_instance, "c": company_id},
        )
    base = {"source_instance": source_instance, "company_id": company_id, "load_id": load_id}
    _insert(conn, "customer_segment", rows.customer_segments, base)
    _insert(conn, "discount_policy", rows.discount_policies, base)
    _insert(conn, "discount_derogation", rows.discount_derogations, base)
    _insert(conn, "freight_contract", rows.freight_contracts, base)
    _insert(conn, "contract_price", rows.contract_prices, base)
    _insert(conn, "cost_reference", rows.cost_references, base)
    append_event(
        conn,
        actor=actor,
        action="reference.loaded",
        object_type="reference_load",
        object_id=str(load_id),
        payload={"source_instance": source_instance, "company_id": company_id, "source_kind": source_kind,
                 "source_ref": source_ref, "content_hash": digest, "row_counts": rows.counts()},
    )
    return load_id


def _insert(conn: Connection, table: str, rows: list[dict[str, Any]], base: dict[str, Any]) -> None:
    if not rows:
        return
    columns = [*base, *rows[0]]
    conn.execute(
        sa.text(f"insert into semantic.{table} ({', '.join(columns)}) values ({', '.join(':' + c for c in columns)})"),  # noqa: S608
        [{**base, **row} for row in rows],
    )


# --------------------------------------------------------------------------- read side
@dataclass
class ReferenceData:
    """Every term of one instance and company, indexed for the rules. Loaded once per engine run."""

    segments: dict[str, list[dict[str, Any]]]
    policies: list[dict[str, Any]]
    derogations: dict[str, list[dict[str, Any]]]
    freight: dict[str, list[dict[str, Any]]]
    prices: dict[tuple[str, str], list[dict[str, Any]]]
    costs: dict[str, list[dict[str, Any]]]
    load: dict[str, Any] | None

    @staticmethod
    def _valid(row: dict[str, Any], on: date) -> bool:
        return row["valid_from"] <= on and (row["valid_to"] is None or on <= row["valid_to"])

    def segment_of(self, customer_ref: str | None, on: date) -> str | None:
        for row in self.segments.get(customer_ref or "", []):
            if self._valid(row, on):
                return row["segment"]
        return None

    def policies_for(self, customer_ref: str | None, segment: str | None, on: date) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """(applicable policies valid on the date, policies in scope but not valid)."""
        in_scope = [
            p for p in self.policies
            if (p["scope_customer_ref"] is not None and p["scope_customer_ref"] == customer_ref)
            or (p["scope_segment"] is not None and p["scope_segment"] == segment)
        ]
        valid = [p for p in in_scope if self._valid(p, on)]
        return valid, [p for p in in_scope if p not in valid]

    def derogation_for(self, order_ref: str, on: date) -> dict[str, Any] | None:
        for row in self.derogations.get(order_ref, []):
            if self._valid(row, on):
                return row
        return None

    def freight_contract_for(self, customer_ref: str | None, on: date) -> dict[str, Any] | None:
        for row in self.freight.get(customer_ref or "", []):
            if self._valid(row, on):
                return row
        return None

    def contract_price_for(self, customer_ref: str | None, product_code: str | None, on: date, quantity: Decimal) -> dict[str, Any] | None:
        rows = [r for r in self.prices.get((customer_ref or "", product_code or ""), []) if self._valid(r, on) and quantity >= r["min_quantity"]]
        return max(rows, key=lambda r: r["min_quantity"]) if rows else None

    def cost_reference_for(self, product_code: str | None, on: date) -> dict[str, Any] | None:
        rows = [r for r in self.costs.get(product_code or "", []) if self._valid(r, on) and r["frozen_on"] < on]
        return max(rows, key=lambda r: r["frozen_on"]) if rows else None


def read_reference(conn: Connection, source_instance: str, company_id: int) -> ReferenceData:
    def rows(table: str) -> list[dict[str, Any]]:
        return [
            dict(r) for r in conn.execute(
                sa.text(f"select * from semantic.{table} where source_instance = :i and company_id = :c"),  # noqa: S608
                {"i": source_instance, "c": company_id},
            ).mappings()
        ]

    segments: dict[str, list[dict[str, Any]]] = {}
    for r in rows("customer_segment"):
        segments.setdefault(r["customer_ref"], []).append(r)
    derogations: dict[str, list[dict[str, Any]]] = {}
    for r in rows("discount_derogation"):
        derogations.setdefault(r["order_ref"], []).append(r)
    freight: dict[str, list[dict[str, Any]]] = {}
    for r in rows("freight_contract"):
        freight.setdefault(r["customer_ref"], []).append(r)
    prices: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in rows("contract_price"):
        prices.setdefault((r["customer_ref"], r["product_code"]), []).append(r)
    costs: dict[str, list[dict[str, Any]]] = {}
    for r in rows("cost_reference"):
        costs.setdefault(r["product_code"], []).append(r)
    load = conn.execute(
        sa.text("select load_id, source_kind, source_ref, loaded_at, content_hash from semantic.reference_load"
                " where source_instance = :i and company_id = :c order by loaded_at desc limit 1"),
        {"i": source_instance, "c": company_id},
    ).mappings().first()
    return ReferenceData(segments, rows("discount_policy"), derogations, freight, prices, costs, dict(load) if load else None)
