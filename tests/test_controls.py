"""
Control engine — the rules must fire exactly where the policy says they fire.

Threshold behaviour is tested on synthetic facts so the boundaries are explicit,
then the whole framework is run against the reference story.
"""

from __future__ import annotations

import pytest

from src.control_engine import (
    RULES,
    ControlAlert,
    Severity,
    attention_list,
    evaluate,
    evaluate_fact,
    rank_alerts,
)
from src.finance_engine import (
    FactGrain,
    FinancialFact,
    VarianceDirection,
    classify_direction,
    classify_materiality,
    compute_variance,
    run_truth_layer,
)


def make_fact(
    actual: float,
    budget: float | None,
    *,
    higher_is_better: bool = True,
    grain: FactGrain = FactGrain.METRIC,
    key: str = "test_metric",
    label: str = "Test Metric",
) -> FinancialFact:
    variance, variance_pct = compute_variance(actual, budget)
    return FinancialFact(
        key=key,
        label=label,
        period="2026-07",
        grain=grain,
        actual=actual,
        budget=budget,
        variance=variance,
        variance_pct=variance_pct,
        direction=classify_direction(variance, higher_is_better=higher_is_better),
        materiality=classify_materiality(
            variance, variance_pct, has_budget=budget is not None
        ),
        higher_is_better=higher_is_better,
        account=key if grain is FactGrain.ACCOUNT else None,
    )


@pytest.fixture(scope="module")
def story_alerts():
    _, facts = run_truth_layer()
    return evaluate(facts)


# --------------------------------------------------------------------------- #
# Absolute materiality
# --------------------------------------------------------------------------- #


def test_absolute_rule_fires_exactly_at_the_threshold():
    # A cost metric €100,000 over budget: at the threshold, so it fires.
    alert = evaluate_fact(make_fact(2_100_000, 2_000_000, higher_is_better=False))
    assert alert is not None
    assert alert.rule_id == "ABS_MATERIALITY"
    assert alert.severity is Severity.HIGH


def test_absolute_rule_does_not_fire_one_euro_below_the_threshold():
    # €99,999 over budget on a €2m base: under both the absolute and relative rules.
    assert evaluate_fact(make_fact(2_099_999, 2_000_000, higher_is_better=False)) is None


# --------------------------------------------------------------------------- #
# Relative materiality
# --------------------------------------------------------------------------- #


def test_relative_rule_fires_at_ten_percent_when_above_the_absolute_floor():
    alert = evaluate_fact(make_fact(330_000, 300_000, higher_is_better=False))
    assert alert is not None
    assert alert.rule_id == "REL_MATERIALITY"
    assert alert.severity is Severity.MEDIUM


def test_relative_rule_does_not_fire_below_ten_percent():
    assert evaluate_fact(make_fact(329_000, 300_000, higher_is_better=False)) is None


def test_relative_rule_respects_the_absolute_floor():
    """A 20% swing on a small base is not escalated to a controller."""
    fact = make_fact(120_000, 100_000, higher_is_better=False)
    assert fact.variance_pct == pytest.approx(0.20)
    assert abs(fact.variance) < 25_000
    assert evaluate_fact(fact) is None


# --------------------------------------------------------------------------- #
# Missing budget
# --------------------------------------------------------------------------- #


def test_missing_budget_rule_fires_on_account_facts():
    alert = evaluate_fact(
        make_fact(22_000, None, higher_is_better=False, grain=FactGrain.ACCOUNT)
    )
    assert alert is not None
    assert alert.rule_id == "MISSING_BUDGET"
    assert alert.severity is Severity.MEDIUM
    assert alert.variance is None


def test_missing_budget_rule_is_scoped_to_account_grain():
    """Metric-level budget absence is not an account governance gap."""
    assert evaluate_fact(make_fact(22_000, None, grain=FactGrain.METRIC)) is None


def test_missing_budget_rule_ignores_empty_accounts():
    assert (
        evaluate_fact(make_fact(0, None, grain=FactGrain.ACCOUNT)) is None
    )


# --------------------------------------------------------------------------- #
# Severity policy
# --------------------------------------------------------------------------- #


def test_favorable_breach_ranks_one_level_below_the_unfavorable_equivalent():
    unfavorable = evaluate_fact(make_fact(4_850_000, 5_000_000, higher_is_better=True))
    favorable = evaluate_fact(make_fact(5_150_000, 5_000_000, higher_is_better=True))

    assert unfavorable.severity is Severity.HIGH
    assert unfavorable.direction is VarianceDirection.UNFAVORABLE
    assert favorable.severity is Severity.MEDIUM
    assert favorable.direction is VarianceDirection.FAVORABLE


