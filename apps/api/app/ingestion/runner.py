"""Idempotent batch ingestion into the raw layer.

- Every observed record is hashed; a new version is written only when the hash
  changes, so replaying a batch adds nothing.
- Extraction restarts from the stored (write_date, id) watermark minus an
  overlap window, which re-reads late commits; the hash makes the overlap free.
- Deletions are found by comparing the source id list with current records.
- Each model commits separately. A failed model leaves its watermark
  untouched, so the next run resumes from the last committed point.
- Batch start, per-model results and batch end are appended to the audit chain.

Limit: the Odoo API offers no cross-call snapshot. A batch is consistent per
record, and changes committed during extraction are caught by the next overlap.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine

from app.audit.log import append_event, content_hash
from app.ingestion.sources import ODOO_DATETIME, Source, Watermark, parse_odoo_datetime

FOUNDATION_MODELS = (
    "res.company",
    "res.currency",
    "res.currency.rate",
    "uom.uom",
    "account.account",
    "res.partner",
    "product.category",
    "product.template",
    "product.product",
    "sale.order",
    "sale.order.line",
    "stock.picking",
    "stock.move",
    "purchase.order",
    "purchase.order.line",
    "account.move",
    "account.move.line",
)
# Dataset demo_v2 and a live company with projects, HR and analytic time entries.
PROJECT_MODELS = (
    "account.payment",
    "res.users",
    "account.analytic.account",
    "project.tags",
    "project.project",
    "project.task",
    "project.milestone",
    "hr.department",
    "hr.job",
    "resource.calendar",
    "hr.employee",
    "hr.skill",
    "hr.employee.skill",
    "account.analytic.line",
)
INGESTED_MODELS = FOUNDATION_MODELS + PROJECT_MODELS
DEFAULT_OVERLAP_SECONDS = 300
DELETION_HASH = "deleted".ljust(64, "0")


@dataclass
class ModelResult:
    model: str
    extracted: int = 0
    new_versions: int = 0
    unchanged: int = 0
    deletions: int = 0
    missing_fields: list[str] = field(default_factory=list)
    watermark: Watermark | None = None


@dataclass
class BatchResult:
    batch_id: uuid.UUID
    batch_seq: int
    status: str
    models: dict[str, ModelResult]

    @property
    def new_versions(self) -> int:
        return sum(m.new_versions for m in self.models.values())


def mapped_fields(spec: dict[str, Any], model: str) -> list[str]:
    return list(spec["models"][model]["fields"])


def ingest(
    engine: Engine,
    source: Source,
    spec: dict[str, Any],
    *,
    models: tuple[str, ...] = INGESTED_MODELS,
    overlap_seconds: int = DEFAULT_OVERLAP_SECONDS,
    actor: str = "service:ingestion",
) -> BatchResult:
    batch_id = uuid.uuid4()
    with engine.begin() as conn:
        batch_seq = conn.execute(
            sa.text(
                "insert into raw.ingestion_batch (batch_id, source_instance, source_kind, status, overlap_seconds, models)"
                " values (:b, :i, :k, 'RUNNING', :o, :m) returning batch_seq"
            ),
            {
                "b": batch_id,
                "i": source.source_instance,
                "k": source.source_kind,
                "o": overlap_seconds,
                "m": list(models),
            },
        ).scalar_one()
        append_event(
            conn,
            actor=actor,
            action="ingestion.batch_started",
            object_type="ingestion_batch",
            object_id=str(batch_id),
            run_id=str(batch_id),
            payload={
                "source_instance": source.source_instance,
                "source_kind": source.source_kind,
                "models": list(models),
                "overlap_seconds": overlap_seconds,
            },
        )

    results: dict[str, ModelResult] = {}
    current_model = None
    try:
        for model in models:
            current_model = model
            with engine.begin() as conn:
                results[model] = _ingest_model(conn, source, spec, model, batch_id, batch_seq, overlap_seconds)
                append_event(
                    conn,
                    actor=actor,
                    action="ingestion.model_committed",
                    object_type="ingestion_batch",
                    object_id=str(batch_id),
                    run_id=str(batch_id),
                    payload={"model": model, **_result_payload(results[model])},
                )
    except Exception as exc:
        with engine.begin() as conn:
            message = f"{type(exc).__name__} on {current_model}: {str(exc)[:300]}"
            conn.execute(
                sa.text(
                    "update raw.ingestion_batch set status = 'FAILED', finished_at = now(), error = :e where batch_id = :b"
                ),
                {"e": message, "b": batch_id},
            )
            append_event(
                conn,
                actor=actor,
                action="ingestion.batch_failed",
                object_type="ingestion_batch",
                object_id=str(batch_id),
                run_id=str(batch_id),
                payload={"model": current_model, "error_type": type(exc).__name__},
            )
        raise

    stats = {model: _result_payload(result) for model, result in results.items()}
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "update raw.ingestion_batch set status = 'SUCCEEDED', finished_at = now(), stats = cast(:s as jsonb)"
                " where batch_id = :b"
            ),
            {"s": json.dumps(stats), "b": batch_id},
        )
        append_event(
            conn,
            actor=actor,
            action="ingestion.batch_succeeded",
            object_type="ingestion_batch",
            object_id=str(batch_id),
            run_id=str(batch_id),
            payload={"stats_hash": content_hash(stats), "new_versions": sum(s["new_versions"] for s in stats.values())},
        )
    return BatchResult(batch_id, batch_seq, "SUCCEEDED", results)


def _result_payload(result: ModelResult) -> dict[str, Any]:
    return {
        "extracted": result.extracted,
        "new_versions": result.new_versions,
        "unchanged": result.unchanged,
        "deletions": result.deletions,
        "missing_fields": result.missing_fields,
    }


def _ingest_model(
    conn: Connection,
    source: Source,
    spec: dict[str, Any],
    model: str,
    batch_id: uuid.UUID,
    batch_seq: int,
    overlap_seconds: int,
) -> ModelResult:
    result = ModelResult(model)
    wanted = mapped_fields(spec, model)
    available = source.available_fields(model)
    fields = [name for name in wanted if name in available]
    result.missing_fields = sorted(set(wanted) - set(fields))
    if "write_date" not in fields or "id" not in fields:
        raise RuntimeError(f"{model} cannot be ingested incrementally without id and write_date")

    stored = conn.execute(
        sa.text("select write_date, last_id from raw.watermark where source_instance = :i and source_model = :m"),
        {"i": source.source_instance, "m": model},
    ).first()
    after = None
    if stored is not None:
        start = stored.write_date - timedelta(seconds=overlap_seconds)
        after = Watermark(start.strftime(ODOO_DATETIME), 0)

    current = {
        row.source_id: row
        for row in conn.execute(
            sa.text(
                "select source_id, version_no, record_hash, is_deleted from raw.source_record_current"
                " where source_instance = :i and source_model = :m"
            ),
            {"i": source.source_instance, "m": model},
        )
    }
    extracted_at = datetime.now(UTC)
    versions: list[dict[str, Any]] = []
    unchanged_ids: list[int] = []
    high = Watermark(stored.write_date.strftime(ODOO_DATETIME), stored.last_id) if stored else None

    for record in source.iter_changed(model, fields, after):
        result.extracted += 1
        record_hash = content_hash(record)
        existing = current.get(record["id"])
        mark = Watermark(record["write_date"], record["id"])
        high = mark if high is None or mark > high else high
        if existing is not None and existing.record_hash == record_hash and not existing.is_deleted:
            unchanged_ids.append(record["id"])
            continue
        versions.append(_version_row(source, model, record, record_hash, existing, batch_id, batch_seq, extracted_at))

    live_ids = source.all_ids(model)
    for source_id, existing in current.items():
        if not existing.is_deleted and source_id not in live_ids:
            versions.append(
                {
                    "i": source.source_instance,
                    "m": model,
                    "sid": source_id,
                    "v": existing.version_no + 1,
                    "c": None,
                    "wd": None,
                    "h": DELETION_HASH,
                    "del": True,
                    "p": None,
                    "b": batch_id,
                    "bs": batch_seq,
                    "x": extracted_at,
                }
            )
            result.deletions += 1

    if versions:
        conn.execute(
            sa.text(
                "insert into raw.source_record_version (source_instance, source_model, source_id, version_no, company_id,"
                " source_write_date, record_hash, is_deletion, payload, batch_id, batch_seq, extracted_at)"
                " values (:i, :m, :sid, :v, :c, :wd, :h, :del, cast(:p as jsonb), :b, :bs, :x)"
            ),
            versions,
        )
        conn.execute(
            sa.text(
                "insert into raw.source_record_current (source_instance, source_model, source_id, version_id, version_no,"
                " record_hash, is_deleted, last_seen_batch_id)"
                " select distinct on (source_id) source_instance, source_model, source_id, version_id, version_no,"
                " record_hash, is_deletion, batch_id from raw.source_record_version"
                " where batch_id = :b and source_instance = :i and source_model = :m order by source_id, version_no desc"
                " on conflict (source_instance, source_model, source_id) do update set version_id = excluded.version_id,"
                " version_no = excluded.version_no, record_hash = excluded.record_hash, is_deleted = excluded.is_deleted,"
                " last_seen_batch_id = excluded.last_seen_batch_id"
            ),
            {"b": batch_id, "i": source.source_instance, "m": model},
        )
    if unchanged_ids:
        conn.execute(
            sa.text(
                "update raw.source_record_current set last_seen_batch_id = :b"
                " where source_instance = :i and source_model = :m and source_id = any(:ids)"
            ),
            {"b": batch_id, "i": source.source_instance, "m": model, "ids": unchanged_ids},
        )
    result.new_versions = len(versions) - result.deletions
    result.unchanged = len(unchanged_ids)
    result.watermark = high

    if high is not None:
        conn.execute(
            sa.text(
                "insert into raw.watermark (source_instance, source_model, write_date, last_id, batch_id)"
                " values (:i, :m, :wd, :id, :b) on conflict (source_instance, source_model) do update set"
                " write_date = excluded.write_date, last_id = excluded.last_id, batch_id = excluded.batch_id,"
                " updated_at = now()"
            ),
            {
                "i": source.source_instance,
                "m": model,
                "wd": parse_odoo_datetime(high.write_date),
                "id": high.record_id,
                "b": batch_id,
            },
        )
    conn.execute(
        sa.text(
            "insert into raw.batch_model_state (batch_id, source_model, status, extracted, new_versions, unchanged,"
            " deletions, missing_fields, watermark_write_date, watermark_id)"
            " values (:b, :m, 'SUCCEEDED', :e, :n, :u, :d, :mf, :wd, :wid)"
        ),
        {
            "b": batch_id,
            "m": model,
            "e": result.extracted,
            "n": result.new_versions,
            "u": result.unchanged,
            "d": result.deletions,
            "mf": result.missing_fields,
            "wd": parse_odoo_datetime(high.write_date) if high else None,
            "wid": high.record_id if high else None,
        },
    )
    return result


def _version_row(source, model, record, record_hash, existing, batch_id, batch_seq, extracted_at) -> dict[str, Any]:
    company = record.get("company_id")
    company_id = (
        int(company[0]) if isinstance(company, list) and company else (record["id"] if model == "res.company" else None)
    )
    return {
        "i": source.source_instance,
        "m": model,
        "sid": record["id"],
        "v": (existing.version_no + 1) if existing else 1,
        "c": company_id,
        "wd": parse_odoo_datetime(record["write_date"]),
        "h": record_hash,
        "del": False,
        "p": json.dumps(record),
        "b": batch_id,
        "bs": batch_seq,
        "x": extracted_at,
    }
