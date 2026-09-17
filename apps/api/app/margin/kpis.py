"""Margin KPI conventions: pure functions, unit-tested, referenced by `semantic/metrics.yml`.

Every figure the Command Center shows is computed here or by the rules in `app.margin.rules`; nothing is
recomputed in a view, a prompt or a spreadsheet.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
LEAKAGE_TYPES = ("discount", "price", "freight", "cost")


def gross_margin(revenue: Decimal, cogs: Decimal | None) -> Decimal | None:
    """Posted revenue minus posted cost of goods sold. None when COGS is not defensible for the period."""
    return None if cogs is None else revenue - cogs


def gross_margin_pct(margin: Decimal | None, revenue: Decimal) -> Decimal | None:
    """Ratio of sums, never an average of ratios; None when margin is unknown or revenue is zero."""
    if margin is None or not revenue:
        return None
    return (margin * 100 / revenue).quantize(CENT, rounding=ROUND_HALF_UP)


def margin_basis(revenue_status: str, cogs_status: str, cogs: Decimal | None) -> tuple[str, str]:
    """(basis, status) from the reconciliation of the period.

    RECONCILED_COGS when COGS reconciled; UNAVAILABLE when no COGS can be defended; MANAGEMENT_PROXY otherwise.
    Status is UNRECONCILED when either check failed, so the figure is shown but blocked.
    """
    if cogs_status == "RECONCILED":
        basis = "RECONCILED_COGS"
    elif cogs_status == "UNAVAILABLE" or cogs is None:
        basis = "UNAVAILABLE"
    else:
        basis = "MANAGEMENT_PROXY"
    if "UNRECONCILED" in (revenue_status, cogs_status):
        return basis, "UNRECONCILED"
    return basis, ("UNAVAILABLE" if basis == "UNAVAILABLE" else "OK")


def total_addressable_leakage(exposures: list[tuple[Decimal, str]]) -> Decimal:
    """Sum of adverse exposures whose driver is at least partially controllable."""
    return sum((amount for amount, controllability in exposures if controllability != "NOT_CONTROLLABLE"), Decimal(0))


def recoverable_from_customer(exposures: list[tuple[Decimal, str]]) -> Decimal:
    """Sum of adverse exposures of the billing component (price, discount, freight); cost variances are not receivable."""
    return sum((amount for amount, component in exposures if component == "billing_leakage"), Decimal(0))


def gm_pct_delta_points(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
    return None if current is None or previous is None else current - previous


def is_deteriorating(delta_points: Decimal | None, threshold_points: Decimal) -> bool:
    return delta_points is not None and -delta_points >= threshold_points


def margin_at_policy(gross_margin_value: Decimal, leakage_by_type: dict[str, Decimal]) -> Decimal:
    """Illustrative bridge end point: posted margin plus every confirmed or probable leakage."""
    return gross_margin_value + sum((leakage_by_type.get(t, Decimal(0)) for t in LEAKAGE_TYPES), Decimal(0))
