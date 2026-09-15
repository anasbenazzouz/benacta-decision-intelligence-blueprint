"""Margin at completion erosion between the previous locked forecast and the forecast in force.

The decomposition is deterministic and complete: margin change = revenue change - sum of EAC changes by cost
category, with labour split by role into hours and rate effects. Any unexplained remainder is reported as a residual,
never hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.engine import Connection

from app.controlling.metrics import COST_CATEGORIES, ProjectMetrics, _rows, compute_project_metrics, fmt

DEFAULT_EROSION_AMOUNT = Decimal(50000)
DEFAULT_EROSION_POINTS = Decimal(2)


@dataclass
class ErosionResult:
    project_code: str
    previous_cutoff: date
    cutoff: date
    status: str  # EROSION, NO_EROSION, UNKNOWN
    reason: str | None
    previous: dict[str, str | None]
    current: dict[str, str | None]
    margin_change: Decimal | None
    revenue_change: Decimal | None
    eac_change: Decimal | None
    by_category: dict[str, Decimal]
    labour_by_role: dict[str, dict[str, str]]
    residual: Decimal | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_code": self.project_code, "previous_cutoff": str(self.previous_cutoff), "cutoff": str(self.cutoff),
            "status": self.status, "reason": self.reason, "previous": self.previous, "current": self.current,
            "margin_change": fmt(self.margin_change), "revenue_change": fmt(self.revenue_change), "eac_change": fmt(self.eac_change),
            "by_category": {k: fmt(v) for k, v in self.by_category.items()}, "labour_by_role": self.labour_by_role,
            "residual": fmt(self.residual),
        }


def _at_completion(m: ProjectMetrics, category: str) -> Decimal:
    return m.by_category["actual"].get(category, Decimal(0)) + m.by_category["etc"].get(category, Decimal(0))


def _summary(m: ProjectMetrics) -> dict[str, str | None]:
    return {key: fmt(m.value(key)) for key in
            ("forecast_revenue_at_completion", "actual_cost", "etc", "eac", "forecast_margin_amount", "forecast_margin_pct")} | {
        "forecast_version": m.versions.forecast["label"] if m.versions.forecast else None}


def compare(current: ProjectMetrics, previous: ProjectMetrics, conn: Connection | None = None) -> ErosionResult:
    base = dict(project_code=current.project["project_code"], previous_cutoff=previous.cutoff, cutoff=current.cutoff,
                previous=_summary(previous), current=_summary(current))
    if current.value("forecast_margin_amount") is None or previous.value("forecast_margin_amount") is None:
        return ErosionResult(**base, status="UNKNOWN", reason="margin at completion unavailable for one of the two cutoffs",
                             margin_change=None, revenue_change=None, eac_change=None, by_category={}, labour_by_role={}, residual=None)

    margin_change = current.value("forecast_margin_amount") - previous.value("forecast_margin_amount")
    revenue_change = current.value("forecast_revenue_at_completion") - previous.value("forecast_revenue_at_completion")
    eac_change = current.value("eac") - previous.value("eac")
    categories = sorted(set(COST_CATEGORIES) & (set(current.by_category["actual"]) | set(current.by_category["etc"])
                                                | set(previous.by_category["actual"]) | set(previous.by_category["etc"])))
    by_category = {category: _at_completion(current, category) - _at_completion(previous, category) for category in categories}

    labour_by_role: dict[str, dict[str, str]] = {}
    rates = _role_rates(conn, current, previous) if conn is not None else {}
    for role in sorted(set(current.hours_by_role["actual"]) | set(current.hours_by_role["etc"])
                       | set(previous.hours_by_role["actual"]) | set(previous.hours_by_role["etc"])):
        hours_now = current.hours_by_role["actual"].get(role, Decimal(0)) + current.hours_by_role["etc"].get(role, Decimal(0))
        hours_before = previous.hours_by_role["actual"].get(role, Decimal(0)) + previous.hours_by_role["etc"].get(role, Decimal(0))
        rate = rates.get(role)
        hours_change = hours_now - hours_before
        labour_by_role[role] = {
            "hours_change": fmt(hours_change, "h"),
            "rate": fmt(rate),
            "cost_change": fmt(hours_change * rate) if rate is not None else None,
        }
    residual = margin_change - (revenue_change - sum(by_category.values(), Decimal(0)))
    points = (previous.value("forecast_margin_pct") or Decimal(0)) - (current.value("forecast_margin_pct") or Decimal(0))
    eroded = -margin_change >= DEFAULT_EROSION_AMOUNT or points >= DEFAULT_EROSION_POINTS
    return ErosionResult(**base, status="EROSION" if eroded else "NO_EROSION", reason=None, margin_change=margin_change,
                         revenue_change=revenue_change, eac_change=eac_change, by_category=by_category,
                         labour_by_role=labour_by_role, residual=residual)


def _role_rates(conn: Connection, current: ProjectMetrics, previous: ProjectMetrics) -> dict[str, Decimal]:
    """Single hourly rate per role when plan lines of both forecasts and the employees agree; otherwise no rate."""
    version_ids = [v["version_id"] for v in (current.versions.forecast, previous.versions.forecast) if v]
    rows = _rows(conn, "select resource_or_role as role, array_agg(distinct planned_rate) as rates from planning.plan_line"
                 " where version_id = any(cast(:v as uuid[])) and cost_category = 'LABOUR' group by 1", v=version_ids)
    employee_rates = {r["role"]: r["rates"] for r in _rows(
        conn, "select role, array_agg(distinct hourly_cost) as rates from marts.dim_employee where snapshot_id = :s group by 1",
        s=current.snapshot_id)}
    rates = {}
    for row in rows:
        plan = {r for r in row["rates"] if r is not None}
        actual = {r for r in employee_rates.get(row["role"], []) if r is not None}
        if len(plan) == 1 and plan == actual:
            rates[row["role"]] = next(iter(plan))
    return rates


def detect_erosion(conn: Connection, snapshot_id, project_code: str, cutoff: date, previous_cutoff: date) -> ErosionResult:
    current = compute_project_metrics(conn, snapshot_id, project_code, cutoff)
    previous = compute_project_metrics(conn, snapshot_id, project_code, previous_cutoff)
    return compare(current, previous, conn)
