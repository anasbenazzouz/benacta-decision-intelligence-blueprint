"""Read side: overview, queue, case and reconciliation report through the service and through the API give
the same figures for the same snapshot, and the report carries the closed-period fields."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app import main
from app.fixtures.demo_dataset import build_demo_dataset
from app.ingestion.runner import FOUNDATION_MODELS, ingest
from app.ingestion.sources import FixtureSource
from app.margin import reference
from app.margin.engine import run_engine
from app.margin.service import exception_case, exception_queue, margin_overview
from app.marts.build import TRANSFORMATION_VERSION, build_marts
from app.marts.reconcile import reconcile, reconciliation_report
from app.ops.discover_odoo import load_spec


@pytest.fixture(scope="module")
def built(engine):
    dataset = build_demo_dataset()
    source = FixtureSource(dataset, source_instance=f"fixture_service_{uuid.uuid4().hex[:8]}")
    batch = ingest(engine, source, load_spec(), models=FOUNDATION_MODELS)
    build_marts(engine, batch.batch_id)
    reconcile(engine, source, batch.batch_id)
    with engine.begin() as conn:
        reference.store_reference(conn, reference.rows_from_terms(dataset.terms, owner="test", source="fixture"),
                                  source_instance=source.source_instance, company_id=1, source_kind="FIXTURE_TERMS", source_ref="demo_v1")
    run_engine(engine, batch.batch_id)
    return {"engine": engine, "snapshot": batch.batch_id, "source": source}


@pytest.fixture(scope="module")
def client(built, monkeypatch_module):
    monkeypatch_module.setattr(main, "_engine", lambda: built["engine"])
    monkeypatch_module.setattr(main, "_instance", lambda: built["source"].source_instance)
    return TestClient(main.app)


@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch

    patch = MonkeyPatch()
    yield patch
    patch.undo()


def test_overview_answers_the_first_cfo_questions(built):
    with built["engine"].connect() as conn:
        overview = margin_overview(conn, built["snapshot"])
    assert overview["period"] == "2026-08" and overview["status"] == "OK" and overview["margin_basis"] == ["RECONCILED_COGS"]
    k = overview["kpis"]
    assert Decimal(k["gross_margin"]) == Decimal(k["revenue"]) - Decimal(k["cogs"])
    assert k["gross_margin_pct"] is not None and k["previous_goods_gross_margin_pct"] is not None
    assert Decimal(k["goods_gross_margin"]) == Decimal(k["revenue_goods"]) - Decimal(k["cogs"])
    assert Decimal(k["revenue_goods"]) + Decimal(k["revenue_services"]) == Decimal(k["revenue"])
    assert isinstance(k["deteriorating"], bool) and k["realised_recovery"] == "0.00" and "NOT_MEASURED" in k["recovery_status"]
    assert overview["waterfall"][0]["step"].startswith("Gross margin") and overview["waterfall"][-1]["step"].startswith("Margin at policy")
    with built["engine"].connect() as conn:
        july = margin_overview(conn, built["snapshot"], "2026-07")
    assert Decimal(july["kpis"]["detected_leakage"]) == Decimal("3050.00")
    assert Decimal(july["kpis"]["recoverable_from_customer"]) == Decimal("2250.00")
    causes = {c["cause"]: Decimal(c["adverse_exposure"]) for c in july["drivers"]["causes"]}
    assert causes == {"DISCOUNT_ABOVE_CAP": Decimal("1000.00"), "PURCHASE_PRICE_VARIANCE": Decimal("800.00"), "PRICE_BELOW_CONTRACT": Decimal("600.00"),
                      "PRICELIST_MISMATCH": Decimal("400.00"), "FREIGHT_NOT_INVOICED": Decimal("250.00")}
    assert july["drivers"]["customers"][0]["customer"] == "Orsay Hydraulics"
    assert july["drivers"]["orders"][0]["order"] == "BD/SO/DISC-001"


def test_queue_ranks_material_confirmed_leakage_first(built):
    with built["engine"].connect() as conn:
        queue = exception_queue(conn, built["snapshot"])
    assert queue[0]["classification"] == "CONFIRMED_LEAKAGE" and queue[0]["subject_ref"].startswith("BD/SO/DISC-001")
    assert all(q["suggested_follow_up"] for q in queue) and all(q["age_days"] is not None for q in queue)
    for column in ("case_ref", "cause", "controllability", "confidence", "owner", "status", "severity", "material", "rule_name"):
        assert column in queue[0]
    confirmed = [q for q in queue if q["classification"] == "CONFIRMED_LEAKAGE"]
    review = [q for q in queue if q["classification"] in ("DATA_QUALITY_ISSUE", "INSUFFICIENT_EVIDENCE")]
    assert len(confirmed) == 7 and len(review) == 4
    assert max(queue.index(q) for q in confirmed) < min(queue.index(q) for q in review)
    with built["engine"].connect() as conn:
        july_only = exception_queue(conn, built["snapshot"], period="2026-07", classification="CONFIRMED_LEAKAGE")
    assert {q["subject_ref"].split(" / ")[0] for q in july_only} == {"BD/SO/DISC-001", "BD/SO/FREIGHT-001", "BD/SO/COST-001", "BD/SO/PRICE-001",
                                                                  "BD/SO/PLIST-001"}


def test_case_drills_down_to_transactions_rules_and_lineage(built):
    with built["engine"].connect() as conn:
        queue = exception_queue(conn, built["snapshot"])
        case = exception_case(conn, built["snapshot"], queue[0]["case_ref"])
        assert exception_case(conn, built["snapshot"], "MC-999999") is None
    assert case["rule"]["rule_id"] == "DISCOUNT_CAP" and case["rule"]["version"] == 1 and case["rule"]["formula"]
    assert case["evaluation"]["adverse_exposure"] == "1000.00"
    assert case["evidence"]["applied_policy"]["policy_id"] == "POL-DISC-STANDARD"
    drill = case["drill_down"]
    assert len(drill["order_lines"]) == 1 and drill["order_lines"][0]["default_code"] == "SC1"
    assert len(drill["invoice_lines"]) == 1 and drill["invoice_lines"][0]["link_cardinality"] == "1:1"
    assert len(drill["deliveries"]) == 1 and len(drill["cost_allocations"]) == 1 and len(drill["receipts"]) == 1 and len(drill["posted_cogs"]) == 1
    assert {c["check_id"] for c in case["period_reconciliation"]} == {"REVENUE_POSTED", "COGS_POSTED", "INVOICE_HEADER_LINES"}
    assert all(c["status"] == "RECONCILED" for c in case["period_reconciliation"])
    assert case["lineage"] and case["lineage"][0]["source_model"] == "sale.order.line" and case["lineage"][0]["record_hash"]
    assert case["suggested_follow_up"]["label"] == "Suggested follow-up" and case["suggested_follow_up"]["status"] == "PENDING_REVIEW"
    assert case["investigation"] is None and case["decisions"] == [] and case["actions"] == []


def test_reconciliation_report_carries_closed_period_fields(built):
    report = reconciliation_report(built["engine"], built["snapshot"], "2026-07")
    assert report["transformation_version"] == TRANSFORMATION_VERSION
    assert report["source_timestamp"] and report["ingestion_timestamp"] and report["margin_basis"] == "RECONCILED_COGS"
    assert report["period_status"] == {"2026-07": "RECONCILED"}
    for check in report["checks"]:
        assert check["period"] == "2026-07" and check["tolerance"] == "0.01" and check["status"] == "RECONCILED"
        assert check["source_total"] is not None and check["analytical_total"] is not None and check["explanation"]
    header = next(c for c in report["checks"] if c["check_id"] == "INVOICE_HEADER_LINES")
    assert header["independence"] == "SOURCE_HEADER" and header["detail"]["invoices"] > 0


def test_api_returns_the_same_figures_as_the_service(built, client):
    snapshot = str(built["snapshot"])
    with built["engine"].connect() as conn:
        overview = margin_overview(conn, built["snapshot"], "2026-07")
        queue = exception_queue(conn, built["snapshot"], period="2026-07")
        case = exception_case(conn, built["snapshot"], queue[0]["case_ref"])
    api_overview = client.get("/api/v1/margin/overview", params={"period": "2026-07", "snapshot": snapshot}).json()
    assert api_overview["kpis"] == overview["kpis"] and api_overview["waterfall"] == overview["waterfall"]
    api_queue = client.get("/api/v1/margin/exceptions", params={"period": "2026-07", "snapshot": snapshot}).json()
    assert [(q["case_ref"], q["adverse_exposure"]) for q in api_queue] == [(q["case_ref"], q["adverse_exposure"]) for q in queue]
    api_case = client.get(f"/api/v1/margin/exceptions/{queue[0]['case_ref']}", params={"snapshot": snapshot}).json()
    assert api_case["evaluation"] == case["evaluation"] and api_case["evidence"] == case["evidence"]
    assert client.get("/api/v1/margin/exceptions/MC-999999", params={"snapshot": snapshot}).status_code == 404
    assert client.get("/api/v1/margin/overview", params={"snapshot": "not-a-uuid"}).status_code == 400
    rules = client.get("/api/v1/margin/rules").json()
    assert {r["rule_id"] for r in rules} == {"DISCOUNT_CAP", "PRICE_BELOW_BASELINE", "FREIGHT_REBILL", "COST_REFERENCE_VARIANCE", "INVOICE_WITHOUT_SALE_LINK"}
    report = client.get("/api/v1/reconciliation", params={"period": "2026-07", "snapshot": snapshot}).json()
    assert report["period_status"] == {"2026-07": "RECONCILED"}
    assert client.get("/api/v1/health").json() == {"status": "ok"}
