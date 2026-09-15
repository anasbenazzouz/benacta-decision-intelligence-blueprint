"""Connection doctor: configuration presence and live verification per connection.

Statuses: VERIFIED (a live call succeeded now), FAILED, NOT_CONFIGURED,
NOT_IMPLEMENTED (the connection exists in configuration but no client ships yet).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.connectors.guards import analytics_target_guard, odoo_write_guard
from app.connectors.odoo import OdooError, OdooJson2Client, OdooReader


@dataclass(frozen=True)
class ConnectionStatus:
    connection: str
    status: str
    detail: str


def check_odoo_api(settings: Settings) -> tuple[ConnectionStatus, bool | None]:
    """Returns the status and whether the configured sandbox company exists."""
    if not settings.odoo_api_configured:
        return ConnectionStatus(
            "odoo_api", "NOT_CONFIGURED", "set ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY"
        ), None
    try:
        with OdooJson2Client.from_settings(settings, max_retries=0) as client:
            reader = OdooReader(client)
            version = reader.version().get("version")
            companies = reader.search_read("res.company", [], ["name"])
    except (OdooError, OSError) as exc:
        return ConnectionStatus("odoo_api", "FAILED", type(exc).__name__ + ": " + str(exc)[:160]), None
    names = {c["name"] for c in companies}
    sandbox_exists = settings.odoo_sandbox_company in names if settings.odoo_sandbox_company else False
    return (
        ConnectionStatus("odoo_api", "VERIFIED", f"version {version}, {len(companies)} visible company(ies), JSON-2"),
        sandbox_exists,
    )


def run_checks(settings: Settings) -> tuple[list[ConnectionStatus], list]:
    odoo, sandbox_exists = check_odoo_api(settings)
    statuses = [
        ConnectionStatus("mode", "INFO", settings.benacta_mode.value),
        odoo,
        ConnectionStatus(
            "odoo_read_dsn",
            "NOT_CONFIGURED" if settings.odoo_read_dsn is None else "NOT_IMPLEMENTED",
            "Odoo Online exposes no direct PostgreSQL access; the API adapter is used",
        ),
    ]
    analytics = analytics_target_guard(settings)
    statuses.append(
        ConnectionStatus(
            "analytics_database",
            "NOT_CONFIGURED"
            if settings.analytics_database_url is None
            else "NOT_IMPLEMENTED"
            if analytics.allowed
            else "FAILED",
            "; ".join(c.name for c in analytics.checks if not c.passed) or "static target checks passed",
        )
    )
    for name, configured in (
        ("neo4j", settings.describe()["neo4j"]),
        ("llm", settings.describe()["llm"]),
    ):
        statuses.append(
            ConnectionStatus(name, "NOT_CONFIGURED" if configured != "CONFIGURED" else "NOT_IMPLEMENTED", configured)
        )
    write_guard = odoo_write_guard(settings, sandbox_company_exists=sandbox_exists)
    return statuses, write_guard.checks


def main(settings: Settings) -> int:
    statuses, write_checks = run_checks(settings)
    width = max(len(s.connection) for s in statuses)
    print("Connections")
    for s in statuses:
        print(f"  {s.connection.ljust(width)}  {s.status.ljust(15)}  {s.detail}")
    print("\nOdoo write guard (all must pass before any seed or write-back)")
    for check in write_checks:
        print(f"  [{'x' if check.passed else ' '}] {check.name}: {check.detail}")
    return 0 if all(s.status != "FAILED" for s in statuses) else 1
