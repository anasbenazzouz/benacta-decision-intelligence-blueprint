"""Human decisions on exception cases: recommendations, the state machine, and the append-only decision record.

A recommendation is a proposal for a named person, never a decision. The state machine is explicit and small;
illegal transitions, missing reasons, missing roles and stale versions are refused with typed errors that the CLI
and the API map to exit codes and HTTP statuses. Every decision is appended to the audit chain.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from app.audit.log import append_event, canonical_json, content_hash
from app.numbers import decimal_text
from app.planning.domain import Actor, Role

NON_TERMINAL = ("NEW", "OPEN", "UNDER_REVIEW", "EVIDENCE_REQUESTED", "DEFERRED")
# decision type -> {status before: status after}
TRANSITIONS: dict[str, dict[str, str]] = {
    "ASSIGN": {"NEW": "OPEN", "OPEN": "OPEN", "UNDER_REVIEW": "UNDER_REVIEW", "EVIDENCE_REQUESTED": "EVIDENCE_REQUESTED",
               "DEFERRED": "DEFERRED", "APPROVED": "APPROVED"},
    "REQUEST_EVIDENCE": {"NEW": "EVIDENCE_REQUESTED", "OPEN": "EVIDENCE_REQUESTED", "UNDER_REVIEW": "EVIDENCE_REQUESTED"},
    "DEFER": {"NEW": "DEFERRED", "OPEN": "DEFERRED", "UNDER_REVIEW": "DEFERRED", "EVIDENCE_REQUESTED": "DEFERRED"},
    "APPROVE": {s: "APPROVED" for s in NON_TERMINAL},
    "REJECT": {s: "REJECTED" for s in NON_TERMINAL},
    "REOPEN": {"REJECTED": "OPEN", "DEFERRED": "OPEN", "EVIDENCE_REQUESTED": "OPEN", "CLOSED": "OPEN", "NO_LONGER_RAISED": "OPEN"},
    "COMMENT": {s: s for s in (*NON_TERMINAL, "APPROVED", "ACTIONED", "REJECTED")},
    "CLOSE": {"ACTIONED": "CLOSED", "APPROVED": "CLOSED", "REJECTED": "CLOSED"},
}
REASON_REQUIRED = frozenset({"REJECT", "DEFER", "REQUEST_EVIDENCE", "REOPEN"})
APPROVER_ONLY = frozenset({"APPROVE", "REJECT", "CLOSE"})
ACTING_ROLES = frozenset({Role.ANALYST, Role.PROJECT_CONTROLLER, Role.FINANCE_APPROVER, Role.ADMIN})
RECOMMENDATION_STATUS_AFTER = {"APPROVE": "APPROVED", "REJECT": "REJECTED", "REQUEST_EVIDENCE": "EVIDENCE_REQUESTED",
                               "DEFER": "DEFERRED", "REOPEN": "PENDING_REVIEW"}

# Deterministic recommendation per cause. `action_key` names the controlled action that executes once approved.
TEMPLATES: dict[str, dict[str, str]] = {
    "DISCOUNT_ABOVE_CAP": {"title": "Recover the discount above policy or obtain a derogation",
                           "rationale": "The discount exceeds the applicable policy cap without a valid derogation. Either a finance approver "
                                        "grants a dated derogation, or a complementary invoice recovers the excess.",
                           "basis": "BILLING_EXPOSURE"},
    "PRICE_BELOW_CONTRACT": {"title": "Invoice the difference to the contract price or record the amendment",
                             "rationale": "The unit price is below the contract price valid on the order date. Recover the difference or "
                                          "record the signed amendment that justifies the price.", "basis": "BILLING_EXPOSURE"},
    "PRICE_BELOW_CUSTOMER_PRICELIST": {"title": "Correct the price against the customer's price list",
                                       "rationale": "The unit price is below the price list assigned to the customer.", "basis": "BILLING_EXPOSURE"},
    "PRICE_BELOW_LIST_PRICE": {"title": "Confirm or correct the price below list",
                               "rationale": "No contract or customer price list explains a price below the product list price.", "basis": "BILLING_EXPOSURE"},
    "PRICE_BELOW_HISTORICAL": {"title": "Review the price against comparable recent orders",
                               "rationale": "The price is below the comparable historical baseline; the evidence is probable, not contractual.",
                               "basis": "BILLING_EXPOSURE"},
    "PRICELIST_MISMATCH": {"title": "Re-price the order on the customer's price list",
                           "rationale": "The order applied a price list that is not the customer's; that list explains the low price.",
                           "basis": "BILLING_EXPOSURE"},
    "FREIGHT_NOT_INVOICED": {"title": "Issue the contractual freight invoice",
                             "rationale": "Goods are fully delivered and invoiced under a rebill clause and no freight was invoiced.",
                             "basis": "BILLING_EXPOSURE"},
    "FREIGHT_PARTIALLY_INVOICED": {"title": "Invoice the remaining contractual freight",
                                   "rationale": "Freight was invoiced below the contractual amount.", "basis": "BILLING_EXPOSURE"},
    "PURCHASE_PRICE_VARIANCE": {"title": "Review the supplier price against the frozen reference",
                                "rationale": "Realised cost exceeds the frozen reference; this is a procurement action, not a customer recovery.",
                                "basis": "NOT_RECEIVABLE"},
    "MISSING_COST": {"title": "Post or attribute the missing receipt cost", "rationale": "The margin of this line cannot be relied on without cost.",
                     "basis": "UNKNOWN"},
    "POLICY_EXPIRED": {"title": "Renew the expired discount policy, then reassess", "rationale": "No valid policy covers the order date.", "basis": "UNKNOWN"},
    "NO_POLICY": {"title": "Record the applicable discount policy", "rationale": "No policy covers this customer or segment.", "basis": "UNKNOWN"},
    "POLICY_CONFLICT": {"title": "Resolve the conflicting discount policies", "rationale": "Two policies of equal priority give different caps.",
                        "basis": "UNKNOWN"},
    "NO_COST_REFERENCE": {"title": "Freeze a reference cost for the product", "rationale": "No reference cost is valid on the order date.", "basis": "UNKNOWN"},
    "NO_PRICE_BASELINE": {"title": "Record a contract price or price list for the product", "rationale": "No defensible price baseline exists.",
                          "basis": "UNKNOWN"},
    "UNRESOLVED_UNIT_OR_PRODUCT": {"title": "Correct the product master", "rationale": "Quantities, prices and costs of this line cannot be checked until the "
                                  "unit of measure is resolved on the product.", "basis": "UNKNOWN"},
    "MISSING_PRODUCT": {"title": "Attach a product to the order line", "rationale": "The line has no product to check against terms.", "basis": "UNKNOWN"},
    "INVOICE_WITHOUT_ORDER": {"title": "Link the invoice to its order or document the exception",
                              "rationale": "Posted revenue with no order behind it cannot be checked against price, discount or freight terms.",
                              "basis": "UNKNOWN"},
}
DEFAULT_TEMPLATE = {"title": "Review the evidence and decide", "rationale": "No deterministic template exists for this cause.", "basis": "UNKNOWN"}
EXECUTABLE_ACTION = "REVIEW_ACTIVITY"


class DecisionError(RuntimeError):
    http_status = 422


class StaleCase(DecisionError):
    http_status = 409


class IllegalTransition(DecisionError):
    http_status = 422


class NotAuthorised(DecisionError):
    http_status = 403


class CaseNotFound(DecisionError):
    http_status = 404


@dataclass(frozen=True)
class DecisionResult:
    decision_id: uuid.UUID
    case_ref: str
    decision_type: str
    status_before: str
    status_after: str
    version: int


def _row(conn: Connection, sql: str, **params: Any) -> dict[str, Any] | None:
    row = conn.execute(sa.text(sql), params).mappings().first()
    return dict(row) if row else None


def load_case(conn: Connection, case_ref: str) -> dict[str, Any]:
    case = _row(conn, "select * from decision.exception_case where case_ref = :r or cast(case_id as text) = :r for update", r=case_ref)
    if case is None:
        raise CaseNotFound(f"no case {case_ref}")
    return case


def current_recommendation(conn: Connection, case_id: uuid.UUID) -> dict[str, Any] | None:
    return _row(conn, "select * from decision.margin_recommendation where case_id = :c and status <> 'SUPERSEDED' order by version desc limit 1", c=case_id)


# --------------------------------------------------------------------------- recommendations
def build_recommendation(case: dict[str, Any], evaluation: dict[str, Any], *, snapshot_id: uuid.UUID, thresholds_version: str) -> dict[str, Any]:
    template = TEMPLATES.get(evaluation["cause"], DEFAULT_TEMPLATE)
    basis = template["basis"]
    adverse = evaluation.get("adverse_exposure")
    estimated = adverse if basis == "BILLING_EXPOSURE" and adverse else None
    impact = {
        "estimated_recovery": decimal_text(estimated),
        "recovery_basis": basis,
        "adverse_exposure": decimal_text(adverse),
        "potential_exposure": decimal_text(evaluation.get("potential_exposure")),
        "exposure_stage": evaluation.get("exposure_stage"),
        "note": {"BILLING_EXPOSURE": "recoverable through a complementary invoice or a corrected order",
                 "NOT_RECEIVABLE": "a cost variance is not recovered from the customer; the benefit is future purchase cost",
                 "UNKNOWN": "no recovery can be estimated until the evidence is complete"}[basis],
    }
    evidence_refs = [f"rule:{evaluation['rule_id']}:v{evaluation['rule_version']}", f"subject:{evaluation['subject_type']}:{evaluation['subject_id']}",
                     f"snapshot:{snapshot_id}"]
    payload = {"case_id": str(case["case_id"]), "cause": evaluation["cause"], "classification": evaluation["classification"],
               "adverse_exposure": decimal_text(adverse), "potential_exposure": decimal_text(evaluation.get("potential_exposure")),
               "rule_version": evaluation["rule_version"], "thresholds_version": thresholds_version, "template": template["title"]}
    return {
        "action_key": EXECUTABLE_ACTION,
        "title": template["title"],
        "rationale": template["rationale"],
        "requires_role": Role.FINANCE_APPROVER.value,
        "estimated_recovery": estimated,
        "recovery_basis": basis,
        "expected_impact": impact,
        "evidence_refs": evidence_refs,
        "snapshot_id": snapshot_id,
        "rule_version": evaluation["rule_version"],
        "thresholds_version": thresholds_version,
        "payload_hash": content_hash(payload),
    }


def ensure_recommendation(conn: Connection, case: dict[str, Any], evaluation: dict[str, Any], *, snapshot_id: uuid.UUID,
                          thresholds_version: str, actor: str = "service:margin-engine") -> str:
    """Create the first recommendation, or a new version when the evidence changed while the case is still open.

    Returns CREATED, SUPERSEDED, UNCHANGED or FROZEN (a decided case keeps the recommendation it was decided on).
    """
    proposal = build_recommendation(case, evaluation, snapshot_id=snapshot_id, thresholds_version=thresholds_version)
    current = current_recommendation(conn, case["case_id"])
    if current is not None and current["payload_hash"] == proposal["payload_hash"]:
        return "UNCHANGED"
    if current is not None and case["status"] not in NON_TERMINAL:
        return "FROZEN"
    version = 1
    outcome = "CREATED"
    if current is not None:
        conn.execute(sa.text("update decision.margin_recommendation set status = 'SUPERSEDED' where recommendation_id = :r"),
                     {"r": current["recommendation_id"]})
        version = current["version"] + 1
        outcome = "SUPERSEDED"
    recommendation_id = uuid.uuid4()
    conn.execute(sa.text("""
        insert into decision.margin_recommendation (recommendation_id, case_id, version, source, action_key, title, rationale, requires_role,
            estimated_recovery, recovery_basis, expected_impact, evidence_refs, status, snapshot_id, rule_version, thresholds_version, payload_hash)
        values (:r, :c, :v, 'DETERMINISTIC_TEMPLATE', :k, :t, :ra, :ro, :e, :b, cast(:i as jsonb), cast(:ev as jsonb), 'PENDING_REVIEW', :s, :rv, :tv, :h)"""),
        {"r": recommendation_id, "c": case["case_id"], "v": version, "k": proposal["action_key"], "t": proposal["title"], "ra": proposal["rationale"],
         "ro": proposal["requires_role"], "e": proposal["estimated_recovery"], "b": proposal["recovery_basis"],
         "i": canonical_json(proposal["expected_impact"]), "ev": canonical_json(proposal["evidence_refs"]), "s": snapshot_id,
         "rv": proposal["rule_version"], "tv": thresholds_version, "h": proposal["payload_hash"]})
    conn.execute(sa.text("update decision.exception_case set estimated_recovery = :e where case_id = :c"),
                 {"e": proposal["estimated_recovery"], "c": case["case_id"]})
    append_event(conn, actor=actor, action="recommendation.proposed", object_type="exception_case", object_id=case["case_ref"],
                 payload={"recommendation_id": str(recommendation_id), "version": version, "outcome": outcome, "action_key": proposal["action_key"],
                          "estimated_recovery": decimal_text(proposal["estimated_recovery"]), "recovery_basis": proposal["recovery_basis"],
                          "payload_hash": proposal["payload_hash"]})
    return outcome


# --------------------------------------------------------------------------- decisions
def decide(
    conn: Connection,
    actor: Actor,
    case_ref: str,
    decision_type: str,
    *,
    expected_version: int | None = None,
    reason: str | None = None,
    comment: str | None = None,
    assigned_to: str | None = None,
    defer_until: date | None = None,
) -> DecisionResult:
    if decision_type not in TRANSITIONS:
        raise IllegalTransition(f"unknown decision type {decision_type}")
    if not (actor.roles & ACTING_ROLES):
        raise NotAuthorised(f"{actor.user_id} has no role allowed to act on a case")
    if decision_type in APPROVER_ONLY and not actor.can(Role.FINANCE_APPROVER) and not actor.can(Role.ADMIN):
        raise NotAuthorised(f"{decision_type} requires the finance_approver role")
    if decision_type in REASON_REQUIRED and not (reason and reason.strip()):
        raise IllegalTransition(f"{decision_type} requires a reason")
    if decision_type == "ASSIGN" and not assigned_to:
        raise IllegalTransition("ASSIGN requires assigned_to")
    if decision_type == "DEFER" and defer_until is None:
        raise IllegalTransition("DEFER requires defer_until")

    case = load_case(conn, case_ref)
    if case["company_id"] not in actor.company_ids:
        raise NotAuthorised(f"{actor.user_id} may not act on company {case['company_id']}")
    if expected_version is not None and expected_version != case["version"]:
        raise StaleCase(f"case {case['case_ref']} is at version {case['version']}, decision was taken on version {expected_version}")
    status_before = case["status"]
    if status_before not in TRANSITIONS[decision_type]:
        raise IllegalTransition(f"{decision_type} is not allowed on a case in status {status_before}")
    status_after = TRANSITIONS[decision_type][status_before]
    recommendation = current_recommendation(conn, case["case_id"])
    if decision_type == "APPROVE" and recommendation is None:
        raise IllegalTransition("nothing to approve: the case has no pending recommendation")
    if decision_type == "APPROVE" and recommendation["requires_role"] == Role.FINANCE_APPROVER.value and not (
        actor.can(Role.FINANCE_APPROVER) or actor.can(Role.ADMIN)
    ):
        raise NotAuthorised("the recommendation requires the finance_approver role")

    version_after = case["version"] + 1
    now = datetime.now(UTC)
    decision_id = uuid.uuid4()
    conn.execute(sa.text("""
        insert into decision.case_decision (decision_id, case_id, recommendation_id, decision_type, actor, actor_roles, status_before, status_after,
            case_version_before, case_version_after, reason, comment, assigned_to, defer_until, decided_at)
        values (:d, :c, :r, :t, :a, :roles, :sb, :sa, :vb, :va, :re, :co, :as, :du, :now)"""),
        {"d": decision_id, "c": case["case_id"], "r": recommendation["recommendation_id"] if recommendation else None, "t": decision_type,
         "a": actor.user_id, "roles": sorted(r.value for r in actor.roles), "sb": status_before, "sa": status_after, "vb": case["version"],
         "va": version_after, "re": reason, "co": comment, "as": assigned_to, "du": defer_until, "now": now})
    updates = {"status": status_after, "version": version_after}
    if decision_type == "ASSIGN":
        updates["owner"] = assigned_to
        updates["assigned_to"] = assigned_to
    if decision_type == "DEFER":
        updates["defer_until"] = defer_until
    if decision_type in ("APPROVE", "REJECT"):
        updates["decided_at"] = now
    if decision_type == "REOPEN":
        updates["decided_at"] = None
        updates["actioned_at"] = None
        updates["defer_until"] = None
    sets = ", ".join(f"{k} = :{k}" for k in updates)
    conn.execute(sa.text(f"update decision.exception_case set {sets} where case_id = :c"), {**updates, "c": case["case_id"]})  # noqa: S608 keys fixed above
    if recommendation is not None and decision_type in RECOMMENDATION_STATUS_AFTER:
        conn.execute(sa.text("update decision.margin_recommendation set status = :s where recommendation_id = :r"),
                     {"s": RECOMMENDATION_STATUS_AFTER[decision_type], "r": recommendation["recommendation_id"]})
    if decision_type == "APPROVE":
        conn.execute(sa.text("""
            insert into decision.case_impact (case_id, snapshot_id, estimated_recovery, approved_at, realisation_status, reason)
            values (:c, :s, :e, :now, :st, :re)
            on conflict (case_id) do update set estimated_recovery = excluded.estimated_recovery, approved_at = excluded.approved_at,
                realisation_status = excluded.realisation_status, reason = excluded.reason, measured_at = now()"""),
            {"c": case["case_id"], "s": recommendation["snapshot_id"], "e": recommendation["estimated_recovery"], "now": now,
             "st": "NOT_MEASURED" if recommendation["recovery_basis"] == "BILLING_EXPOSURE" else "NOT_MEASURABLE",
             "re": "no posted document after the decision yet" if recommendation["recovery_basis"] == "BILLING_EXPOSURE"
             else "recovery is not receivable from the customer for this cause"})
    append_event(conn, actor=f"user:{actor.user_id}", action=f"decision.{decision_type.lower()}", object_type="exception_case",
                 object_id=case["case_ref"], correlation_id=str(decision_id),
                 payload={"decision_id": str(decision_id), "status_before": status_before, "status_after": status_after,
                          "version_before": case["version"], "version_after": version_after, "roles": sorted(r.value for r in actor.roles),
                          "reason": reason, "comment": comment, "assigned_to": assigned_to,
                          "defer_until": None if defer_until is None else str(defer_until),
                          "recommendation_id": str(recommendation["recommendation_id"]) if recommendation else None,
                          "estimated_recovery": decimal_text(Decimal(str(recommendation["estimated_recovery"]))) if recommendation and recommendation["estimated_recovery"] is not None else None})
    return DecisionResult(decision_id, case["case_ref"], decision_type, status_before, status_after, version_after)


def parse_actor(user_id: str, roles: list[str], company_ids: list[int] | None = None) -> Actor:
    """Pilot identity for the CLI and the API: a named user and declared roles. Not an authentication system."""
    parsed = frozenset(Role(r.strip().lower()) for r in roles if r.strip())
    return Actor(user_id, parsed, frozenset(company_ids or [1]))
