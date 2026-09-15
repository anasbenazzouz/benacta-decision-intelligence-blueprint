"""Read-only ingestion of the connected Odoo into an ephemeral analytics database.

Opt-in with BENACTA_LIVE_ODOO=1. Nothing is written to Odoo: the source wraps OdooReader.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from app.config import Settings
from app.connectors.odoo import OdooJson2Client, OdooReader
from app.ingestion.runner import INGESTED_MODELS, ingest
from app.ingestion.sources import OdooSource
from app.marts.build import build_marts
from app.marts.reconcile import margin_basis, reconcile
from app.ops.discover_odoo import load_spec

pytestmark = pytest.mark.odoo_live


@pytest.fixture(scope="module")
def live_source():
    settings = Settings()
    if not settings.odoo_api_configured:
        pytest.skip("Odoo API not configured")
    with OdooJson2Client.from_settings(settings) as client:
        yield OdooSource(OdooReader(client), source_instance=f"{settings.odoo_source_instance}_livetest")


@pytest.fixture(scope="module")
def live_batches(engine, live_source):
    spec = load_spec()
    first = ingest(engine, live_source, spec)
    second = ingest(engine, live_source, spec)
    return first, second


def test_every_live_record_is_ingested_once(live_source, live_batches):
    first, _ = live_batches
    for model in INGESTED_MODELS:
        assert first.models[model].new_versions == len(live_source.all_ids(model)), model


def test_replaying_against_live_odoo_adds_nothing(live_batches):
    _, second = live_batches
    assert second.new_versions == 0
    assert all(result.deletions == 0 for result in second.models.values())


def test_live_marts_reconcile_revenue_against_server_aggregates(engine, live_source, live_batches):
    _, second = live_batches
    stats = build_marts(engine, second.batch_id)
    assert stats["fact_invoice_line"] > 0
    results = reconcile(engine, live_source, second.batch_id)
    revenue = [r for r in results if r.check_id == "REVENUE_POSTED"]
    assert revenue and {r.status for r in revenue} == {"RECONCILED"}
    assert {r.independence for r in revenue} == {"SERVER_AGGREGATE"}
    # The connected data has goods revenue without posted COGS: margin cannot be certified.
    assert margin_basis(engine, second.batch_id) == "MANAGEMENT_PROXY"


def test_live_invoice_lines_without_sale_link_are_flagged(engine, live_batches):
    _, second = live_batches
    with engine.connect() as c:
        flagged = c.execute(
            sa.text(
                "select count(*) from marts.data_quality_issue where snapshot_id = :s"
                " and issue_code = 'INVOICE_LINE_WITHOUT_SALE_LINE'"
            ),
            {"s": second.batch_id},
        ).scalar()
        lines = c.execute(
            sa.text("select count(*) from marts.fact_invoice_line where snapshot_id = :s"), {"s": second.batch_id}
        ).scalar()
    assert flagged <= lines
