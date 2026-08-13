"""
BENACTA Business Semantic Layer.

A ledger row is not a business fact. This module holds the governed definitions
that give raw extract rows their business meaning:

    business units -> cost centers -> accounts -> account categories
    metric definitions composed over those categories

The extract carries codes. The semantic model carries meaning, and it is the
authority: a row referencing an unknown account, or claiming a category that
disagrees with the governed chart of accounts, is rejected rather than silently
aggregated. That rejection is the point it is where "raw data" becomes
"business meaning".

Sign convention: all amounts are stored as positive magnitudes. Revenue and cost
accounts are distinguished by their category, and metric definitions apply the
signs. This keeps the extract readable and keeps debit/credit sign errors out of
the demonstration.

This module has no dependency on any AI component part of the trust
boundary enforced by `tests/test_ai_independence.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

# --------------------------------------------------------------------------- #
# Materiality policy
#
# These thresholds are business policy, not implementation detail. They are
# stated here once and consumed by both the finance engine (fact materiality)
# and the control engine (rule thresholds), so the two can never drift apart.
# The same thresholds are published in data/context/finance_policy.md, which
# makes them retrievable as evidence for why an item was flagged.
# --------------------------------------------------------------------------- #

MATERIALITY_ABSOLUTE_EUR = 100_000.0
MATERIALITY_RELATIVE_PCT = 0.10
MATERIALITY_RELATIVE_FLOOR_EUR = 25_000.0


class SemanticMappingError(ValueError):
    """A ledger row could not be mapped onto a governed business object."""


class AccountCategory(str, Enum):
    """The governed categories that metric definitions are composed from."""

    REVENUE = "REVENUE"
    DIRECT_MATERIALS = "DIRECT_MATERIALS"
    EXTERNAL_CONTRACTORS = "EXTERNAL_CONTRACTORS"
    DIRECT_PROJECT_COSTS = "DIRECT_PROJECT_COSTS"
    PERSONNEL = "PERSONNEL"
    TRAVEL = "TRAVEL"
    FACILITIES = "FACILITIES"
    OTHER_OPEX = "OTHER_OPEX"


REVENUE_CATEGORIES: tuple[AccountCategory, ...] = (AccountCategory.REVENUE,)

DIRECT_COST_CATEGORIES: tuple[AccountCategory, ...] = (
    AccountCategory.DIRECT_MATERIALS,
    AccountCategory.EXTERNAL_CONTRACTORS,
    AccountCategory.DIRECT_PROJECT_COSTS,
)

OPEX_CATEGORIES: tuple[AccountCategory, ...] = (
    AccountCategory.PERSONNEL,
    AccountCategory.TRAVEL,
    AccountCategory.FACILITIES,
    AccountCategory.OTHER_OPEX,
)

#: Whether a larger amount is good news, per category. This is business meaning
#: that raw rows do not carry: +€120k of contractor spend and +€120k of revenue
#: are the same number and opposite news.
CATEGORY_HIGHER_IS_BETTER: Mapping[AccountCategory, bool] = {
    AccountCategory.REVENUE: True,
    **{category: False for category in DIRECT_COST_CATEGORIES + OPEX_CATEGORIES},
}


# --------------------------------------------------------------------------- #
# Business objects
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class BusinessUnit:
    key: str
    name: str


@dataclass(frozen=True)
class CostCenter:
    key: str
    name: str
    business_unit: str  # BusinessUnit.key


@dataclass(frozen=True)
class Account:
    code: str
    name: str
    category: AccountCategory


@dataclass(frozen=True)
class LedgerEntry:
    """One extract row, resolved against the semantic model."""

    period: str
    business_unit: BusinessUnit
    cost_center: CostCenter
    account: Account
    amount: float

    @property
    def category(self) -> AccountCategory:
        return self.account.category


@dataclass(frozen=True)
class MetricDefinition:
    """
    A metric is a signed composition over account categories.

    Keeping the composition declarative means the finance engine contains one
    aggregation routine rather than one hand-written formula per metric, and the
    architecture view can render how each figure is built.
    """

    key: str
    label: str
    positive: tuple[AccountCategory, ...]
    negative: tuple[AccountCategory, ...] = ()
    higher_is_better: bool = True
    headline: bool = False
    description: str = ""

    @property
    def categories(self) -> tuple[AccountCategory, ...]:
        return self.positive + self.negative

    def sign_for(self, category: AccountCategory) -> int:
        if category in self.positive:
            return 1
        if category in self.negative:
            return -1
        return 0


#: The four headline KPIs shown to executives, plus the component metrics that
#: explain them. Components are what make a variance actionable: "EBITDA is down"
#: is a symptom; "contractors are €120k over" is something a controller can own.
METRICS: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        key="revenue",
        label="Revenue",
        positive=REVENUE_CATEGORIES,
        higher_is_better=True,
        headline=True,
        description="Recognised revenue for the period.",
    ),
    MetricDefinition(
        key="gross_margin",
        label="Gross Margin",
        positive=REVENUE_CATEGORIES,
        negative=DIRECT_COST_CATEGORIES,
        higher_is_better=True,
        headline=True,
        description="Revenue less direct project and material costs.",
    ),
    MetricDefinition(
        key="operating_expenses",
        label="Operating Expenses",
        positive=OPEX_CATEGORIES,
        higher_is_better=False,
        headline=True,
        description="Personnel, travel, facilities and other operating costs.",
    ),
    MetricDefinition(
        key="ebitda",
        label="EBITDA",
        positive=REVENUE_CATEGORIES,
        negative=DIRECT_COST_CATEGORIES + OPEX_CATEGORIES,
        higher_is_better=True,
        headline=True,
        description="Gross margin less operating expenses.",
    ),
    MetricDefinition(
        key="direct_materials",
        label="Direct Materials",
        positive=(AccountCategory.DIRECT_MATERIALS,),
        higher_is_better=False,
        description="Raw materials, components and spare parts purchased.",
    ),
    MetricDefinition(
        key="external_contractors",
        label="External Contractors",
        positive=(AccountCategory.EXTERNAL_CONTRACTORS,),
        higher_is_better=False,
        description="External engineering and subcontracted field labour.",
    ),
    MetricDefinition(
        key="direct_project_costs",
        label="Direct Project Costs",
        positive=(AccountCategory.DIRECT_PROJECT_COSTS,),
        higher_is_better=False,
        description="Milestone-linked site installation, commissioning and equipment costs.",
    ),
    MetricDefinition(
        key="personnel_costs",
        label="Personnel Costs",
        positive=(AccountCategory.PERSONNEL,),
        higher_is_better=False,
        description="Salaries and employment costs.",
    ),
    MetricDefinition(
        key="travel",
        label="Travel",
        positive=(AccountCategory.TRAVEL,),
        higher_is_better=False,
        description="Travel and accommodation.",
    ),
    MetricDefinition(
        key="facilities",
        label="Facilities",
        positive=(AccountCategory.FACILITIES,),
        higher_is_better=False,
        description="Facilities and utilities.",
    ),
    MetricDefinition(
        key="other_opex",
        label="Other Operating Expenses",
        positive=(AccountCategory.OTHER_OPEX,),
        higher_is_better=False,
        description="Professional fees, IT and other operating costs.",
    ),
)


# --------------------------------------------------------------------------- #
# The governed model of the fictional company
#
# Meridian Industrial Group a mid-sized industrial and project engineering
# company. Entirely fictional. Amounts in Euros.
# --------------------------------------------------------------------------- #

COMPANY_NAME = "Meridian Industrial Group"

BUSINESS_UNITS: tuple[BusinessUnit, ...] = (
    BusinessUnit("BU-PRJ", "Projects"),
    BusinessUnit("BU-SVC", "Service & Maintenance"),
)

COST_CENTERS: tuple[CostCenter, ...] = (
    CostCenter("CC-4100", "Project Delivery", "BU-PRJ"),
    CostCenter("CC-4200", "Engineering", "BU-PRJ"),
    CostCenter("CC-4900", "Projects Administration", "BU-PRJ"),
    CostCenter("CC-5100", "Field Service", "BU-SVC"),
    CostCenter("CC-5900", "Service Administration", "BU-SVC"),
)

ACCOUNTS: tuple[Account, ...] = (
    Account("700100", "Project Revenue Milestones", AccountCategory.REVENUE),
    Account("700200", "Project Revenue Engineering Services", AccountCategory.REVENUE),
    Account("700300", "Service Contract Revenue", AccountCategory.REVENUE),
    Account("700400", "Spare Parts & Repairs Revenue", AccountCategory.REVENUE),
    Account("601100", "Raw Materials & Components", AccountCategory.DIRECT_MATERIALS),
    Account("601200", "Spare Parts Purchases", AccountCategory.DIRECT_MATERIALS),
    Account("604100", "External Engineering Contractors", AccountCategory.EXTERNAL_CONTRACTORS),
    Account("604200", "Subcontracted Field Labour", AccountCategory.EXTERNAL_CONTRACTORS),
    Account("605100", "Site Installation & Commissioning", AccountCategory.DIRECT_PROJECT_COSTS),
    Account("605200", "Equipment Rental Projects", AccountCategory.DIRECT_PROJECT_COSTS),
    Account("641100", "Salaries Project Delivery", AccountCategory.PERSONNEL),
    Account("641200", "Salaries Engineering", AccountCategory.PERSONNEL),
    Account("641300", "Salaries Field Service", AccountCategory.PERSONNEL),
    Account("641900", "Salaries Projects Administration", AccountCategory.PERSONNEL),
    Account("641950", "Salaries Service Administration", AccountCategory.PERSONNEL),
    Account("625100", "Travel & Accommodation Projects", AccountCategory.TRAVEL),
    Account("625200", "Travel & Accommodation Service", AccountCategory.TRAVEL),
    Account("625300", "Travel Administration", AccountCategory.TRAVEL),
    Account("613100", "Facilities & Utilities Projects", AccountCategory.FACILITIES),
    Account("613200", "Facilities & Utilities Service", AccountCategory.FACILITIES),
    Account("628100", "Professional Fees", AccountCategory.OTHER_OPEX),
    Account("628200", "IT & Communications", AccountCategory.OTHER_OPEX),
    Account("628400", "Customer Workshop Logistics", AccountCategory.OTHER_OPEX),
)


@dataclass(frozen=True)
class SemanticModel:
    """The governed business model. Extract rows are validated against it."""

    company: str
    business_units: tuple[BusinessUnit, ...]
    cost_centers: tuple[CostCenter, ...]
    accounts: tuple[Account, ...]
    metrics: tuple[MetricDefinition, ...]

    # -- lookups ---------------------------------------------------------- #

    def business_unit(self, key: str) -> BusinessUnit:
        for unit in self.business_units:
            if unit.key == key:
                return unit
        raise SemanticMappingError(f"Unknown business unit: {key!r}")

    def cost_center(self, key: str) -> CostCenter:
        for center in self.cost_centers:
            if center.key == key:
                return center
        raise SemanticMappingError(f"Unknown cost center: {key!r}")

    def account(self, code: str) -> Account:
        for account in self.accounts:
            if account.code == code:
                return account
        raise SemanticMappingError(f"Unknown account: {code!r}")

    def metric(self, key: str) -> MetricDefinition:
        for metric in self.metrics:
            if metric.key == key:
                return metric
        raise SemanticMappingError(f"Unknown metric: {key!r}")

    @property
    def headline_metrics(self) -> tuple[MetricDefinition, ...]:
        return tuple(m for m in self.metrics if m.headline)

    @property
    def component_metrics(self) -> tuple[MetricDefinition, ...]:
        return tuple(m for m in self.metrics if not m.headline)

    def cost_centers_of(self, business_unit_key: str) -> tuple[CostCenter, ...]:
        return tuple(c for c in self.cost_centers if c.business_unit == business_unit_key)

    # -- mapping ---------------------------------------------------------- #

    def map_row(
        self,
        *,
        period: str,
        business_unit: str,
        cost_center: str,
        account: str,
        account_category: str,
        amount: float,
    ) -> LedgerEntry:
        """
        Resolve one extract row into a business object, or reject it.

        Rejection cases are deliberate governance, not defensive programming:
        an unknown code or a category that contradicts the chart of accounts
        means the extract and the governed model disagree, and a decision system
        must not quietly average over that.
        """
        unit = self.business_unit(business_unit)
        center = self.cost_center(cost_center)
        resolved_account = self.account(account)

        if center.business_unit != unit.key:
            raise SemanticMappingError(
                f"Cost center {center.key!r} belongs to {center.business_unit!r}, "
                f"not {unit.key!r}"
            )

        try:
            declared = AccountCategory(account_category)
        except ValueError as exc:
            raise SemanticMappingError(
                f"Unknown account category: {account_category!r}"
            ) from exc

        if declared is not resolved_account.category:
            raise SemanticMappingError(
                f"Account {resolved_account.code!r} is governed as "
                f"{resolved_account.category.value!r} but the extract declared "
                f"{declared.value!r}"
            )

        return LedgerEntry(
            period=period,
            business_unit=unit,
            cost_center=center,
            account=resolved_account,
            amount=float(amount),
        )


#: The single governed model instance used by the application and the tests.
SEMANTIC_MODEL = SemanticModel(
    company=COMPANY_NAME,
    business_units=BUSINESS_UNITS,
    cost_centers=COST_CENTERS,
    accounts=ACCOUNTS,
    metrics=METRICS,
)
