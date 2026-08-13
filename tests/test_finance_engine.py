"""
Deterministic finance engine the figures must be right, and reproducibly right.

The reconciliation tests deliberately recompute the headline metrics from their
components rather than asserting hard-coded totals, so a change to the fictional
dataset cannot silently break the arithmetic the whole story depends on.
"""

from __future__ import annotations

import pytest

from src.domain import (
    DIRECT_COST_CATEGORIES,
    OPEX_CATEGORIES,
    SEMANTIC_MODEL,
    SemanticMappingError,
)
from src.finance_engine import (
    CALC_VERSION,
    DEFAULT_PERIOD,
    FactGrain,
    Materiality,
    VarianceDirection,
    build_facts,
    compute_variance,
    fact_for,
    facts_at_grain,
    headline_facts,
    run_truth_layer,
)

PERIOD = DEFAULT_PERIOD


@pytest.fixture(scope="module")
def truth():
    ledger, facts = run_truth_layer()
    return ledger, facts


@pytest.fixture(scope="module")
def facts(truth):
    return truth[1]


# --------------------------------------------------------------------------- #
# The two formulas
# --------------------------------------------------------------------------- #


def test_variance_is_actual_minus_budget():
    assert compute_variance(4_720_000.0, 5_000_000.0)[0] == -280_000.0
    assert compute_variance(160_000.0, 122_000.0)[0] == 38_000.0


def test_variance_pct_is_variance_over_absolute_budget():
    _, pct = compute_variance(4_720_000.0, 5_000_000.0)
    assert pct == pytest.approx(-0.056)

    _, pct = compute_variance(160_000.0, 122_000.0)
    assert pct == pytest.approx(0.311475, abs=1e-6)


def test_variance_pct_uses_absolute_budget_so_sign_comes_from_the_variance():
    variance, pct = compute_variance(-50.0, -100.0)
    assert variance == 50.0
    assert pct == pytest.approx(0.5)


def test_variance_pct_is_none_when_budget_is_zero():
    variance, pct = compute_variance(1_000.0, 0.0)
    assert variance == 1_000.0
    assert pct is None


def test_missing_budget_yields_no_variance_at_all():
    assert compute_variance(22_000.0, None) == (None, None)


# --------------------------------------------------------------------------- #
# Business meaning
# --------------------------------------------------------------------------- #


def test_direction_is_business_aware_not_sign_aware(facts):
    revenue = fact_for(facts, "revenue")
    contractors = fact_for(facts, "external_contractors")
    materials = fact_for(facts, "direct_materials")

    # Revenue below plan and costs above plan are both bad news, with
    # opposite signs. Costs below plan are good news.
    assert revenue.variance < 0
    assert revenue.direction is VarianceDirection.UNFAVORABLE
    assert contractors.variance > 0
    assert contractors.direction is VarianceDirection.UNFAVORABLE
    assert materials.variance < 0
    assert materials.direction is VarianceDirection.FAVORABLE


def test_unknown_account_is_rejected_rather_than_aggregated():
    with pytest.raises(SemanticMappingError, match="Unknown account"):
        SEMANTIC_MODEL.map_row(
            period=PERIOD,
            business_unit="BU-PRJ",
            cost_center="CC-4100",
            account="999999",
            account_category="REVENUE",
            amount=1.0,
        )


def test_category_disagreeing_with_the_chart_of_accounts_is_rejected():
    with pytest.raises(SemanticMappingError, match="governed as"):
        SEMANTIC_MODEL.map_row(
            period=PERIOD,
            business_unit="BU-PRJ",
            cost_center="CC-4100",
            account="700100",  # governed as REVENUE
            account_category="TRAVEL",
            amount=1.0,
        )


def test_cost_center_must_belong_to_the_declared_business_unit():
    with pytest.raises(SemanticMappingError, match="belongs to"):
        SEMANTIC_MODEL.map_row(
            period=PERIOD,
            business_unit="BU-SVC",
            cost_center="CC-4100",  # a Projects cost center
            account="700100",
            account_category="REVENUE",
            amount=1.0,
        )


# --------------------------------------------------------------------------- #
# Story reconciliation the numbers the whole project narrates
# --------------------------------------------------------------------------- #


def test_revenue_matches_the_reference_story(facts):
    revenue = fact_for(facts, "revenue")
    assert revenue.actual == 4_720_000.00
    assert revenue.budget == 5_000_000.00
    assert revenue.variance == -280_000.00
    assert revenue.variance_pct == pytest.approx(-0.056)
    assert revenue.materiality is Materiality.HIGH


def test_component_movements_match_the_reference_story(facts):
    assert fact_for(facts, "external_contractors").variance == 120_000.00
    assert fact_for(facts, "direct_materials").variance == -85_000.00
    assert fact_for(facts, "direct_project_costs").variance == -180_000.00

    travel = fact_for(facts, "travel")
    assert travel.variance == 38_000.00
    assert travel.variance_pct == pytest.approx(0.311475, abs=1e-6)


