"""Project Status Report: dated, versioned, immutable once published.

The content is assembled only from the metric service, the erosion comparison and plan versions. It keeps physical
progress, recognised revenue, billed amount and collected cash apart. A published report keeps its figures,
versions, rules and comments; later data produces a new revision.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
import yaml
from sqlalchemy.engine import Connection

from app.audit.log import append_event, canonical_json, content_hash
from app.config import REPO_ROOT
from app.controlling.erosion import compare
from app.controlling.metrics import (
    ProjectMetrics,
    _rows,
    compute_project_metrics,
    fmt,
    month_first,
    pending_change_order_scenario,
)
from app.planning.domain import Actor, Role

SCHEMA_VERSION = 1
CONTRACTS_PATH = REPO_ROOT / "semantic" / "metrics.yml"


class PsrError(RuntimeError):
    pass


def contract_versions() -> dict[str, int]:
    contracts = yaml.safe_load(CONTRACTS_PATH.read_text(encoding="utf-8"))["metrics"]
    return {c["metric_id"]: c["version"] for c in contracts}


def _metric(m: ProjectMetrics, metric_id: str) -> dict[str, Any]:
    return m.metrics[metric_id].as_dict()


def month_before(cutoff: date) -> date:
    """Last day of the month preceding the cutoff month."""
    return month_first(cutoff) - timedelta(days=1)


def build_psr_content(conn: Connection, snapshot_id: uuid.UUID, project_code: str, cutoff: date) -> dict[str, Any]:
    current = compute_project_metrics(conn, snapshot_id, project_code, cutoff)
    prior_cutoff = month_before(cutoff)
    previous = compute_project_metrics(conn, snapshot_id, project_code, prior_cutoff)
    change = compare(current, previous, conn)
    project = current.project
    contracts = contract_versions()
    used = sorted(current.metrics)
    missing_contracts = [metric_id for metric_id in used if metric_id not in contracts]
    if missing_contracts:
        raise PsrError(f"metrics without a semantic contract: {missing_contracts}")

    orders = current.metrics["forecast_revenue_at_completion"].inputs.get("orders", [])
    fixed_rate = project["fixed_rate_per_eur"]

    def eur(amount: str) -> str:
        value = Decimal(amount)
        return fmt(value if not fixed_rate else value / fixed_rate)

    snapshot = _rows(conn, "select built_at, source_instance from marts.snapshot where snapshot_id = :s", s=snapshot_id)[0]
    freshness = _rows(
        conn,
        "select max(source_write_date) as latest from raw.source_record_version where source_instance = :i"
        " and batch_seq <= (select batch_seq from raw.ingestion_batch where batch_id = :s)",
        s=snapshot_id, i=snapshot["source_instance"],
    )[0]["latest"]
    planned_cash = _rows(
        conn,
        "select to_char(period, 'YYYY-MM') as period, sum(planned_billing) as billing, sum(planned_cash_collection) as cash"
        " from planning.plan_line where version_id = :v and cost_category = 'REVENUE' group by 1 order by 1 limit 6",
        v=current.versions.forecast["version_id"],
    ) if current.versions.forecast else []

    facts = []
    for metric_id, template in (
        ("eac", "Estimate at completion is {value} EUR."),
        ("forecast_margin_amount", "Forecast margin at completion is {value} EUR."),
        ("cost_variance_at_completion", "Cost variance at completion against the approved budget is {value} EUR (positive is unfavourable)."),
        ("overdue_amount", "Overdue receivables amount to {value} EUR including taxes."),
    ):
        value = current.value(metric_id)
        if value is not None:
            facts.append({"type": "OBSERVED_FACT", "text": template.format(value=fmt(value)), "numeric_claim_refs": [metric_id]})
    if change.status == "EROSION":
        facts.append({"type": "OBSERVED_FACT", "numeric_claim_refs": ["forecast_margin_amount"],
                      "text": f"Margin at completion changed by {fmt(change.margin_change)} EUR since {change.previous['forecast_version']}."})
    notes = _rows(conn, "select value_text, author, evidence_ref from planning.assumption where version_id = :v and key = 'forecast_change_note'",
                  v=current.versions.forecast["version_id"]) if current.versions.forecast else []
    hypotheses = [{"type": "SUPPORTED_HYPOTHESIS", "text": n["value_text"], "evidence_refs": [n["evidence_ref"]],
                   "support": f"declared by {n['author']} in the forecast; not independently verified"} for n in notes]
    unresolved = [{"type": "UNRESOLVED", "text": issue["detail"]} for issue in current.data_quality]

    content = {
        "schema_version": SCHEMA_VERSION,
        "report": {"period": f"{cutoff:%Y-%m}", "cutoff_date": str(cutoff), "snapshot_id": str(snapshot_id),
                   "snapshot_built_at": snapshot["built_at"].isoformat(), "latest_source_change": str(freshness) if freshness else None,
                   "source_instance": snapshot["source_instance"], "currency": "EUR"},
        "identity": {"project_code": project_code, "name": project["name"], "customer": project["customer_name"],
                     "project_manager": project["manager_name"], "business_unit": project["business_unit"],
                     "contract_type": project["contract_type"], "phase": project["phase"],
                     "date_start": str(project["date_start"]), "date_end": str(project["date_end"]),
                     "contract_currency": project["contract_currency"], "fixed_rate_per_eur": str(fixed_rate) if fixed_rate else None},
        "versions": {"forecast": current.versions.forecast, "previous_forecast": current.versions.previous_forecast,
                     "approved_budget": current.versions.budget, "baseline_budget": current.versions.baseline,
                     "pending_change_order_scenario": current.versions.pending_co},
        "contract_and_revenue": {
            "initial_contract": next((eur(o["amount"]) for o in orders if o["is_contract"] and o["state"] == "sale"), None),
            "approved_change_orders": fmt(sum((Decimal(eur(o["amount"])) for o in orders if not o["is_contract"] and o["state"] == "sale"), Decimal(0))),
            "pending_change_orders": _metric(current, "pending_change_orders"),
            "pending_change_order_scenario": pending_change_order_scenario(conn, current),
            "revised_contract_value": _metric(current, "forecast_revenue_at_completion"),
            "recognised_revenue": {"status": "UNAVAILABLE", "reason": "no approved revenue recognition policy"},
            "billed": _metric(current, "billed_amount"),
            "collected_ttc": _metric(current, "collected_amount"),
            "remaining_to_bill": _metric(current, "remaining_to_bill"),
        },
        "costs_and_forecast": {
            "approved_budget": _metric(current, "approved_budget"),
            "actual_cost": _metric(current, "actual_cost"),
            "open_commitments": _metric(current, "open_commitments"),
            "uncommitted_etc": _metric(current, "uncommitted_etc"),
            "etc": _metric(current, "etc"),
            "eac": _metric(current, "eac"),
            "cost_variance_at_completion": _metric(current, "cost_variance_at_completion"),
            "forecast_margin_amount": _metric(current, "forecast_margin_amount"),
            "forecast_margin_pct": _metric(current, "forecast_margin_pct"),
            "received_not_billed": _metric(current, "received_not_billed"),
            "by_category": {k: {c: fmt(v) for c, v in values.items()} for k, values in current.by_category.items()},
            "change_since_previous_forecast": change.as_dict(),
        },
        "execution": {
            "physical_progress_pct": _metric(current, "physical_progress_pct"),
            "cost_consumption_ratio": _metric(current, "cost_consumption_ratio"),
            "milestones": current.milestones,
            "hours": {"planned": _metric(current, "planned_hours"), "actual": _metric(current, "actual_hours"),
                      "at_completion": _metric(current, "hours_at_completion"),
                      "by_role": {k: {r: fmt(v, "h") for r, v in values.items()} for k, values in current.hours_by_role.items()}},
            "exceptions": current.exceptions + ([{"code": "MARGIN_EROSION", "amount": fmt(change.margin_change)}] if change.status == "EROSION" else []),
        },
        "treasury": {
            "receivables": current.receivables, "overdue_ttc": _metric(current, "overdue_amount"),
            "not_yet_due_ttc": _metric(current, "not_yet_due_amount"), "delayed_billing": _metric(current, "delayed_billing_amount"),
            "planned_billing_and_cash": [{"period": r["period"], "billing": fmt(r["billing"]),
                                          "cash_ttc": fmt(r["cash"])} for r in planned_cash],
        },
        "data_quality": {"status": "OK" if not current.data_quality else "ISSUES", "issues": current.data_quality},
        "commentary": {"mode": "DETERMINISTIC_NO_LLM", "label": "sans LLM", "computed_facts": facts, "hypotheses": hypotheses,
                       "unresolved": unresolved, "recommendations": [], "owner": project["manager_name"], "validation": "PENDING"},
        "metric_contracts": {metric_id: contracts[metric_id] for metric_id in used},
    }
    return content


def save_draft(conn: Connection, actor: Actor, content: dict[str, Any], company_id: int = 1) -> uuid.UUID:
    if not actor.can(Role.PROJECT_CONTROLLER):
        raise PsrError("preparing a status report requires the project_controller role")
    identity, report = content["identity"], content["report"]
    revision = conn.execute(
        sa.text("select coalesce(max(revision), 0) + 1 from decision.project_status_report where source_instance = :i"
                " and company_id = :c and project_code = :p and period = :per"),
        {"i": report["source_instance"], "c": company_id, "p": identity["project_code"], "per": report["period"]},
    ).scalar_one()
    psr_id = uuid.uuid4()
    versions = content["versions"]
    conn.execute(
        sa.text(
            "insert into decision.project_status_report (psr_id, source_instance, company_id, project_code, period, revision,"
            " cutoff_date, snapshot_id, forecast_version_id, previous_forecast_version_id, budget_version_id, status, content,"
            " content_hash, prepared_by) values (:id, :i, :c, :p, :per, :rev, :cut, :s, :fv, :pfv, :bv, 'DRAFT',"
            " cast(:content as jsonb), :h, :by)"
        ),
        {"id": psr_id, "i": report["source_instance"], "c": company_id, "p": identity["project_code"], "per": report["period"],
         "rev": revision, "cut": report["cutoff_date"], "s": report["snapshot_id"],
         "fv": (versions["forecast"] or {}).get("version_id"), "pfv": (versions["previous_forecast"] or {}).get("version_id"),
         "bv": (versions["approved_budget"] or {}).get("version_id"), "content": canonical_json(content),
         "h": content_hash(content), "by": actor.user_id},
    )
    append_event(conn, actor=actor.user_id, action="psr.draft_saved", object_type="project_status_report", object_id=str(psr_id),
                 payload={"project_code": identity["project_code"], "period": report["period"], "revision": revision,
                          "content_hash": content_hash(content)})
    return psr_id


def publish(conn: Connection, actor: Actor, psr_id: uuid.UUID, validated_comment: str) -> None:
    row = conn.execute(sa.text("select status, prepared_by, content_hash from decision.project_status_report where psr_id = :id"),
                       {"id": psr_id}).first()
    if row is None:
        raise PsrError(f"status report {psr_id} does not exist")
    if not actor.can(Role.FINANCE_APPROVER):
        raise PsrError("publishing a status report requires the finance_approver role")
    if row.prepared_by == actor.user_id:
        raise PsrError("maker-checker: the preparer cannot publish the same report")
    if row.status != "DRAFT":
        raise PsrError("only a draft report can be published")
    if not validated_comment.strip():
        raise PsrError("a published report needs the owner's validated comment")
    conn.execute(
        sa.text("update decision.project_status_report set status = 'PUBLISHED', approved_by = :a, approved_at = now(),"
                " validated_comment = :c where psr_id = :id"),
        {"a": actor.user_id, "c": validated_comment, "id": psr_id},
    )
    append_event(conn, actor=actor.user_id, action="psr.published", object_type="project_status_report", object_id=str(psr_id),
                 payload={"content_hash": row.content_hash})
