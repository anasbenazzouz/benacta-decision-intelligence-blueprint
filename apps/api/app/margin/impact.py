"""Impact tracking: estimated recovery when a recommendation is approved, realised recovery only from posted
documents dated after the decision. Nothing is estimated into the realised column.

Measured for the billing component (discount, price, freight): posted customer invoice lines linked to the
subject's order lines, or freight lines on the subject's invoices, with an accounting date after the decision.
Cost variances are not receivable from the customer and stay NOT_MEASURABLE in this version.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from app.audit.log import append_event, canonical_json
from app.numbers import decimal_text

TOLERANCE = Decimal("0.01")


def _rows(conn: Connection, sql: str, **params: Any) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(sa.text(sql), params).mappings()]


def _recovery_lines(conn: Connection, snapshot_id: uuid.UUID, case: dict[str, Any], freight_codes: frozenset[str]) -> list[dict[str, Any]]:
    decided = case["decided_at"]
    if case["subject_type"] == "sale_order_line":
        return _rows(conn, """
            select i.invoice_line_id, i.invoice_name, i.accounting_date, i.revenue_company_ccy, b.allocation_weight
            from marts.bridge_sale_invoice_line b
            join marts.fact_invoice_line i on i.snapshot_id = b.snapshot_id and i.invoice_line_id = b.invoice_line_id
            where b.snapshot_id = :s and b.sale_line_id = :l and i.move_type = 'out_invoice' and i.accounting_date > cast(:d as date)
            order by i.accounting_date, i.invoice_line_id""", s=snapshot_id, l=case["subject_id"], d=decided.date())
    if case["subject_type"] == "sale_order":
        return _rows(conn, """
            with order_lines as (select sale_line_id from marts.fact_sales_order_line where snapshot_id = :s and sale_order_id = :o),
                 order_invoices as (select distinct i.invoice_id from marts.bridge_sale_invoice_line b
                                    join marts.fact_invoice_line i on i.snapshot_id = b.snapshot_id and i.invoice_line_id = b.invoice_line_id
                                    where b.snapshot_id = :s and b.sale_line_id in (select sale_line_id from order_lines))
            select i.invoice_line_id, i.invoice_name, i.accounting_date, i.revenue_company_ccy, cast(1 as numeric) as allocation_weight
            from marts.fact_invoice_line i join marts.dim_product p on p.snapshot_id = i.snapshot_id and p.product_id = i.product_id
            where i.snapshot_id = :s and i.move_type = 'out_invoice' and p.default_code = any(:codes) and i.accounting_date > cast(:d as date)
              and (i.invoice_id in (select invoice_id from order_invoices)
                   or exists (select 1 from marts.bridge_sale_invoice_line b where b.snapshot_id = i.snapshot_id and b.invoice_line_id = i.invoice_line_id
                              and b.sale_line_id in (select sale_line_id from order_lines)))
            order by i.accounting_date, i.invoice_line_id""", s=snapshot_id, o=case["subject_id"], codes=sorted(freight_codes) or [""], d=decided.date())
    return []


def measure_impacts(conn: Connection, snapshot_id: uuid.UUID, source_instance: str, *, freight_codes: frozenset[str],
                    actor: str = "service:margin-engine") -> dict[str, int]:
    """Re-measure every approved or actioned case of the instance against the snapshot. Returns counts by status."""
    cases = _rows(conn, """
        select c.*, i.estimated_recovery as impact_estimate, i.realisation_status as previous_status, i.realised_recovery as previous_realised,
               r.recovery_basis
        from decision.exception_case c
        join decision.case_impact i on i.case_id = c.case_id
        left join decision.margin_recommendation r on r.case_id = c.case_id and r.status <> 'SUPERSEDED'
        where c.source_instance = :i and c.status in ('APPROVED', 'ACTIONED', 'CLOSED') and c.decided_at is not null""", i=source_instance)
    counts: dict[str, int] = {}
    for case in cases:
        estimate = case["impact_estimate"]
        if case["recovery_basis"] != "BILLING_EXPOSURE" or estimate is None:
            status, realised, evidence, reason, realised_at = "NOT_MEASURABLE", None, [], "recovery is not receivable from the customer for this cause", None
        else:
            lines = _recovery_lines(conn, snapshot_id, case, freight_codes)
            realised = sum((r["revenue_company_ccy"] * (r["allocation_weight"] or 1) for r in lines), Decimal(0))
            evidence = [{"invoice_line_id": r["invoice_line_id"], "invoice": r["invoice_name"], "accounting_date": str(r["accounting_date"]),
                         "revenue_company_ccy": decimal_text(r["revenue_company_ccy"])} for r in lines]
            realised_at = max((r["accounting_date"] for r in lines), default=None)
            if not lines or realised <= 0:
                status, realised, reason = "NOT_MEASURED", None, "no posted document after the decision yet"
            elif realised + TOLERANCE >= estimate:
                status, reason = "MEASURED", "posted invoice lines after the decision cover the estimate"
            else:
                status, reason = "PARTIAL", "posted invoice lines after the decision cover part of the estimate"
        variance = None if realised is None or estimate is None else realised - estimate
        conn.execute(sa.text("""
            update decision.case_impact set snapshot_id = :s, realised_recovery = :r, realised_at = :ra, realisation_status = :st,
                realisation_evidence = cast(:ev as jsonb), reason = :re, variance = :v, measured_at = now() where case_id = :c"""),
            {"s": snapshot_id, "r": realised, "ra": realised_at, "st": status, "ev": canonical_json(evidence), "re": reason, "v": variance, "c": case["case_id"]})
        counts[status] = counts.get(status, 0) + 1
        if status != case["previous_status"] or (realised or Decimal(0)) != (case["previous_realised"] or Decimal(0)):
            append_event(conn, actor=actor, action="impact.measured", object_type="exception_case", object_id=case["case_ref"],
                         payload={"snapshot_id": str(snapshot_id), "estimated_recovery": decimal_text(estimate), "realised_recovery": decimal_text(realised),
                                  "realisation_status": status, "variance": decimal_text(variance), "evidence": evidence})
    return counts
