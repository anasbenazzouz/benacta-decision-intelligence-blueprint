"""Read side of Margin Control: the same functions serve the CLI, the API and later the cockpit.

Every figure comes from `marts.fact_margin_period`, `marts.fact_margin_rule_evaluation` and the facts behind
them. Nothing is recomputed here; the service assembles, ranks and explains.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from app.margin import kpis
from app.margin.rules import RULES
from app.margin.thresholds import Thresholds, load_thresholds
from app.numbers import decimal_text

LEAKAGE_CLASSES = ("CONFIRMED_LEAKAGE", "PROBABLE_LEAKAGE")
CLASS_RANK = {"CONFIRMED_LEAKAGE": 0, "PROBABLE_LEAKAGE": 1, "DATA_QUALITY_ISSUE": 2, "INSUFFICIENT_EVIDENCE": 3}
SEVERITY_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "NONE": 3}

# Deterministic next step per cause. Labelled "Suggested follow-up": a proposal for a human, never a decision.
SUGGESTED_FOLLOW_UP: dict[str, str] = {
    "DISCOUNT_ABOVE_CAP": "Obtain a derogation from the finance approver or issue a complementary invoice for the excess discount.",
    "PRICE_BELOW_CONTRACT": "Compare the order with the contract price and issue a complementary invoice or record the agreed amendment.",
    "PRICE_BELOW_CUSTOMER_PRICELIST": "Check the customer's price list against the order and correct the price before the next invoice.",
    "PRICE_BELOW_LIST_PRICE": "Confirm the commercial reason for the price below list, or correct it before invoicing.",
    "PRICE_BELOW_HISTORICAL": "Review the price against recent orders of the same product; confirm or correct.",
    "PRICELIST_MISMATCH": "The order applied a price list that is not the customer's: correct the order price list and re-price open lines.",
    "FREIGHT_NOT_INVOICED": "Issue the contractual freight invoice or record the waiver approved by the account manager.",
    "FREIGHT_PARTIALLY_INVOICED": "Invoice the remaining contractual freight or record the approved reduction.",
    "PURCHASE_PRICE_VARIANCE": "Review the supplier price against the frozen reference with procurement; update the reference or renegotiate.",
    "MISSING_COST": "Post or attribute the missing receipt cost before the margin of this line can be relied on.",
    "POLICY_EXPIRED": "Renew or replace the expired discount policy; until then the discount cannot be assessed.",
    "NO_POLICY": "Record the applicable discount policy for this customer or segment.",
    "POLICY_CONFLICT": "Resolve the conflicting discount policies (one priority, one cap) before assessing the line.",
    "NO_COST_REFERENCE": "Freeze a reference cost for this product so realised costs can be compared.",
    "NO_PRICE_BASELINE": "Record a contract price or a price list for this product so the price can be checked.",
    "INVOICE_WITHOUT_ORDER": "Link the invoice to its order, or document why this revenue has no order behind it.",
}


def _rows(conn: Connection, sql: str, **params: Any) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(sa.text(sql), params).mappings()]


def _s(value: Any) -> Any:
    if isinstance(value, Decimal):
        return decimal_text(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _clean(row: dict[str, Any]) -> dict[str, Any]:
    return {k: _s(v) for k, v in row.items()}


# --------------------------------------------------------------------------- overview
def margin_overview(conn: Connection, snapshot_id: uuid.UUID, period: str | None = None, thresholds: Thresholds | None = None) -> dict[str, Any]:
    thresholds = thresholds or load_thresholds()
    periods = _rows(conn, "select * from marts.fact_margin_period where snapshot_id = :s order by company_id, period", s=snapshot_id)
    if not periods:
        return {"snapshot_id": str(snapshot_id), "status": "NO_DATA", "periods": []}
    latest = period or max(p["period"] for p in periods)
    current = [p for p in periods if p["period"] == latest]
    previous_periods = sorted({p["period"] for p in periods if p["period"] < latest})
    previous = [p for p in periods if p["period"] == previous_periods[-1]] if previous_periods else []

    def total(rows: list[dict[str, Any]], key: str) -> Decimal | None:
        values = [r[key] for r in rows if r[key] is not None]
        return sum(values, Decimal(0)) if values and len(values) == len(rows) else None

    revenue, gm = total(current, "revenue"), total(current, "gross_margin")
    gm_pct = kpis.gross_margin_pct(gm, revenue) if revenue is not None else None
    # The percentage signal is computed on goods revenue with posted cost of goods sold: service revenue carries no
    # posted cost in this model, so blending it would move the percentage with the sales mix, not with margin.
    goods_revenue, cogs_total = total(current, "revenue_goods"), total(current, "cogs")
    goods_gm = kpis.gross_margin(goods_revenue, cogs_total) if goods_revenue is not None else None
    goods_gm_pct = kpis.gross_margin_pct(goods_gm, goods_revenue) if goods_revenue is not None else None
    prev_goods_revenue, prev_cogs = total(previous, "revenue_goods"), total(previous, "cogs")
    prev_goods_gm = kpis.gross_margin(prev_goods_revenue, prev_cogs) if prev_goods_revenue is not None else None
    prev_goods_gm_pct = kpis.gross_margin_pct(prev_goods_gm, prev_goods_revenue) if prev_goods_revenue is not None else None
    delta_points = kpis.gm_pct_delta_points(goods_gm_pct, prev_goods_gm_pct)
    deteriorating = kpis.is_deteriorating(delta_points, thresholds.gm_pct_deterioration_points)
    leakage = {k: sum((r[k] for r in current), Decimal(0)) for k in ("discount_leakage", "price_leakage", "freight_leakage", "cost_leakage",
                                                                       "total_addressable_leakage", "recoverable_from_customer", "untraceable_revenue")}
    basis = sorted({r["margin_basis"] for r in current})
    status = "UNRECONCILED" if any(r["margin_status"] == "UNRECONCILED" for r in current) else (
        "UNAVAILABLE" if gm is None else "OK")
    waterfall = None
    if gm is not None:
        steps = [("Gross margin (posted)", gm)]
        running = gm
        for label, key in (("Discount leakage", "discount_leakage"), ("Price leakage", "price_leakage"), ("Freight not recharged", "freight_leakage"),
                           ("Cost above reference", "cost_leakage")):
            if leakage[key]:
                running += leakage[key]
                steps.append((label, leakage[key]))
        running = kpis.margin_at_policy(gm, {k.replace("_leakage", ""): v for k, v in leakage.items()})
        steps.append(("Margin at policy (illustrative)", running))
        waterfall = [{"step": s, "amount": decimal_text(a)} for s, a in steps]
    decisions = _decision_kpis(conn, snapshot_id, latest)
    return {
        "snapshot_id": str(snapshot_id),
        "period": latest,
        "previous_period": previous_periods[-1] if previous_periods else None,
        "status": status,
        "margin_basis": basis,
        "kpis": {
            "revenue": _s(revenue), "revenue_goods": _s(total(current, "revenue_goods")), "revenue_services": _s(total(current, "revenue_services")),
            "cogs": _s(cogs_total), "gross_margin": _s(gm), "gross_margin_pct": _s(gm_pct),
            "goods_gross_margin": _s(goods_gm), "goods_gross_margin_pct": _s(goods_gm_pct),
            "previous_goods_gross_margin_pct": _s(prev_goods_gm_pct), "goods_gross_margin_pct_delta_points": _s(delta_points),
            "deteriorating": deteriorating, "deterioration_threshold_points": str(thresholds.gm_pct_deterioration_points),
            "margin_pct_basis": "goods revenue with posted cost of goods sold; service revenue carries no posted cost",
            "detected_leakage": _s(sum((leakage[k] for k in ("discount_leakage", "price_leakage", "freight_leakage", "cost_leakage")), Decimal(0))),
            "recoverable_from_customer": _s(leakage["recoverable_from_customer"]),
            "total_addressable_leakage": _s(leakage["total_addressable_leakage"]),
            "untraceable_revenue": _s(leakage["untraceable_revenue"]),
            **decisions,
            "exceptions_material": sum(r["exceptions_material"] for r in current),
            "exceptions_review": sum(r["exceptions_review"] for r in current),
        },
        "waterfall": waterfall,
        "periods": [_clean(p) for p in periods],
        "drivers": _drivers(conn, snapshot_id, latest),
        "thresholds": thresholds.as_dict(),
    }


def _decision_kpis(conn: Connection, snapshot_id: uuid.UUID, period: str) -> dict[str, Any]:
    """Approved and realised recovery, acceptance rate and cycle times for the cases of a period."""
    row = conn.execute(sa.text("""
        with cases as (
            select c.case_id, c.status, c.estimated_recovery, c.first_detected_at, c.decided_at, c.actioned_at, i.realised_recovery, i.realisation_status
            from decision.exception_case c
            join marts.fact_margin_rule_evaluation e on e.snapshot_id = :s and e.rule_id = c.rule_id and e.subject_type = c.subject_type
                 and e.subject_id = c.subject_id and e.period = :p
            left join decision.case_impact i on i.case_id = c.case_id
            where c.source_instance = (select source_instance from marts.snapshot where snapshot_id = :s))
        select coalesce(sum(case when status in ('APPROVED', 'ACTIONED', 'CLOSED') then estimated_recovery end), 0) as approved,
               coalesce(sum(case when status in ('APPROVED', 'ACTIONED', 'CLOSED') then realised_recovery end), 0) as realised,
               count(*) filter (where status in ('APPROVED', 'ACTIONED', 'CLOSED')) as approved_n,
               count(*) filter (where status = 'REJECTED') as rejected_n,
               count(*) filter (where status in ('APPROVED', 'ACTIONED', 'CLOSED') and realisation_status in ('MEASURED', 'PARTIAL')) as measured_n,
               avg(extract(epoch from (decided_at - first_detected_at)) / 3600) filter (where decided_at is not null) as hours_to_decision,
               avg(extract(epoch from (actioned_at - decided_at)) / 3600) filter (where actioned_at is not null) as hours_to_action
        from cases"""), {"s": snapshot_id, "p": period}).mappings().first()
    decided = row["approved_n"] + row["rejected_n"]
    acceptance = None if not decided else (Decimal(row["approved_n"]) * 100 / decided).quantize(Decimal("0.01"))
    return {
        "approved_recovery": decimal_text(row["approved"]),
        "realised_recovery": decimal_text(row["realised"]),
        "recovery_status": (f"{row['measured_n']} of {row['approved_n']} approved case(s) measured from posted documents"
                            if row["approved_n"] else "NOT_MEASURED: no approved recommendation in the period"),
        "recommendation_acceptance_rate_pct": decimal_text(acceptance),
        "decisions_taken": decided,
        "avg_hours_detection_to_decision": None if row["hours_to_decision"] is None else str(round(row["hours_to_decision"], 1)),
        "avg_hours_decision_to_action": None if row["hours_to_action"] is None else str(round(row["hours_to_action"], 1)),
    }


def _drivers(conn: Connection, snapshot_id: uuid.UUID, period: str) -> dict[str, list[dict[str, Any]]]:
    where = ("where e.snapshot_id = :s and e.period = :p and e.classification in ('CONFIRMED_LEAKAGE', 'PROBABLE_LEAKAGE')")
    by_customer = _rows(conn, f"""
        select c.name as customer, c.ref as customer_ref, sum(e.adverse_exposure) as adverse_exposure, count(*) as exceptions
        from marts.fact_margin_rule_evaluation e
        join marts.dim_partner c on c.snapshot_id = e.snapshot_id and c.partner_id = e.customer_id
        {where} group by 1, 2 order by 3 desc limit 10""", s=snapshot_id, p=period)  # noqa: S608 fixed fragment
    by_product = _rows(conn, f"""
        select p.name as product, p.default_code as product_code, sum(e.adverse_exposure) as adverse_exposure, count(*) as exceptions
        from marts.fact_margin_rule_evaluation e
        join marts.dim_product p on p.snapshot_id = e.snapshot_id and p.product_id = e.product_id
        {where} group by 1, 2 order by 3 desc limit 10""", s=snapshot_id, p=period)  # noqa: S608
    by_order = _rows(conn, f"""
        select o.order_name as "order", sum(e.adverse_exposure) as adverse_exposure, count(*) as exceptions
        from marts.fact_margin_rule_evaluation e
        join (select distinct snapshot_id, sale_order_id, order_name from marts.fact_sales_order_line) o
          on o.snapshot_id = e.snapshot_id and o.sale_order_id = e.sale_order_id
        {where} group by 1 order by 2 desc limit 10""", s=snapshot_id, p=period)  # noqa: S608
    by_cause = _rows(conn, f"""
        select e.exposure_type, e.cause, e.controllability, sum(e.adverse_exposure) as adverse_exposure, count(*) as exceptions
        from marts.fact_margin_rule_evaluation e {where} group by 1, 2, 3 order by 4 desc""", s=snapshot_id, p=period)  # noqa: S608
    return {"customers": [_clean(r) for r in by_customer], "products": [_clean(r) for r in by_product],
            "orders": [_clean(r) for r in by_order], "causes": [_clean(r) for r in by_cause]}


# --------------------------------------------------------------------------- queue
def exception_queue(conn: Connection, snapshot_id: uuid.UUID, *, period: str | None = None, classification: str | None = None,
                    include_resolved: bool = False, limit: int = 100) -> list[dict[str, Any]]:
    rows = _rows(conn, """
        select c.case_id, c.case_ref, c.status, c.owner, c.first_detected_at, c.version, c.first_snapshot_id, c.resolved_snapshot_id, c.resolved_note,
               c.assigned_to, c.defer_until, c.decided_at, c.actioned_at, c.estimated_recovery,
               r.status as recommendation_status, r.title as recommendation_title, r.version as recommendation_version,
               e.rule_id, e.rule_version, e.subject_type, e.subject_id, e.subject_ref, e.period, e.order_date, e.outcome, e.classification, e.cause,
               e.exposure_type, e.component, e.expected_amount, e.actual_amount, e.adverse_exposure, e.potential_exposure, e.exposure_stage,
               e.currency_code, e.severity, e.confidence, e.controllability, e.material, e.requires_human_review,
               p.name as customer, p.ref as customer_ref, d.name as product, d.default_code as product_code
        from decision.exception_case c
        join marts.fact_margin_rule_evaluation e on e.snapshot_id = :s and e.rule_id = c.rule_id and e.subject_type = c.subject_type
             and e.subject_id = c.subject_id
        left join marts.dim_partner p on p.snapshot_id = e.snapshot_id and p.partner_id = e.customer_id
        left join marts.dim_product d on d.snapshot_id = e.snapshot_id and d.product_id = e.product_id
        left join decision.margin_recommendation r on r.case_id = c.case_id and r.status <> 'SUPERSEDED'
        where c.source_instance = (select source_instance from marts.snapshot where snapshot_id = :s)
          and (cast(:p as text) is null or e.period = :p) and (cast(:c as text) is null or e.classification = :c)
          and (:r or c.status <> 'NO_LONGER_RAISED')""", s=snapshot_id, p=period, c=classification, r=include_resolved)
    now = datetime.now(UTC)
    queue = []
    for r in rows:
        first = r["first_detected_at"]
        age_days = (now - first).days if first else None
        queue.append({
            **_clean(r), "age_days": age_days,
            "rule_name": RULES[r["rule_id"]]["name"],
            "suggested_follow_up": SUGGESTED_FOLLOW_UP.get(r["cause"], "Review the evidence and decide."),
        })
    queue.sort(key=lambda q: (0 if q["material"] else 1, CLASS_RANK.get(q["classification"], 9), SEVERITY_RANK.get(q["severity"], 9),
                              -Decimal(q["adverse_exposure"] or q["potential_exposure"] or 0), q["case_ref"]))
    return queue[:limit]


# --------------------------------------------------------------------------- case
def exception_case(conn: Connection, snapshot_id: uuid.UUID, case_ref: str) -> dict[str, Any] | None:
    case = conn.execute(sa.text("select * from decision.exception_case where case_ref = :r or cast(case_id as text) = :r"),
                        {"r": case_ref}).mappings().first()
    if case is None:
        return None
    evaluation = conn.execute(sa.text(
        "select * from marts.fact_margin_rule_evaluation where snapshot_id = :s and rule_id = :rule and subject_type = :st and subject_id = :sid"),
        {"s": snapshot_id, "rule": case["rule_id"], "st": case["subject_type"], "sid": case["subject_id"]}).mappings().first()
    if evaluation is None:
        return {"case": _clean(dict(case)), "evaluation": None, "note": "no evaluation of this subject in the requested snapshot"}
    ev = dict(evaluation)
    evidence = ev.pop("evidence")
    related = _rows(conn, """
        select rule_id, rule_version, outcome, classification, cause, adverse_exposure, potential_exposure, severity, confidence, evidence->>'reason' as reason
        from marts.fact_margin_rule_evaluation where snapshot_id = :s and overlap_group = :g and not (rule_id = :rule)
        order by rule_id""", s=snapshot_id, g=f"{case['subject_type']}:{case['subject_id']}", rule=case["rule_id"])
    return {
        "case": _clean(dict(case)),
        "rule": {**RULES[case["rule_id"]], "rule_id": case["rule_id"]},
        "evaluation": _clean(ev),
        "evidence": evidence,
        "drill_down": _drill_down(conn, snapshot_id, case["subject_type"], case["subject_id"]),
        "related_evaluations_same_subject": [_clean(r) for r in related],
        "period_reconciliation": [_clean(r) for r in _rows(
            conn, "select check_id, status, independence, expected, actual, difference, tolerance, explanation, transformation_version"
                  " from marts.reconciliation_result where snapshot_id = :s and company_id = :c and period = :p order by check_id",
            s=snapshot_id, c=ev["company_id"], p=ev["period"])],
        "lineage": _lineage(conn, snapshot_id, case["subject_type"], case["subject_id"]),
        "suggested_follow_up": {"label": "Suggested follow-up", "text": SUGGESTED_FOLLOW_UP.get(ev["cause"], "Review the evidence and decide."),
                                "requires_role": "finance_approver", "status": "PENDING_REVIEW"},
        "investigation": _latest_investigation(conn, case["case_ref"]),
        **_workflow(conn, case["case_id"]),
    }


def _latest_investigation(conn: Connection, case_ref: str) -> dict[str, Any] | None:
    row = conn.execute(sa.text("select investigation_id, mode, report, created_at from decision.investigation where subject_type = 'exception_case'"
                               " and subject_id = :c order by created_at desc limit 1"), {"c": case_ref}).mappings().first()
    if row is None:
        return None
    return {**row["report"], "investigation_id": str(row["investigation_id"]), "created_at": row["created_at"].isoformat()}


def _workflow(conn: Connection, case_id: uuid.UUID) -> dict[str, Any]:
    recommendation = conn.execute(sa.text("select * from decision.margin_recommendation where case_id = :c and status <> 'SUPERSEDED'"
                                          " order by version desc limit 1"), {"c": case_id}).mappings().first()
    impact = conn.execute(sa.text("select * from decision.case_impact where case_id = :c"), {"c": case_id}).mappings().first()
    return {
        "recommendation": _clean(dict(recommendation)) if recommendation else None,
        "decisions": [_clean(r) for r in _rows(conn, "select * from decision.case_decision where case_id = :c order by decided_at, decision_id", c=case_id)],
        "actions": [_clean(r) for r in _rows(conn, "select * from decision.case_action where case_id = :c order by created_at, action_id", c=case_id)],
        "impact": _clean(dict(impact)) if impact else None,
    }


def case_audit(conn: Connection, case_ref: str) -> dict[str, Any] | None:
    """Everything that happened to a case: evaluations across snapshots, recommendations, decisions, actions, impact, audit events."""
    case = conn.execute(sa.text("select * from decision.exception_case where case_ref = :r or cast(case_id as text) = :r"), {"r": case_ref}).mappings().first()
    if case is None:
        return None
    evaluations = _rows(conn, """
        select e.snapshot_id, s.batch_seq, s.transformation_version, e.rule_id, e.rule_version, e.thresholds_version, e.outcome, e.classification, e.cause,
               e.adverse_exposure, e.potential_exposure, e.confidence, e.computed_at
        from marts.fact_margin_rule_evaluation e join marts.snapshot s on s.snapshot_id = e.snapshot_id
        where s.source_instance = :i and e.rule_id = :r and e.subject_type = :t and e.subject_id = :sid order by s.batch_seq""",
        i=case["source_instance"], r=case["rule_id"], t=case["subject_type"], sid=case["subject_id"])
    events = _rows(conn, "select sequence, occurred_at, actor, action, correlation_id, payload, prev_hash, event_hash from audit.event"
                         " where object_type = 'exception_case' and object_id = :r order by sequence", r=case["case_ref"])
    return {
        "case": _clean(dict(case)),
        "evaluations": [_clean(r) for r in evaluations],
        "recommendations": [_clean(r) for r in _rows(conn, "select * from decision.margin_recommendation where case_id = :c order by version", c=case["case_id"])],
        **_workflow(conn, case["case_id"]),
        "lineage": _lineage(conn, case["last_snapshot_id"], case["subject_type"], case["subject_id"]),
        "audit_events": [_clean(r) for r in events],
    }


def impact_register(conn: Connection, source_instance: str) -> list[dict[str, Any]]:
    return [_clean(r) for r in _rows(conn, """
        select c.case_ref, c.subject_ref, c.status, c.cause, c.owner, c.decided_at, c.actioned_at, i.estimated_recovery, i.realised_recovery, i.realised_at,
               i.realisation_status, i.variance, i.reason, i.realisation_evidence, i.measured_at
        from decision.case_impact i join decision.exception_case c on c.case_id = i.case_id
        where c.source_instance = :i order by c.decided_at, c.case_ref""", i=source_instance)]


def _drill_down(conn: Connection, snapshot_id: uuid.UUID, subject_type: str, subject_id: int) -> dict[str, Any]:
    """KPI-to-transaction drill-down: the order line, its invoices, deliveries, receipts and posted cost."""
    if subject_type == "invoice_line":
        line = _rows(conn, "select * from marts.fact_invoice_line where snapshot_id = :s and invoice_line_id = :i", s=snapshot_id, i=subject_id)
        return {"invoice_line": _clean(line[0]) if line else None}
    where = "sale_line_id = :i" if subject_type == "sale_order_line" else "sale_order_id = :i"
    lines = _rows(conn, f"select f.*, p.default_code, p.name as product_name from marts.fact_sales_order_line f"  # noqa: S608
                        f" left join marts.dim_product p on p.snapshot_id = f.snapshot_id and p.product_id = f.product_id"
                        f" where f.snapshot_id = :s and f.{where} order by f.sale_line_id", s=snapshot_id, i=subject_id)
    ids = [line["sale_line_id"] for line in lines]
    invoices = _rows(conn, """
        select b.sale_line_id, b.link_cardinality, b.allocation_weight, i.invoice_line_id, i.invoice_id, i.invoice_name, i.move_type,
               i.accounting_date, i.quantity_signed, i.price_unit, i.discount_pct, i.subtotal_signed, i.revenue_company_ccy, i.currency_code
        from marts.bridge_sale_invoice_line b join marts.fact_invoice_line i on i.snapshot_id = b.snapshot_id and i.invoice_line_id = b.invoice_line_id
        where b.snapshot_id = :s and b.sale_line_id = any(:ids) order by i.accounting_date, i.invoice_line_id""", s=snapshot_id, ids=ids or [0])
    moves = _rows(conn, "select * from marts.fact_stock_move where snapshot_id = :s and sale_line_id = any(:ids) order by move_date", s=snapshot_id, ids=ids or [0])
    allocations = _rows(conn, "select * from marts.fact_cost_allocation where snapshot_id = :s and sale_line_id = any(:ids) order by delivery_move_id, allocation_no",
                        s=snapshot_id, ids=ids or [0])
    receipt_ids = [a["receipt_move_id"] for a in allocations if a["receipt_move_id"]]
    receipts = _rows(conn, "select * from marts.fact_stock_move where snapshot_id = :s and move_id = any(:ids) order by move_date", s=snapshot_id, ids=receipt_ids or [0])
    invoice_ids = sorted({i["invoice_id"] for i in invoices})
    cogs = _rows(conn, "select * from marts.fact_posted_cogs_line where snapshot_id = :s and invoice_id = any(:ids) order by move_line_id", s=snapshot_id, ids=invoice_ids or [0])
    return {"order_lines": [_clean(r) for r in lines], "invoice_lines": [_clean(r) for r in invoices], "deliveries": [_clean(r) for r in moves],
            "cost_allocations": [_clean(r) for r in allocations], "receipts": [_clean(r) for r in receipts], "posted_cogs": [_clean(r) for r in cogs]}


def _lineage(conn: Connection, snapshot_id: uuid.UUID, subject_type: str, subject_id: int) -> list[dict[str, Any]]:
    """Raw source record versions behind the subject, as of the snapshot."""
    model = {"sale_order_line": "sale.order.line", "sale_order": "sale.order", "invoice_line": "account.move.line"}[subject_type]
    return [_clean(r) for r in _rows(conn, """
        select v.source_instance, v.source_model, v.source_id, v.version_no, v.version_id, v.source_write_date, v.record_hash, v.batch_id, v.extracted_at
        from raw.source_record_version v join raw.ingestion_batch b on b.batch_id = :s
        where v.source_instance = b.source_instance and v.source_model = :m and v.source_id = :i and v.batch_seq <= b.batch_seq
        order by v.version_no""", s=snapshot_id, m=model, i=subject_id)]


def rule_catalogue() -> list[dict[str, Any]]:
    return [{"rule_id": rule_id, **spec} for rule_id, spec in RULES.items()]
