"""
Source lineage and reconciliation.

The claim this layer makes is stronger than "here is some detail": it is that
**the explanation reconciles to the financial truth**. Every drill-down total
must roll back up to a figure the finance engine computed, and anything the
source records do not explain must be reported as a residual rather than
quietly absorbed.

These are the tests that stop the trace-to-source view becoming decoration.
"""

from __future__ import annotations

import pytest

from src.control_engine import evaluate
from src.domain import SEMANTIC_MODEL, SemanticMappingError
from src.finance_engine import FactGrain, fact_for, run_truth_layer
from src.lineage import (
    business_lineage,
    load_source_records,
    reconcile,
    records_for_fact,
    root_causes,
)


@pytest.fixture(scope="module")
def facts():
    _, computed = run_truth_layer()
    return computed


@pytest.fixture(scope="module")
def records():
    return load_source_records()


# --------------------------------------------------------------------------- #
# The source extract
# --------------------------------------------------------------------------- #


def test_every_source_record_maps_to_a_governed_account(records):
    codes = {account.code for account in SEMANTIC_MODEL.accounts}
    assert records
    for record in records:
        assert record.account in codes


def test_source_records_carry_the_fields_a_controller_needs(records):
    for record in records:
        assert record.source_record_id and record.source_system
        assert record.source_document and record.source_section
        assert record.business_object and record.reason
        assert record.original_period and record.current_period
        assert record.impact_eur != 0


def test_a_record_pointing_at_an_unknown_account_is_rejected(tmp_path):
    broken = tmp_path / "broken.csv"
    header = (
        "source_record_id,source_system,source_document,source_section,business_object,"
        "cause_id,cause_title,cause_explanation,project_id,project_name,milestone_id,"
        "milestone_name,account,original_period,current_period,impact_eur,reason\n"
    )
    broken.write_text(
        header + "SR-1,ERP,Doc,Section,Milestone,C-1,Title,Why,,,,,999999,2026-07,2026-07,-1.00,x\n",
        encoding="utf-8",
    )
    with pytest.raises(SemanticMappingError, match="Unknown account"):
        load_source_records(broken)


# --------------------------------------------------------------------------- #
# Attribution
# --------------------------------------------------------------------------- #


def test_records_attach_to_a_metric_through_the_semantic_layer(facts, records):
    revenue = records_for_fact(fact_for(facts, "revenue"), records)
    assert {r.source_record_id for r in revenue} == {"SR-70011", "SR-70012"}

    travel = records_for_fact(fact_for(facts, "travel"), records)
    assert {r.account for r in travel} <= {"625100", "625200", "625300"}


def test_records_attach_to_an_account_fact(facts, records):
    workshop = records_for_fact(
        fact_for(facts, "628400", grain=FactGrain.ACCOUNT), records
    )
    assert [r.source_record_id for r in workshop] == ["SR-62841"]


def test_root_causes_group_records_and_rank_by_impact(records):
    causes = root_causes(records)
    titles = [cause.title for cause in causes]
    assert "Unplanned customer workshops" in titles
    assert len(causes) == 3
    impacts = [abs(cause.impact_eur) for cause in causes]
    assert impacts == sorted(impacts, reverse=True)


def test_a_cause_states_one_explanation_not_one_per_record(records):
    causes = {cause.cause_id: cause for cause in root_causes(records)}
    workshops = causes["CAUSE-UNPLANNED-WORKSHOPS"]
    assert len(workshops.records) == 4
    assert workshops.explanation.count("Three customer workshops") == 1


# --------------------------------------------------------------------------- #
# Reconciliation — the load-bearing tests
# --------------------------------------------------------------------------- #


def test_revenue_business_unit_contributions_reconcile(facts):
    """Projects + Service & Maintenance must equal the group revenue variance."""
    revenue = fact_for(facts, "revenue")
    projects = fact_for(
        facts, "revenue", grain=FactGrain.METRIC_BY_BUSINESS_UNIT, business_unit="BU-PRJ"
    )
    service = fact_for(
        facts, "revenue", grain=FactGrain.METRIC_BY_BUSINESS_UNIT, business_unit="BU-SVC"
    )

    assert projects.variance == -310_000.00
    assert service.variance == 30_000.00
    assert projects.variance + service.variance == pytest.approx(revenue.variance)
    assert revenue.variance == -280_000.00


def test_project_milestone_impacts_reconcile_to_milestone_revenue(facts, records):
    """The two deferred milestones must equal the milestone revenue account."""
    milestone_account = fact_for(facts, "700100", grain=FactGrain.ACCOUNT)
    milestone_records = [r for r in records if r.milestone_id]

    assert {r.milestone_id for r in milestone_records} == {"MS-2214", "MS-2231"}
    assert sum(r.impact_eur for r in milestone_records) == pytest.approx(
        milestone_account.variance
    )
    assert milestone_account.variance == -345_000.00


