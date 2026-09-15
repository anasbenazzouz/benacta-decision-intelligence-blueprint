"""Operational commands for the analytical foundation."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import date

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from app.audit.log import export_jsonl, verify_chain
from app.config import REPO_ROOT, Mode, Settings
from app.connectors.odoo import OdooJson2Client, OdooReader
from app.controlling.seed_plans import seed_plans
from app.db import migrate
from app.db.engine import analytics_engine
from app.fixtures.demo_dataset import DEFAULT_ANCHOR, build_demo_dataset
from app.fixtures.projects_dataset import extend_with_projects
from app.ingestion.runner import BatchResult, ingest
from app.ingestion.sources import FixtureSource, OdooSource, Source
from app.marts.build import build_marts
from app.marts.reconcile import margin_basis, reconcile
from app.ops.discover_odoo import load_spec

# Source instance written by `benacta seed-fixtures` (dataset demo_v2 = demo_v1 + projects).
FIXTURE_SOURCE_INSTANCE = "fixture_demo_v2"


def run_migrations(settings: Settings) -> str | None:
    engine = analytics_engine(settings)
    try:
        migrate.upgrade(engine)
        return migrate.current_revision(engine)
    finally:
        engine.dispose()


@contextmanager
def configured_source(settings: Settings, anchor: date = DEFAULT_ANCHOR):
    if settings.benacta_mode is Mode.FIXTURE:
        yield FixtureSource(extend_with_projects(build_demo_dataset(anchor=anchor)))
        return
    with OdooJson2Client.from_settings(settings) as client:
        yield OdooSource(OdooReader(client), settings.odoo_source_instance)


def latest_snapshot(engine: Engine, source_instance: str) -> uuid.UUID:
    with engine.connect() as conn:
        snapshot = conn.execute(
            sa.text(
                "select batch_id from raw.ingestion_batch where source_instance = :i and status = 'SUCCEEDED'"
                " order by batch_seq desc limit 1"
            ),
            {"i": source_instance},
        ).scalar()
    if snapshot is None:
        raise RuntimeError(f"no succeeded ingestion batch for {source_instance}; run ingest first")
    return snapshot


def _print_batch(batch: BatchResult) -> None:
    print(f"batch {batch.batch_id} (seq {batch.batch_seq}) {batch.status}")
    for model, result in batch.models.items():
        missing = f" missing={','.join(result.missing_fields)}" if result.missing_fields else ""
        print(
            f"  {model:22} extracted={result.extracted:5} new={result.new_versions:5} "
            f"unchanged={result.unchanged:5} deleted={result.deletions}{missing}"
        )


def _print_reconciliation(engine: Engine, source: Source, snapshot: uuid.UUID) -> None:
    rows = reconcile(engine, source, snapshot)
    summary: dict[tuple[str, str], int] = {}
    for row in rows:
        summary[(row.check_id, row.status)] = summary.get((row.check_id, row.status), 0) + 1
    print(f"reconciliation ({source.independence}):")
    for (check, status), count in sorted(summary.items()):
        print(f"  {check:15} {status:12} {count} period(s)")
    print(f"margin basis: {margin_basis(engine, snapshot)}")


def run_pipeline(settings: Settings, *, steps: tuple[str, ...], anchor: date = DEFAULT_ANCHOR) -> int:
    engine = analytics_engine(settings)
    try:
        with configured_source(settings, anchor) as source:
            snapshot = None
            if "ingest" in steps:
                batch = ingest(engine, source, load_spec())
                _print_batch(batch)
                snapshot = batch.batch_id
            if "marts" in steps:
                snapshot = snapshot or latest_snapshot(engine, source.source_instance)
                stats = build_marts(engine, snapshot)
                print("marts " + ", ".join(f"{table}={count}" for table, count in stats.items() if count))
            if "plans" in steps and isinstance(source, FixtureSource) and source.dataset.plans:
                snapshot = snapshot or latest_snapshot(engine, source.source_instance)
                with engine.begin() as conn:
                    seeded = seed_plans(conn, source.dataset.plans, snapshot, source.source_instance)
                print(f"plans created={len(seeded.created)} skipped={len(seeded.skipped)} (already present)")
            if "reconcile" in steps:
                snapshot = snapshot or latest_snapshot(engine, source.source_instance)
                _print_reconciliation(engine, source, snapshot)
            if "reference" in steps:
                snapshot = snapshot or latest_snapshot(engine, source.source_instance)
                _load_reference(engine, source, snapshot)
            if "exceptions" in steps:
                snapshot = snapshot or latest_snapshot(engine, source.source_instance)
                _run_exceptions(engine, snapshot)
            if "documents" in steps:
                _register_documents(engine)
    finally:
        engine.dispose()
    return 0


def _load_reference(engine: Engine, source: Source, snapshot: uuid.UUID) -> None:
    """Fixture terms in fixture mode; the policy register file in connected mode."""
    from app.margin import reference

    with engine.connect() as conn:
        companies = conn.execute(
            sa.text("select company_id from marts.dim_company where snapshot_id = :s order by company_id"), {"s": snapshot}
        ).scalars().all()
    if isinstance(source, FixtureSource):
        rows = reference.rows_from_terms(
            source.dataset.terms, owner="Sales finance controller (synthetic)", source=f"fixture {source.dataset.dataset_id} terms"
        )
        kind, ref = "FIXTURE_TERMS", source.dataset.dataset_id
    elif reference.REGISTER_PATH.exists():
        _raw, rows = reference.load_register()
        kind, ref = "POLICY_REGISTER", str(reference.REGISTER_PATH.relative_to(REPO_ROOT))
    else:
        print(f"reference: no policy register at {reference.REGISTER_PATH.relative_to(REPO_ROOT)}; rules will report insufficient evidence")
        return
    with engine.begin() as conn:
        for company_id in companies:
            reference.store_reference(conn, rows, source_instance=source.source_instance, company_id=company_id, source_kind=kind, source_ref=ref)
    print(f"reference ({kind}): " + ", ".join(f"{k}={v}" for k, v in rows.counts().items()))


def _register_documents(engine: Engine) -> None:
    from app.margin.documents import register_corpus

    with engine.begin() as conn:
        summary = register_corpus(conn)
    print(f"documents: {len(summary['indexed'])} governed document(s) indexed" + (f", {len(summary['refused'])} refused" if summary['refused'] else ""))
    for refusal in summary["refused"]:
        print(f"  refused {refusal['file']}: {refusal['reason']}")


def _run_exceptions(engine: Engine, snapshot: uuid.UUID) -> None:
    from app.margin.engine import run_engine

    run = run_engine(engine, snapshot)
    summary = run.summary()
    classes = ", ".join(f"{k}={v}" for k, v in summary["by_classification"].items())
    print(f"margin exceptions: {summary['evaluations']} evaluations ({classes}); cases created={summary['cases_created']}"
          f" updated={summary['cases_updated']} resolved={summary['cases_resolved']}; periods={summary['periods']}; thresholds {summary['thresholds']}")


def run_verify_audit(settings: Settings, export: bool) -> int:
    engine = analytics_engine(settings)
    try:
        with engine.connect() as conn:
            result = verify_chain(conn)
            if export:
                path = REPO_ROOT / ".benacta" / "exports" / "audit.jsonl"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(export_jsonl(conn), encoding="utf-8")
                print(f"exported {path.relative_to(REPO_ROOT)}")
    finally:
        engine.dispose()
    print(
        f"audit chain {'VALID' if result.valid else 'BROKEN'}: {result.events_checked} event(s) checked"
        + (f", first broken sequence {result.first_broken_sequence} ({result.reason})" if not result.valid else "")
    )
    return 0 if result.valid else 1
