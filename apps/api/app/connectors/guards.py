"""Target controls run before any migration, seed or write-back.

Each guard returns every check with its outcome so that a refusal explains
itself, instead of failing on the first condition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from urllib.parse import urlsplit

from app.config import Mode, Settings


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


@dataclass
class GuardReport:
    guard: str
    checks: list[Check] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return bool(self.checks) and all(check.passed for check in self.checks)

    def add(self, name: str, passed: bool, detail: str) -> None:
        self.checks.append(Check(name, passed, detail))

    def raise_if_blocked(self) -> None:
        if not self.allowed:
            failed = "; ".join(f"{c.name}: {c.detail}" for c in self.checks if not c.passed)
            raise TargetGuardError(f"{self.guard} blocked ({failed or 'no checks evaluated'})")


class TargetGuardError(RuntimeError):
    pass


def _database_name(url: str) -> str:
    return urlsplit(url).path.lstrip("/").split("?")[0]


def analytics_target_guard(settings: Settings) -> GuardReport:
    """Static checks that the analytics URL is the BENACTA database, not Odoo's."""
    report = GuardReport("analytics_migration")
    if settings.analytics_database_url is None:
        report.add("analytics_url_configured", False, "ANALYTICS_DATABASE_URL is not set")
        return report

    url = settings.analytics_database_url.get_secret_value()
    name = _database_name(url)
    report.add("analytics_url_configured", True, "set")
    report.add(
        "expected_database_name",
        name == settings.analytics_db_expected_name,
        f"database name must equal ANALYTICS_DB_EXPECTED_NAME ({settings.analytics_db_expected_name})",
    )
    report.add(
        "not_odoo_database_name",
        not settings.odoo_db or name != settings.odoo_db,
        "analytics database name must differ from ODOO_DB",
    )
    if settings.odoo_read_dsn is not None:
        odoo = urlsplit(settings.odoo_read_dsn.get_secret_value())
        analytics = urlsplit(url)
        same = (odoo.hostname, odoo.port, _database_name(odoo.geturl())) == (
            analytics.hostname,
            analytics.port,
            name,
        )
        report.add("not_odoo_read_dsn", not same, "analytics URL must not point at ODOO_READ_DSN")
    return report


# Tables that only exist in an Odoo database. Checked on the live connection before migrating.
ODOO_SIGNATURE_TABLES = ("ir_module_module", "res_users", "ir_model")


def odoo_write_guard(
    settings: Settings,
    *,
    sandbox_company_exists: bool | None = None,
    today: date | None = None,
) -> GuardReport:
    """Every condition required before writing to Odoo.

    `sandbox_company_exists` comes from a live read of res.company; None means
    it was not checked, which blocks.
    """
    report = GuardReport("odoo_write")
    today = today or datetime.now(UTC).date()

    report.add(
        "mode_is_sandbox",
        settings.benacta_mode is Mode.ODOO_SANDBOX,
        f"BENACTA_MODE={settings.benacta_mode.value}",
    )
    report.add("writes_enabled", settings.odoo_writes_enabled, "ODOO_WRITES_ENABLED must be true")
    target = settings.odoo_target
    report.add(
        "target_allowlisted",
        target is not None and target in settings.odoo_sandbox_allowlist,
        f"target {target or 'unknown'} must be listed in ODOO_SANDBOX_ALLOWLIST",
    )

    company = settings.odoo_sandbox_company
    protected = {name.casefold() for name in settings.odoo_protected_companies}
    report.add(
        "sandbox_company_named",
        bool(company) and company.casefold() not in protected,
        "ODOO_SANDBOX_COMPANY must be set and must not be a protected company",
    )
    report.add(
        "sandbox_company_exists",
        sandbox_company_exists is True,
        "sandbox company must be verified on the live instance",
    )

    attested = _parse_date(settings.odoo_backup_attested_at)
    fresh = attested is not None and 0 <= (today - attested).days <= settings.odoo_backup_max_age_days
    report.add(
        "backup_attested",
        fresh and bool(settings.odoo_backup_reference),
        f"ODOO_BACKUP_ATTESTED_AT within {settings.odoo_backup_max_age_days} days and ODOO_BACKUP_REFERENCE required",
    )
    return report


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
