"""
BENACTA — Deterministic Finance Engine. The value core.

Every figure in the system is computed here, in code, from the governed business
objects. Nothing downstream may recompute financial truth: the interpretation
layer receives these facts and explains them.

    variance     = actual - budget
    variance_pct = variance / abs(budget)      (None when budget is zero)

A missing budget line is not a zero budget. It produces no variance, is marked
NOT_ASSESSED, and is surfaced by the control engine as a governance gap.

This module imports nothing but the standard library, pandas and the semantic
layer. It has no dependency on any AI component, and
`tests/test_ai_independence.py` enforces that structurally.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from src.domain import (
    MATERIALITY_ABSOLUTE_EUR,
    MATERIALITY_RELATIVE_FLOOR_EUR,
    MATERIALITY_RELATIVE_PCT,
    SEMANTIC_MODEL,
    Account,
    CATEGORY_HIGHER_IS_BETTER,
    LedgerEntry,
    MetricDefinition,
    SemanticModel,
)

#: Bumped whenever the calculation of any figure changes. Recorded on every fact
#: so an audit trail can state which version of the rules produced a number.
CALC_VERSION = "1.0.0"

#: The reference period of the fictional demonstration.
DEFAULT_PERIOD = "2026-07"

_REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = _REPO_ROOT / "data"
DEFAULT_ACTUALS_PATH = DATA_DIR / "actuals.csv"
DEFAULT_BUDGET_PATH = DATA_DIR / "budget.csv"

_EXTRACT_COLUMNS = (
    "period",
    "business_unit",
    "cost_center",
    "account",
    "account_category",
    "amount",
)

#: Money is rounded to cents, percentages to six decimal places, so that repeated
#: runs are bit-for-bit identical and float noise never reaches a report.
_MONEY_DP = 2
_PCT_DP = 6


class FactGrain(str, Enum):
    """The level a fact is stated at. Controls declare which grains they apply to."""

    METRIC = "METRIC"
    METRIC_BY_BUSINESS_UNIT = "METRIC_BY_BUSINESS_UNIT"
    ACCOUNT = "ACCOUNT"


class VarianceDirection(str, Enum):
    FAVORABLE = "FAVORABLE"
    UNFAVORABLE = "UNFAVORABLE"
    NEUTRAL = "NEUTRAL"


class Materiality(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    NONE = "NONE"
    #: No budget line exists, so the movement cannot be assessed against plan.
    NOT_ASSESSED = "NOT_ASSESSED"


@dataclass(frozen=True)
class FinancialFact:
    """
    One computed truth: what a metric (or account) did against plan.

    This is the only object the interpretation layer is allowed to reason about.
    """

    key: str  # metric key, or account code at ACCOUNT grain
    label: str
    period: str
    grain: FactGrain
    actual: float
    budget: float | None
    variance: float | None
    variance_pct: float | None
    direction: VarianceDirection
    materiality: Materiality
    higher_is_better: bool
    business_unit: str | None = None
    account: str | None = None
    calc_version: str = CALC_VERSION

    @property
    def fact_id(self) -> str:
        """Stable identifier used by control alerts and the audit trail."""
        return f"{self.grain.value}:{self.key}:{self.business_unit or '-'}:{self.period}"

    @property
    def has_budget(self) -> bool:
        return self.budget is not None


@dataclass(frozen=True)
class Ledger:
    """The mapped extract: business objects, not rows."""

    actuals: tuple[LedgerEntry, ...]
    budgets: tuple[LedgerEntry, ...]
    source_files: tuple[str, ...]


# --------------------------------------------------------------------------- #
# Pure calculations
# --------------------------------------------------------------------------- #


def compute_variance(actual: float, budget: float | None) -> tuple[float | None, float | None]:
    """
    The two formulas the whole system depends on.

    Returns (variance, variance_pct). Both are None when there is no budget line.
    variance_pct is None when the budget is exactly zero — a zero budget has a
    variance but no meaningful percentage.
    """
    if budget is None:
        return None, None

    variance = round(actual - budget, _MONEY_DP)
    if budget == 0:
        return variance, None
    return variance, round(variance / abs(budget), _PCT_DP)


def classify_direction(
    variance: float | None, *, higher_is_better: bool
) -> VarianceDirection:
    """Whether a movement is good news depends on the metric, not the sign."""
    if variance is None or variance == 0:
        return VarianceDirection.NEUTRAL
    if higher_is_better:
        return VarianceDirection.FAVORABLE if variance > 0 else VarianceDirection.UNFAVORABLE
    return VarianceDirection.FAVORABLE if variance < 0 else VarianceDirection.UNFAVORABLE


def classify_materiality(
    variance: float | None, variance_pct: float | None, *, has_budget: bool
) -> Materiality:
    """
    Materiality per the published policy (see domain.py and finance_policy.md).

    HIGH   absolute variance at or above the absolute threshold
    MEDIUM relative variance at or above the relative threshold, and large
           enough in absolute terms to be worth a controller's attention
    """
    if not has_budget or variance is None:
        return Materiality.NOT_ASSESSED
    if abs(variance) >= MATERIALITY_ABSOLUTE_EUR:
        return Materiality.HIGH
    if (
        variance_pct is not None
        and abs(variance_pct) >= MATERIALITY_RELATIVE_PCT
        and abs(variance) >= MATERIALITY_RELATIVE_FLOOR_EUR
    ):
        return Materiality.MEDIUM
    return Materiality.NONE


def _make_fact(
    *,
    key: str,
    label: str,
    period: str,
    grain: FactGrain,
    actual: float,
    budget: float | None,
    higher_is_better: bool,
    business_unit: str | None = None,
    account: str | None = None,
) -> FinancialFact:
    variance, variance_pct = compute_variance(actual, budget)
    return FinancialFact(
        key=key,
        label=label,
        period=period,
        grain=grain,
        actual=round(actual, _MONEY_DP),
        budget=None if budget is None else round(budget, _MONEY_DP),
        variance=variance,
        variance_pct=variance_pct,
        direction=classify_direction(variance, higher_is_better=higher_is_better),
        materiality=classify_materiality(
            variance, variance_pct, has_budget=budget is not None
        ),
        higher_is_better=higher_is_better,
        business_unit=business_unit,
        account=account,
    )


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def load_entries(path: Path, model: SemanticModel = SEMANTIC_MODEL) -> tuple[LedgerEntry, ...]:
    """Read an extract and map every row onto the governed business model."""
    frame = pd.read_csv(path, dtype={"account": str})

    missing = [column for column in _EXTRACT_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"{path.name} is missing column(s): {', '.join(missing)}")

    entries = []
    for position, row in enumerate(frame.to_dict("records"), start=2):  # 1 = header
        try:
            entries.append(
                model.map_row(
                    period=str(row["period"]),
                    business_unit=str(row["business_unit"]),
                    cost_center=str(row["cost_center"]),
                    account=str(row["account"]),
                    account_category=str(row["account_category"]),
                    amount=float(row["amount"]),
                )
            )
        except Exception as exc:  # noqa: BLE001 - re-raised with row context
            raise type(exc)(f"{path.name} line {position}: {exc}") from exc
    return tuple(entries)


def load_ledger(
    actuals_path: Path = DEFAULT_ACTUALS_PATH,
    budget_path: Path = DEFAULT_BUDGET_PATH,
    model: SemanticModel = SEMANTIC_MODEL,
) -> Ledger:
    return Ledger(
        actuals=load_entries(actuals_path, model),
        budgets=load_entries(budget_path, model),
        source_files=(actuals_path.name, budget_path.name),
    )


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #


def _total_for_metric(entries: Iterable[LedgerEntry], metric: MetricDefinition) -> float:
    """Apply the metric's declared signs to the entries in scope."""
    return sum(metric.sign_for(entry.category) * entry.amount for entry in entries)


