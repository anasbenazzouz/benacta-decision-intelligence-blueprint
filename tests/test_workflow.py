"""
Human control, decision/action, and the audit trail.

State transitions must be deterministic and refuse the illegal ones: the claim
"a controller remains accountable" is only true if the machine cannot publish
without one.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from src.approval import (
    InvalidTransition as ReviewTransitionError,
    ReviewRecord,
    ReviewState,
)
from src.audit import AuditStep, AuditTrail
from src.commentary import DemoProvider, InterpretationMode
from src.decision_log import (
    DecisionIssue,
    DecisionLog,
    DecisionStatus,
    InvalidTransition as DecisionTransitionError,
)
from src.pipeline import build_session

FIXED_TIME = datetime(2026, 8, 3, 9, 30, tzinfo=timezone.utc)


def fixed_clock():
    return FIXED_TIME


@pytest.fixture(scope="module")
def session():
    """A full pipeline run with the deterministic provider."""
    return build_session(provider=DemoProvider())


# --------------------------------------------------------------------------- #
# Review state machine
# --------------------------------------------------------------------------- #


def test_review_starts_as_a_draft():
    review = ReviewRecord("ISS-01")
    assert review.state is ReviewState.DRAFT
    assert review.label == "AI DRAFT"
    assert not review.is_approved


def test_the_happy_path_is_draft_review_approved():
    review = ReviewRecord("ISS-01", clock=fixed_clock)
    review.submit_for_review()
    assert review.state is ReviewState.AWAITING_REVIEW
    assert review.label == "CONTROLLER REVIEW"

    review.approve("A. Controller", "Consistent with the milestone register.")
    assert review.is_approved
    assert review.reviewer == "A. Controller"
    assert [e.to_state for e in review.history] == [
        ReviewState.AWAITING_REVIEW,
        ReviewState.APPROVED,
    ]
    assert all(event.timestamp == FIXED_TIME for event in review.history)


def test_a_draft_cannot_be_approved_without_review():
    review = ReviewRecord("ISS-01")
    with pytest.raises(ReviewTransitionError, match="Cannot move review"):
        review.approve("A. Controller")


def test_an_approved_commentary_is_final():
    review = ReviewRecord("ISS-01")
    review.submit_for_review()
    review.approve("A. Controller")
    with pytest.raises(ReviewTransitionError):
        review.request_revision("A. Controller", "Actually, no.")


def test_approval_requires_a_named_reviewer():
    review = ReviewRecord("ISS-01")
    review.submit_for_review()
    with pytest.raises(ReviewTransitionError, match="named reviewer"):
        review.approve("   ")


def test_a_revision_request_must_say_what_needs_revising():
    review = ReviewRecord("ISS-01")
    review.submit_for_review()
    with pytest.raises(ReviewTransitionError, match="what needs revising"):
        review.request_revision("A. Controller", "")


def test_rejection_is_a_designed_path_back_to_review():
    review = ReviewRecord("ISS-01")
    review.submit_for_review()
    review.request_revision("A. Controller", "Quantify the August recovery.")
    assert review.state is ReviewState.REVISION_REQUESTED
    assert review.label == "REVISION REQUESTED"

    review.resubmit()
    review.approve("A. Controller")
    assert review.is_approved
    assert len(review.history) == 4


# --------------------------------------------------------------------------- #
# Decision and action
# --------------------------------------------------------------------------- #


def test_issue_lifecycle_reaches_an_owned_action():
    issue = DecisionIssue(
        issue_id="ISS-01", title="Revenue below budget", fact_id="METRIC:revenue:-:2026-07"
    )
    assert issue.status is DecisionStatus.OPEN

    issue.advance(DecisionStatus.UNDER_REVIEW, actor="system")
    issue.advance(DecisionStatus.APPROVED, actor="A. Controller")
    issue.advance(
        DecisionStatus.ACTION_REQUIRED,
        actor="A. Controller",
        owner="Project Finance",
        next_step="Review milestone recognition.",
        due_date=date(2026, 8, 14),
    )

    assert issue.is_actionable
    assert issue.status_label == "ACTION REQUIRED"
    assert issue.owner == "Project Finance"
    assert issue.due_date == date(2026, 8, 14)


def test_an_action_without_an_owner_is_not_an_action():
    issue = DecisionIssue(issue_id="ISS-01", title="x", fact_id="f")
    issue.advance(DecisionStatus.UNDER_REVIEW, actor="system")
    issue.advance(DecisionStatus.APPROVED, actor="A. Controller")

    with pytest.raises(DecisionTransitionError, match="owner and a next step"):
        issue.advance(DecisionStatus.ACTION_REQUIRED, actor="A. Controller")


def test_illegal_status_jumps_are_refused():
    issue = DecisionIssue(issue_id="ISS-01", title="x", fact_id="f")
    with pytest.raises(DecisionTransitionError, match="Cannot move issue"):
        issue.advance(DecisionStatus.CLOSED, actor="someone")


def test_a_closed_issue_stays_closed():
    issue = DecisionIssue(issue_id="ISS-01", title="x", fact_id="f")
    issue.advance(DecisionStatus.UNDER_REVIEW, actor="system")
    issue.advance(DecisionStatus.APPROVED, actor="A. Controller")
    issue.advance(DecisionStatus.CLOSED, actor="A. Controller")
    with pytest.raises(DecisionTransitionError):
        issue.advance(DecisionStatus.ACTION_REQUIRED, actor="A. Controller")


def test_decision_log_registers_and_filters_issues():
    log = DecisionLog()
    log.add(DecisionIssue(issue_id="ISS-01", title="a", fact_id="f1"))
    log.add(DecisionIssue(issue_id="ISS-02", title="b", fact_id="f2"))

    assert len(log) == 2
    with pytest.raises(ValueError):
        log.add(DecisionIssue(issue_id="ISS-01", title="dup", fact_id="f3"))
    assert log.with_status(DecisionStatus.OPEN) == log.issues
    assert log.open_actions == ()


# --------------------------------------------------------------------------- #
# Audit trail
# --------------------------------------------------------------------------- #


def test_audit_records_are_sequential_and_serialisable():
    trail = AuditTrail(clock=fixed_clock)
    trail.record(AuditStep.FACTS_COMPUTED, refs={"calc_version": "1.0.0"}, fact_count=56)
    trail.record(AuditStep.REVIEW_DECIDED, issue_id="ISS-01", state=ReviewState.APPROVED)

    assert [r.sequence for r in trail.records] == [1, 2]
    assert trail.for_issue("ISS-01")[0].step is AuditStep.REVIEW_DECIDED

    payload = trail.to_json()
    assert '"APPROVED"' in payload  # enums serialise by value
    assert FIXED_TIME.isoformat() in payload


def test_audit_export_writes_json(tmp_path):
    trail = AuditTrail()
    trail.record(AuditStep.SOURCE_LOADED, refs={"source_files": ["actuals.csv"]})
    path = trail.export(tmp_path / "nested" / "audit.json")
    assert path.exists()
    assert "actuals.csv" in path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# The assembled loop
# --------------------------------------------------------------------------- #


def test_session_builds_the_attention_list_with_drafts(session):
    assert len(session.items) == 5
    assert session.items[0].alert.metric == "revenue"
    for item in session.items:
        assert item.commentary.mode is InterpretationMode.DEMO
        assert item.review.state is ReviewState.DRAFT
        assert item.issue.status is DecisionStatus.OPEN


def test_session_records_the_pipeline_in_the_audit_trail(session):
    steps = set(session.audit.steps_taken())
    assert {
        AuditStep.SOURCE_LOADED,
        AuditStep.FACTS_COMPUTED,
        AuditStep.CONTROLS_EVALUATED,
        AuditStep.CONTEXT_RETRIEVED,
        AuditStep.INTERPRETATION_DRAFTED,
        AuditStep.DECISION_RECORDED,
    } <= steps


def test_lower_ranked_alerts_are_reported_not_silently_dropped(session):
    assert len(session.alerts) > len(session.items)
    notes = [r.detail.get("note", "") for r in session.audit.records]
    assert any("were not interpreted" in note for note in notes)


def test_full_loop_from_truth_to_audited_action():
    """TRUTH → CONTEXT → INTERPRETATION → REVIEW → DECISION → ACTION → AUDIT."""
    session = build_session(provider=DemoProvider())
    issue_id = session.items[0].issue_id

    session.submit_for_review(issue_id)
    session.approve(issue_id, "A. Controller", "Consistent with the milestone register.")
    session.assign_action(
        issue_id,
        actor="A. Controller",
        owner="Project Finance",
        next_step="Review milestone recognition for the rescheduled milestones.",
        due_date=date(2026, 8, 14),
    )

    item = session.item(issue_id)
    assert item.review.is_approved
    assert item.review.reviewer == "A. Controller"
    assert item.issue.is_actionable
    assert session.log.open_actions == (item.issue,)

    lineage = session.audit.for_issue(issue_id)
    steps = [record.step for record in lineage]
    assert steps == [
        AuditStep.CONTEXT_RETRIEVED,
        AuditStep.SOURCE_ATTRIBUTED,
        AuditStep.INTERPRETATION_DRAFTED,
        AuditStep.DECISION_RECORDED,
        AuditStep.REVIEW_SUBMITTED,
        AuditStep.REVIEW_DECIDED,
        AuditStep.ACTION_ASSIGNED,
    ]
    assert all(record.refs["fact_id"] == item.fact.fact_id for record in lineage)


def test_revision_path_is_auditable():
    session = build_session(provider=DemoProvider())
    issue_id = session.items[0].issue_id

    session.submit_for_review(issue_id)
    session.request_revision(issue_id, "A. Controller", "Quantify the August recovery.")
    assert session.item(issue_id).review.state is ReviewState.REVISION_REQUESTED

    session.resubmit(issue_id)
    session.approve(issue_id, "A. Controller")
    assert session.item(issue_id).review.is_approved

    comments = [r.detail.get("comment") for r in session.audit.for_issue(issue_id)]
    assert "Quantify the August recovery." in comments


def test_nothing_is_approved_before_a_human_acts(session):
    assert not any(item.review.is_approved for item in session.items)
    assert session.log.open_actions == ()