def test_favorable_cost_underspend_is_still_reported():
    """Governed truth reports good news too — it just does not outrank bad news."""
    alert = evaluate_fact(make_fact(800_000, 980_000, higher_is_better=False))
    assert alert is not None
    assert alert.direction is VarianceDirection.FAVORABLE
    assert "favourable" in alert.business_message


def test_a_fact_produces_at_most_one_alert():
    """A variance breaching both rules is reported once, by the more severe rule."""
    fact = make_fact(550_000, 400_000, higher_is_better=False)
    assert abs(fact.variance) >= 100_000
    assert abs(fact.variance_pct) >= 0.10  # both rules would match
    assert evaluate_fact(fact).rule_id == "ABS_MATERIALITY"


def test_materiality_rules_do_not_double_count_business_unit_facts():
    fact = make_fact(
        3_090_000, 3_400_000, grain=FactGrain.METRIC_BY_BUSINESS_UNIT
    )
    assert abs(fact.variance) >= 100_000
    assert evaluate_fact(fact) is None


# --------------------------------------------------------------------------- #
# The reference story
# --------------------------------------------------------------------------- #


def test_story_produces_the_expected_ranked_alerts(story_alerts):
    assert [(a.metric, a.severity.value) for a in story_alerts] == [
        ("revenue", "HIGH"),
        ("ebitda", "HIGH"),
        ("gross_margin", "HIGH"),
        ("external_contractors", "HIGH"),
        ("travel", "MEDIUM"),
        ("628400", "MEDIUM"),
        ("direct_project_costs", "MEDIUM"),
        ("direct_materials", "LOW"),
    ]


def test_ranking_puts_unfavorable_before_favorable_at_equal_severity(story_alerts):
    medium = [a for a in story_alerts if a.severity is Severity.MEDIUM]
    directions = [a.direction for a in medium]
    assert directions == [
        VarianceDirection.UNFAVORABLE,  # travel
        VarianceDirection.NEUTRAL,  # unbudgeted account
        VarianceDirection.FAVORABLE,  # deferred project costs
    ]


def test_favorable_procurement_variance_is_surfaced(story_alerts):
    materials = next(a for a in story_alerts if a.metric == "direct_materials")
    assert materials.severity is Severity.LOW
    assert materials.direction is VarianceDirection.FAVORABLE
    assert materials.rule_id == "REL_MATERIALITY"


def test_attention_list_is_the_top_ranked_items(story_alerts):
    top = attention_list(story_alerts, limit=5)
    assert len(top) == 5
    assert top == story_alerts[:5]
    assert all(a.severity is not Severity.LOW for a in top)


def test_every_alert_carries_a_readable_business_message(story_alerts):
    for alert in story_alerts:
        assert alert.business_message
        assert alert.label in alert.business_message
        assert "€" in alert.business_message
        assert alert.business_message.endswith(".")
        # No engineering vocabulary reaches the executive surface.
        assert "variance_pct" not in alert.business_message
        assert alert.rule_id not in alert.business_message


def test_revenue_alert_states_the_threshold_it_breached(story_alerts):
    revenue = next(a for a in story_alerts if a.metric == "revenue")
    assert revenue.business_message == (
        "Revenue is €280,000 below budget (-5.6%), exceeding the €100,000 "
        "materiality threshold."
    )
    assert revenue.threshold == 100_000.0


def test_unbudgeted_account_alert_names_the_account(story_alerts):
    workshop = next(a for a in story_alerts if a.metric == "628400")
    assert workshop.rule_id == "MISSING_BUDGET"
    assert "Customer Workshop Logistics" in workshop.business_message
    assert "no budget line" in workshop.business_message


def test_every_alert_links_back_to_its_fact(story_alerts):
    _, facts = run_truth_layer()
    known = {fact.fact_id for fact in facts}
    assert all(alert.fact_id in known for alert in story_alerts)


# --------------------------------------------------------------------------- #
# Framework properties
# --------------------------------------------------------------------------- #


def test_rules_are_uniquely_identified_and_prioritised():
    assert len({rule.rule_id for rule in RULES}) == len(RULES)
    assert len({rule.priority for rule in RULES}) == len(RULES)
    assert all(rule.description for rule in RULES)


def test_evaluation_is_deterministic():
    _, facts = run_truth_layer()
    assert evaluate(facts) == evaluate(facts)


def test_ranking_is_stable_regardless_of_input_order(story_alerts):
    assert rank_alerts(tuple(reversed(story_alerts))) == story_alerts


def test_alerts_are_immutable(story_alerts):
    with pytest.raises(Exception):
        story_alerts[0].severity = Severity.LOW  # type: ignore[misc]
    assert isinstance(story_alerts[0], ControlAlert)
