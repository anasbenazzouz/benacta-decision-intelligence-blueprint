"""Load generated plan files through the user import path, then apply the approval workflow.

Idempotent: a version that already exists (same instance, company, project, type, scenario, label) is skipped, so a
replay never duplicates a version nor reopens a locked one.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from app.planning import service
from app.planning.domain import Actor, Role
from app.planning.importer import ImportContext, import_plan

CONTROLLER = Actor("E04", frozenset({Role.PROJECT_CONTROLLER}), frozenset({1}))
APPROVER = Actor("FIN-01", frozenset({Role.FINANCE_APPROVER}), frozenset({1}))
ORDER = {"BUDGET_BASELINE": 0, "BUDGET_REVISED": 1, "FORECAST": 2}


@dataclass
class SeedPlansResult:
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def known_projects(conn: Connection, snapshot_id: uuid.UUID) -> dict[str, str]:
    rows = conn.execute(
        sa.text("select project_code, business_unit from marts.dim_project where snapshot_id = :s and not is_internal"),
        {"s": snapshot_id},
    ).all()
    return {r.project_code: r.business_unit for r in rows}


def seed_plans(conn: Connection, plans: list, snapshot_id: uuid.UUID, source_instance: str, company_id: int = 1) -> SeedPlansResult:
    ctx = ImportContext(company_id=company_id, source_instance=source_instance, known_projects=known_projects(conn, snapshot_id))
    result = SeedPlansResult()
    for plan in sorted(plans, key=lambda p: (p.project_code, ORDER[p.version_type], str(p.cutoff_date), p.scenario)):
        name = f"{plan.project_code} {plan.version_type} {plan.scenario} {plan.label}"
        exists = conn.execute(
            sa.text(
                "select 1 from planning.plan_version where source_instance = :i and company_id = :c and project_code = :p"
                " and version_type = :t and scenario = :s and label = :l"
            ),
            {"i": source_instance, "c": company_id, "p": plan.project_code, "t": plan.version_type, "s": plan.scenario, "l": plan.label},
        ).first()
        if exists:
            result.skipped.append(name)
            continue
        imported = import_plan(conn, plan.rows, ctx, CONTROLLER, source="SEED", file_name=f"{name}.csv")
        if imported.status != "VALIDATED":
            details = "; ".join(f"row {e.row_number} {e.code}: {e.message}" for e in imported.errors[:5])
            raise RuntimeError(f"seed plan rejected for {name}: {details}")
        version_id = imported.version_id
        service.record_assignments(conn, CONTROLLER, version_id, plan.assignments)
        for assumption in plan.assumptions:
            service.record_assumption(conn, CONTROLLER, version_id, assumption["key"],
                                      value_numeric=assumption.get("value_numeric"), value_text=assumption.get("value_text"),
                                      evidence_ref=assumption.get("evidence_ref"))
        if plan.target_status in ("SUBMITTED", "APPROVED", "LOCKED"):
            service.submit(conn, CONTROLLER, version_id)
        if plan.target_status in ("APPROVED", "LOCKED"):
            service.approve(conn, APPROVER, version_id)
        if plan.target_status == "LOCKED":
            service.lock(conn, APPROVER, version_id)
        result.created.append(name)
    return result
