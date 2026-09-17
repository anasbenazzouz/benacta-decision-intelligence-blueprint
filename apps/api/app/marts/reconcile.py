"""Reconcile marts against control totals, per company and month.

Control totals are not re-summed from our own extract: on Odoo they come from
`formatted_read_group`, aggregated by the server at reconciliation time
(SERVER_AGGREGATE). Fixture control totals come from the fixture source itself
and are labelled FIXTURE_CONTROL_TOTAL, never presented as independent evidence.

Checks:
- REVENUE_POSTED: signed revenue of posted customer invoice and credit note product lines
- COGS_POSTED: posted COGS items on expense accounts (the expense side of the cost pair, direct
  cost or plain expense depending on the chart). When goods were invoiced in a month without any
  posted COGS, the check is UNAVAILABLE and gross margin can only be a management proxy.
- INVOICE_HEADER_LINES: the untaxed amount of every posted invoice header against the sum of
  its product lines in the marts (SOURCE_HEADER: the source's own header, consistent with its
  lines by construction, so a difference is an extraction or transformation defect).

Every row carries the tolerance, the source timestamp of the newest record behind the
snapshot, the ingestion timestamp and the transformation version, so a closed period can be
reported and re-verified later.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from app.audit.log import append_event
from app.ingestion.sources import Source
from app.numbers import decimal_text

TOLERANCE = Decimal("0.01")
REVENUE_DOMAIN = [
    ["display_type", "=", "product"],
    ["parent_state", "=", "posted"],
    ["move_id.move_type", "in", ["out_invoice", "out_refund"]],
]
# Account types of the expense side of a posted cost-of-goods-sold pair: direct cost accounts, or plain expense accounts
# where the chart carries no direct cost type (Odoo 19 with the French chart posts on 607 "Goods", type expense).
COGS_ACCOUNT_TYPES = frozenset({"expense_direct_cost", "expense"})
COGS_DOMAIN = [
    ["display_type", "=", "cogs"],
    ["parent_state", "=", "posted"],
    ["account_id.account_type", "in", sorted(COGS_ACCOUNT_TYPES)],
]


@dataclass(frozen=True)
class ReconciliationRow:
    check_id: str
    company_id: int
    period: str
    status: str
    independence: str
    expected: Decimal | None
    actual: Decimal | None
    explanation: str
    tolerance: Decimal = TOLERANCE
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def difference(self) -> Decimal | None:
        return (self.actual - self.expected) if self.expected is not None and self.actual is not None else None


@dataclass(frozen=True)
class SnapshotProvenance:
    source_timestamp: datetime | None
    ingested_at: datetime | None
    transformation_version: str | None


def _month_bounds(period: str) -> tuple[str, str]:
    year, month = map(int, period.split("-"))
    start = date(year, month, 1)
    end = date(year + (month == 12), month % 12 + 1, 1)
    return str(start), str(end)


def _status(expected: Decimal | None, actual: Decimal) -> tuple[str, str]:
    if expected is None:
        return "UNAVAILABLE", "source control total could not be computed"
    difference = actual - expected
    if abs(difference) <= TOLERANCE:
        return "RECONCILED", "marts total equals the source control total within 0.01"
    return "UNRECONCILED", (
        f"difference {difference}: records changed after the snapshot, excluded lines, or an extraction gap"
    )


def snapshot_provenance(engine: Engine, snapshot_id: uuid.UUID) -> SnapshotProvenance:
    with engine.connect() as conn:
        row = conn.execute(
            sa.text(
                "select b.finished_at, s.transformation_version,"
                " (select max(v.source_write_date) from raw.source_record_version v"
                "   where v.source_instance = b.source_instance and v.batch_seq <= b.batch_seq"
                "     and v.source_model in ('account.move', 'account.move.line')) as source_timestamp"
                " from raw.ingestion_batch b left join marts.snapshot s on s.snapshot_id = b.batch_id where b.batch_id = :s"
            ),
            {"s": snapshot_id},
        ).first()
    if row is None:
        return SnapshotProvenance(None, None, None)
    return SnapshotProvenance(row.source_timestamp, row.finished_at, row.transformation_version)


def reconcile(
    engine: Engine, source: Source, snapshot_id: uuid.UUID, *, actor: str = "service:reconciliation"
) -> list[ReconciliationRow]:
    with engine.connect() as conn:
        revenue = conn.execute(
            sa.text(
                "select company_id, to_char(accounting_date, 'YYYY-MM') as period, sum(revenue_company_ccy) as total"
                " from marts.fact_invoice_line where snapshot_id = :s group by 1, 2"
            ),
            {"s": snapshot_id},
        ).all()
        cogs = {
            (r.company_id, r.period): r.total
            for r in conn.execute(
                sa.text(
                    "select company_id, to_char(accounting_date, 'YYYY-MM') as period, sum(balance) as total"
                    " from marts.fact_posted_cogs_line where snapshot_id = :s group by 1, 2"
                ),
                {"s": snapshot_id},
            )
        }
        # Goods revenue, storable or not: selling goods without any posted COGS leaves margin unprovable.
        goods_revenue_lines = {
            (r.company_id, r.period): r.lines
            for r in conn.execute(
                sa.text(
                    "select i.company_id, to_char(i.accounting_date, 'YYYY-MM') as period, count(*) as lines"
                    " from marts.fact_invoice_line i join marts.dim_product p"
                    " on p.snapshot_id = i.snapshot_id and p.product_id = i.product_id"
                    " where i.snapshot_id = :s and p.product_type = 'consu' group by 1, 2"
                ),
                {"s": snapshot_id},
            )
        }
        header_rows = _invoice_headers(conn, snapshot_id)

    rows: list[ReconciliationRow] = []
    periods = sorted({(r.company_id, r.period) for r in revenue} | set(cogs))
    for company_id, period in periods:
        start, end = _month_bounds(period)
        window = [["date", ">=", start], ["date", "<", end]]

        actual_revenue = next(
            (r.total for r in revenue if (r.company_id, r.period) == (company_id, period)), Decimal(0)
        )
        expected_revenue = _control_total(source, REVENUE_DOMAIN + window, company_id, negate=True)
        status, explanation = _status(expected_revenue, actual_revenue)
        rows.append(
            ReconciliationRow(
                "REVENUE_POSTED",
                company_id,
                period,
                status,
                source.independence,
                expected_revenue,
                actual_revenue,
                explanation,
            )
        )

        actual_cogs = cogs.get((company_id, period), Decimal(0))
        expected_cogs = _control_total(source, COGS_DOMAIN + window, company_id, negate=False)
        if expected_cogs == 0 and actual_cogs == 0 and goods_revenue_lines.get((company_id, period)):
            rows.append(
                ReconciliationRow(
                    "COGS_POSTED",
                    company_id,
                    period,
                    "UNAVAILABLE",
                    "NONE",
                    Decimal(0),
                    Decimal(0),
                    "goods were invoiced but no COGS is posted: gross margin is a management proxy",
                )
            )
        else:
            status, explanation = _status(expected_cogs, actual_cogs)
            rows.append(
                ReconciliationRow(
                    "COGS_POSTED",
                    company_id,
                    period,
                    status,
                    source.independence,
                    expected_cogs,
                    actual_cogs,
                    explanation,
                )
            )
        rows.append(_header_check(company_id, period, header_rows.get((company_id, period), [])))

    provenance = snapshot_provenance(engine, snapshot_id)
    with engine.begin() as conn:
        conn.execute(sa.text("delete from marts.reconciliation_result where snapshot_id = :s"), {"s": snapshot_id})
        if rows:
            conn.execute(
                sa.text(
                    "insert into marts.reconciliation_result (snapshot_id, check_id, company_id, period, status,"
                    " independence, expected, actual, difference, explanation, tolerance, source_timestamp, ingested_at,"
                    " transformation_version, detail) values (:s, :c, :co, :p, :st, :ind, :e, :a, :d, :x, :t, :src, :ing,"
                    " :tv, cast(:det as jsonb))"
                ),
                [
                    {
                        "s": snapshot_id,
                        "c": r.check_id,
                        "co": r.company_id,
                        "p": r.period,
                        "st": r.status,
                        "ind": r.independence,
                        "e": r.expected,
                        "a": r.actual,
                        "d": r.difference,
                        "x": r.explanation,
                        "t": r.tolerance,
                        "src": provenance.source_timestamp,
                        "ing": provenance.ingested_at,
                        "tv": provenance.transformation_version,
                        "det": json.dumps(r.detail),
                    }
                    for r in rows
                ],
            )
        summary: dict[str, int] = {}
        for r in rows:
            summary[f"{r.check_id}:{r.status}"] = summary.get(f"{r.check_id}:{r.status}", 0) + 1
        append_event(
            conn,
            actor=actor,
            action="marts.reconciled",
            object_type="snapshot",
            object_id=str(snapshot_id),
            run_id=str(snapshot_id),
            payload={
                "independence": source.independence,
                "results": summary,
                "transformation_version": provenance.transformation_version,
            },
        )
    return rows


def _invoice_headers(conn, snapshot_id: uuid.UUID) -> dict[tuple[int, str], list[dict[str, Any]]]:
    """Posted revenue invoice headers of the snapshot next to the sum of their product lines in the marts."""
    rows = conn.execute(
        sa.text(
            "with batch as (select source_instance, batch_seq from raw.ingestion_batch where batch_id = :s),"
            " headers as ("
            "   select h.source_id as invoice_id, h.company_id, to_char(cast(h.payload->>'date' as date), 'YYYY-MM') as period,"
            "          h.payload->>'name' as name, cast(h.payload->>'amount_untaxed_signed' as numeric) as header_amount"
            "   from batch b, staging.records_at(b.source_instance, 'account.move', b.batch_seq) h"
            "   where h.payload->>'state' = 'posted' and h.payload->>'move_type' in ('out_invoice', 'out_refund'))"
            " select hd.invoice_id, hd.company_id, hd.period, hd.name, hd.header_amount,"
            "        coalesce((select sum(revenue_company_ccy) from marts.fact_invoice_line l"
            "                  where l.snapshot_id = :s and l.invoice_id = hd.invoice_id), 0) as lines_amount"
            " from headers hd order by hd.period, hd.invoice_id"
        ),
        {"s": snapshot_id},
    ).mappings()
    grouped: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for r in rows:
        grouped.setdefault((r["company_id"], r["period"]), []).append(dict(r))
    return grouped


def _header_check(company_id: int, period: str, headers: list[dict[str, Any]]) -> ReconciliationRow:
    if not headers:
        return ReconciliationRow(
            "INVOICE_HEADER_LINES", company_id, period, "UNAVAILABLE", "NONE", None, Decimal(0),
            "no posted invoice header found for the period", detail={"invoices": 0},
        )
    expected = sum((h["header_amount"] or Decimal(0) for h in headers), Decimal(0))
    actual = sum((h["lines_amount"] for h in headers), Decimal(0))
    mismatched = [
        {"invoice_id": h["invoice_id"], "name": h["name"], "header": str(h["header_amount"]), "lines": str(h["lines_amount"])}
        for h in headers
        if abs((h["header_amount"] or Decimal(0)) - h["lines_amount"]) > TOLERANCE
    ]
    if mismatched:
        return ReconciliationRow(
            "INVOICE_HEADER_LINES", company_id, period, "UNRECONCILED", "SOURCE_HEADER", expected, actual,
            f"{len(mismatched)} invoice(s) whose product lines do not sum to the header",
            detail={"invoices": len(headers), "mismatched": mismatched[:50]},
        )
    return ReconciliationRow(
        "INVOICE_HEADER_LINES", company_id, period, "RECONCILED", "SOURCE_HEADER", expected, actual,
        "every posted invoice header equals the sum of its product lines within 0.01", detail={"invoices": len(headers)},
    )


def _control_total(source: Source, domain: list, company_id: int, *, negate: bool) -> Decimal | None:
    try:
        totals = source.sum_by_company("account.move.line", domain, "balance")
    except Exception:  # noqa: BLE001 - an unavailable control total is a status, not a crash
        return None
    value = totals.get(company_id, Decimal(0))
    return -value if negate else value


def margin_basis(engine: Engine, snapshot_id: uuid.UUID) -> str:
    """RECONCILED_COGS only when every COGS check reconciled; otherwise the margin is a management proxy."""
    with engine.connect() as conn:
        statuses = (
            conn.execute(
                sa.text(
                    "select distinct status from marts.reconciliation_result where snapshot_id = :s and check_id = 'COGS_POSTED'"
                ),
                {"s": snapshot_id},
            )
            .scalars()
            .all()
        )
    return "RECONCILED_COGS" if statuses == ["RECONCILED"] else "MANAGEMENT_PROXY"


def reconciliation_report(engine: Engine, snapshot_id: uuid.UUID, period: str | None = None) -> dict[str, Any]:
    """The closed-period report: every check with its totals, tolerance, timestamps and versions."""
    provenance = snapshot_provenance(engine, snapshot_id)
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text(
                "select check_id, company_id, period, status, independence, expected, actual, difference, tolerance,"
                " explanation, detail from marts.reconciliation_result where snapshot_id = :s"
                " and (cast(:p as text) is null or period = :p) order by company_id, period, check_id"
            ),
            {"s": snapshot_id, "p": period},
        ).mappings().all()
    checks = [
        {
            "check_id": r["check_id"], "company_id": r["company_id"], "period": r["period"], "status": r["status"],
            "independence": r["independence"], "source_total": decimal_text(r["expected"]),
            "analytical_total": decimal_text(r["actual"]), "difference": decimal_text(r["difference"]),
            "tolerance": decimal_text(r["tolerance"]), "explanation": r["explanation"], "detail": r["detail"],
        }
        for r in rows
    ]
    periods = sorted({c["period"] for c in checks})
    return {
        "snapshot_id": str(snapshot_id),
        "period": period,
        "periods": periods,
        "source_timestamp": None if provenance.source_timestamp is None else provenance.source_timestamp.isoformat(),
        "ingestion_timestamp": None if provenance.ingested_at is None else provenance.ingested_at.isoformat(),
        "transformation_version": provenance.transformation_version,
        "period_status": {
            p: ("RECONCILED" if all(c["status"] == "RECONCILED" for c in checks if c["period"] == p and c["check_id"] != "COGS_POSTED")
                and all(c["status"] in ("RECONCILED", "UNAVAILABLE") for c in checks if c["period"] == p and c["check_id"] == "COGS_POSTED")
                else "BLOCKED")
            for p in periods
        },
        "margin_basis": margin_basis(engine, snapshot_id),
        "checks": checks,
    }
