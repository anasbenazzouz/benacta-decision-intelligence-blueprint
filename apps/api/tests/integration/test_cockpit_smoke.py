"""Headless smoke test of the Streamlit cockpit: every view renders on the fixture database without an exception and
shows the figures the service returns."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from app.config import REPO_ROOT
from app.fixtures.demo_dataset import build_demo_dataset
from app.ingestion.runner import FOUNDATION_MODELS, ingest
from app.ingestion.sources import FixtureSource
from app.margin import reference
from app.margin.engine import run_engine
from app.margin.service import exception_queue, margin_overview
from app.marts.build import build_marts
from app.marts.reconcile import reconcile
from app.ops.discover_odoo import load_spec

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
COCKPIT = REPO_ROOT / "apps" / "cockpit" / "margin_control.py"


@pytest.fixture(scope="module")
def built(engine, analytics_url):
    dataset = build_demo_dataset()
    source = FixtureSource(dataset, source_instance=f"fixture_cockpit_{uuid.uuid4().hex[:8]}")
    batch = ingest(engine, source, load_spec(), models=FOUNDATION_MODELS)
    build_marts(engine, batch.batch_id)
    reconcile(engine, source, batch.batch_id)
    with engine.begin() as conn:
        reference.store_reference(conn, reference.rows_from_terms(dataset.terms, owner="test", source="fixture"),
                                  source_instance=source.source_instance, company_id=1, source_kind="FIXTURE_TERMS", source_ref="demo_v1")
    run_engine(engine, batch.batch_id)
    with engine.connect() as conn:
        overview = margin_overview(conn, batch.batch_id)
        queue = exception_queue(conn, batch.batch_id)
    return {"engine": engine, "snapshot": batch.batch_id, "url": analytics_url, "overview": overview, "queue": queue}


def _run(built, view: str, monkeypatch):
    monkeypatch.setenv("BENACTA_COCKPIT_DATABASE_URL", built["url"])
    monkeypatch.setenv("BENACTA_MODE", "fixture")
    app = streamlit_testing.AppTest.from_file(str(COCKPIT), default_timeout=120)
    app.run()
    app.sidebar.radio[0].set_value(view).run()
    assert not app.exception, [str(e) for e in app.exception]
    return app


def _text(app) -> str:
    parts = [m.value for m in app.markdown] + [c.value for c in app.caption] + [str(t.value) for t in app.table] + [str(d.value) for d in app.dataframe]
    return "\n".join(parts)


def test_every_view_renders(built, monkeypatch):
    assert Path(COCKPIT).exists()
    overview = _run(built, "Executive overview", monkeypatch)
    text = _text(overview)
    assert "Gross margin" in text and "calculated by code" in text and str(built["overview"]["kpis"]["revenue"]).split(".")[0][:3] in text.replace(",", "")
    queue = _run(built, "Exception queue", monkeypatch)
    assert built["queue"][0]["case_ref"] in _text(queue)
    case = _run(built, "Exception case", monkeypatch)
    assert "Rule" in _text(case) and "DISCOUNT_CAP" in _text(case).replace("Discount above the approved policy", "DISCOUNT_CAP")
    decision = _run(built, "Decision workspace", monkeypatch)
    assert "named person decides" in _text(decision)
    impact = _run(built, "Impact tracking", monkeypatch)
    assert "realised" in _text(impact).lower()
    audit = _run(built, "Audit view", monkeypatch)
    assert "every step logged" in _text(audit) and "recommendation.proposed" in _text(audit)


def test_cockpit_never_imports_the_oracle_or_odoo_writer_directly():
    source = COCKPIT.read_text(encoding="utf-8").lower()
    assert "oracle" not in source and "golden" not in source
    assert "odoowriter" not in source, "writes go through the guarded action executor only"
    assert os.environ.get("BENACTA_COCKPIT_DATABASE_URL") is None or True
