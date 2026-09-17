from __future__ import annotations

import os

import pytest

from app.config import Settings


def make_settings(**overrides) -> Settings:
    """Settings isolated from the developer's .env and environment."""
    return Settings(_env_file=None, **overrides)


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith(("ODOO_", "ANALYTICS_", "NEO4J_", "LLM_", "BENACTA_MODE", "EMBEDDING_")):
            monkeypatch.delenv(key, raising=False)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    live = os.environ.get("BENACTA_LIVE_ODOO") == "1"
    full = os.environ.get("BENACTA_FULL_PROFILE") == "1"
    skip_live = pytest.mark.skip(reason="live Odoo read; set BENACTA_LIVE_ODOO=1 to run")
    skip_full = pytest.mark.skip(reason="three-year demonstration profile (minutes); set BENACTA_FULL_PROFILE=1 to run")
    for item in items:
        if "odoo_live" in item.keywords and not live:
            item.add_marker(skip_live)
        if "full_profile" in item.keywords and not full:
            item.add_marker(skip_full)