def test_gross_margin_reconciles_from_revenue_and_direct_costs(truth):
    ledger, facts = truth
    direct_cost_variance = sum(
        fact_for(facts, key).variance
        for key in ("direct_materials", "external_contractors", "direct_project_costs")
    )
    gross_margin = fact_for(facts, "gross_margin")

    assert gross_margin.variance == pytest.approx(
        fact_for(facts, "revenue").variance - direct_cost_variance
    )
    assert gross_margin.variance == -135_000.00


def test_ebitda_reconciles_from_gross_margin_and_operating_expenses(facts):
    ebitda = fact_for(facts, "ebitda")
    expected = (
        fact_for(facts, "gross_margin").variance
        - fact_for(facts, "operating_expenses").variance
    )
    assert ebitda.variance == pytest.approx(expected)
    assert ebitda.variance == -200_000.00
    assert fact_for(facts, "operating_expenses").variance == 65_000.00


def test_metric_totals_equal_the_sum_of_their_categories(truth):
    """Each headline metric is exactly its declared composition of the ledger."""
    ledger, facts = truth
    for metric in SEMANTIC_MODEL.metrics:
        expected_actual = sum(
            metric.sign_for(entry.category) * entry.amount
            for entry in ledger.actuals
            if entry.period == PERIOD
        )
        assert fact_for(facts, metric.key).actual == pytest.approx(expected_actual)


def test_gross_margin_percentage_holds_despite_the_revenue_miss(facts):
    """Lower procurement costs protect the margin rate a story detail that must be true."""
    gross_margin = fact_for(facts, "gross_margin")
    revenue = fact_for(facts, "revenue")

    actual_rate = gross_margin.actual / revenue.actual
    budget_rate = gross_margin.budget / revenue.budget
    assert actual_rate >= budget_rate


# --------------------------------------------------------------------------- #
# Grains
# --------------------------------------------------------------------------- #


def test_business_unit_facts_sum_to_the_company_figure(facts):
    for metric in SEMANTIC_MODEL.metrics:
        company = fact_for(facts, metric.key)
        by_unit = sum(
            fact_for(
                facts,
                metric.key,
                grain=FactGrain.METRIC_BY_BUSINESS_UNIT,
                business_unit=unit.key,
            ).actual
            for unit in SEMANTIC_MODEL.business_units
        )
        assert by_unit == pytest.approx(company.actual)


def test_revenue_drill_down_shows_where_the_miss_sits(facts):
    projects = fact_for(
        facts, "revenue", grain=FactGrain.METRIC_BY_BUSINESS_UNIT, business_unit="BU-PRJ"
    )
    service = fact_for(
        facts, "revenue", grain=FactGrain.METRIC_BY_BUSINESS_UNIT, business_unit="BU-SVC"
    )
    assert projects.variance == -310_000.00
    assert service.variance == 30_000.00
    assert projects.variance + service.variance == fact_for(facts, "revenue").variance


def test_account_without_a_budget_line_is_not_assessed(facts):
    workshop = fact_for(facts, "628400", grain=FactGrain.ACCOUNT)
    assert workshop.actual == 22_000.00
    assert workshop.budget is None
    assert workshop.variance is None
    assert workshop.variance_pct is None
    assert workshop.materiality is Materiality.NOT_ASSESSED
    assert workshop.has_budget is False


def test_it_is_the_only_account_without_a_budget(facts):
    unbudgeted = [
        fact.key
        for fact in facts_at_grain(facts, FactGrain.ACCOUNT)
        if not fact.has_budget
    ]
    assert unbudgeted == ["628400"]


def test_every_account_fact_maps_to_a_governed_account(facts):
    codes = {account.code for account in SEMANTIC_MODEL.accounts}
    for fact in facts_at_grain(facts, FactGrain.ACCOUNT):
        assert fact.key in codes


# --------------------------------------------------------------------------- #
# Materiality and reproducibility
# --------------------------------------------------------------------------- #


def test_materiality_classification(facts):
    assert fact_for(facts, "revenue").materiality is Materiality.HIGH  # €280k
    assert fact_for(facts, "travel").materiality is Materiality.MEDIUM  # +31%
    assert fact_for(facts, "personnel_costs").materiality is Materiality.NONE  # €5k
    assert fact_for(facts, "facilities").materiality is Materiality.NONE  # nil


def test_headline_metrics_are_the_four_executive_kpis(facts):
    assert [fact.label for fact in headline_facts(facts)] == [
        "Revenue",
        "Gross Margin",
        "Operating Expenses",
        "EBITDA",
    ]


def test_every_fact_records_the_calculation_version(facts):
    assert all(fact.calc_version == CALC_VERSION for fact in facts)


def test_same_inputs_produce_identical_output():
    _, first = run_truth_layer()
    _, second = run_truth_layer()
    assert first == second


def test_fact_ids_are_unique(facts):
    ids = [fact.fact_id for fact in facts]
    assert len(ids) == len(set(ids))
