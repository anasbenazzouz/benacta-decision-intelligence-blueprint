"""Project controlling metrics at a cutoff, from one snapshot and the plan versions in force.

Every value is a `MetricValue` carrying its contract id (semantic/metrics.yml), a status and the inputs it was
computed from. Conventions are those of docs/project_controlling_model.md; the arithmetic helpers at the top are
pure and unit-tested on their own.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection

CENT = Decimal("0.01")
COST_CATEGORIES = ("LABOUR", "SUBCONTRACT", "MATERIALS", "CONTINGENCY", "OTHER")
AGEING_BUCKETS = (("1-30", 1, 30), ("31-90", 31, 90), ("91-180", 91, 180), ("181-365", 181, 365), ("above-365", 366, None))


# --------------------------------------------------------------------------- pure conventions
def eac(actual_cost: Decimal, etc: Decimal | None) -> Decimal | None:
    """EAC = actual cost to cutoff + ETC. ETC already includes open commitments; they are never added again."""
    return None if etc is None else actual_cost + etc


def open_commitment(ordered_amount: Decimal, billed_amount: Decimal) -> tuple[Decimal, bool]:
    """Remaining commitment of a purchase line and whether it is over-billed (commitment floored at zero)."""
    remaining = ordered_amount - billed_amount
    return (max(remaining, Decimal(0)), remaining < 0)


def uncommitted_etc(etc: Decimal | None, commitments: Decimal) -> Decimal | None:
    return None if etc is None else etc - commitments


def cost_variance_at_completion(eac_value: Decimal | None, approved_budget: Decimal | None) -> Decimal | None:
    """Positive is unfavourable."""
    return None if eac_value is None or approved_budget is None else eac_value - approved_budget


def margin(frac: Decimal | None, eac_value: Decimal | None) -> Decimal | None:
    return None if frac is None or eac_value is None else frac - eac_value


def ratio_pct(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator in (None, Decimal(0)):
        return None
    return (numerator * 100 / denominator).quantize(CENT, rounding=ROUND_HALF_UP)


def ageing_bucket(days_past_due: int) -> str | None:
    for name, low, high in AGEING_BUCKETS:
        if days_past_due >= low and (high is None or days_past_due <= high):
            return name
    return None


def to_eur(amount: Decimal, currency: str, fixed_rate: Decimal | None) -> Decimal | None:
    """Project view: contract-currency amounts converted at the fixed project rate (units per EUR)."""
    if currency == "EUR":
        return amount
    if not fixed_rate:
        return None
    return (amount / fixed_rate).quantize(CENT, rounding=ROUND_HALF_UP)


def month_first(day: date) -> date:
    return date(day.year, day.month, 1)


def fmt(value: Decimal | None, unit: str = "EUR") -> str | None:
    """Display form: amounts and percentages to 2 decimals, hours without trailing zeros or exponent."""
    if value is None:
        return None
    if unit == "h":
        text = format(value.normalize(), "f")
        return "0" if text in ("-0", "") else text
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


# --------------------------------------------------------------------------- results
@dataclass
class MetricValue:
    metric_id: str
    value: Decimal | None
    unit: str = "EUR"
    status: str = "OK"
    reason: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id, "value": fmt(self.value, self.unit), "unit": self.unit,
            "status": self.status, "reason": self.reason, "inputs": self.inputs,
        }


@dataclass
class Versions:
    forecast: dict[str, Any] | None
    previous_forecast: dict[str, Any] | None
    budget: dict[str, Any] | None
    baseline: dict[str, Any] | None
    pending_co: dict[str, Any] | None


@dataclass
class ProjectMetrics:
    project: dict[str, Any]
    cutoff: date
    snapshot_id: uuid.UUID
    versions: Versions
    metrics: dict[str, MetricValue]
    by_category: dict[str, dict[str, Decimal]]
    hours_by_role: dict[str, dict[str, Decimal]]
    receivables: list[dict[str, Any]]
    milestones: list[dict[str, Any]]
    data_quality: list[dict[str, Any]]
    exceptions: list[dict[str, Any]]

    def value(self, metric_id: str) -> Decimal | None:
        return self.metrics[metric_id].value


# --------------------------------------------------------------------------- data access
def _rows(conn: Connection, sql: str, **params: Any) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(sa.text(sql), params).mappings()]


def _version_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {"version_id": str(row["version_id"]), "label": row["label"], "status": row["status"],
            "cutoff_date": str(row["cutoff_date"]) if row["cutoff_date"] else None, "version_type": row["version_type"],
            "scenario": row["scenario"]}


def resolve_versions(conn: Connection, source_instance: str, company_id: int, project_code: str, cutoff: date) -> Versions:
    base = (
        "select version_id, label, status, cutoff_date, version_type, scenario from planning.plan_version"
        " where source_instance = :i and company_id = :c and project_code = :p"
    )
    params = {"i": source_instance, "c": company_id, "p": project_code, "cut": cutoff}
    forecast = _rows(conn, base + " and version_type = 'FORECAST' and scenario = 'BASE' and cutoff_date = :cut"
                     " and status in ('APPROVED', 'LOCKED') order by approved_at desc limit 1", **params)
    previous = _rows(conn, base + " and version_type = 'FORECAST' and scenario = 'BASE' and cutoff_date < :cut"
                     " and status = 'LOCKED' order by cutoff_date desc, locked_at desc limit 1", **params)
    revised = _rows(conn, base + " and version_type = 'BUDGET_REVISED' and status in ('APPROVED', 'LOCKED')"
                    " and cutoff_date <= :cut order by cutoff_date desc, approved_at desc limit 1", **params)
    baseline = _rows(conn, base + " and version_type = 'BUDGET_BASELINE' and status = 'LOCKED'"
                     " and cutoff_date <= :cut order by cutoff_date desc limit 1", **params)
    pending = _rows(conn, base + " and version_type = 'FORECAST' and scenario = 'PENDING_CO' and cutoff_date = :cut"
                    " and status in ('APPROVED', 'LOCKED') order by approved_at desc limit 1", **params)
    budget = revised[0] if revised else (baseline[0] if baseline else None)
    return Versions(_version_row(forecast[0] if forecast else None), _version_row(previous[0] if previous else None),
                    _version_row(budget), _version_row(baseline[0] if baseline else None),
                    _version_row(pending[0] if pending else None))


def plan_totals(conn: Connection, version_id: str | None, after: date | None = None) -> tuple[dict[str, Decimal], dict[str, Decimal], Decimal | None]:
    """Cost by category, hours by role and total cost of a version (optionally for periods after a month)."""
    if version_id is None:
        return {}, {}, None
    rows = _rows(
        conn,
        "select cost_category, resource_or_role, sum(planned_cost) as cost, sum(planned_hours) as hours"
        " from planning.plan_line where version_id = :v and cost_category <> 'REVENUE'"
        " and (cast(:after as date) is null or period > :after) group by 1, 2",
        v=version_id, after=after,
    )
    by_category: dict[str, Decimal] = defaultdict(Decimal)
    hours: dict[str, Decimal] = defaultdict(Decimal)
    for row in rows:
        if row["cost"] is not None:
            by_category[row["cost_category"]] += row["cost"]
        if row["hours"] is not None and row["cost_category"] == "LABOUR":
            hours[row["resource_or_role"]] += row["hours"]
    return dict(by_category), dict(hours), sum(by_category.values(), Decimal(0))


def compute_project_metrics(conn: Connection, snapshot_id: uuid.UUID, project_code: str, cutoff: date) -> ProjectMetrics:
    project_rows = _rows(conn, "select p.*, s.source_instance from marts.dim_project p join marts.snapshot s using (snapshot_id)"
                         " where p.snapshot_id = :s and p.project_code = :c", s=snapshot_id, c=project_code)
    if not project_rows:
        raise LookupError(f"project {project_code} not found in snapshot {snapshot_id}")
    project = project_rows[0]
    pid, company = project["project_id"], project["company_id"]
    currency = project["contract_currency"] or "EUR"
    fixed_rate = project["fixed_rate_per_eur"]
    cutoff_month = month_first(cutoff)
    versions = resolve_versions(conn, project["source_instance"], company, project_code, cutoff)
    dq: list[dict[str, Any]] = []
    metrics: dict[str, MetricValue] = {}

    # actual cost by category
    actual: dict[str, Decimal] = defaultdict(Decimal)
    labour = _rows(conn, "select coalesce(sum(t.cost_amount), 0) as cost from marts.fact_timesheet t"
                   " where t.snapshot_id = :s and t.project_id = :p and t.entry_date <= :cut", s=snapshot_id, p=pid, cut=cutoff)[0]["cost"]
    actual["LABOUR"] += labour
    for row in _rows(conn, "select cost_category, sum(amount) as amount from marts.fact_vendor_bill_line where snapshot_id = :s"
                     " and project_id = :p and accounting_date <= :cut group by 1", s=snapshot_id, p=pid, cut=cutoff):
        actual[row["cost_category"]] += row["amount"]
    actual_total = sum(actual.values(), Decimal(0))
    metrics["actual_cost"] = MetricValue("actual_cost", actual_total, inputs={"by_category": {k: fmt(v) for k, v in actual.items()}})

    # open commitments by category, billed as of cutoff
    commitments: dict[str, Decimal] = defaultdict(Decimal)
    received_not_billed = Decimal(0)
    for row in _rows(
        conn,
        "select c.purchase_line_id, c.cost_category, c.ordered_amount, c.price_unit, c.received_quantity,"
        " coalesce((select sum(b.amount) from marts.fact_vendor_bill_line b where b.snapshot_id = c.snapshot_id"
        " and b.purchase_line_id = c.purchase_line_id and b.accounting_date <= :cut), 0) as billed"
        " from marts.fact_purchase_commitment c where c.snapshot_id = :s and c.project_id = :p and c.order_date <= :cut",
        s=snapshot_id, p=pid, cut=cutoff,
    ):
        remaining, over_billed = open_commitment(row["ordered_amount"], row["billed"])
        commitments[row["cost_category"]] += remaining
        if over_billed:
            dq.append({"code": "PURCHASE_LINE_OVER_BILLED", "detail": f"purchase line {row['purchase_line_id']} billed above ordered amount"})
        received_value = row["received_quantity"] * row["price_unit"]
        received_not_billed += max(received_value - row["billed"], Decimal(0))
    commitments_total = sum(commitments.values(), Decimal(0))
    metrics["open_commitments"] = MetricValue("open_commitments", commitments_total, inputs={"by_category": {k: fmt(v) for k, v in commitments.items()}})
    metrics["received_not_billed"] = MetricValue("received_not_billed", received_not_billed,
                                                 reason="valued at order price; accruals review only")

    # ETC and EAC
    forecast_id = versions.forecast["version_id"] if versions.forecast else None
    etc_by_category, etc_hours, etc_total = plan_totals(conn, forecast_id, after=cutoff_month)
    if forecast_id is None:
        reason = f"no approved BASE forecast at cutoff {cutoff}"
        metrics["etc"] = MetricValue("etc", None, status="UNKNOWN", reason=reason)
        metrics["eac"] = MetricValue("eac", None, status="UNKNOWN", reason=reason)
        dq.append({"code": "FORECAST_MISSING", "detail": reason})
    else:
        metrics["etc"] = MetricValue("etc", etc_total, inputs={"version_id": forecast_id, "by_category": {k: fmt(v) for k, v in etc_by_category.items()}})
        metrics["eac"] = MetricValue("eac", eac(actual_total, etc_total), inputs={"actual_cost": fmt(actual_total), "etc": fmt(etc_total)})
        for category, committed in commitments.items():
            if committed > etc_by_category.get(category, Decimal(0)):
                dq.append({"code": "ETC_BELOW_OPEN_COMMITMENTS",
                           "detail": f"{category}: ETC {etc_by_category.get(category, Decimal(0))} below open commitments {committed}"})
    metrics["uncommitted_etc"] = MetricValue("uncommitted_etc", uncommitted_etc(metrics["etc"].value, commitments_total),
                                             status=metrics["etc"].status, reason=metrics["etc"].reason)

    # budget
    budget_id = versions.budget["version_id"] if versions.budget else None
    budget_by_category, budget_hours, budget_total = plan_totals(conn, budget_id)
    metrics["approved_budget"] = MetricValue(
        "approved_budget", budget_total, status="OK" if budget_id else "UNKNOWN",
        reason=None if budget_id else "no approved budget effective at cutoff", inputs={"version_id": budget_id},
    )
    metrics["cost_variance_at_completion"] = MetricValue(
        "cost_variance_at_completion", cost_variance_at_completion(metrics["eac"].value, budget_total),
        status="OK" if metrics["eac"].value is not None and budget_total is not None else "UNKNOWN",
    )

    # revenue at completion
    orders = _rows(conn, "select order_name, state, order_date, is_contract, currency_code, amount_untaxed_ccy from marts.fact_change_order"
                   " where snapshot_id = :s and project_id = :p order by order_date", s=snapshot_id, p=pid)
    approved_ccy = sum((o["amount_untaxed_ccy"] for o in orders if o["state"] == "sale" and o["order_date"] <= cutoff), Decimal(0))
    pending_ccy = sum((o["amount_untaxed_ccy"] for o in orders if o["state"] in ("draft", "sent") and o["order_date"] <= cutoff), Decimal(0))
    frac = to_eur(approved_ccy, currency, fixed_rate) if orders else None
    metrics["forecast_revenue_at_completion"] = MetricValue(
        "forecast_revenue_at_completion", frac, status="OK" if frac is not None else "UNKNOWN",
        reason=None if frac is not None else "no confirmed contract order or missing fixed project rate",
        inputs={"basis": "CONTRACT_APPROVED", "contract_currency": currency, "fixed_rate_per_eur": str(fixed_rate) if fixed_rate else None,
                "orders": [{"name": o["order_name"], "state": o["state"], "is_contract": o["is_contract"],
                            "order_date": str(o["order_date"]), "amount": fmt(o["amount_untaxed_ccy"])} for o in orders]},
    )
    metrics["pending_change_orders"] = MetricValue("pending_change_orders", to_eur(pending_ccy, currency, fixed_rate))
    margin_value = margin(frac, metrics["eac"].value)
    metrics["forecast_margin_amount"] = MetricValue("forecast_margin_amount", margin_value, status="OK" if margin_value is not None else "UNKNOWN",
                                                    reason=metrics["eac"].reason if margin_value is None else None)
    metrics["forecast_margin_pct"] = MetricValue("forecast_margin_pct", ratio_pct(margin_value, frac), unit="%",
                                                 status="OK" if margin_value is not None and frac else "UNKNOWN")

    # billing, collection, receivables
    receivables = []
    billed_ccy = Decimal(0)
    collected_ccy = Decimal(0)
    overdue_ccy = Decimal(0)
    not_due_ccy = Decimal(0)
    buckets: dict[str, Decimal] = defaultdict(Decimal)
    for inv in _rows(conn, "select r.*, coalesce((select sum(p.amount_ccy) from marts.fact_customer_payment p where p.snapshot_id = r.snapshot_id"
                     " and p.invoice_id = r.invoice_id and p.payment_date <= :cut), 0) as paid from marts.fact_receivable r"
                     " where r.snapshot_id = :s and r.project_id = :p and r.invoice_date <= :cut order by r.invoice_date",
                     s=snapshot_id, p=pid, cut=cutoff):
        billed_ccy += inv["amount_untaxed_ccy"]
        collected_ccy += inv["paid"]
        residual = inv["amount_total_ccy"] - inv["paid"]
        days = (cutoff - inv["due_date"]).days if inv["due_date"] else None
        status = "PAID" if residual <= 0 else ("OVERDUE" if days is not None and days > 0 else "NOT_YET_DUE")
        if inv["move_type"] == "out_invoice" and residual > 0:
            if status == "OVERDUE":
                overdue_ccy += residual
                buckets[ageing_bucket(days)] += residual
            else:
                not_due_ccy += residual
        receivables.append({"invoice": inv["invoice_name"], "invoice_date": str(inv["invoice_date"]), "due_date": str(inv["due_date"]),
                            "total_ttc": fmt(to_eur(inv["amount_total_ccy"], currency, fixed_rate)),
                            "paid_ttc": fmt(to_eur(inv["paid"], currency, fixed_rate)),
                            "residual_ttc": fmt(to_eur(residual, currency, fixed_rate)), "days_past_due": days if status == "OVERDUE" else 0,
                            "status": status})
    billed = to_eur(billed_ccy, currency, fixed_rate)
    metrics["billed_amount"] = MetricValue("billed_amount", billed)
    metrics["collected_amount"] = MetricValue("collected_amount", to_eur(collected_ccy, currency, fixed_rate), unit="EUR_TTC")
    metrics["overdue_amount"] = MetricValue("overdue_amount", to_eur(overdue_ccy, currency, fixed_rate), unit="EUR_TTC",
                                            inputs={"buckets": {k: fmt(to_eur(v, currency, fixed_rate)) for k, v in buckets.items()}})
    metrics["not_yet_due_amount"] = MetricValue("not_yet_due_amount", to_eur(not_due_ccy, currency, fixed_rate), unit="EUR_TTC")
    metrics["remaining_to_bill"] = MetricValue("remaining_to_bill", None if frac is None or billed is None else frac - billed,
                                               status="OK" if frac is not None else "UNKNOWN")

    # hours
    actual_hours: dict[str, Decimal] = defaultdict(Decimal)
    for row in _rows(conn, "select e.role, sum(t.hours) as hours from marts.fact_timesheet t join marts.dim_employee e"
                     " on e.snapshot_id = t.snapshot_id and e.employee_id = t.employee_id where t.snapshot_id = :s and t.project_id = :p"
                     " and t.entry_date <= :cut group by 1", s=snapshot_id, p=pid, cut=cutoff):
        actual_hours[row["role"] or "UNMAPPED"] += row["hours"]
    total_actual_hours = sum(actual_hours.values(), Decimal(0))
    metrics["actual_hours"] = MetricValue("actual_hours", total_actual_hours, unit="h")
    metrics["planned_hours"] = MetricValue("planned_hours", sum(budget_hours.values(), Decimal(0)) if budget_id else None, unit="h",
                                           status="OK" if budget_id else "UNKNOWN", inputs={"version_id": budget_id})
    metrics["hours_at_completion"] = MetricValue(
        "hours_at_completion", total_actual_hours + sum(etc_hours.values(), Decimal(0)) if forecast_id else None, unit="h",
        status="OK" if forecast_id else "UNKNOWN",
    )

    # progress
    progress = None
    if forecast_id:
        found = _rows(conn, "select value_numeric, author, evidence_ref from planning.assumption where version_id = :v"
                      " and key = 'physical_progress_pct' and work_package = ''", v=forecast_id)
        progress = found[0] if found else None
    metrics["physical_progress_pct"] = MetricValue(
        "physical_progress_pct", progress["value_numeric"] if progress else None, unit="%",
        status="OK" if progress else "UNKNOWN", reason=None if progress else "no declared physical progress for the forecast in force",
        inputs={"declared_by": progress["author"], "evidence_ref": progress["evidence_ref"]} if progress else {},
    )
    metrics["cost_consumption_ratio"] = MetricValue("cost_consumption_ratio", ratio_pct(actual_total, metrics["eac"].value), unit="%",
                                                    status="OK" if metrics["eac"].value else "UNKNOWN",
                                                    reason="shown next to physical progress, never used as progress")

    # milestones and billing shift
    previous_id = versions.previous_forecast["version_id"] if versions.previous_forecast else None
    milestones = []
    for ms in _rows(conn, "select * from marts.dim_milestone where snapshot_id = :s and project_id = :p order by deadline", s=snapshot_id, p=pid):
        late = ms["deadline"] is not None and ms["deadline"] < cutoff and not (ms["is_reached"] and ms["reached_date"] and ms["reached_date"] <= cutoff)
        planned = {}
        amount = ms["billing_amount"]
        amount_eur = to_eur(amount, currency, fixed_rate) if amount is not None else None
        for label, version_id in (("previous", previous_id), ("current", forecast_id)):
            if version_id and ms["milestone_code"]:
                # planned billing lines are keyed by the milestone code (work_package of REVENUE lines)
                match = _rows(conn, "select min(period) as period from planning.plan_line where version_id = :v"
                              " and cost_category = 'REVENUE' and work_package = :k and planned_billing is not null",
                              v=version_id, k=ms["milestone_code"])
                if match and match[0]["period"]:
                    planned[label] = str(match[0]["period"])[:7]
        milestones.append({
            "milestone_code": ms["milestone_code"], "name": ms["name"], "deadline": str(ms["deadline"]) if ms["deadline"] else None,
            "is_reached": ms["is_reached"],
            "reached_date": str(ms["reached_date"]) if ms["reached_date"] else None, "billing_amount": fmt(amount_eur),
            "late": late, "days_late": (cutoff - ms["deadline"]).days if late else 0,
            "previous_planned_billing_period": planned.get("previous"), "current_planned_billing_period": planned.get("current"),
        })
    delayed = sum((Decimal(m["billing_amount"]) for m in milestones if m["late"] and m["billing_amount"]), Decimal(0))
    metrics["delayed_billing_amount"] = MetricValue("delayed_billing_amount", delayed)

    # timesheet completeness: planned for the cutoff month by the previous forecast but no time logged
    missing = []
    if previous_id:
        missing = _rows(
            conn,
            "select a.employee_code from planning.assignment a where a.version_id = :v and a.period = :m and a.planned_hours > 0"
            " and not exists (select 1 from marts.fact_timesheet t join marts.dim_employee e on e.snapshot_id = t.snapshot_id"
            " and e.employee_id = t.employee_id where t.snapshot_id = :s and t.project_id = :p and e.employee_code = a.employee_code"
            " and t.entry_date >= :m and t.entry_date <= :cut) group by a.employee_code order by 1",
            v=previous_id, m=cutoff_month, s=snapshot_id, p=pid, cut=cutoff,
        )
    if missing:
        dq.append({"code": "TIMESHEETS_INCOMPLETE", "detail": f"planned but no time logged in {cutoff_month:%Y-%m}: "
                   + ", ".join(r["employee_code"] for r in missing), "count": len(missing)})

    # marts data quality issues touching this project
    for issue in _rows(conn, "select issue_code, detail from marts.data_quality_issue where snapshot_id = :s and detail like :needle",
                       s=snapshot_id, needle=f"%{project_code}%"):
        if issue["issue_code"] == "VENDOR_BILL_PROJECT_MISMATCH" and f"purchase line of {project_code}" in issue["detail"]:
            dq.append({"code": issue["issue_code"], "detail": issue["detail"]})

    # unapproved change order work
    unapproved_cost = _rows(
        conn,
        "select coalesce(sum(t.cost_amount), 0) as cost from marts.fact_timesheet t join marts.dim_work_package w"
        " on w.snapshot_id = t.snapshot_id and w.task_id = t.task_id where t.snapshot_id = :s and t.project_id = :p"
        " and w.is_change_order_scope and t.entry_date <= :cut", s=snapshot_id, p=pid, cut=cutoff,
    )[0]["cost"]
    metrics["unapproved_change_order_cost"] = MetricValue("unapproved_change_order_cost", unapproved_cost)

    result = ProjectMetrics(
        project=project, cutoff=cutoff, snapshot_id=snapshot_id, versions=versions, metrics=metrics,
        by_category={"actual": dict(actual), "open_commitments": dict(commitments), "etc": etc_by_category, "budget": budget_by_category},
        hours_by_role={"actual": dict(actual_hours), "etc": etc_hours, "budget": budget_hours},
        receivables=receivables, milestones=milestones, data_quality=dq, exceptions=[],
    )
    result.exceptions = detect_exceptions(result)
    return result


def pending_change_order_scenario(conn: Connection, m: ProjectMetrics) -> dict[str, Any] | None:
    """PENDING_CO scenario: revenue adds pending change orders, ETC comes from the scenario version. Never alters BASE."""
    if m.versions.pending_co is None:
        return None
    _by_category, _hours, etc_total = plan_totals(conn, m.versions.pending_co["version_id"], after=month_first(m.cutoff))
    frac = m.value("forecast_revenue_at_completion")
    pending = m.value("pending_change_orders") or Decimal(0)
    scenario_frac = None if frac is None else frac + pending
    scenario_eac = eac(m.value("actual_cost"), etc_total)
    scenario_margin = margin(scenario_frac, scenario_eac)
    return {"version": m.versions.pending_co, "frac": fmt(scenario_frac), "etc": fmt(etc_total), "eac": fmt(scenario_eac),
            "margin": fmt(scenario_margin), "margin_pct": fmt(ratio_pct(scenario_margin, scenario_frac))}


# --------------------------------------------------------------------------- exception rules (materiality configurable)
DEFAULT_THRESHOLDS = {"budget_overrun_amount": Decimal(25000)}


def detect_exceptions(m: ProjectMetrics, thresholds: dict[str, Decimal] | None = None) -> list[dict[str, Any]]:
    limits = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    found: list[dict[str, Any]] = []
    variance = m.value("cost_variance_at_completion")
    if variance is not None and variance >= limits["budget_overrun_amount"]:
        found.append({"code": "BUDGET_OVERRUN_AT_COMPLETION", "amount": fmt(variance), "metric_id": "cost_variance_at_completion"})
    late = [ms for ms in m.milestones if ms["late"]]
    if late:
        found.append({"code": "MILESTONE_LATE", "amount": fmt(m.value("delayed_billing_amount")), "milestones": [ms["name"] for ms in late]})
    if (m.value("overdue_amount") or Decimal(0)) > 0:
        found.append({"code": "RECEIVABLE_OVERDUE", "amount": fmt(m.value("overdue_amount")), "metric_id": "overdue_amount"})
    if (m.value("unapproved_change_order_cost") or Decimal(0)) > 0 and (m.value("pending_change_orders") or Decimal(0)) > 0:
        found.append({"code": "UNAPPROVED_CHANGE_ORDER_WORK", "amount": fmt(m.value("unapproved_change_order_cost"))})
    for issue in m.data_quality:
        if issue["code"] in ("FORECAST_MISSING", "TIMESHEETS_INCOMPLETE"):
            found.append({"code": issue["code"], "detail": issue["detail"]})
    return found