def _entries_for_period(
    entries: Sequence[LedgerEntry], period: str, business_unit: str | None = None
) -> tuple[LedgerEntry, ...]:
    return tuple(
        entry
        for entry in entries
        if entry.period == period
        and (business_unit is None or entry.business_unit.key == business_unit)
    )


def _metric_fact(
    metric: MetricDefinition,
    actuals: Sequence[LedgerEntry],
    budgets: Sequence[LedgerEntry],
    *,
    period: str,
    grain: FactGrain,
    business_unit: str | None = None,
) -> FinancialFact:
    scoped_actuals = _entries_for_period(actuals, period, business_unit)
    scoped_budgets = _entries_for_period(budgets, period, business_unit)

    # A metric has a budget when any budget line contributes to it. Absent
    # budget lines for individual accounts are a control matter, handled at
    # ACCOUNT grain, so that one unbudgeted account does not invalidate the
    # comparison for an entire metric.
    contributes = any(
        metric.sign_for(entry.category) != 0 for entry in scoped_budgets
    )

    return _make_fact(
        key=metric.key,
        label=metric.label,
        period=period,
        grain=grain,
        actual=_total_for_metric(scoped_actuals, metric),
        budget=_total_for_metric(scoped_budgets, metric) if contributes else None,
        higher_is_better=metric.higher_is_better,
        business_unit=business_unit,
    )


