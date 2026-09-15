"""FastAPI application. Routes are added sprint by sprint under /api/v1."""

from __future__ import annotations

from fastapi import FastAPI

from app.config import get_settings

app = FastAPI(title="BENACTA Decision System API", version="0.1.0")


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