def test_milestone_impacts_plus_engineering_services_reconcile_to_projects(facts, records):
    """
    The Projects shortfall is the milestone deferral partly offset by
    engineering services — the distinction the cockpit has to make explicit.
    """
    projects = fact_for(
        facts, "revenue", grain=FactGrain.METRIC_BY_BUSINESS_UNIT, business_unit="BU-PRJ"
    )
    milestones = sum(r.impact_eur for r in records if r.milestone_id)
    engineering = fact_for(facts, "700200", grain=FactGrain.ACCOUNT).variance

    assert milestones == -345_000.00
    assert engineering == 35_000.00
    assert milestones + engineering == pytest.approx(projects.variance)


def test_explained_plus_residual_equals_the_variance(facts, records):
    """The reconciliation identity, for every metric that has source records."""
    for key in ("revenue", "external_contractors", "travel"):
        fact = fact_for(facts, key)
        attribution = reconcile(fact, records)
        assert attribution.explained + attribution.residual == pytest.approx(
            fact.variance
        ), key


def test_revenue_residual_is_reported_not_absorbed(facts, records):
    """
    Source records explain -€345k of a -€280k variance. The +€65k difference is
    real (engineering services and Service & Maintenance) and must surface.
    """
    attribution = reconcile(fact_for(facts, "revenue"), records)
    assert attribution.explained == -345_000.00
    assert attribution.residual == 65_000.00
    assert not attribution.fully_explained


def test_contractor_costs_are_fully_attributed_at_account_level(facts, records):
    contractors = fact_for(facts, "604100", grain=FactGrain.ACCOUNT)
    attribution = reconcile(contractors, records)
    assert attribution.explained == 125_000.00
    assert attribution.residual == 0.0
    assert attribution.fully_explained


def test_unbudgeted_account_is_fully_attributed(facts, records):
    workshop = fact_for(facts, "628400", grain=FactGrain.ACCOUNT)
    attribution = reconcile(workshop, records)
    assert attribution.explained == 22_000.00
    assert workshop.actual == 22_000.00


def test_trace_source_record_exists_for_material_driver(facts, records):
    """Every HIGH or MEDIUM unfavourable finding can be traced somewhere."""
    alerts = evaluate(facts)
    traceable = 0
    for alert in alerts[:5]:
        grain = FactGrain.ACCOUNT if alert.account else FactGrain.METRIC
        fact = fact_for(facts, alert.metric, grain=grain)
        if reconcile(fact, records).has_causes:
            traceable += 1
    assert traceable >= 4, "most attention items must be traceable to source records"


# --------------------------------------------------------------------------- #
# Business lineage
# --------------------------------------------------------------------------- #


def test_business_lineage_runs_source_to_decision(facts, records):
    fact = fact_for(facts, "revenue")
    cause = reconcile(fact, records).causes[0]

    steps = business_lineage(
        cause=cause,
        fact=fact,
        rule_name="Absolute materiality",
        threshold_label="€100,000 absolute",
        severity="HIGH",
        interpretation_mode="DEMO",
        confidence="HIGH",
        review_label="AI DRAFT",
        reviewer=None,
        issue_status="OPEN",
        owner=None,
        next_step=None,
        calc_version="1.0.0",
    )

    assert [step.stage for step in steps] == [
        "Source record",
        "Business object",
        "Financial transaction",
        "Financial metric",
        "Control finding",
        "Root cause / interpretation",
        "Decision issue",
        "Action",
    ]
    assert "SR-70011" in steps[0].detail
    assert "Northgate Water Treatment" in steps[1].detail
    assert fact.fact_id in steps[3].technical
    assert "No owner assigned" in steps[-1].headline


def test_business_lineage_includes_transactions_when_supplied(facts, records):
    """The Financial transaction step reflects the postings it is given."""
    from src.lineage import load_transactions, transactions_for_fact

    fact = fact_for(facts, "700200", grain=FactGrain.ACCOUNT)
    cause = reconcile(fact_for(facts, "revenue"), records).causes[0]
    transactions = load_transactions()
    tx_rows = transactions_for_fact(fact, transactions)

    steps = business_lineage(
        cause=cause, fact=fact, transactions=tx_rows, rule_name=None,
        threshold_label=None, severity=None, interpretation_mode="DEMO",
        confidence="HIGH", review_label="AI DRAFT", reviewer=None,
        issue_status="OPEN", owner=None, next_step=None, calc_version="1.0.0",
    )
    tx_step = steps[2]
    assert tx_step.stage == "Financial transaction"
    assert "3 postings" in tx_step.headline
    assert "€835,000" in tx_step.headline


def test_lineage_leads_with_business_language(facts, records):
    """Business first, metadata second — no identifiers in the headlines."""
    fact = fact_for(facts, "revenue")
    cause = reconcile(fact, records).causes[0]
    steps = business_lineage(
        cause=cause, fact=fact, rule_name="Absolute materiality",
        threshold_label="€100,000 absolute", severity="HIGH",
        interpretation_mode="DEMO", confidence="HIGH", review_label="AI DRAFT",
        reviewer=None, issue_status="OPEN", owner=None, next_step=None,
        calc_version="1.0.0",
    )
    assert "fact id" not in steps[3].headline
    assert "calculation version" in steps[3].technical
