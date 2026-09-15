"""Version lifecycle: DRAFT -> SUBMITTED -> APPROVED -> LOCKED, and revisions.

Authorisation is checked here and again by database constraints (maker-checker, frozen lines, forward-only
status). Every transition is appended to the audit chain.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from app.audit.log import append_event
from app.planning.domain import Actor, Role, VersionStatus


class PlanningError(RuntimeError):
    pass


@dataclass(frozen=True)
class VersionRef:
    version_id: uuid.UUID
    company_id: int
    project_code: str
    version_type: str
    scenario: str
    label: str
    cutoff_date: date | None
    status: str
    submitted_by: str | None


def get_version(conn: Connection, version_id: uuid.UUID | str) -> VersionRef:
    row = conn.execute(
        sa.text(
            "select version_id, company_id, project_code, version_type, scenario, label, cutoff_date, status, submitted_by"
            " from planning.plan_version where version_id = :v"
        ),
        {"v": version_id},
    ).first()
    if row is None:
        raise PlanningError(f"version {version_id} does not exist")
    return VersionRef(**row._mapping)


def _check_access(actor: Actor, version: VersionRef) -> None:
    if not actor.can_access_project(version.company_id, version.project_code):
        raise PlanningError(f"{actor.user_id} may not act on project {version.project_code}")


def _transition(conn: Connection, actor: Actor, version: VersionRef, target: VersionStatus, stamp: str) -> None:
    """Move to `target`, stamping `<stamp>_by` and `<stamp>_at` (stamp is one of submitted, approved, locked)."""
    if stamp not in {"submitted", "approved", "locked"}:
        raise ValueError(stamp)
    conn.execute(
        sa.text(
            f"update planning.plan_version set status = :status, {stamp}_by = :actor, {stamp}_at = now()"  # noqa: S608
            " where version_id = :v"
        ),
        {"status": target.value, "actor": actor.user_id, "v": version.version_id},
    )
    append_event(
        conn,
        actor=actor.user_id,
        action=f"planning.version_{target.value.lower()}",
        object_type="plan_version",
        object_id=str(version.version_id),
        payload={
            "project_code": version.project_code,
            "label": version.label,
            "version_type": version.version_type,
            "scenario": version.scenario,
            "from": version.status,
            "to": target.value,
        },
    )


def submit(conn: Connection, actor: Actor, version_id: uuid.UUID | str) -> None:
    version = get_version(conn, version_id)
    _check_access(actor, version)
    if not actor.can(Role.PROJECT_CONTROLLER):
        raise PlanningError("submitting a version requires the project_controller role")
    if version.status != VersionStatus.DRAFT:
        raise PlanningError(f"only a DRAFT can be submitted (status {version.status})")
    lines = conn.execute(sa.text("select count(*) from planning.plan_line where version_id = :v"), {"v": version.version_id}).scalar()
    if not lines:
        raise PlanningError("an empty version cannot be submitted")
    _transition(conn, actor, version, VersionStatus.SUBMITTED, "submitted")


def approve(conn: Connection, actor: Actor, version_id: uuid.UUID | str) -> None:
    version = get_version(conn, version_id)
    _check_access(actor, version)
    if not actor.can(Role.FINANCE_APPROVER):
        raise PlanningError("approving a version requires the finance_approver role; admin is not implicit")
    if version.status != VersionStatus.SUBMITTED:
        raise PlanningError(f"only a SUBMITTED version can be approved (status {version.status})")
    if version.submitted_by == actor.user_id:
        raise PlanningError("maker-checker: the submitter cannot approve the same version")
    _transition(conn, actor, version, VersionStatus.APPROVED, "approved")


def lock(conn: Connection, actor: Actor, version_id: uuid.UUID | str) -> None:
    version = get_version(conn, version_id)
    _check_access(actor, version)
    if not actor.can(Role.FINANCE_APPROVER):
        raise PlanningError("locking a version requires the finance_approver role")
    if version.status != VersionStatus.APPROVED:
        raise PlanningError(f"only an APPROVED version can be locked (status {version.status})")
    _transition(conn, actor, version, VersionStatus.LOCKED, "locked")


def revise(conn: Connection, actor: Actor, version_id: uuid.UUID | str, *, label: str, cutoff_date: date | None = None) -> uuid.UUID:
    """Create a DRAFT copy referencing its parent. The parent is never modified."""
    parent = get_version(conn, version_id)
    _check_access(actor, parent)
    if not actor.can(Role.PROJECT_CONTROLLER):
        raise PlanningError("revising a version requires the project_controller role")
    new_id = uuid.uuid4()
    conn.execute(
        sa.text(
            "insert into planning.plan_version (version_id, company_id, source_instance, project_code, version_type,"
            " scenario, label, cutoff_date, currency, status, parent_version_id, author, source)"
            " select :n, company_id, source_instance, project_code, version_type, scenario, :l, coalesce(:c, cutoff_date),"
            " currency, 'DRAFT', version_id, :a, 'UI' from planning.plan_version where version_id = :p"
        ),
        {"n": new_id, "l": label, "c": cutoff_date, "a": actor.user_id, "p": parent.version_id},
    )
    conn.execute(
        sa.text(
            "insert into planning.plan_line (version_id, business_unit, work_package, cost_category, resource_or_role,"
            " period, currency, planned_hours, planned_rate, planned_cost, planned_revenue, planned_billing,"
            " planned_cash_collection) select :n, business_unit, work_package, cost_category, resource_or_role, period,"
            " currency, planned_hours, planned_rate, planned_cost, planned_revenue, planned_billing,"
            " planned_cash_collection from planning.plan_line where version_id = :p"
        ),
        {"n": new_id, "p": parent.version_id},
    )
    append_event(
        conn, actor=actor.user_id, action="planning.version_revised", object_type="plan_version", object_id=str(new_id),
        payload={"parent_version_id": str(parent.version_id), "label": label},
    )
    return new_id


def record_assumption(
    conn: Connection, actor: Actor, version_id: uuid.UUID | str, key: str, *, value_numeric: Decimal | None = None,
    value_text: str | None = None, work_package: str = "", evidence_ref: str | None = None,
) -> None:
    version = get_version(conn, version_id)
    _check_access(actor, version)
    conn.execute(
        sa.text(
            "insert into planning.assumption (version_id, key, work_package, value_numeric, value_text, author, evidence_ref)"
            " values (:v, :k, :w, :n, :t, :a, :e)"
        ),
        {"v": version.version_id, "k": key, "w": work_package, "n": value_numeric, "t": value_text, "a": actor.user_id, "e": evidence_ref},
    )


def record_assignments(conn: Connection, actor: Actor, version_id: uuid.UUID | str, rows: list[dict[str, Any]]) -> None:
    version = get_version(conn, version_id)
    _check_access(actor, version)
    if rows:
        conn.execute(
            sa.text(
                "insert into planning.assignment (version_id, work_package, employee_code, role, period, planned_hours)"
                " values (:v, :wp, :e, :r, :p, :h)"
            ),
            [{"v": version.version_id, "wp": r["work_package"], "e": r["employee_code"], "r": r["role"], "p": r["period"],
              "h": r["planned_hours"]} for r in rows],
        )
