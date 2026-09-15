"""Planning vocabulary shared by import, services and metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class VersionType(StrEnum):
    BUDGET_BASELINE = "BUDGET_BASELINE"
    BUDGET_REVISED = "BUDGET_REVISED"
    FORECAST = "FORECAST"


class Scenario(StrEnum):
    BASE = "BASE"
    FAVOURABLE = "FAVOURABLE"
    UNFAVOURABLE = "UNFAVOURABLE"
    PENDING_CO = "PENDING_CO"


class VersionStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    LOCKED = "LOCKED"


COST_CATEGORIES = ("LABOUR", "SUBCONTRACT", "MATERIALS", "CONTINGENCY", "OTHER")
REVENUE_CATEGORY = "REVENUE"
ALL_CATEGORIES = (*COST_CATEGORIES, REVENUE_CATEGORY)

COST_MEASURES = ("planned_hours", "planned_rate", "planned_cost")
REVENUE_MEASURES = ("planned_revenue", "planned_billing", "planned_cash_collection")
MEASURES = (*COST_MEASURES, *REVENUE_MEASURES)

CSV_COLUMNS = (
    "project_code",
    "version_type",
    "scenario",
    "label",
    "cutoff_date",
    "currency",
    "business_unit",
    "work_package",
    "cost_category",
    "resource_or_role",
    "period",
    *MEASURES,
)
VERSION_HEADER_COLUMNS = ("project_code", "version_type", "scenario", "label", "cutoff_date", "currency")


class Role(StrEnum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    PROJECT_CONTROLLER = "project_controller"
    FINANCE_APPROVER = "finance_approver"
    ADMIN = "admin"


@dataclass(frozen=True)
class Actor:
    """Server-side identity. Roles are never taken from client input."""

    user_id: str
    roles: frozenset[Role]
    company_ids: frozenset[int]
    project_codes: frozenset[str] | None = None  # None: every project of the allowed companies

    def can(self, role: Role) -> bool:
        return role in self.roles

    def can_access_project(self, company_id: int, project_code: str) -> bool:
        if company_id not in self.company_ids:
            return False
        return self.project_codes is None or project_code in self.project_codes


@dataclass
class ValidationIssue:
    row_number: int
    code: str
    message: str
    field: str | None = None


@dataclass
class ImportResult:
    import_id: str
    status: str
    version_id: str | None
    errors: list[ValidationIssue] = field(default_factory=list)
    totals: dict[str, str] = field(default_factory=dict)
