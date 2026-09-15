"""Portfolio overview: the same metric service as the status reports, one row per delivery project.

Totals never hide unknown values: a project whose EAC is UNKNOWN is excluded from EAC and margin totals and counted.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.engine import Connection

from app.controlling.erosion import compare
from app.controlling.metrics import _rows, compute_project_metrics, fmt, ratio_pct
from app.controlling.psr import month_before

ROW_METRICS = (
    "forecast_revenue_at_completion", "approved_budget", "actual_cost", "open_commitments", "etc", "eac",
    "cost_variance_at_completion", "forecast_margin_amount", "forecast_margin_pct", "billed_amount", "collected_amount",
    "overdue_amount", "delayed_billing_amount",
)


def portfolio_overview(conn: Connection, snapshot_id: uuid.UUID, cutoff: date, business_unit: str | None = None) -> dict[str, Any]:
    projects = _rows(conn, "select project_code, business_unit from marts.dim_project where snapshot_id = :s and not is_internal"
                     " and (cast(:bu as text) is null or business_unit = :bu) order by project_code", s=snapshot_id, bu=business_unit)
    rows = []
    totals = {key: Decimal(0) for key in ("forecast_revenue_at_completion", "eac", "forecast_margin_amount", "overdue_amount", "delayed_billing_amount")}
    unknown_eac = []
    for project in projects:
        current = compute_project_metrics(conn, snapshot_id, project["project_code"], cutoff)
        previous = compute_project_metrics(conn, snapshot_id, project["project_code"], month_before(cutoff))
        change = compare(current, previous, conn)
        exceptions = sorted({e["code"] for e in current.exceptions} | ({"MARGIN_EROSION"} if change.status == "EROSION" else set()))
        rows.append({
            "project_code": project["project_code"], "business_unit": project["business_unit"], "name": current.project["name"],
            **{key: current.metrics[key].as_dict()["value"] for key in ROW_METRICS},
            "margin_change_since_previous_forecast": fmt(change.margin_change), "exceptions": exceptions,
            "data_quality": sorted({d["code"] for d in current.data_quality}),
        })
        if current.value("eac") is None:
            unknown_eac.append(project["project_code"])
            totals["overdue_amount"] += current.value("overdue_amount") or Decimal(0)
            totals["delayed_billing_amount"] += current.value("delayed_billing_amount") or Decimal(0)
            continue
        for key in totals:
            totals[key] += current.value(key) or Decimal(0)
    return {
        "cutoff": str(cutoff), "snapshot_id": str(snapshot_id), "business_unit": business_unit, "projects": rows,
        "totals": {**{key: fmt(value) for key, value in totals.items()},
                   "forecast_margin_pct": fmt(ratio_pct(totals["forecast_margin_amount"], totals["forecast_revenue_at_completion"])),
                   "projects_excluded_unknown_eac": unknown_eac},
    }
