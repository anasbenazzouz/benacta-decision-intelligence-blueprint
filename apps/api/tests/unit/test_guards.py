from __future__ import annotations

from datetime import date

import pytest

from app.connectors.guards import TargetGuardError, analytics_target_guard, odoo_write_guard
from tests.conftest import make_settings

TODAY = date(2026, 9, 14)


def _failed(report) -> set[str]:
    return {c.name for c in report.checks if not c.passed}


class TestAnalyticsTargetGuard:
    def test_missing_url_blocks(self):
        report = analytics_target_guard(make_settings())
        assert not report.allowed
        with pytest.raises(TargetGuardError):
            report.raise_if_blocked()

    def test_expected_benacta_database_passes(self):
        settings = make_settings(
            odoo_db="benacta",
            analytics_database_url="postgresql://u:p@analytics.example:5432/benacta_analytics?sslmode=require",
        )
        report = analytics_target_guard(settings)
        assert report.allowed, report.checks

    def test_unexpected_database_name_blocks(self):
        settings = make_settings(analytics_database_url="postgresql://u:p@h/postgres")
        assert "expected_database_name" in _failed(analytics_target_guard(settings))

    def test_odoo_database_name_blocks_even_if_expected_name_is_misconfigured(self):
        settings = make_settings(
            odoo_db="benacta",
            analytics_db_expected_name="benacta",
            analytics_database_url="postgresql://u:p@h/benacta",
        )
        assert "not_odoo_database_name" in _failed(analytics_target_guard(settings))

    def test_same_target_as_odoo_read_dsn_blocks(self):
        dsn = "postgresql://u:p@odoo-db.example:5432/benacta_analytics"
        settings = make_settings(odoo_read_dsn=dsn, analytics_database_url=dsn)
        assert "not_odoo_read_dsn" in _failed(analytics_target_guard(settings))


def _sandbox_ready(**overrides):
    values = dict(
        benacta_mode="odoo_sandbox",
        odoo_url="https://example.odoo.com",
        odoo_db="example",
        odoo_writes_enabled=True,
        odoo_sandbox_allowlist="example.odoo.com/example",
        odoo_sandbox_company="BENACTA DEMO",
        odoo_backup_attested_at="2026-09-13",
        odoo_backup_reference="example_2026-09-13.zip",
    )
    values.update(overrides)
    return make_settings(**values)


class TestOdooWriteGuard:
    def test_default_configuration_blocks_and_explains_every_condition(self):
        report = odoo_write_guard(make_settings(), today=TODAY)
        assert not report.allowed
        assert _failed(report) == {
            "mode_is_sandbox",
            "writes_enabled",
            "target_allowlisted",
            "sandbox_company_named",
            "sandbox_company_exists",
            "backup_attested",
        }

    def test_all_conditions_met_allows(self):
        report = odoo_write_guard(_sandbox_ready(), sandbox_company_exists=True, today=TODAY)
        assert report.allowed, _failed(report)
        report.raise_if_blocked()

    def test_unchecked_company_blocks(self):
        report = odoo_write_guard(_sandbox_ready(), sandbox_company_exists=None, today=TODAY)
        assert _failed(report) == {"sandbox_company_exists"}

    @pytest.mark.parametrize("company", ["Benacta", "benacta", ""])
    def test_protected_or_empty_company_blocks(self, company):
        report = odoo_write_guard(
            _sandbox_ready(odoo_sandbox_company=company), sandbox_company_exists=True, today=TODAY
        )
        assert "sandbox_company_named" in _failed(report)

    def test_target_not_in_allowlist_blocks(self):
        settings = _sandbox_ready(odoo_url="https://other.odoo.com")
        report = odoo_write_guard(settings, sandbox_company_exists=True, today=TODAY)
        assert _failed(report) == {"target_allowlisted"}

    @pytest.mark.parametrize(
        ("attested", "reference"),
        [("2026-09-01", "x.zip"), ("2026-09-15", "x.zip"), ("not-a-date", "x.zip"), ("2026-09-13", None)],
    )
    def test_stale_future_invalid_or_unreferenced_backup_blocks(self, attested, reference):
        settings = _sandbox_ready(odoo_backup_attested_at=attested, odoo_backup_reference=reference)
        report = odoo_write_guard(settings, sandbox_company_exists=True, today=TODAY)
        assert _failed(report) == {"backup_attested"}

    def test_fixture_mode_blocks_even_with_everything_else(self):
        report = odoo_write_guard(_sandbox_ready(benacta_mode="fixture"), sandbox_company_exists=True, today=TODAY)
        assert _failed(report) == {"mode_is_sandbox"}


class TestOdooConfigurationGuard:
    def test_configuration_does_not_require_a_backup_but_keeps_every_other_check(self):
        settings = _sandbox_ready(odoo_backup_attested_at=None, odoo_backup_reference=None)
        report = odoo_write_guard(settings, sandbox_company_exists=True, today=TODAY, require_backup=False)
        assert report.allowed and report.guard == "odoo_configuration"
        assert "backup_attested" not in {c.name for c in report.checks}

    def test_configuration_still_blocks_without_writes_or_allowlist(self):
        settings = _sandbox_ready(odoo_writes_enabled=False, odoo_sandbox_allowlist="")
        report = odoo_write_guard(settings, sandbox_company_exists=True, today=TODAY, require_backup=False)
        assert _failed(report) == {"writes_enabled", "target_allowlisted"}

    def test_business_writes_still_require_the_backup(self):
        settings = _sandbox_ready(odoo_backup_attested_at=None)
        assert _failed(odoo_write_guard(settings, sandbox_company_exists=True, today=TODAY)) == {"backup_attested"}
