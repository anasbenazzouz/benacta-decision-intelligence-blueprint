"""FastAPI application. Routes are added milestone by milestone under /api/v1.

Read routes serve the same service functions as the CLI, so the same snapshot gives the same figures on
every surface. The API opens the analytics database lazily and never talks to Odoo per request.
"""

from __future__ import annotations

import uuid
from datetime import date
from functools import lru_cache

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine

from app.config import Mode, get_settings

app = FastAPI(title="BENACTA Decision System API", version="0.2.0")


@lru_cache
def _engine() -> Engine:
    from app.db.engine import analytics_engine

    return analytics_engine(get_settings())


def _instance() -> str:
    from app.ops.pipeline import FIXTURE_SOURCE_INSTANCE

    settings = get_settings()
    return FIXTURE_SOURCE_INSTANCE if settings.benacta_mode is Mode.FIXTURE else settings.odoo_source_instance


def _snapshot(snapshot: str | None) -> uuid.UUID:
    from app.ops.pipeline import latest_snapshot

    if snapshot:
        try:
            return uuid.UUID(snapshot)
        except ValueError as exc:
            raise HTTPException(400, "snapshot must be a UUID") from exc
    try:
        return latest_snapshot(_engine(), _instance())
    except RuntimeError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    """Liveness only: the process answers."""
    return {"status": "ok"}


@app.get("/api/v1/ready")
def ready() -> dict[str, object]:
    """Readiness from configuration. Live checks run through `benacta doctor`, not per request."""
    settings = get_settings()
    connections = settings.describe()
    # Fixture mode needs no external connection. Connected mode is not ready without Odoo.
    is_ready = settings.benacta_mode.value == "fixture" or connections["odoo_api"] == "CONFIGURED"
    return {"ready": is_ready, "connections": connections}


@app.get("/api/v1/margin/overview")
def margin_overview_route(period: str | None = None, snapshot: str | None = None) -> dict:
    from app.margin.service import margin_overview

    with _engine().connect() as conn:
        return margin_overview(conn, _snapshot(snapshot), period)


@app.get("/api/v1/margin/exceptions")
def margin_exceptions_route(
    period: str | None = None,
    classification: str | None = None,
    include_resolved: bool = False,
    limit: int = Query(100, ge=1, le=1000),
    snapshot: str | None = None,
) -> list[dict]:
    from app.margin.service import exception_queue

    with _engine().connect() as conn:
        return exception_queue(conn, _snapshot(snapshot), period=period, classification=classification,
                               include_resolved=include_resolved, limit=limit)


@app.get("/api/v1/margin/exceptions/{case_ref}")
def margin_case_route(case_ref: str, snapshot: str | None = None) -> dict:
    from app.margin.service import exception_case

    with _engine().connect() as conn:
        case = exception_case(conn, _snapshot(snapshot), case_ref)
    if case is None:
        raise HTTPException(404, f"no case {case_ref}")
    return case


class DecisionBody(BaseModel):
    decision_type: str = Field(pattern="^(APPROVE|REJECT|REQUEST_EVIDENCE|ASSIGN|DEFER|COMMENT|REOPEN|CLOSE)$")
    expected_version: int | None = None
    reason: str | None = None
    comment: str | None = None
    assigned_to: str | None = None
    defer_until: date | None = None


class ActionBody(BaseModel):
    confirm: bool = False


def _actor(actor: str | None, roles: str | None):
    """Pilot identity from headers `X-Benacta-Actor` and `X-Benacta-Roles`; not an authentication system (see docs/security_notes.md)."""
    from app.margin.decisions import parse_actor

    if not actor:
        raise HTTPException(401, "X-Benacta-Actor header required")
    try:
        return parse_actor(actor, (roles or "").split(","))
    except ValueError as exc:
        raise HTTPException(400, f"unknown role: {exc}") from exc


@app.post("/api/v1/margin/exceptions/{case_ref}/decisions", status_code=201)
def margin_decision_route(case_ref: str, body: DecisionBody, x_benacta_actor: str | None = Header(default=None),
                          x_benacta_roles: str | None = Header(default=None)) -> dict:
    from app.margin.decisions import DecisionError, decide

    actor = _actor(x_benacta_actor, x_benacta_roles)
    try:
        with _engine().begin() as conn:
            result = decide(conn, actor, case_ref, body.decision_type, expected_version=body.expected_version, reason=body.reason,
                            comment=body.comment, assigned_to=body.assigned_to, defer_until=body.defer_until)
    except DecisionError as exc:
        raise HTTPException(exc.http_status, str(exc)) from exc
    return {"decision_id": str(result.decision_id), "case_ref": result.case_ref, "decision_type": result.decision_type,
            "status_before": result.status_before, "status_after": result.status_after, "version": result.version}


@app.post("/api/v1/margin/exceptions/{case_ref}/actions")
def margin_action_route(case_ref: str, body: ActionBody, x_benacta_actor: str | None = Header(default=None),
                        x_benacta_roles: str | None = Header(default=None)) -> dict:
    from app.margin.actions import execute_review_activity, plan_review_activity
    from app.margin.decisions import DecisionError

    actor = _actor(x_benacta_actor, x_benacta_roles)
    try:
        with _engine().begin() as conn:
            plan = plan_review_activity(conn, case_ref)
            if not body.confirm:
                return {"status": "DRY_RUN", "case_ref": plan.case_ref, "target_model": plan.target_model, "target_res_id": plan.target_res_id,
                        "external_id": plan.external_id, "request": plan.vals}
            result = execute_review_activity(conn, get_settings(), actor, case_ref)
    except DecisionError as exc:
        raise HTTPException(exc.http_status, str(exc)) from exc
    return {"action_id": str(result.action_id), "status": result.status, "detail": result.detail, "response": result.response}


class InvestigateBody(BaseModel):
    use_llm: bool = False


@app.post("/api/v1/margin/exceptions/{case_ref}/investigate", status_code=201)
def margin_investigate_route(case_ref: str, body: InvestigateBody) -> dict:
    from app.margin.investigation import investigate
    from app.margin.llm import provider_from_settings

    provider = provider_from_settings(get_settings()) if body.use_llm else None
    try:
        with _engine().begin() as conn:
            return investigate(conn, _snapshot(None), case_ref, provider=provider)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    finally:
        if provider is not None:
            provider.close()


@app.get("/api/v1/margin/impact")
def margin_impact_route() -> list[dict]:
    from app.margin.service import impact_register

    with _engine().connect() as conn:
        return impact_register(conn, _instance())


@app.get("/api/v1/margin/exceptions/{case_ref}/audit")
def margin_audit_route(case_ref: str) -> dict:
    from app.margin.service import case_audit

    with _engine().connect() as conn:
        audit = case_audit(conn, case_ref)
    if audit is None:
        raise HTTPException(404, f"no case {case_ref}")
    return audit


@app.get("/api/v1/margin/rules")
def margin_rules_route() -> list[dict]:
    from app.margin.service import rule_catalogue

    return rule_catalogue()


@app.get("/api/v1/reconciliation")
def reconciliation_route(period: str | None = None, snapshot: str | None = None) -> dict:
    from app.marts.reconcile import reconciliation_report

    return reconciliation_report(_engine(), _snapshot(snapshot), period)
