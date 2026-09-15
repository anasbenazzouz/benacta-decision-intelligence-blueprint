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
    if os.environ.get("BENACTA_LIVE_ODOO") == "1":
        return
    skip = pytest.mark.skip(reason="live Odoo read; set BENACTA_LIVE_ODOO=1 to run")
    for item in items:
        if "odoo_live" in item.keywords:
            item.add_marker(skip)
