"""
BENACTA — Decision and Action Layer.

Insight without action is incomplete.

A reviewed issue does not end at commentary: it acquires an owner, a next step
and a status. This is the smallest thing that honestly demonstrates
INSIGHT → DECISION → ACTION without pretending to be a workflow engine.

An issue cannot be marked ACTION_REQUIRED without an owner and a next step —
an action nobody owns is not an action.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Callable, Iterable


class DecisionStatus(str, Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    CLOSED = "CLOSED"


DECISION_STATUS_LABELS: dict[DecisionStatus, str] = {
    DecisionStatus.OPEN: "OPEN",
    DecisionStatus.UNDER_REVIEW: "UNDER REVIEW",
    DecisionStatus.APPROVED: "APPROVED",
    DecisionStatus.ACTION_REQUIRED: "ACTION REQUIRED",
    DecisionStatus.CLOSED: "CLOSED",
}

_ALLOWED: dict[DecisionStatus, frozenset[DecisionStatus]] = {
    DecisionStatus.OPEN: frozenset({DecisionStatus.UNDER_REVIEW}),
    DecisionStatus.UNDER_REVIEW: frozenset(
        {DecisionStatus.APPROVED, DecisionStatus.OPEN}
    ),
    DecisionStatus.APPROVED: frozenset(
        {DecisionStatus.ACTION_REQUIRED, DecisionStatus.CLOSED}
    ),
    DecisionStatus.ACTION_REQUIRED: frozenset({DecisionStatus.CLOSED}),
    DecisionStatus.CLOSED: frozenset(),
}


class InvalidTransition(RuntimeError):
    """An attempt to move an issue to a status it cannot reach from here."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class DecisionEvent:
    from_status: DecisionStatus
    to_status: DecisionStatus
    actor: str
    note: str | None
    timestamp: datetime


@dataclass
class DecisionIssue:
    """One thing that needs a decision, and what happened to it."""

    issue_id: str
    title: str
    fact_id: str
    rule_id: str | None = None
    severity: str | None = None
    status: DecisionStatus = DecisionStatus.OPEN
    owner: str | None = None
    next_step: str | None = None
    due_date: date | None = None
    history: list[DecisionEvent] = field(default_factory=list)
    clock: Callable[[], datetime] = _utc_now

    @property
    def status_label(self) -> str:
        return DECISION_STATUS_LABELS[self.status]

    @property
    def is_actionable(self) -> bool:
        return self.status is DecisionStatus.ACTION_REQUIRED

    def advance(
        self,
        to_status: DecisionStatus,
        *,
        actor: str,
        note: str | None = None,
        owner: str | None = None,
        next_step: str | None = None,
        due_date: date | None = None,
    ) -> DecisionEvent:
        if to_status not in _ALLOWED[self.status]:
            raise InvalidTransition(
                f"Cannot move issue from {self.status.value} to {to_status.value}."
            )

        owner = owner or self.owner
        next_step = next_step or self.next_step

        if to_status is DecisionStatus.ACTION_REQUIRED and not (owner and next_step):
            raise InvalidTransition(
                "An action requires both an owner and a next step."
            )

        event = DecisionEvent(
            from_status=self.status,
            to_status=to_status,
            actor=actor,
            note=note,
            timestamp=self.clock(),
        )
        self.status = to_status
        self.owner = owner
        self.next_step = next_step
        if due_date is not None:
            self.due_date = due_date
        self.history.append(event)
        return event


class DecisionLog:
    """The register of issues raised in a review cycle."""

    def __init__(self) -> None:
        self._issues: dict[str, DecisionIssue] = {}

    def add(self, issue: DecisionIssue) -> DecisionIssue:
        if issue.issue_id in self._issues:
            raise ValueError(f"Issue {issue.issue_id!r} already exists.")
        self._issues[issue.issue_id] = issue
        return issue

    def get(self, issue_id: str) -> DecisionIssue:
        return self._issues[issue_id]

    @property
    def issues(self) -> tuple[DecisionIssue, ...]:
        return tuple(self._issues.values())

    def with_status(self, *statuses: DecisionStatus) -> tuple[DecisionIssue, ...]:
        wanted = set(statuses)
        return tuple(issue for issue in self._issues.values() if issue.status in wanted)

    @property
    def open_actions(self) -> tuple[DecisionIssue, ...]:
        return self.with_status(DecisionStatus.ACTION_REQUIRED)

    def __len__(self) -> int:
        return len(self._issues)

    def __iter__(self) -> Iterable[DecisionIssue]:
        return iter(self._issues.values())
