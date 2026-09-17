"""Decision state machine and recommendation templates, without a database."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.margin import decisions
from app.margin.decisions import IllegalTransition, NotAuthorised, build_recommendation, decide, parse_actor
from app.planning.domain import Role

APPROVER = parse_actor("FIN-01", ["finance_approver"])
ANALYST = parse_actor("AN-01", ["analyst"])
VIEWER = parse_actor("VW-01", ["viewer"])


def test_every_transition_lands_on_a_known_status():
    statuses = {"NEW", "OPEN", "UNDER_REVIEW", "EVIDENCE_REQUESTED", "DEFERRED", "APPROVED", "REJECTED", "ACTIONED", "CLOSED", "NO_LONGER_RAISED"}
    for decision_type, table in decisions.TRANSITIONS.items():
        for before, after in table.items():
            assert before in statuses and after in statuses, decision_type
    assert decisions.TRANSITIONS["APPROVE"]["NEW"] == "APPROVED" and "APPROVED" not in decisions.TRANSITIONS["APPROVE"]
    assert decisions.TRANSITIONS["REOPEN"]["REJECTED"] == "OPEN" and "ACTIONED" not in decisions.TRANSITIONS["REOPEN"]
    assert decisions.TRANSITIONS["CLOSE"]["ACTIONED"] == "CLOSED" and "NEW" not in decisions.TRANSITIONS["CLOSE"]


def test_preconditions_are_refused_before_any_database_access():
    with pytest.raises(NotAuthorised):
        decide(None, VIEWER, "MC-000001", "COMMENT", comment="hi")
    with pytest.raises(NotAuthorised):
        decide(None, ANALYST, "MC-000001", "APPROVE")
    with pytest.raises(IllegalTransition):
        decide(None, APPROVER, "MC-000001", "REJECT")  # no reason
    with pytest.raises(IllegalTransition):
        decide(None, ANALYST, "MC-000001", "ASSIGN")  # no assignee
    with pytest.raises(IllegalTransition):
        decide(None, ANALYST, "MC-000001", "DEFER", reason="later")  # no date
    with pytest.raises(IllegalTransition):
        decide(None, ANALYST, "MC-000001", "ESCALATE")


def test_parse_actor_rejects_unknown_roles_and_keeps_company_scope():
    actor = parse_actor("X", ["finance_approver", "analyst"], [1, 2])
    assert actor.roles == frozenset({Role.FINANCE_APPROVER, Role.ANALYST}) and actor.company_ids == frozenset({1, 2})
    with pytest.raises(ValueError):
        parse_actor("X", ["superuser"])


def _evaluation(**overrides) -> dict:
    base = {"cause": "DISCOUNT_ABOVE_CAP", "classification": "CONFIRMED_LEAKAGE", "adverse_exposure": Decimal("1000.00"),
            "potential_exposure": None, "exposure_stage": "INVOICED", "rule_id": "DISCOUNT_CAP", "rule_version": 1,
            "subject_type": "sale_order_line", "subject_id": 7}
    base.update(overrides)
    return base


def test_recommendation_estimates_recovery_only_for_billing_exposure():
    case = {"case_id": uuid.uuid4(), "case_ref": "MC-000001"}
    billing = build_recommendation(case, _evaluation(), snapshot_id=uuid.uuid4(), thresholds_version="demo/v1")
    assert billing["estimated_recovery"] == Decimal("1000.00") and billing["recovery_basis"] == "BILLING_EXPOSURE"
    assert billing["requires_role"] == "finance_approver" and billing["action_key"] == "REVIEW_ACTIVITY" and billing["payload_hash"]
    cost = build_recommendation(case, _evaluation(cause="PURCHASE_PRICE_VARIANCE", rule_id="COST_REFERENCE_VARIANCE", adverse_exposure=Decimal("800")),
                                snapshot_id=uuid.uuid4(), thresholds_version="demo/v1")
    assert cost["estimated_recovery"] is None and cost["recovery_basis"] == "NOT_RECEIVABLE"
    unknown = build_recommendation(case, _evaluation(cause="POLICY_EXPIRED", classification="INSUFFICIENT_EVIDENCE", adverse_exposure=None,
                                                     potential_exposure=Decimal("244.80")), snapshot_id=uuid.uuid4(), thresholds_version="demo/v1")
    assert unknown["estimated_recovery"] is None and unknown["recovery_basis"] == "UNKNOWN"
    assert unknown["expected_impact"]["potential_exposure"] == "244.80"


def test_recommendation_hash_changes_with_the_exposure_not_with_the_snapshot():
    case = {"case_id": uuid.uuid4(), "case_ref": "MC-000001"}
    a = build_recommendation(case, _evaluation(), snapshot_id=uuid.uuid4(), thresholds_version="demo/v1")
    b = build_recommendation(case, _evaluation(), snapshot_id=uuid.uuid4(), thresholds_version="demo/v1")
    c = build_recommendation(case, _evaluation(adverse_exposure=Decimal("900")), snapshot_id=uuid.uuid4(), thresholds_version="demo/v1")
    assert a["payload_hash"] == b["payload_hash"] != c["payload_hash"]


def test_every_template_cause_names_a_basis():
    for cause, template in decisions.TEMPLATES.items():
        assert template["basis"] in {"BILLING_EXPOSURE", "NOT_RECEIVABLE", "UNKNOWN"}, cause
        assert template["title"] and template["rationale"]
