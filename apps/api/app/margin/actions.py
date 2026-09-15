"""Controlled action: a review activity on the source document, created in Odoo only after a human approval.

Scope of the first write-back, deliberately narrow: one `mail.activity` on the sale order or the invoice behind the
exception, in the sandbox company, through `odoo_write_guard` and `OdooWriter`, idempotent by an external
identifier under module `benacta_demo`, fully recorded with the guard report and the response. Prices, invoices,
journal entries and contractual conditions are never changed by BENACTA.

In fixture mode there is no target system: the action is planned and recorded, never marked executed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from app.audit.log import append_event, canonical_json
from app.config import Mode, Settings
from app.connectors.guards import odoo_write_guard
from app.connectors.odoo import OdooJson2Client, OdooReader, OdooWriter
from app.margin.decisions import CaseNotFound, IllegalTransition, current_recommendation, load_case
from app.numbers import decimal_text
from app.planning.domain import Actor

XMLID_MODULE = "benacta_demo"
ACTION_KEY = "REVIEW_ACTIVITY"
ACTIVITY_TYPE_XMLID = ("mail", "mail_activity_data_todo")
TARGET_BY_SUBJECT = {"sale_order_line": "sale.order", "sale_order": "sale.order", "invoice_line": "account.move"}


class ActionRefused(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True)
class ActionPlan:
    case_ref: str
    case_id: uuid.UUID
    decision_id: uuid.UUID | None
    target_model: str
    target_res_id: int
    external_id: str
    vals: dict[str, Any]


@dataclass(frozen=True)
class ActionResult:
    action_id: uuid.UUID
    status: str
    detail: str
    response: dict[str, Any] | None = None


def _evaluation(conn: Connection, case: dict[str, Any]) -> dict[str, Any] | None:
    row = conn.execute(sa.text("""
        select e.*, f.sale_order_id as line_order_id from marts.fact_margin_rule_evaluation e
        left join marts.fact_sales_order_line f on f.snapshot_id = e.snapshot_id and f.sale_line_id = e.subject_id and e.subject_type = 'sale_order_line'
        where e.snapshot_id = :s and e.rule_id = :r and e.subject_type = :t and e.subject_id = :i"""),
        {"s": case["last_snapshot_id"], "r": case["rule_id"], "t": case["subject_type"], "i": case["subject_id"]}).mappings().first()
    return dict(row) if row else None


def plan_review_activity(conn: Connection, case_ref: str, *, deadline_days: int = 7) -> ActionPlan:
    case = load_case(conn, case_ref)
    evaluation = _evaluation(conn, case)
    if evaluation is None:
        raise CaseNotFound(f"case {case_ref} has no evaluation in its last snapshot")
    recommendation = current_recommendation(conn, case["case_id"])
    if recommendation is None:
        raise IllegalTransition(f"case {case_ref} has no recommendation")
    decision = conn.execute(sa.text("select decision_id from decision.case_decision where case_id = :c and decision_type = 'APPROVE'"
                                    " order by decided_at desc limit 1"), {"c": case["case_id"]}).scalar()
    if case["subject_type"] == "sale_order_line":
        res_id = evaluation["line_order_id"] or evaluation["sale_order_id"]
    elif case["subject_type"] == "sale_order":
        res_id = case["subject_id"]
    else:
        invoice = conn.execute(sa.text("select invoice_id from marts.fact_invoice_line where snapshot_id = :s and invoice_line_id = :i"),
                               {"s": case["last_snapshot_id"], "i": case["subject_id"]}).scalar()
        res_id = invoice
    evidence = evaluation["evidence"]
    amount = decimal_text(evaluation["adverse_exposure"]) or decimal_text(evaluation["potential_exposure"]) or "n/a"
    note = (
        f"<p><b>BENACTA Margin Control {case['case_ref']}</b> ({evaluation['classification']}, {evaluation['cause']})</p>"
        f"<p>{recommendation['title']}. {recommendation['rationale']}</p>"
        f"<p>Rule {evaluation['rule_id']} v{evaluation['rule_version']}: expected {decimal_text(evaluation['expected_amount'])}, "
        f"actual {decimal_text(evaluation['actual_amount'])}, adverse exposure {amount} {evaluation['currency_code']}. "
        f"Severity {evaluation['severity']}, confidence {evaluation['confidence']}.</p>"
        f"<p>Reason: {evidence.get('reason')}</p>"
        f"<p>Approved in BENACTA; evidence and lineage: case {case['case_ref']}, snapshot {case['last_snapshot_id']}.</p>"
    )
    vals = {
        "summary": f"BENACTA {case['case_ref']}: {recommendation['title']} ({amount} {evaluation['currency_code']})",
        "note": note,
        "date_deadline": str(date.today() + timedelta(days=deadline_days)),
        "res_model": TARGET_BY_SUBJECT[case["subject_type"]],
        "res_id": int(res_id),
    }
    return ActionPlan(case["case_ref"], case["case_id"], decision, vals["res_model"], int(res_id),
                      f"margin_action__{case['case_ref']}__{ACTION_KEY}", vals)


def _record(conn: Connection, plan: ActionPlan, actor: Actor, *, status: str, target_system: str, response: dict[str, Any] | None = None,
            guard: dict[str, Any] | None = None, error: str | None = None) -> uuid.UUID:
    action_id = uuid.uuid4()
    conn.execute(sa.text("""
        insert into decision.case_action (action_id, case_id, decision_id, action_key, target_system, target_model, target_res_id, external_id, status,
            request, response, guard, error, actor, executed_at)
        values (:a, :c, :d, :k, :ts, :tm, :ti, :x, :st, cast(:rq as jsonb), cast(:rs as jsonb), cast(:g as jsonb), :e, :u, :ex)"""),
        {"a": action_id, "c": plan.case_id, "d": plan.decision_id, "k": ACTION_KEY, "ts": target_system, "tm": plan.target_model, "ti": plan.target_res_id,
         "x": plan.external_id, "st": status, "rq": canonical_json(plan.vals), "rs": canonical_json(response) if response is not None else None,
         "g": canonical_json(guard) if guard is not None else None, "e": error, "u": actor.user_id,
         "ex": datetime.now(UTC) if status == "EXECUTED" else None})
    append_event(conn, actor=f"user:{actor.user_id}", action=f"action.{status.lower()}", object_type="exception_case", object_id=plan.case_ref,
                 correlation_id=str(plan.decision_id) if plan.decision_id else None,
                 payload={"action_id": str(action_id), "action_key": ACTION_KEY, "target_system": target_system, "target_model": plan.target_model,
                          "target_res_id": plan.target_res_id, "external_id": plan.external_id, "response": response, "guard": guard, "error": error})
    return action_id


def execute_review_activity(conn: Connection, settings: Settings, actor: Actor, case_ref: str, *, client: OdooJson2Client | None = None) -> ActionResult:
    """Execute the approved review activity. Refusals are recorded, never raised past the caller."""
    plan = plan_review_activity(conn, case_ref)
    case = load_case(conn, case_ref)
    target = "fixture" if settings.benacta_mode is Mode.FIXTURE else "odoo"
    executed = conn.execute(sa.text("select action_id from decision.case_action where external_id = :x and status = 'EXECUTED'"),
                            {"x": plan.external_id}).scalar()
    if executed is not None or case["status"] == "ACTIONED":
        action_id = _record(conn, plan, actor, status="REFUSED", target_system=target, error=f"already executed as action {executed}")
        return ActionResult(action_id, "REFUSED", "DUPLICATE")
    if case["status"] != "APPROVED":
        action_id = _record(conn, plan, actor, status="REFUSED", target_system=target,
                            error=f"case status {case['status']}: only an APPROVED case can be actioned")
        return ActionResult(action_id, "REFUSED", "NOT_APPROVED")
    if settings.benacta_mode is Mode.FIXTURE:
        action_id = _record(conn, plan, actor, status="PLANNED", target_system="fixture",
                            error="fixture mode has no target system; the request is recorded, nothing was executed")
        return ActionResult(action_id, "PLANNED", "FIXTURE_MODE", plan.vals)

    own_client = client is None
    client = client or OdooJson2Client.from_settings(settings, max_retries=0)
    try:
        reader = OdooReader(client)
        exists = bool(settings.odoo_sandbox_company) and bool(reader.search_count("res.company", [["name", "=", settings.odoo_sandbox_company]]))
        guard = odoo_write_guard(settings, sandbox_company_exists=exists)
        guard_report = {"guard": guard.guard, "allowed": guard.allowed, "checks": [{"name": c.name, "passed": c.passed} for c in guard.checks]}
        if not guard.allowed:
            failed = ", ".join(c.name for c in guard.checks if not c.passed)
            action_id = _record(conn, plan, actor, status="REFUSED", target_system="odoo", guard=guard_report, error=f"write guard blocked: {failed}")
            return ActionResult(action_id, "REFUSED", "GUARD_BLOCKED")
        if reader.search_count("ir.model.data", [["module", "=", XMLID_MODULE], ["name", "=", plan.external_id]]):
            action_id = _record(conn, plan, actor, status="REFUSED", target_system="odoo", guard=guard_report,
                                error="an activity with this external identifier already exists in Odoo")
            return ActionResult(action_id, "REFUSED", "DUPLICATE_IN_TARGET")
        try:
            activity_type = reader.search_read("ir.model.data", [["module", "=", ACTIVITY_TYPE_XMLID[0]], ["name", "=", ACTIVITY_TYPE_XMLID[1]]], ["res_id"])
            model_id = reader.search_read("ir.model", [["model", "=", plan.target_model]], ["id"])
            user = reader.search_read("res.users", [["login", "=", settings.odoo_username]], ["id"], limit=1)
            if not activity_type or not model_id:
                raise RuntimeError("activity type or target model not found in Odoo")
            writer = OdooWriter(client, guard)
            vals = {**plan.vals, "activity_type_id": activity_type[0]["res_id"], "res_model_id": model_id[0]["id"],
                    **({"user_id": user[0]["id"]} if user else {})}
            [activity_id] = writer.create("mail.activity", [vals])
            writer.create("ir.model.data", [{"module": XMLID_MODULE, "name": plan.external_id, "model": "mail.activity", "res_id": activity_id, "noupdate": True}])
        except Exception as exc:  # noqa: BLE001 - the failure is recorded, then re-raised for the caller
            action_id = _record(conn, plan, actor, status="FAILED", target_system="odoo", guard=guard_report, error=f"{type(exc).__name__}: {str(exc)[:300]}")
            return ActionResult(action_id, "FAILED", type(exc).__name__)
        response = {"mail_activity_id": activity_id, "external_id": f"{XMLID_MODULE}.{plan.external_id}"}
        action_id = _record(conn, plan, actor, status="EXECUTED", target_system="odoo", guard=guard_report, response=response)
        conn.execute(sa.text("update decision.exception_case set status = 'ACTIONED', actioned_at = now(), version = version + 1 where case_id = :c"),
                     {"c": plan.case_id})
        conn.execute(sa.text("update decision.case_impact set executed_at = now(), measured_at = now() where case_id = :c"), {"c": plan.case_id})
        return ActionResult(action_id, "EXECUTED", "REVIEW_ACTIVITY_CREATED", response)
    finally:
        if own_client:
            client.close()
