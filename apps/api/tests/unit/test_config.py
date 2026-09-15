from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Mode
from tests.conftest import make_settings

SECRET = "super-secret-value-123"


def test_default_mode_is_fixture_without_any_credential():
    settings = make_settings()
    assert settings.benacta_mode is Mode.FIXTURE
    assert settings.odoo_api_configured is False
    assert settings.odoo_writes_enabled is False


@pytest.mark.parametrize("value", ["production", "PROD"])
def test_production_mode_is_rejected(value):
    with pytest.raises(ValidationError, match="production mode is not supported"):
        make_settings(benacta_mode=value)


def test_describe_reports_presence_and_never_secret_values():
    settings = make_settings(
        odoo_url="https://example.odoo.com",
        odoo_db="example",
        odoo_username="bot@example.invalid",
        odoo_api_key=SECRET,
        analytics_database_url=f"postgresql://u:{SECRET}@db.example/benacta_analytics",
        llm_api_key=SECRET,
    )
    described = settings.describe()
    assert described["odoo_api"] == "CONFIGURED"
    assert described["llm"] == "PARTIAL"
    rendered = repr(described) + repr(settings)
    assert SECRET not in rendered
    assert "bot@example.invalid" not in repr(described)


def test_odoo_target_is_host_and_database():
    settings = make_settings(odoo_url="https://example.odoo.com/", odoo_db="example")
    assert settings.odoo_target == "example.odoo.com/example"


def test_comma_separated_lists_are_parsed():
    settings = make_settings(odoo_sandbox_allowlist="a.odoo.com/a, b.odoo.com/b", odoo_protected_companies="X,Y")
    assert settings.odoo_sandbox_allowlist == ["a.odoo.com/a", "b.odoo.com/b"]
    assert settings.odoo_protected_companies == ["X", "Y"]
