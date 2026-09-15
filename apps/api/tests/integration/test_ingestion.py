from __future__ import annotations

import copy
import uuid
from datetime import timedelta

import pytest
import sqlalchemy as sa

from app.audit.log import verify_chain
from app.fixtures.demo_dataset import build_demo_dataset
from app.ingestion.runner import FOUNDATION_MODELS, ingest
from app.ingestion.sources import FixtureSource
from app.ops.discover_odoo import load_spec
from tests.integration.conftest import scalar

SPEC = load_spec()
MODELS = ("res.partner", "sale.order", "sale.order.line")


@pytest.fixture(scope="module")
def dataset():
    return build_demo_dataset()


def _source(dataset, instance=None):
    return FixtureSource(copy.deepcopy(dataset), source_instance=instance or f"fixture_test_{uuid.uuid4().hex[:8]}")


def _payload_at(engine, instance, model, source_id, batch_seq):
    with engine.connect() as c:
        return c.execute(
            sa.text("select payload from staging.records_at(:i, :m, :s) where source_id = :id"),
            {"i": instance, "m": model, "s": batch_seq, "id": source_id},
        ).scalar()


def test_full_ingestion_then_replay_adds_no_duplicate(engine, dataset):
    source = _source(dataset)
    first = ingest(engine, source, SPEC, models=FOUNDATION_MODELS)
    expected = sum(len(dataset.records[m]) for m in first.models)
    assert first.new_versions == expected

    second = ingest(engine, source, SPEC, models=FOUNDATION_MODELS)
    assert second.new_versions == 0
    assert all(m.deletions == 0 for m in second.models.values())
    assert (
        scalar(
            engine,
            "select count(*) from raw.source_record_version where source_instance = :i",
            i=source.source_instance,
        )
        == expected
    )
    with engine.connect() as c:
        assert verify_chain(c).valid


def test_changed_record_gets_a_new_version_and_history_is_kept(engine, dataset):
    source = _source(dataset)
    first = ingest(engine, source, SPEC, models=MODELS)
    line = source.dataset.find(
        "sale.order.line",
        order_id=[source.dataset.find("sale.order", name="BD/SO/DISC-001")[0]["id"], "BD/SO/DISC-001"],
    )[0]
    line["discount"] = 20.0
    line["write_date"] = "2026-09-01 08:00:00"

    second = ingest(engine, source, SPEC, models=MODELS)
    assert second.models["sale.order.line"].new_versions == 1
    assert (
        _payload_at(engine, source.source_instance, "sale.order.line", line["id"], first.batch_seq)["discount"] == 15.0
    )
    assert (
        _payload_at(engine, source.source_instance, "sale.order.line", line["id"], second.batch_seq)["discount"] == 20.0
    )


def test_deletion_is_detected_from_the_id_list_not_the_watermark(engine, dataset):
    source = _source(dataset)
    first = ingest(engine, source, SPEC, models=MODELS)
    removed = source.dataset.records["res.partner"].pop()

    second = ingest(engine, source, SPEC, models=MODELS)
    assert second.models["res.partner"].deletions == 1
    assert _payload_at(engine, source.source_instance, "res.partner", removed["id"], first.batch_seq) is not None
    assert _payload_at(engine, source.source_instance, "res.partner", removed["id"], second.batch_seq) is None

    source.dataset.records["res.partner"].append(removed)
    third = ingest(engine, source, SPEC, models=MODELS)
    assert third.models["res.partner"].new_versions == 1, "a reappearing record becomes a new version"


def test_late_commit_inside_the_overlap_window_is_captured(engine, dataset):
    source = _source(dataset)
    ingest(engine, source, SPEC, models=MODELS)
    watermark = scalar(
        engine,
        "select write_date from raw.watermark where source_instance = :i and source_model = 'sale.order'",
        i=source.source_instance,
    )
    late = copy.deepcopy(source.dataset.records["sale.order"][0])
    late["id"] = 99999
    late["name"] = "BD/SO/LATE"
    # Committed in Odoo before the last watermark but not visible to the previous extraction.
    late["write_date"] = (watermark - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
    source.dataset.records["sale.order"].append(late)

    result = ingest(engine, source, SPEC, models=MODELS, overlap_seconds=600)
    assert result.models["sale.order"].new_versions == 1


class _FailingSource(FixtureSource):
    fail_on = "sale.order.line"

    def iter_changed(self, model, fields, after, page_size=500):
        if model == self.fail_on:
            raise ConnectionError("source unavailable")
        yield from super().iter_changed(model, fields, after, page_size)


def test_failed_batch_is_recorded_and_the_next_run_resumes(engine, dataset):
    instance = f"fixture_test_{uuid.uuid4().hex[:8]}"
    failing = _FailingSource(copy.deepcopy(dataset), source_instance=instance)
    with pytest.raises(ConnectionError):
        ingest(engine, failing, SPEC, models=MODELS)
    assert scalar(engine, "select status from raw.ingestion_batch where source_instance = :i", i=instance) == "FAILED"
    assert scalar(engine, "select count(*) from raw.watermark where source_instance = :i", i=instance) == 2, (
        "models committed before the failure keep their watermark"
    )

    resumed = ingest(engine, FixtureSource(copy.deepcopy(dataset), source_instance=instance), SPEC, models=MODELS)
    assert resumed.models["res.partner"].new_versions == 0
    assert resumed.models["sale.order"].new_versions == 0
    assert resumed.models["sale.order.line"].new_versions == len(dataset.records["sale.order.line"])
    with engine.connect() as c:
        actions = (
            c.execute(
                sa.text(
                    "select action from audit.event where run_id in (select batch_id::text from raw.ingestion_batch"
                    " where source_instance = :i) order by sequence"
                ),
                {"i": instance},
            )
            .scalars()
            .all()
        )
    assert "ingestion.batch_failed" in actions and actions[-1] == "ingestion.batch_succeeded"
