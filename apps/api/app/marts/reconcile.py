"""Reconcile marts against control totals computed by the source, per company and month.

Control totals are not re-summed from our own extract: on Odoo they come from
`formatted_read_group`, aggregated by the server at reconciliation time
(SERVER_AGGREGATE). Fixture control totals come from the fixture source itself
and are labelled FIXTURE_CONTROL_TOTAL, never presented as independent evidence.

Checks:
- REVENUE_POSTED: signed revenue of posted customer invoice and credit note product lines
- COGS_POSTED: posted COGS items on direct cost accounts. When goods were invoiced in a
  month without any posted COGS, the check is UNAVAILABLE and gross margin can only be a
  management proxy.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from app.audit.log import append_event
from app.ingestion.sources import Source

TOLERANCE = Decimal("0.01")
REVENUE_DOMAIN = [
    ["display_type", "=", "product"],
    ["parent_state", "=", "posted"],
    ["move_id.move_type", "in", ["out_invoice", "out_refund"]],
]
COGS_DOMAIN = [
    ["display_type", "=", "cogs"],
    ["parent_state", "=", "posted"],
    ["account_id.account_type", "=", "expense_direct_cost"],
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

    with engine.begin() as conn:
        conn.execute(sa.text("delete from marts.reconciliation_result where snapshot_id = :s"), {"s": snapshot_id})
        if rows:
            conn.execute(
                sa.text(
                    "insert into marts.reconciliation_result (snapshot_id, check_id, company_id, period, status,"
                    " independence, expected, actual, difference, explanation) values (:s, :c, :co, :p, :st, :ind, :e,"
                    " :a, :d, :x)"
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
                        "d": (r.actual - r.expected) if r.expected is not None and r.actual is not None else None,
                        "x": r.explanation,
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
            payload={"independence": source.independence, "results": summary},
        )
    return rows


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
