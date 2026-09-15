from __future__ import annotations

import json
from datetime import date

import httpx

from app.connectors.odoo import READ_METHODS, OdooJson2Client
from app.ops import seed_odoo
from tests.conftest import make_settings


class _RecordingOdoo:
    """Fake Odoo that answers reads and records every called method."""

    def __init__(self, *, company_exists: bool, usd_active: bool = False):
        self.calls: list[tuple[str, str]] = []
        self.company_exists = company_exists
        self.usd_active = usd_active

    def handler(self, request: httpx.Request) -> httpx.Response:
        model, method = request.url.path.split("/")[3:5]
        self.calls.append((model, method))
        body = json.loads(request.content or b"{}")
        if model == "ir.module.module":
            return httpx.Response(200, json=[{"name": n} for n in seed_odoo.REQUIRED_MODULES])
        if model == "res.company":
            rows = [{"id": 2, "name": body["domain"][0][2], "account_peppol_proxy_state": "not_registered"}]
            return httpx.Response(200, json=rows if self.company_exists else [])
        if model == "res.currency":
            return httpx.Response(200, json=[{"id": 2, "active": self.usd_active}])
        return httpx.Response(200, json=[])


def _settings(**overrides):
    values = dict(
        benacta_mode="odoo_sandbox",
        odoo_url="https://example.odoo.com",
        odoo_db="example",
        odoo_username="bot@example.invalid",
        odoo_api_key="k",
        odoo_sandbox_company="BENACTA DEMO",
    )
    values.update(overrides)
    return make_settings(**values)


def _patch_client(monkeypatch, fake: _RecordingOdoo):
    original = OdooJson2Client.from_settings.__func__

    def from_settings(cls, settings, **kwargs):
        return original(cls, settings, transport=httpx.MockTransport(fake.handler), **kwargs)

    monkeypatch.setattr(OdooJson2Client, "from_settings", classmethod(from_settings))


def test_seed_is_refused_by_the_guard_and_only_reads(monkeypatch, capsys):
    fake = _RecordingOdoo(company_exists=True)
    _patch_client(monkeypatch, fake)
    assert seed_odoo.seed(_settings()) == 2
    assert "Nothing was written" in capsys.readouterr().out
    assert fake.calls and all(method in READ_METHODS for _, method in fake.calls)


def test_dry_run_plans_every_step_and_flags_shared_configuration(monkeypatch, tmp_path):
    monkeypatch.setattr(seed_odoo, "PLAN_DIR", tmp_path)
    fake = _RecordingOdoo(company_exists=False)
    _patch_client(monkeypatch, fake)
    assert seed_odoo.dry_run(_settings()) == 0
    plan = json.loads(next(tmp_path.glob("seed_plan_*.json")).read_text(encoding="utf-8"))

    assert [op["model"] for op in plan["operations"]] == [model for model, _ in seed_odoo.OPERATIONS]
    sale = next(op for op in plan["operations"] if op["model"] == "sale.order")
    assert sale["objects"] == 123 and sale["detail"] == {"sale": 118, "draft": 4, "cancel": 1}
    decisions = {p["check"] for p in plan["prerequisites"] if p["decision_needed"]}
    assert "sandbox company 'BENACTA DEMO' exists" in decisions
    assert "USD currency active (global setting)" in decisions
    assert not next(c for c in plan["guard"] if c["check"] == "sandbox_company_exists")["passed"]
    assert all(method in READ_METHODS for _, method in fake.calls)


def test_guard_passing_still_writes_nothing_until_the_executor_is_verified(monkeypatch):
    fake = _RecordingOdoo(company_exists=True)
    _patch_client(monkeypatch, fake)
    settings = _settings(
        odoo_writes_enabled=True,
        odoo_sandbox_allowlist="example.odoo.com/example",
        odoo_backup_attested_at=date.today().isoformat(),
        odoo_backup_reference="backup.zip",
    )
    assert seed_odoo.seed(settings) == 3
    assert all(method in READ_METHODS for _, method in fake.calls)
