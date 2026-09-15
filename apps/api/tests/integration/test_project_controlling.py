"""Project controlling on dataset demo_v2 against the hand-written projects oracle."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
import sqlalchemy as sa

from app.audit.log import content_hash, verify_chain
from app.config import REPO_ROOT
from app.controlling.erosion import detect_erosion
from app.controlling.investigation import investigate_margin_erosion, save_investigation
from app.controlling.metrics import compute_project_metrics, pending_change_order_scenario
from app.controlling.portfolio import portfolio_overview
from app.controlling.psr import PsrError, build_psr_content, publish, save_draft
from app.controlling.seed_plans import APPROVER, CONTROLLER, seed_plans
from app.fixtures.demo_dataset import build_demo_dataset
from app.fixtures.projects_dataset import extend_with_projects
from app.ingestion.runner import ingest
from app.ingestion.sources import FixtureSource
from app.marts.build import build_marts
from app.ops.discover_odoo import load_spec
from app.planning import service
from app.planning.domain import Actor, Role
from app.planning.importer import ImportContext, import_plan, parse_csv
from app.planning.service import PlanningError
from tests.oracle import dec, load_projects_oracle

ORACLE = load_projects_oracle()
CUTOFF = date.fromisoformat(ORACLE["cutoff"])
PREVIOUS = date.fromisoformat(ORACLE["previous_cutoff"])
METRIC_KEYS = {
    "frac": "forecast_revenue_at_completion", "approved_budget": "approved_budget", "actual_cost": "actual_cost",
    "open_commitments": "open_commitments", "etc": "etc", "eac": "eac", "uncommitted_etc": "uncommitted_etc",
    "cost_variance_at_completion": "cost_variance_at_completion", "margin": "forecast_margin_amount",
    "margin_pct": "forecast_margin_pct", "billed": "billed_amount", "collected_ttc": "collected_amount",
    "overdue_ttc": "overdue_amount", "not_yet_due_ttc": "not_yet_due_amount", "remaining_to_bill": "remaining_to_bill",
    "pending_change_orders": "pending_change_orders",
}


@pytest.fixture(scope="module")
def world(engine):
    dataset = extend_with_projects(build_demo_dataset())
    source = FixtureSource(dataset, source_instance=f"fixture_projects_{uuid.uuid4().hex[:8]}")
    batch = ingest(engine, source, load_spec())
    build_marts(engine, batch.batch_id)
    with engine.begin() as conn:
        seeded = seed_plans(conn, dataset.plans, batch.batch_id, source.source_instance)
    return {"engine": engine, "snapshot": batch.batch_id, "source": source, "dataset": dataset, "seeded": seeded}


def metrics(world, code, cutoff=CUTOFF):
    with world["engine"].connect() as conn:
        return compute_project_metrics(conn, world["snapshot"], code, cutoff)


def assert_values(m, expected: dict, label: str):
    for key, metric_id in METRIC_KEYS.items():
        if key not in expected:
            continue
        got, want = m.value(metric_id), expected[key]
        if want is None:
            assert got is None, f"{label} {key}: expected UNKNOWN, got {got}"
        else:
            assert got is not None and Decimal(got).quantize(Decimal("0.01")) == dec(want).quantize(Decimal("0.01")), f"{label} {key}: {got} != {want}"


@pytest.mark.parametrize("code", sorted(ORACLE["projects"]))
def test_project_metrics_match_oracle(world, code):
    expected = ORACLE["projects"][code]
    m = metrics(world, code)
    assert_values(m, expected, code)
    for category, want in expected.get("actual_cost_by_category", {}).items():
        assert m.by_category["actual"].get(category, Decimal(0)) == dec(want), (code, category)
    for category, want in expected.get("open_commitments_by_category", {}).items():
        assert m.by_category["open_commitments"].get(category, Decimal(0)) == dec(want), (code, category)
    if "hours" in expected:
        assert m.value("planned_hours") == dec(expected["hours"]["budget"])
        assert m.value("actual_hours") == dec(expected["hours"]["actual"])
        assert m.value("hours_at_completion") == dec(expected["hours"]["at_completion"])
    for bucket, want in expected.get("overdue_buckets_ttc", {}).items():
        assert dec(m.metrics["overdue_amount"].inputs["buckets"][bucket]) == dec(want)
    with world["engine"].connect() as conn:
        erosion = detect_erosion(conn, world["snapshot"], code, CUTOFF, PREVIOUS)
    codes = {e["code"] for e in m.exceptions} | ({"MARGIN_EROSION"} if erosion.status == "EROSION" else set())
    assert codes == set(expected["exceptions"]), code


@pytest.mark.parametrize("code", sorted(c for c, v in ORACLE["projects"].items() if "previous" in v))
def test_previous_cutoff_metrics_match_oracle(world, code):
    assert_values(metrics(world, code, PREVIOUS), ORACLE["projects"][code]["previous"], f"{code}@previous")


def test_margin_erosion_decomposition(world):
    expected = ORACLE["projects"]["PRJ-02"]["erosion"]
    with world["engine"].connect() as conn:
        result = detect_erosion(conn, world["snapshot"], "PRJ-02", CUTOFF, PREVIOUS)
    assert result.status == "EROSION"
    assert result.margin_change == dec(expected["margin_change"])
    assert result.revenue_change == dec(expected["revenue_change"])
    assert result.eac_change == dec(expected["eac_change"])
    for category, want in expected["by_category"].items():
        assert result.by_category.get(category, Decimal(0)) == dec(want), category
    for role, want in expected["labour_by_role"].items():
        got = result.labour_by_role[role]
        assert dec(got["hours_change"]) == dec(want["hours_change"])
        assert dec(got["rate"]) == dec(want["rate"])
        assert dec(got["cost_change"]) == dec(want["cost_change"])
    assert result.residual == dec(expected["residual"])


def test_late_milestone_shifts_billing(world):
    expected = ORACLE["projects"]["PRJ-02"]["late_milestones"][0]
    late = [ms for ms in metrics(world, "PRJ-02").milestones if ms["late"]]
    assert len(late) == 1
    assert late[0]["name"] == expected["name"] and late[0]["deadline"] == expected["deadline"]
    assert late[0]["days_late"] == expected["days_late"]
    assert dec(late[0]["billing_amount"]) == dec(expected["billing_amount"])
    assert late[0]["previous_planned_billing_period"] == expected["previous_planned_billing_period"]
    assert late[0]["current_planned_billing_period"] == expected["current_planned_billing_period"]
    assert not [ms for ms in metrics(world, "PRJ-01").milestones if ms["late"]]


def test_commitment_already_in_etc_is_not_added_twice(world):
    expected = ORACLE["projects"]["PRJ-03"]
    m = metrics(world, "PRJ-03")
    naive = m.value("actual_cost") + m.value("open_commitments") + m.value("etc")
    assert naive == dec(expected["naive_double_counted_eac"])
    assert m.value("eac") == dec(expected["eac"]) != naive
    assert not [d for d in m.data_quality if d["code"] == "ETC_BELOW_OPEN_COMMITMENTS"]


def test_vendor_bill_moves_from_commitment_to_actual_once(world):
    now, before = metrics(world, "PRJ-04"), metrics(world, "PRJ-04", PREVIOUS)
    bill = dec(ORACLE["projects"]["PRJ-04"]["august_vendor_bill"])
    assert now.by_category["actual"]["SUBCONTRACT"] - before.by_category["actual"]["SUBCONTRACT"] == bill
    assert before.value("open_commitments") - now.value("open_commitments") == bill
    assert now.value("eac") == before.value("eac")


def test_pending_change_order_only_in_scenario(world):
    expected = ORACLE["projects"]["PRJ-06"]
    m = metrics(world, "PRJ-06")
    assert m.value("forecast_margin_amount") == dec(expected["margin"])
    with world["engine"].connect() as conn:
        scenario = pending_change_order_scenario(conn, m)
    for key, want in expected["pending_co_scenario"].items():
        assert dec(scenario[key]) == dec(want), key
    assert m.value("unapproved_change_order_cost") == dec(expected["unapproved_change_order_cost_to_date"])


def test_missing_forecast_is_unknown_and_missing_time_is_flagged(world):
    expected = ORACLE["projects"]["PRJ-08"]
    m = metrics(world, "PRJ-08")
    assert m.metrics["eac"].status == "UNKNOWN" and m.metrics["eac"].reason == expected["eac_reason"]
    assert m.metrics["forecast_margin_amount"].value is None
    incomplete = [d for d in m.data_quality if d["code"] == "TIMESHEETS_INCOMPLETE"]
    assert len(incomplete) == 1 and incomplete[0]["count"] == expected["missing_timesheet_employee_months"]


def test_reconciliation_inconsistency_is_flagged_without_moving_cost(world):
    assert "VENDOR_BILL_PROJECT_MISMATCH" in {d["code"] for d in metrics(world, "PRJ-09").data_quality}
    assert metrics(world, "PRJ-01").value("actual_cost") == dec(ORACLE["projects"]["PRJ-01"]["actual_cost"])
    assert not metrics(world, "PRJ-01").data_quality


def test_private_task_without_project_is_not_a_work_package(world):
    with world["engine"].connect() as conn:
        orphans = conn.execute(sa.text("select count(*) from marts.dim_work_package where snapshot_id = :s and project_id is null"),
                               {"s": world["snapshot"]}).scalar_one()
        packages = conn.execute(sa.text("select count(*) from marts.dim_work_package where snapshot_id = :s"), {"s": world["snapshot"]}).scalar_one()
    assert orphans == 0
    assert packages == sum(1 for t in world["dataset"].records["project.task"] if t["project_id"] and not t["parent_id"])


def test_progress_is_never_cost_ratio(world):
    m = metrics(world, "PRJ-02")
    assert m.value("physical_progress_pct") == Decimal("42")
    assert m.value("cost_consumption_ratio") == Decimal("47.62")
    assert m.metrics["physical_progress_pct"].inputs["declared_by"] == CONTROLLER.user_id


def test_foreign_currency_contract_uses_fixed_project_rate(world):
    m = metrics(world, "PRJ-07")
    assert m.metrics["forecast_revenue_at_completion"].inputs["contract_currency"] == "USD"
    assert m.value("forecast_revenue_at_completion") == dec(ORACLE["projects"]["PRJ-07"]["frac"])


# --------------------------------------------------------------------------- planning workflow and locks
def a_locked_version(world, code="PRJ-01", label="FC-2026-07"):
    with world["engine"].connect() as conn:
        return conn.execute(sa.text("select version_id from planning.plan_version where source_instance = :i and project_code = :p"
                                    " and label = :l and scenario = 'BASE'"),
                            {"i": world["source"].source_instance, "p": code, "l": label}).scalar_one()


def test_locked_version_refuses_any_edit_in_the_database(world):
    version = a_locked_version(world)
    for statement in ("update planning.plan_line set planned_cost = planned_cost + 1 where version_id = :v",
                      "delete from planning.plan_line where version_id = :v",
                      "update planning.plan_version set status = 'DRAFT' where version_id = :v",
                      "update planning.plan_version set label = 'edited' where version_id = :v",
                      "delete from planning.plan_version where version_id = :v"):
        with pytest.raises(sa.exc.DBAPIError), world["engine"].begin() as conn:
            conn.execute(sa.text(statement), {"v": version})


def test_revision_creates_a_draft_child_and_leaves_parent_unchanged(world):
    parent = a_locked_version(world)
    with world["engine"].begin() as conn:
        before = conn.execute(sa.text("select count(*), sum(planned_cost) from planning.plan_line where version_id = :v"), {"v": parent}).one()
        child = service.revise(conn, CONTROLLER, parent, label="FC-2026-07-R1")
        row = conn.execute(sa.text("select status, parent_version_id from planning.plan_version where version_id = :v"), {"v": child}).one()
        after = conn.execute(sa.text("select count(*), sum(planned_cost) from planning.plan_line where version_id = :v"), {"v": parent}).one()
    assert row.status == "DRAFT" and row.parent_version_id == parent
    assert tuple(before) == tuple(after)


def test_maker_checker_and_roles_on_versions(world):
    parent = a_locked_version(world, "PRJ-03")
    both = Actor("controller-and-approver", frozenset({Role.PROJECT_CONTROLLER, Role.FINANCE_APPROVER}), frozenset({1}))
    with world["engine"].begin() as conn:
        draft = service.revise(conn, both, parent, label="FC-2026-07-MC")
        service.submit(conn, both, draft)
        with pytest.raises(PlanningError, match="maker-checker"):
            service.approve(conn, both, draft)
        admin_only = Actor("admin", frozenset({Role.ADMIN}), frozenset({1}))
        with pytest.raises(PlanningError, match="finance_approver"):
            service.approve(conn, admin_only, draft)
        outsider = Actor("other-company", frozenset({Role.FINANCE_APPROVER}), frozenset({2}))
        with pytest.raises(PlanningError, match="may not act"):
            service.approve(conn, outsider, draft)
        service.approve(conn, APPROVER, draft)
    with pytest.raises(sa.exc.DBAPIError), world["engine"].begin() as conn:
        conn.execute(sa.text("update planning.plan_version set approved_by = submitted_by where version_id = :v"), {"v": draft})


def template_rows(**overrides):
    rows = parse_csv((REPO_ROOT / "data" / "templates" / "plan_lines_template.csv").read_bytes())
    return [{**r, "project_code": "PRJ-01", "business_unit": "AUTOMATION", "label": "FC-2026-09-IMPORT", **overrides} for r in rows]


def test_rejected_import_keeps_its_error_report_and_creates_no_version(world):
    ctx = ImportContext(company_id=1, source_instance=world["source"].source_instance, known_projects={"PRJ-01": "AUTOMATION"})
    bad = template_rows()
    bad[0] = {**bad[0], "period": "2026-09"}
    with world["engine"].begin() as conn:
        result = import_plan(conn, bad, ctx, CONTROLLER, source="CSV", file_name="bad.csv")
        errors = conn.execute(sa.text("select row_number, code from planning.import_error where import_id = :i"),
                              {"i": result.import_id}).all()
        versions = conn.execute(sa.text("select count(*) from planning.plan_version where label = 'FC-2026-09-IMPORT'")).scalar_one()
    assert result.status == "REJECTED" and result.version_id is None
    assert (2, "PERIOD_NOT_AFTER_CUTOFF") in {tuple(e) for e in errors}
    assert versions == 0

    with world["engine"].begin() as conn:
        clean = import_plan(conn, template_rows(), ctx, CONTROLLER, source="CSV", file_name="clean.csv")
        lines = conn.execute(sa.text("select v.status, l.cost_category, l.planned_hours, l.planned_cost from planning.plan_line l"
                                     " join planning.plan_version v using (version_id) where v.version_id = :v"),
                             {"v": clean.version_id}).all()
    assert clean.status == "VALIDATED" and {line.status for line in lines} == {"DRAFT"}
    assert sum(line.planned_cost for line in lines if line.planned_cost is not None) == Decimal(57800)
    assert [line.planned_cost for line in lines if line.cost_category == "REVENUE"] == [None, None]
    assert any(line.cost_category != "LABOUR" and line.planned_hours is None for line in lines)


def test_seed_plans_is_idempotent(world):
    with world["engine"].begin() as conn:
        again = seed_plans(conn, world["dataset"].plans, world["snapshot"], world["source"].source_instance)
    assert not again.created and len(again.skipped) == len(world["dataset"].plans)


# --------------------------------------------------------------------------- status reports
def test_psr_is_versioned_immutable_once_published_and_history_is_kept(world):
    engine = world["engine"]
    with engine.begin() as conn:
        content = build_psr_content(conn, world["snapshot"], "PRJ-02", CUTOFF)
        first = save_draft(conn, CONTROLLER, content)
        with pytest.raises(PsrError, match="maker-checker"):
            publish(conn, Actor(CONTROLLER.user_id, frozenset({Role.FINANCE_APPROVER}), frozenset({1})), first, "ok")
        with pytest.raises(PsrError, match="validated comment"):
            publish(conn, APPROVER, first, " ")
        publish(conn, APPROVER, first, "Recovery plan requested; change order assessment in progress.")
    with pytest.raises(sa.exc.DBAPIError, match="immutable"), engine.begin() as conn:
        conn.execute(sa.text("update decision.project_status_report set content = '{}'::jsonb where psr_id = :i"), {"i": first})
    with engine.begin() as conn:
        second = save_draft(conn, CONTROLLER, build_psr_content(conn, world["snapshot"], "PRJ-02", CUTOFF))
        rows = conn.execute(sa.text("select psr_id, revision, status, content_hash, content from decision.project_status_report"
                                    " where psr_id in (:a, :b) order by revision"), {"a": first, "b": second}).mappings().all()
    assert [r["revision"] for r in rows] == [1, 2]
    assert rows[0]["status"] == "PUBLISHED" and rows[1]["status"] == "DRAFT"
    assert rows[0]["content_hash"] == content_hash(content) == content_hash(rows[0]["content"])


def test_psr_keeps_progress_revenue_billing_and_cash_apart(world):
    with world["engine"].connect() as conn:
        content = build_psr_content(conn, world["snapshot"], "PRJ-02", CUTOFF)
    revenue, execution = content["contract_and_revenue"], content["execution"]
    assert revenue["recognised_revenue"]["status"] == "UNAVAILABLE"
    assert revenue["billed"]["metric_id"] == "billed_amount" and revenue["collected_ttc"]["unit"] == "EUR_TTC"
    assert execution["physical_progress_pct"]["value"] != execution["cost_consumption_ratio"]["value"]
    assert content["commentary"]["mode"] == "DETERMINISTIC_NO_LLM" and content["commentary"]["validation"] == "PENDING"
    assert set(content["metric_contracts"]) >= {"eac", "etc", "open_commitments", "billed_amount", "collected_amount"}
    for fact in content["commentary"]["computed_facts"]:
        assert set(fact["numeric_claim_refs"]) <= set(content["metric_contracts"])


# --------------------------------------------------------------------------- investigation
def test_investigation_explains_with_evidence_limits_and_pending_proposals(world):
    with world["engine"].begin() as conn:
        report = investigate_margin_erosion(conn, world["snapshot"], "PRJ-02", CUTOFF)
        investigation_id = save_investigation(conn, report)
        pending = conn.execute(sa.text("select status from decision.recommendation where investigation_id = :i"),
                               {"i": investigation_id}).scalars().all()
    assert report["status"] == "COMPLETED" and report["label"] == "sans LLM"
    assert [s["step"] for s in report["steps"]] == ["read_governed_metric", "compare_versions", "deterministic_decomposition",
                                                   "traverse_objects", "retrieve_evidence", "explain_with_limits", "submit_for_review"]
    assert report["root_cause_status"] == "SUPPORTED_HYPOTHESIS"
    assert all(h["type"] == "SUPPORTED_HYPOTHESIS" and h["evidence_refs"] for h in report["hypotheses"])
    assert report["evidence_refs"] and report["limits"]
    assert pending and set(pending) == {"PENDING_REVIEW"}
    assert any("900 h" in o["text"] for o in report["observations"])


@pytest.mark.parametrize(("code", "reason"), [("PRJ-01", "no material decrease"), ("PRJ-08", "unavailable")])
def test_investigation_abstains_without_established_erosion(world, code, reason):
    with world["engine"].connect() as conn:
        report = investigate_margin_erosion(conn, world["snapshot"], code, CUTOFF)
    assert report["status"] == "ABSTAINED" and reason in report["abstention_reason"]
    assert not report["proposed_actions"] and not report["hypotheses"]


# --------------------------------------------------------------------------- consistency across views
def test_portfolio_and_status_reports_show_the_same_numbers(world):
    with world["engine"].connect() as conn:
        overview = portfolio_overview(conn, world["snapshot"], CUTOFF)
        for row in overview["projects"]:
            psr = build_psr_content(conn, world["snapshot"], row["project_code"], CUTOFF)
            assert row["eac"] == psr["costs_and_forecast"]["eac"]["value"], row["project_code"]
            assert row["forecast_margin_amount"] == psr["costs_and_forecast"]["forecast_margin_amount"]["value"]
            assert row["overdue_amount"] == psr["treasury"]["overdue_ttc"]["value"]
            assert set(row["exceptions"]) == {e["code"] for e in psr["execution"]["exceptions"]}
    assert overview["totals"]["projects_excluded_unknown_eac"] == ["PRJ-08"]
    assert len(overview["projects"]) == ORACLE["portfolio"]["delivery_projects"]


def test_previous_margin_scenarios_are_preserved_on_demo_v2(world):
    with world["engine"].connect() as conn:
        line = conn.execute(sa.text(
            "select f.qty_ordered, f.price_unit, f.discount_pct, f.subtotal from marts.fact_sales_order_line f"
            " join marts.dim_product p on p.snapshot_id = f.snapshot_id and p.product_id = f.product_id"
            " where f.snapshot_id = :s and f.order_name = 'BD/SO/DISC-001' and p.default_code = 'SC1'"), {"s": world["snapshot"]}).one()
        allocation = conn.execute(sa.text(
            "select sum(a.amount) from marts.fact_cost_allocation a join marts.fact_sales_order_line f on f.snapshot_id = a.snapshot_id"
            " and f.sale_line_id = a.sale_line_id where a.snapshot_id = :s and f.order_name = 'BD/SO/COST-001'"), {"s": world["snapshot"]}).scalar()
        assert verify_chain(conn).valid
    assert (line.qty_ordered, line.price_unit, line.discount_pct, line.subtotal) == (100, 100, 15, 8500)
    assert allocation == Decimal(6800)
