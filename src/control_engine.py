"""
BENACTA — Control Engine.

Transparent rules that decide what a controller should look at. The objective is
explainability, not statistical sophistication: every alert states the rule that
fired, the threshold it breached, and a message a CFO can read without a legend.

Three rules, applied to the facts produced by the deterministic finance engine:

    ABS_MATERIALITY   absolute variance at or above the absolute threshold
    REL_MATERIALITY   relative variance at or above the relative threshold,
                      with an absolute floor so that small bases do not shout
    MISSING_BUDGET    actual spend recorded against no budget line

Two design decisions worth stating, because both are visible in the output:

1. A fact produces at most one alert — the most severe rule that fired. Rule id
   and threshold are recorded, so why an item was flagged stays inspectable,
   but a CFO is not shown the same variance twice.

2. Favourable breaches are reported one severity level below the equivalent
   unfavourable breach. Governed truth reports good news too: a €180k cost
   underspend still needs an explanation, it just does not outrank a revenue
   miss of the same size.

Thresholds live in `src.domain` alongside the rest of the business policy, so
this module and the finance engine can never drift apart. The same thresholds
are published in data/context/finance_policy.md.

No dependency on any AI component.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Iterable

from src.domain import (
    MATERIALITY_ABSOLUTE_EUR,
    MATERIALITY_RELATIVE_FLOOR_EUR,
    MATERIALITY_RELATIVE_PCT,
)
from src.finance_engine import FactGrain, FinancialFact, VarianceDirection


class Severity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


_SEVERITY_ORDER: dict[Severity, int] = {
    Severity.HIGH: 0,
    Severity.MEDIUM: 1,
    Severity.LOW: 2,
}

#: A favourable breach ranks one level below the same unfavourable breach.
_FAVORABLE_DOWNGRADE: dict[Severity, Severity] = {
    Severity.HIGH: Severity.MEDIUM,
    Severity.MEDIUM: Severity.LOW,
    Severity.LOW: Severity.LOW,
}

_DIRECTION_ORDER: dict[VarianceDirection, int] = {
    VarianceDirection.UNFAVORABLE: 0,
    VarianceDirection.NEUTRAL: 1,
    VarianceDirection.FAVORABLE: 2,
}


@dataclass(frozen=True)
class ControlRule:
    rule_id: str
    name: str
    description: str
    grains: tuple[FactGrain, ...]
    base_severity: Severity
    priority: int  # lower wins when several rules fire on the same fact
    threshold: float | None
    threshold_label: str
    predicate: Callable[[FinancialFact], bool]

    def applies_to(self, fact: FinancialFact) -> bool:
        return fact.grain in self.grains and self.predicate(fact)


@dataclass(frozen=True)
class ControlAlert:
    rule_id: str
    rule_name: str
    severity: Severity
    metric: str
    label: str
    period: str
    value: float  # the magnitude the rule tested
    threshold: float | None
    threshold_label: str
    direction: VarianceDirection
    business_message: str
    actual: float
    budget: float | None
    variance: float | None
    variance_pct: float | None
    fact_id: str
    business_unit: str | None = None
    account: str | None = None


# --------------------------------------------------------------------------- #
# Rule predicates
# --------------------------------------------------------------------------- #


def _breaches_absolute(fact: FinancialFact) -> bool:
    return fact.variance is not None and abs(fact.variance) >= MATERIALITY_ABSOLUTE_EUR


def _breaches_relative(fact: FinancialFact) -> bool:
    return (
        fact.variance is not None
        and fact.variance_pct is not None
        and abs(fact.variance_pct) >= MATERIALITY_RELATIVE_PCT
        and abs(fact.variance) >= MATERIALITY_RELATIVE_FLOOR_EUR
    )


def _has_no_budget_line(fact: FinancialFact) -> bool:
    return not fact.has_budget and fact.actual != 0


RULES: tuple[ControlRule, ...] = (
    ControlRule(
        rule_id="ABS_MATERIALITY",
        name="Absolute materiality",
        description=(
            "A variance at or above the absolute materiality threshold is "
            "reported to the controller regardless of its relative size."
        ),
        grains=(FactGrain.METRIC,),
        base_severity=Severity.HIGH,
        priority=1,
        threshold=MATERIALITY_ABSOLUTE_EUR,
        threshold_label=f"€{MATERIALITY_ABSOLUTE_EUR:,.0f} absolute",
        predicate=_breaches_absolute,
    ),
    ControlRule(
        rule_id="REL_MATERIALITY",
        name="Relative materiality",
        description=(
            "A variance at or above the relative materiality threshold is "
            "reported when it is also large enough in absolute terms to matter."
        ),
        grains=(FactGrain.METRIC,),
        base_severity=Severity.MEDIUM,
        priority=2,
        threshold=MATERIALITY_RELATIVE_PCT,
        threshold_label=(
            f"{MATERIALITY_RELATIVE_PCT:.0%} relative "
            f"(floor €{MATERIALITY_RELATIVE_FLOOR_EUR:,.0f})"
        ),
        predicate=_breaches_relative,
    ),
    ControlRule(
        rule_id="MISSING_BUDGET",
        name="Missing budget line",
        description=(
            "Actual amounts recorded against an account with no budget line "
            "cannot be assessed against plan and are reported as a governance gap."
        ),
        grains=(FactGrain.ACCOUNT,),
        base_severity=Severity.MEDIUM,
        priority=3,
        threshold=None,
        threshold_label="budget line required",
        predicate=_has_no_budget_line,
    ),
)


# --------------------------------------------------------------------------- #
# Message construction
# --------------------------------------------------------------------------- #


def _format_eur(amount: float) -> str:
    rounded = round(amount, 2)
    if rounded == int(rounded):
        return f"€{abs(rounded):,.0f}"
    return f"€{abs(rounded):,.2f}"


def _variance_clause(fact: FinancialFact) -> str:
    """"Revenue is €280,000 below budget (-5.6%)" — sign only, no judgement."""
    assert fact.variance is not None  # guarded by the rule predicates
    position = "below" if fact.variance < 0 else "above"
    clause = f"{fact.label} is {_format_eur(fact.variance)} {position} budget"
    if fact.variance_pct is not None:
        clause += f" ({fact.variance_pct:+.1%})"
    return clause


def _build_message(rule: ControlRule, fact: FinancialFact) -> str:
    if rule.rule_id == "MISSING_BUDGET":
        return (
            f"{fact.label} recorded {_format_eur(fact.actual)} of actuals in "
            f"{fact.period} with no budget line, so the movement cannot be "
            f"assessed against plan."
        )

    clause = _variance_clause(fact)
    if rule.rule_id == "ABS_MATERIALITY":
        threshold_text = (
            f"the {_format_eur(MATERIALITY_ABSOLUTE_EUR)} materiality threshold"
        )
    else:
        threshold_text = (
            f"the {MATERIALITY_RELATIVE_PCT:.0%} relative materiality threshold"
        )

    if fact.direction is VarianceDirection.FAVORABLE:
        return (
            f"{clause}. The movement is favourable but exceeds {threshold_text} "
            f"and should be explained."
        )
    return f"{clause}, exceeding {threshold_text}."


# --------------------------------------------------------------------------- #
# Evaluation
# --------------------------------------------------------------------------- #


def _severity_for(rule: ControlRule, fact: FinancialFact) -> Severity:
    if fact.direction is VarianceDirection.FAVORABLE:
        return _FAVORABLE_DOWNGRADE[rule.base_severity]
    return rule.base_severity


def _alert_from(rule: ControlRule, fact: FinancialFact) -> ControlAlert:
    return ControlAlert(
        rule_id=rule.rule_id,
        rule_name=rule.name,
        severity=_severity_for(rule, fact),
        metric=fact.key,
        label=fact.label,
        period=fact.period,
        value=fact.variance if fact.variance is not None else fact.actual,
        threshold=rule.threshold,
        threshold_label=rule.threshold_label,
        direction=fact.direction,
        business_message=_build_message(rule, fact),
        actual=fact.actual,
        budget=fact.budget,
        variance=fact.variance,
        variance_pct=fact.variance_pct,
        fact_id=fact.fact_id,
        business_unit=fact.business_unit,
        account=fact.account,
    )


def evaluate_fact(
    fact: FinancialFact, rules: Iterable[ControlRule] = RULES
) -> ControlAlert | None:
    """Return the alert for the most severe rule that fires, or None."""
    for rule in sorted(rules, key=lambda r: r.priority):
        if rule.applies_to(fact):
            return _alert_from(rule, fact)
    return None


def rank_alerts(alerts: Iterable[ControlAlert]) -> tuple[ControlAlert, ...]:
    """
    Severity first, then unfavourable before favourable, then by size.

    Metric key is the final tie-break so ordering is fully deterministic.
    """
    return tuple(
        sorted(
            alerts,
            key=lambda alert: (
                _SEVERITY_ORDER[alert.severity],
                _DIRECTION_ORDER[alert.direction],
                -abs(alert.value),
                alert.metric,
            ),
        )
    )


def evaluate(
    facts: Iterable[FinancialFact], rules: Iterable[ControlRule] = RULES
) -> tuple[ControlAlert, ...]:
    """Run the control framework over every fact and return ranked alerts."""
    rules = tuple(rules)
    alerts = [alert for fact in facts if (alert := evaluate_fact(fact, rules)) is not None]
    return rank_alerts(alerts)


def attention_list(
    alerts: Iterable[ControlAlert], limit: int = 5
) -> tuple[ControlAlert, ...]:
    """
    The top-ranked items the executive cockpit surfaces as requiring attention.

    The full alert set stays available for the audit trail; this is presentation
    scope, not a filter on what the control framework found.
    """
    return tuple(rank_alerts(alerts)[:limit])
