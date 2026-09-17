"""Decisions, controlled action and impact on the fixture dataset.

The Odoo side of the action is exercised through a fake JSON-2 transport: the guard, the idempotency and the
recorded request are real; no Odoo instance is touched.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal

import httpx
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from app import main
from app.audit.log import verify_chain
from app.connectors.odoo import OdooJson2Client
from app.fixtures.demo_dataset import build_demo_dataset
from app.ingestion.runner import FOUNDATION_MODELS, ingest
from app.ingestion.sources import FixtureSource
from app.margin import reference
from app.margin.actions import execute_review_activity, plan_review_activity
from app.margin.decisions import IllegalTransition, NotAuthorised, StaleCase, decide, parse_actor
from app.margin.engine import run_engine
from app.margin.service import case_audit, exception_case, exception_queue, impact_register, margin_overview
from app.marts.build import build_marts
from app.marts.reconcile import reconcile
from app.ops.discover_odoo import load_spec
from tests.conftest import make_settings

APPROVER = parse_actor("FIN-01", ["finance_approver"])
ANALYST = parse_actor("AN-01", ["analyst"])
TODAY = date.today()


@pytest.fixture(scope="module")
def built(engine):
    dataset = build_demo_dataset()
    source = FixtureSource(dataset, source_instance=f"fixture_workflow_{uuid.uuid4().hex[:8]}")
    batch = ingest(engine, source, load_spec(), models=FOUNDATION_MODELS)
    build_marts(engine, batch.batch_id)
    reconcile(engine, source, batch.batch_id)
    with engine.begin() as conn:
        reference.store_reference(conn, reference.rows_from_terms(dataset.terms, owner="test", source="fixture"),
                                  source_instance=source.source_instance, company_id=1, source_kind="FIXTURE_TERMS", source_ref="demo_v1")
    run = run_engine(engine, batch.batch_id)
    return {"engine": engine, "snapshot": batch.batch_id, "source": source, "run": run}


def case_ref(built, subject_prefix: str) -> str:
    with built["engine"].connect() as conn:
        return next(q["case_ref"] for q in exception_queue(conn, built["snapshot"]) if q["subject_ref"].startswith(subject_prefix))


def case_row(built, ref: str) -> dict:
    with built["engine"].connect() as c:
        return dict(c.execute(sa.text("select * from decision.exception_case where case_ref = :r"), {"r": ref}).mappings().one())


def test_every_case_carries_one_pending_recommendation(built):
    run = built["run"]
    assert run.recommendations == {"CREATED": 11}
    with built["engine"].connect() as conn:
        queue = exception_queue(conn, built["snapshot"])
        disc = exception_case(conn, built["snapshot"], case_ref(built, "BD/SO/DISC-001"))
        cost = exception_case(conn, built["snapshot"], case_ref(built, "BD/SO/COST-001"))
    assert all(q["recommendation_status"] == "PENDING_REVIEW" for q in queue)
    assert disc["recommendation"]["estimated_recovery"] == "1000.00" and disc["recommendation"]["recovery_basis"] == "BILLING_EXPOSURE"
    assert disc["recommendation"]["source"] == "DETERMINISTIC_TEMPLATE" and disc["recommendation"]["status"] == "PENDING_REVIEW"
    assert cost["recommendation"]["estimated_recovery"] is None and cost["recommendation"]["recovery_basis"] == "NOT_RECEIVABLE"
    assert disc["decisions"] == [] and disc["actions"] == [] and disc["impact"] is None


def test_decision_workflow_with_maker_checker_and_stale_versions(built):
    ref = case_ref(built, "BD/SO/DISC-001")
    engine = built["engine"]
    with engine.begin() as conn:
        assigned = decide(conn, ANALYST, ref, "ASSIGN", assigned_to="AN-02", comment="please review", expected_version=1)
    assert (assigned.status_before, assigned.status_after, assigned.version) == ("NEW", "OPEN", 2)
    assert case_row(built, ref)["owner"] == "AN-02"
    with engine.begin() as conn, pytest.raises(NotAuthorised):
        decide(conn, ANALYST, ref, "APPROVE", expected_version=2)
    with engine.begin() as conn, pytest.raises(StaleCase):
        decide(conn, APPROVER, ref, "APPROVE", expected_version=1)
    with engine.begin() as conn, pytest.raises(IllegalTransition):
        decide(conn, APPROVER, ref, "CLOSE", expected_version=2)
    with engine.begin() as conn:
        approved = decide(conn, APPROVER, ref, "APPROVE", expected_version=2, comment="recover through a complementary invoice")
    assert (approved.status_before, approved.status_after, approved.version) == ("OPEN", "APPROVED", 3)
    row = case_row(built, ref)
    assert row["status"] == "APPROVED" and row["decided_at"] is not None and row["estimated_recovery"] == Decimal("1000.00")
    with engine.connect() as conn:
        case = exception_case(conn, built["snapshot"], ref)
        assert case["recommendation"]["status"] == "APPROVED"
        assert [d["decision_type"] for d in case["decisions"]] == ["ASSIGN", "APPROVE"]
        assert case["decisions"][1]["actor"] == "FIN-01" and case["decisions"][1]["actor_roles"] == ["finance_approver"]
        assert case["impact"]["realisation_status"] == "NOT_MEASURED" and case["impact"]["estimated_recovery"] == "1000.00"
        actions = conn.execute(sa.text("select action from audit.event where object_type = 'exception_case' and object_id = :r order by sequence"),
                               {"r": ref}).scalars().all()
    assert actions[-2:] == ["decision.assign", "decision.approve"]
    with engine.begin() as conn, pytest.raises(IllegalTransition):
        decide(conn, APPROVER, ref, "APPROVE", expected_version=3)


def test_decisions_are_append_only(built):
    ref = case_ref(built, "BD/SO/DISC-001")
    with built["engine"].connect() as conn:
        decision_id = conn.execute(sa.text("select decision_id from decision.case_decision d join decision.exception_case c on c.case_id = d.case_id"
                                           " where c.case_ref = :r limit 1"), {"r": ref}).scalar()
    with pytest.raises(sa.exc.DBAPIError):
        with built["engine"].begin() as conn:
            conn.execute(sa.text("update decision.case_decision set reason = 'x' where decision_id = :d"), {"d": decision_id})
    with pytest.raises(sa.exc.DBAPIError):
        with built["engine"].begin() as conn:
            conn.execute(sa.text("delete from decision.case_decision where decision_id = :d"), {"d": decision_id})


def test_reject_defer_evidence_and_reopen_paths(built):
    engine = built["engine"]
    expired = case_ref(built, "BD/SO/NEG-09")
    with engine.begin() as conn, pytest.raises(IllegalTransition):
        decide(conn, APPROVER, expired, "REJECT")
    with engine.begin() as conn:
        assert decide(conn, APPROVER, expired, "REJECT", reason="policy renewal in progress; discount accepted for this order").status_after == "REJECTED"
    with engine.begin() as conn:
        assert decide(conn, ANALYST, expired, "REOPEN", reason="renewal refused by sales").status_after == "OPEN"
    conflict = case_ref(built, "BD/SO/NEG-10")
    with engine.begin() as conn:
        assert decide(conn, ANALYST, conflict, "REQUEST_EVIDENCE", reason="which policy applies?").status_after == "EVIDENCE_REQUESTED"
    with engine.begin() as conn:
        assert decide(conn, ANALYST, conflict, "DEFER", reason="awaiting sales director", defer_until=date(2026, 10, 15)).status_after == "DEFERRED"
    assert case_row(built, conflict)["defer_until"] == date(2026, 10, 15)
    with engine.begin() as conn:
        assert decide(conn, ANALYST, conflict, "COMMENT", comment="reminder sent").status_after == "DEFERRED"
    with engine.connect() as conn:
        case = exception_case(conn, built["snapshot"], conflict)
    assert case["recommendation"]["status"] == "DEFERRED" and [d["decision_type"] for d in case["decisions"]] == ["REQUEST_EVIDENCE", "DEFER", "COMMENT"]


def test_action_in_fixture_mode_is_planned_never_executed(built):
    ref = case_ref(built, "BD/SO/FREIGHT-001")
    settings = make_settings(benacta_mode="fixture")
    engine = built["engine"]
    with engine.begin() as conn:
        refused = execute_review_activity(conn, settings, APPROVER, ref)
    assert (refused.status, refused.detail) == ("REFUSED", "NOT_APPROVED")
    with engine.begin() as conn:
        decide(conn, APPROVER, ref, "APPROVE")
    with engine.begin() as conn:
        plan = plan_review_activity(conn, ref)
        planned = execute_review_activity(conn, settings, APPROVER, ref)
    assert plan.target_model == "sale.order" and plan.external_id == f"margin_action__{ref}__REVIEW_ACTIVITY"
    assert ref in plan.vals["summary"] and "250" in plan.vals["summary"]
    assert (planned.status, planned.detail) == ("PLANNED", "FIXTURE_MODE")
    assert case_row(built, ref)["status"] == "APPROVED", "a planned action never marks the case as actioned"
    with engine.connect() as conn:
        case = exception_case(conn, built["snapshot"], ref)
    assert [a["status"] for a in case["actions"]] == ["REFUSED", "PLANNED"] and case["actions"][1]["target_system"] == "fixture"


class _FakeOdoo:
    """JSON-2 fake: answers the reads the executor needs and records every write."""

    def __init__(self, *, company_exists=True, already_in_target=False):
        self.calls: list[tuple[str, str, dict]] = []
        self.company_exists = company_exists
        self.already_in_target = already_in_target

    def handler(self, request: httpx.Request) -> httpx.Response:
        model, method = request.url.path.split("/")[3:5]
        body = json.loads(request.content or b"{}")
        self.calls.append((model, method, body))
        if model == "res.company":
            return httpx.Response(200, json=1 if self.company_exists else 0)
        if model == "ir.model.data" and method == "search_count":
            return httpx.Response(200, json=1 if self.already_in_target else 0)
        if model == "ir.model.data" and method == "search_read":
            return httpx.Response(200, json=[{"id": 10, "res_id": 4}])
        if model == "ir.model":
            return httpx.Response(200, json=[{"id": 99}])
        if model == "res.users":
            return httpx.Response(200, json=[{"id": 2}])
        if model == "mail.activity" and method == "create":
            return httpx.Response(200, json=[501])
        if model == "ir.model.data" and method == "create":
            return httpx.Response(200, json=[777])
        return httpx.Response(200, json=[])


def _sandbox_settings(**overrides):
    values = dict(benacta_mode="odoo_sandbox", odoo_url="https://example.odoo.com", odoo_db="example", odoo_username="bot@example.invalid",
                  odoo_api_key="k", odoo_writes_enabled=True, odoo_sandbox_allowlist="example.odoo.com/example", odoo_sandbox_company="BENACTA DEMO",
                  odoo_backup_attested_at=str(TODAY), odoo_backup_reference="backup-2026-09-15.zip")
    values.update(overrides)
    return make_settings(**values)


def test_action_against_a_fake_odoo_is_guarded_idempotent_and_recorded(built):
    engine = built["engine"]
    ref = case_ref(built, "BD/SO/PRICE-001")
    with engine.begin() as conn:
        decide(conn, APPROVER, ref, "APPROVE")

    blocked = _FakeOdoo()
    with engine.begin() as conn:
        with OdooJson2Client("https://example.odoo.com", "example", "k", transport=httpx.MockTransport(blocked.handler)) as client:
            result = execute_review_activity(conn, _sandbox_settings(odoo_writes_enabled=False), APPROVER, ref, client=client)
    assert (result.status, result.detail) == ("REFUSED", "GUARD_BLOCKED")
    assert not [c for c in blocked.calls if c[1] == "create"], "a blocked guard never reaches a write"

    fake = _FakeOdoo()
    with engine.begin() as conn:
        with OdooJson2Client("https://example.odoo.com", "example", "k", transport=httpx.MockTransport(fake.handler)) as client:
            result = execute_review_activity(conn, _sandbox_settings(), APPROVER, ref, client=client)
    assert result.status == "EXECUTED" and result.response == {"mail_activity_id": 501, "external_id": f"benacta_demo.margin_action__{ref}__REVIEW_ACTIVITY"}
    creates = [c for c in fake.calls if c[1] == "create"]
    assert [c[0] for c in creates] == ["mail.activity", "ir.model.data"]
    activity = creates[0][2]["vals_list"][0]
    assert activity["res_model"] == "sale.order" and activity["activity_type_id"] == 4 and activity["res_model_id"] == 99 and activity["user_id"] == 2
    assert ref in activity["summary"] and creates[0][2]["context"]["tracking_disable"] is True
    assert creates[1][2]["vals_list"][0]["module"] == "benacta_demo"
    row = case_row(built, ref)
    assert row["status"] == "ACTIONED" and row["actioned_at"] is not None

    again = _FakeOdoo()
    with engine.begin() as conn:
        with OdooJson2Client("https://example.odoo.com", "example", "k", transport=httpx.MockTransport(again.handler)) as client:
            duplicate = execute_review_activity(conn, _sandbox_settings(), APPROVER, ref, client=client)
    assert (duplicate.status, duplicate.detail) == ("REFUSED", "DUPLICATE") and again.calls == [], "a duplicate is refused before any call"
    with engine.connect() as conn:
        statuses = conn.execute(sa.text("select a.status from decision.case_action a join decision.exception_case c on c.case_id = a.case_id"
                                        " where c.case_ref = :r order by a.created_at"), {"r": ref}).scalars().all()
        assert statuses == ["REFUSED", "EXECUTED", "REFUSED"]
        assert verify_chain(conn).valid


def _append_complementary_invoice(dataset, order_name: str, amount: Decimal, day: date) -> None:
    """A posted invoice with one product line linked to the order line, dated after the decision."""
    order = dataset.find("sale.order", name=order_name)[0]
    line = dataset.find("sale.order.line", order_id=[order["id"], order_name])[0]
    move_id = max(r["id"] for r in dataset.records["account.move"]) + 1
    aml_id = max(r["id"] for r in dataset.records["account.move.line"]) + 1
    stamp = f"{day} 11:00:00"
    dataset.records["account.move"].append({
        "id": move_id, "name": f"BD/INV/COMP-{move_id}", "move_type": "out_invoice", "state": "posted", "company_id": [1, "BENACTA DEMO"],
        "partner_id": order["partner_id"], "currency_id": [1, "EUR"], "invoice_date": str(day), "date": str(day), "invoice_origin": order_name,
        "reversed_entry_id": False, "amount_untaxed_signed": float(amount), "payment_state": "not_paid", "write_date": stamp})
    dataset.records["account.move.line"].append({
        "id": aml_id, "move_id": [move_id, f"BD/INV/COMP-{move_id}"], "company_id": [1, "BENACTA DEMO"], "account_id": [2, "707000 Sales of goods"],
        "display_type": "product", "parent_state": "posted", "product_id": line["product_id"], "quantity": 0.0, "product_uom_id": [1, "Units"],
        "price_unit": float(amount), "discount": 0.0, "price_subtotal": float(amount), "balance": float(-amount), "amount_currency": float(-amount),
        "currency_id": [1, "EUR"], "date": str(day), "sale_line_ids": [line["id"]], "write_date": stamp})
    dataset.records["account.move.line"].append({
        "id": aml_id + 1, "move_id": [move_id, f"BD/INV/COMP-{move_id}"], "company_id": [1, "BENACTA DEMO"], "account_id": [1, "411100 Customers"],
        "display_type": "payment_term", "parent_state": "posted", "product_id": False, "quantity": 0.0, "product_uom_id": False, "price_unit": 0.0,
        "discount": 0.0, "price_subtotal": 0.0, "balance": float(amount), "amount_currency": float(amount), "currency_id": [1, "EUR"], "date": str(day),
        "sale_line_ids": [], "write_date": stamp})


def test_realised_recovery_is_measured_only_from_posted_documents_after_the_decision(built):
    engine, source = built["engine"], built["source"]
    ref = case_ref(built, "BD/SO/DISC-001")  # approved in the workflow test
    assert case_row(built, ref)["status"] == "APPROVED"
    with engine.connect() as conn:
        before = impact_register(conn, source.source_instance)
    assert next(r for r in before if r["case_ref"] == ref)["realisation_status"] == "NOT_MEASURED"

    _append_complementary_invoice(source.dataset, "BD/SO/DISC-001", Decimal("1000.00"), TODAY.replace(day=28))
    batch = ingest(engine, source, load_spec(), models=FOUNDATION_MODELS)
    build_marts(engine, batch.batch_id)
    reconcile(engine, source, batch.batch_id)
    run = run_engine(engine, batch.batch_id)
    assert run.impacts.get("MEASURED", 0) >= 1
    with engine.connect() as conn:
        register = impact_register(conn, source.source_instance)
        disc = next(r for r in register if r["case_ref"] == ref)
        assert (disc["realisation_status"], disc["realised_recovery"], disc["variance"]) == ("MEASURED", "1000.00", "0.00")
        assert disc["realisation_evidence"][0]["invoice"].startswith("BD/INV/COMP-")
        cost = next(r for r in register if r["subject_ref"].startswith("BD/SO/COST-001")) if any(r["subject_ref"].startswith("BD/SO/COST-001") for r in register) else None
        assert cost is None or cost["realisation_status"] == "NOT_MEASURABLE"
        overview = margin_overview(conn, batch.batch_id, "2026-07")
        audit = case_audit(conn, ref)
    k = overview["kpis"]
    assert Decimal(k["approved_recovery"]) >= Decimal("1000.00") and Decimal(k["realised_recovery"]) == Decimal("1000.00")
    assert k["decisions_taken"] >= 1 and k["recommendation_acceptance_rate_pct"] is not None and k["avg_hours_detection_to_decision"] is not None
    assert len(audit["evaluations"]) == 2 and [d["decision_type"] for d in audit["decisions"]] == ["ASSIGN", "APPROVE"]
    assert audit["impact"]["realisation_status"] == "MEASURED"
    assert {e["action"] for e in audit["audit_events"]} >= {"recommendation.proposed", "decision.assign", "decision.approve", "impact.measured"}
    assert all(e["event_hash"] for e in audit["audit_events"])


@pytest.fixture(scope="module")
def client(built):
    from _pytest.monkeypatch import MonkeyPatch

    patch = MonkeyPatch()
    patch.setattr(main, "_engine", lambda: built["engine"])
    patch.setattr(main, "_instance", lambda: built["source"].source_instance)
    patch.setattr(main, "get_settings", lambda: make_settings(benacta_mode="fixture"))
    yield TestClient(main.app)
    patch.undo()


def test_api_decisions_and_actions(built, client):
    ref = case_ref(built, "BD/INV/NEG-11")
    headers = {"X-Benacta-Actor": "FIN-01", "X-Benacta-Roles": "finance_approver"}
    assert client.post(f"/api/v1/margin/exceptions/{ref}/decisions", json={"decision_type": "COMMENT", "comment": "x"}).status_code == 401
    assert client.post(f"/api/v1/margin/exceptions/{ref}/decisions", json={"decision_type": "REJECT"}, headers=headers).status_code == 422
    assert client.post(f"/api/v1/margin/exceptions/{ref}/decisions", json={"decision_type": "APPROVE", "expected_version": 99}, headers=headers).status_code == 409
    assert client.post(f"/api/v1/margin/exceptions/{ref}/decisions", json={"decision_type": "APPROVE"},
                       headers={"X-Benacta-Actor": "AN-01", "X-Benacta-Roles": "analyst"}).status_code == 403
    assert client.post("/api/v1/margin/exceptions/MC-999999/decisions", json={"decision_type": "APPROVE"}, headers=headers).status_code == 404
    created = client.post(f"/api/v1/margin/exceptions/{ref}/decisions", json={"decision_type": "APPROVE", "expected_version": 1, "comment": "link the invoice"},
                          headers=headers)
    assert created.status_code == 201 and created.json()["status_after"] == "APPROVED" and created.json()["version"] == 2
    dry = client.post(f"/api/v1/margin/exceptions/{ref}/actions", json={"confirm": False}, headers=headers).json()
    assert dry["status"] == "DRY_RUN" and dry["target_model"] == "account.move" and dry["external_id"].endswith("REVIEW_ACTIVITY")
    planned = client.post(f"/api/v1/margin/exceptions/{ref}/actions", json={"confirm": True}, headers=headers).json()
    assert planned["status"] == "PLANNED" and planned["detail"] == "FIXTURE_MODE"
    audit = client.get(f"/api/v1/margin/exceptions/{ref}/audit").json()
    assert audit["case"]["status"] == "APPROVED" and [a["status"] for a in audit["actions"]] == ["PLANNED"]
    impact = client.get("/api/v1/margin/impact").json()
    assert any(r["case_ref"] == ref and r["realisation_status"] == "NOT_MEASURABLE" for r in impact), "an unlinked invoice has no receivable recovery"
    assert client.get("/api/v1/margin/exceptions/MC-999999/audit").status_code == 404
