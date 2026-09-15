"""FastAPI application. Routes are added milestone by milestone under /api/v1.

Read routes serve the same service functions as the CLI, so the same snapshot gives the same figures on
every surface. The API opens the analytics database lazily and never talks to Odoo per request.
"""

from __future__ import annotations

import uuid
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query
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


@app.get("/api/v1/margin/rules")
def margin_rules_route() -> list[dict]:
    from app.margin.service import rule_catalogue

    return rule_catalogue()


@app.get("/api/v1/reconciliation")
def reconciliation_route(period: str | None = None, snapshot: str | None = None) -> dict:
    from app.marts.reconcile import reconciliation_report

    return reconciliation_report(_engine(), _snapshot(snapshot), period)
