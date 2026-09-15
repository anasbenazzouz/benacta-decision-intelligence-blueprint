"""Append-only, hash-chained audit journal.

Each event hash covers the previous hash and a canonical serialisation of the
event, so any later edit, deletion or reordering breaks verification. Appends
are serialised with a transaction-level advisory lock. A trigger refuses
UPDATE, DELETE and TRUNCATE for the application role.

This is tamper-evident, not immutable: a database superuser can disable the
trigger and rewrite the chain. Independent signed checkpoints and WORM storage
are documented as hardening, not deployed.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection

GENESIS_HASH = "0" * 64
_APPEND_LOCK_KEY = 0x42454E41  # arbitrary constant shared by every appender
FORBIDDEN_PAYLOAD_KEYS = frozenset({"password", "api_key", "secret", "token", "authorization"})


def _default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    raise TypeError(f"not serialisable in audit payload: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_default)


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _check_payload(payload: dict[str, Any]) -> None:
    stack = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            leaked = {k for k in item if str(k).lower() in FORBIDDEN_PAYLOAD_KEYS}
            if leaked:
                raise ValueError(f"audit payload must not carry secrets: {sorted(leaked)}")
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)


def _event_body(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "sequence": row["sequence"],
        "event_id": str(row["event_id"]),
        # Normalised to UTC: the session time zone must not change the hash.
        "occurred_at": row["occurred_at"].astimezone(UTC).isoformat(),
        "actor": row["actor"],
        "action": row["action"],
        "object_type": row["object_type"],
        "object_id": row["object_id"],
        "correlation_id": row["correlation_id"],
        "run_id": row["run_id"],
        "payload": row["payload"],
    }


def _chain_hash(prev_hash: str, body: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + canonical_json(body)).encode("utf-8")).hexdigest()


def append_event(
    conn: Connection,
    *,
    actor: str,
    action: str,
    object_type: str,
    object_id: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
    run_id: str | None = None,
) -> str:
    """Append within the caller's transaction. Returns the event hash."""
    _check_payload(payload)
    payload = json.loads(canonical_json(payload))
    conn.execute(sa.text("select pg_advisory_xact_lock(:k)"), {"k": _APPEND_LOCK_KEY})
    last = conn.execute(sa.text("select sequence, event_hash from audit.event order by sequence desc limit 1")).first()
    row = {
        "sequence": (last.sequence + 1) if last else 1,
        "event_id": uuid.uuid4(),
        # Server clock, truncated to microseconds so the stored value round-trips exactly.
        "occurred_at": conn.execute(sa.text("select date_trunc('microseconds', clock_timestamp())")).scalar(),
        "actor": actor,
        "action": action,
        "object_type": object_type,
        "object_id": object_id,
        "correlation_id": correlation_id,
        "run_id": run_id,
        "payload": payload,
    }
    prev_hash = last.event_hash if last else GENESIS_HASH
    event_hash = _chain_hash(prev_hash, _event_body(row))
    conn.execute(
        sa.text(
            "insert into audit.event (sequence, event_id, occurred_at, actor, action, object_type, object_id,"
            " correlation_id, run_id, payload, prev_hash, event_hash) values (:sequence, :event_id, :occurred_at,"
            " :actor, :action, :object_type, :object_id, :correlation_id, :run_id, cast(:payload as jsonb),"
            " :prev_hash, :event_hash)"
        ),
        {**row, "payload": canonical_json(payload), "prev_hash": prev_hash, "event_hash": event_hash},
    )
    return event_hash


@dataclass(frozen=True)
class VerificationResult:
    valid: bool
    events_checked: int
    first_broken_sequence: int | None
    reason: str | None


def verify_chain(conn: Connection) -> VerificationResult:
    prev_hash = GENESIS_HASH
    expected_sequence = 1
    count = 0
    rows = conn.execute(sa.text("select * from audit.event order by sequence")).mappings()
    for row in rows:
        count += 1
        if row["sequence"] != expected_sequence:
            return VerificationResult(False, count, row["sequence"], "sequence gap or reordering")
        if row["prev_hash"] != prev_hash:
            return VerificationResult(False, count, row["sequence"], "previous hash mismatch")
        if _chain_hash(prev_hash, _event_body(dict(row))) != row["event_hash"]:
            return VerificationResult(False, count, row["sequence"], "event content altered")
        prev_hash = row["event_hash"]
        expected_sequence += 1
    return VerificationResult(True, count, None, None)


def export_jsonl(conn: Connection) -> str:
    rows = conn.execute(sa.text("select * from audit.event order by sequence")).mappings()
    lines = []
    for row in rows:
        lines.append(
            canonical_json({**_event_body(dict(row)), "prev_hash": row["prev_hash"], "event_hash": row["event_hash"]})
        )
    return "\n".join(lines) + ("\n" if lines else "")
