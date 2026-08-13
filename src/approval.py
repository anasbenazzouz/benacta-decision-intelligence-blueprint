"""
BENACTA Human Control.

AI drafts. Humans approve.

A small, strict state machine standing between a generated interpretation and
anything anyone reads. Illegal transitions raise rather than being coerced: a
draft cannot become approved without a named reviewer passing through review,
and a revision request must say what needs revising.

Rejection is a designed path, not an error case.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable


class ReviewState(str, Enum):
    DRAFT = "DRAFT"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    APPROVED = "APPROVED"
    REVISION_REQUESTED = "REVISION_REQUESTED"


#: What an executive sees (BENACTA UI vocabulary).
REVIEW_STATE_LABELS: dict[ReviewState, str] = {
    ReviewState.DRAFT: "AI DRAFT",
    ReviewState.AWAITING_REVIEW: "CONTROLLER REVIEW",
    ReviewState.APPROVED: "APPROVED",
    ReviewState.REVISION_REQUESTED: "REVISION REQUESTED",
}

_ALLOWED: dict[ReviewState, frozenset[ReviewState]] = {
    ReviewState.DRAFT: frozenset({ReviewState.AWAITING_REVIEW}),
    ReviewState.AWAITING_REVIEW: frozenset(
        {ReviewState.APPROVED, ReviewState.REVISION_REQUESTED}
    ),
    ReviewState.REVISION_REQUESTED: frozenset({ReviewState.AWAITING_REVIEW}),
    ReviewState.APPROVED: frozenset(),
}


class InvalidTransition(RuntimeError):
    """An attempt to move the review to a state it cannot reach from here."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ReviewEvent:
    from_state: ReviewState
    to_state: ReviewState
    actor: str
    comment: str | None
    timestamp: datetime


class ReviewRecord:
    """The review lifecycle of one drafted interpretation."""

    def __init__(
        self,
        subject_id: str,
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.subject_id = subject_id
        self._state = ReviewState.DRAFT
        self._history: list[ReviewEvent] = []
        self._clock = clock

    # -- inspection ------------------------------------------------------- #

    @property
    def state(self) -> ReviewState:
        return self._state

    @property
    def label(self) -> str:
        return REVIEW_STATE_LABELS[self._state]

    @property
    def history(self) -> tuple[ReviewEvent, ...]:
        return tuple(self._history)

    @property
    def is_approved(self) -> bool:
        return self._state is ReviewState.APPROVED

    @property
    def reviewer(self) -> str | None:
        """Who last acted on the review the accountable human."""
        for event in reversed(self._history):
            if event.to_state in (ReviewState.APPROVED, ReviewState.REVISION_REQUESTED):
                return event.actor
        return None

    # -- transitions ------------------------------------------------------ #

    def submit_for_review(self, actor: str = "system") -> ReviewEvent:
        return self._transition(ReviewState.AWAITING_REVIEW, actor, None)

    def approve(self, reviewer: str, comment: str | None = None) -> ReviewEvent:
        if not reviewer or not reviewer.strip():
            raise InvalidTransition("Approval requires a named reviewer.")
        return self._transition(ReviewState.APPROVED, reviewer, comment)

    def request_revision(self, reviewer: str, comment: str) -> ReviewEvent:
        if not reviewer or not reviewer.strip():
            raise InvalidTransition("A revision request requires a named reviewer.")
        if not comment or not comment.strip():
            raise InvalidTransition("A revision request must say what needs revising.")
        return self._transition(ReviewState.REVISION_REQUESTED, reviewer, comment)

    def resubmit(self, actor: str = "system") -> ReviewEvent:
        """Send a redrafted interpretation back for review."""
        return self._transition(ReviewState.AWAITING_REVIEW, actor, None)

    def _transition(
        self, to_state: ReviewState, actor: str, comment: str | None
    ) -> ReviewEvent:
        if to_state not in _ALLOWED[self._state]:
            raise InvalidTransition(
                f"Cannot move review from {self._state.value} to {to_state.value}."
            )
        event = ReviewEvent(
            from_state=self._state,
            to_state=to_state,
            actor=actor,
            comment=comment,
            timestamp=self._clock(),
        )
        self._state = to_state
        self._history.append(event)
        return event
