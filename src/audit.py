"""
BENACTA Audit Trail. Every step logged.

An append-only record of what the system did and why, so that any statement in
the cockpit can be walked backwards to the rows, the rule, the evidence, the
mode of interpretation, and the human who approved it.

This is what makes the architecture inspectable rather than merely asserted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable


class AuditStep(str, Enum):
    SOURCE_LOADED = "SOURCE_LOADED"
    FACTS_COMPUTED = "FACTS_COMPUTED"
    CONTROLS_EVALUATED = "CONTROLS_EVALUATED"
    CONTEXT_RETRIEVED = "CONTEXT_RETRIEVED"
    #: Variance attributed to source records distinct from retrieving context.
    SOURCE_ATTRIBUTED = "SOURCE_ATTRIBUTED"
    INTERPRETATION_DRAFTED = "INTERPRETATION_DRAFTED"
    REVIEW_SUBMITTED = "REVIEW_SUBMITTED"
    REVIEW_DECIDED = "REVIEW_DECIDED"
    DECISION_RECORDED = "DECISION_RECORDED"
    ACTION_ASSIGNED = "ACTION_ASSIGNED"
    ISSUE_CLOSED = "ISSUE_CLOSED"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]
    return value


@dataclass(frozen=True)
class AuditRecord:
    sequence: int
    step: AuditStep
    timestamp: datetime
    issue_id: str | None = None
    refs: dict[str, Any] = field(default_factory=dict)
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "step": self.step.value,
            "timestamp": self.timestamp.isoformat(),
            "issue_id": self.issue_id,
            "refs": _jsonable(self.refs),
            "detail": _jsonable(self.detail),
        }


class AuditTrail:
    """Append-only, in-session, exportable."""

    def __init__(self, *, clock: Callable[[], datetime] = _utc_now) -> None:
        self._records: list[AuditRecord] = []
        self._clock = clock

    def record(
        self,
        step: AuditStep,
        *,
        issue_id: str | None = None,
        refs: dict[str, Any] | None = None,
        **detail: Any,
    ) -> AuditRecord:
        record = AuditRecord(
            sequence=len(self._records) + 1,
            step=step,
            timestamp=self._clock(),
            issue_id=issue_id,
            refs=dict(refs or {}),
            detail=dict(detail),
        )
        self._records.append(record)
        return record

    @property
    def records(self) -> tuple[AuditRecord, ...]:
        return tuple(self._records)

    def for_issue(self, issue_id: str) -> tuple[AuditRecord, ...]:
        """The full lineage of one decision, in order."""
        return tuple(r for r in self._records if r.issue_id == issue_id)

    def steps_taken(self) -> tuple[AuditStep, ...]:
        return tuple(record.step for record in self._records)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps([r.to_dict() for r in self._records], indent=indent, ensure_ascii=False)

    def export(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
        return path

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self) -> Iterable[AuditRecord]:
        return iter(self._records)