def _account_facts(
    actuals: Sequence[LedgerEntry],
    budgets: Sequence[LedgerEntry],
    *,
    period: str,
) -> list[FinancialFact]:
    """
    One fact per account, so that actuals with no budget line are visible.

    Ordered by account code for deterministic output.
    """
    scoped_actuals = _entries_for_period(actuals, period)
    scoped_budgets = _entries_for_period(budgets, period)

    codes = sorted(
        {entry.account.code for entry in scoped_actuals}
        | {entry.account.code for entry in scoped_budgets}
    )

    facts: list[FinancialFact] = []
    for code in codes:
        actual_entries = [e for e in scoped_actuals if e.account.code == code]
        budget_entries = [e for e in scoped_budgets if e.account.code == code]

        account: Account = (actual_entries or budget_entries)[0].account
        units = {e.business_unit.key for e in actual_entries + budget_entries}

        facts.append(
            _make_fact(
                key=code,
                label=account.name,
                period=period,
                grain=FactGrain.ACCOUNT,
                actual=sum(e.amount for e in actual_entries),
                budget=sum(e.amount for e in budget_entries) if budget_entries else None,
                higher_is_better=CATEGORY_HIGHER_IS_BETTER[account.category],
                business_unit=units.pop() if len(units) == 1 else None,
                account=code,
            )
        )
    return facts


def build_facts(
    ledger: Ledger,
    *,
    period: str = DEFAULT_PERIOD,
    model: SemanticModel = SEMANTIC_MODEL,
) -> tuple[FinancialFact, ...]:
    """
    Compute every fact for the period, at three grains:

      METRIC                   company-level metrics — what controls run on
      METRIC_BY_BUSINESS_UNIT  the same metrics per business unit — drill-down
      ACCOUNT                  one fact per account — budget coverage

    Deterministic: metric order follows the semantic model, units and accounts
    are sorted, so the same inputs always produce the same sequence.
    """
    facts: list[FinancialFact] = []

    for metric in model.metrics:
        facts.append(
            _metric_fact(
                metric, ledger.actuals, ledger.budgets, period=period, grain=FactGrain.METRIC
            )
        )

    for unit in sorted(model.business_units, key=lambda u: u.key):
        for metric in model.metrics:
            facts.append(
                _metric_fact(
                    metric,
                    ledger.actuals,
                    ledger.budgets,
                    period=period,
                    grain=FactGrain.METRIC_BY_BUSINESS_UNIT,
                    business_unit=unit.key,
                )
            )

    facts.extend(_account_facts(ledger.actuals, ledger.budgets, period=period))
    return tuple(facts)


# --------------------------------------------------------------------------- #
# Convenience selectors
# --------------------------------------------------------------------------- #


def facts_at_grain(
    facts: Iterable[FinancialFact], grain: FactGrain
) -> tuple[FinancialFact, ...]:
    return tuple(fact for fact in facts if fact.grain is grain)


def fact_for(
    facts: Iterable[FinancialFact],
    key: str,
    *,
    grain: FactGrain = FactGrain.METRIC,
    business_unit: str | None = None,
) -> FinancialFact:
    """
    Look up a single fact by key and grain.

    `business_unit` narrows the search when given; it is only needed to
    disambiguate METRIC_BY_BUSINESS_UNIT facts, since key and grain are
    otherwise unique. Account facts carry the unit their postings belong to,
    so filtering on it by default would hide them.
    """
    for fact in facts:
        if fact.key != key or fact.grain is not grain:
            continue
        if business_unit is not None and fact.business_unit != business_unit:
            continue
        return fact
    raise KeyError(f"No {grain.value} fact for {key!r} (business_unit={business_unit!r})")


def headline_facts(
    facts: Iterable[FinancialFact], model: SemanticModel = SEMANTIC_MODEL
) -> tuple[FinancialFact, ...]:
    """The four KPIs the executive cockpit leads with, in defined order."""
    metric_facts = facts_at_grain(facts, FactGrain.METRIC)
    return tuple(
        fact
        for metric in model.headline_metrics
        for fact in metric_facts
        if fact.key == metric.key
    )


def run_truth_layer(
    actuals_path: Path = DEFAULT_ACTUALS_PATH,
    budget_path: Path = DEFAULT_BUDGET_PATH,
    *,
    period: str = DEFAULT_PERIOD,
    model: SemanticModel = SEMANTIC_MODEL,
) -> tuple[Ledger, tuple[FinancialFact, ...]]:
    """Load the extract and compute every fact. The whole deterministic core."""
    ledger = load_ledger(actuals_path, budget_path, model)
    return ledger, build_facts(ledger, period=period, model=model)
