from __future__ import annotations

from decimal import Decimal

from app.config import REPO_ROOT
from app.planning.domain import Actor, Role
from app.planning.importer import ImportContext, parse_csv, validate

CONTROLLER = Actor("controller", frozenset({Role.PROJECT_CONTROLLER}), frozenset({1}))
CTX = ImportContext(company_id=1, source_instance="test", known_projects={"PRJ-EXAMPLE": "PLANTS"})


def row(**overrides):
    base = {"project_code": "PRJ-EXAMPLE", "version_type": "FORECAST", "scenario": "BASE", "label": "FC-2026-09",
            "cutoff_date": "2026-09-30", "currency": "EUR", "business_unit": "PLANTS", "work_package": "WP20",
            "cost_category": "LABOUR", "resource_or_role": "EN", "period": "2026-10", "planned_hours": "160",
            "planned_rate": "80", "planned_cost": "12800", "planned_revenue": "", "planned_billing": "", "planned_cash_collection": ""}
    base.update(overrides)
    return base


def codes(issues):
    return {issue.code for issue in issues}


def test_template_file_is_valid():
    rows = parse_csv((REPO_ROOT / "data" / "templates" / "plan_lines_template.csv").read_bytes())
    staged, issues, totals = validate(rows, CTX, CONTROLLER)
    assert not issues, issues
    assert totals["planned_cost"] == Decimal(57800)


def test_empty_cell_stays_null_never_zero():
    staged, issues, _ = validate([row(cost_category="SUBCONTRACT", resource_or_role="", planned_hours="", planned_rate="", planned_cost="45000")],
                                 CTX, CONTROLLER)
    assert not issues
    assert staged[0].values["planned_hours"] is None
    assert staged[0].values["planned_cost"] == Decimal(45000)


def test_all_errors_are_reported_with_row_numbers():
    rows = [row(), row(), row(period="2026-09"), row(planned_cost="12000"), row(currency="eur"), row(cost_category="TRAVEL", planned_hours="abc")]
    _, issues, _ = validate(rows, CTX, CONTROLLER)
    found = codes(issues)
    assert {"DUPLICATE_ROW", "PERIOD_NOT_AFTER_CUTOFF", "COST_NOT_HOURS_TIMES_RATE", "MIXED_VERSIONS", "INVALID_CATEGORY", "INVALID_NUMBER"} <= found
    assert any(i.row_number == 3 and i.code == "DUPLICATE_ROW" for i in issues)


def test_unknown_project_business_unit_and_rights():
    assert "UNKNOWN_PROJECT" in codes(validate([row(project_code="PRJ-404")], CTX, CONTROLLER)[1])
    assert "BUSINESS_UNIT_MISMATCH" in codes(validate([row(business_unit="SERVICES")], CTX, CONTROLLER)[1])
    viewer = Actor("viewer", frozenset({Role.VIEWER}), frozenset({1}))
    assert "NOT_AUTHORISED" in codes(validate([row()], CTX, viewer)[1])
    other_company = Actor("controller-b", frozenset({Role.PROJECT_CONTROLLER}), frozenset({2}))
    assert "NOT_AUTHORISED" in codes(validate([row()], CTX, other_company)[1])


def test_revenue_and_cost_measures_do_not_mix():
    revenue_with_cost = row(cost_category="REVENUE", resource_or_role="", planned_billing="1000")
    assert "MEASURE_NOT_ALLOWED" in codes(validate([revenue_with_cost], CTX, CONTROLLER)[1])
    cost_with_billing = row(planned_billing="1000")
    assert "MEASURE_NOT_ALLOWED" in codes(validate([cost_with_billing], CTX, CONTROLLER)[1])


def test_control_totals_and_decimal_comma():
    ctx = ImportContext(company_id=1, source_instance="test", known_projects={"PRJ-EXAMPLE": "PLANTS"},
                        expected_totals={"planned_cost": Decimal("12800.5")})
    _, issues, totals = validate([row(planned_hours="", planned_rate="", planned_cost="12800,5")], ctx, CONTROLLER)
    assert not issues and totals["planned_cost"] == Decimal("12800.5")
    _, issues, _ = validate([row()], ctx, CONTROLLER)
    assert "CONTROL_TOTAL_MISMATCH" in codes(issues)


def test_forecast_requires_cutoff():
    assert "MISSING_VALUE" in codes(validate([row(cutoff_date="")], CTX, CONTROLLER)[1])
