from __future__ import annotations

import importlib

import yaml

from app.config import REPO_ROOT

CATALOG = yaml.safe_load((REPO_ROOT / "data" / "catalog" / "use_cases_v2.yml").read_text(encoding="utf-8"))
CONTRACTS = yaml.safe_load((REPO_ROOT / "semantic" / "metrics.yml").read_text(encoding="utf-8"))
ENTITIES = yaml.safe_load((REPO_ROOT / "ontology" / "entities.yml").read_text(encoding="utf-8"))
RELATIONSHIPS = yaml.safe_load((REPO_ROOT / "ontology" / "relationships.yml").read_text(encoding="utf-8"))

CASE_FIELDS = {"id", "domain", "title", "problem", "persona", "decision", "cadence", "source", "grain", "metrics",
               "deterministic_logic", "ai_role", "evidence", "approval", "action", "outcome_kpi", "dependencies",
               "status", "sprint", "acceptance_test", "portfolio"}


def test_catalogue_has_fifty_stable_cases_with_every_field():
    cases = CATALOG["use_cases"]
    assert [c["id"] for c in cases] == [f"UC{n:02d}" for n in range(1, 51)]
    for case in cases:
        assert CASE_FIELDS <= set(case), case["id"]
        assert case["status"] in CATALOG["statuses"], case["id"]
        assert case["sprint"] in CATALOG["sprints"], case["id"]


def test_only_active_cases_are_scheduled_in_margin_control_milestones():
    """The 50 cases are an opportunity portfolio; only ACTIVE cases drive the backlog (docs/product_backlog.md)."""
    assert CATALOG["active_product"] == "BENACTA Margin Control"
    for case in CATALOG["use_cases"]:
        assert case["portfolio"] in CATALOG["portfolio_classes"], case["id"]
        if case["sprint"] in {"M1", "M2", "M3"}:
            assert case["portfolio"] == "ACTIVE", case["id"]
        if case["portfolio"] == "ACTIVE":
            assert case["sprint"] in {"M1", "M2", "M3"} and case["domain"] in {"margin", "controls"}, case["id"]
        if case["portfolio"] == "OPPORTUNITY":
            assert case["status"] in {"Conference", "Hold"}, case["id"]


def test_no_case_is_marked_live_and_dependencies_exist():
    ids = {c["id"] for c in CATALOG["use_cases"]}
    assert "Live" not in CATALOG["statuses"]
    for case in CATALOG["use_cases"]:
        assert set(case["dependencies"]) <= ids, case["id"]


def test_contracts_have_required_keys_and_importable_calculations():
    required = set(CONTRACTS["required_keys"])
    seen = set()
    for contract in CONTRACTS["metrics"]:
        assert required <= set(contract), contract["metric_id"]
        assert contract["metric_id"] not in seen
        seen.add(contract["metric_id"])
        module, _, attribute = contract["calculation"].partition(":")
        assert hasattr(importlib.import_module(module), attribute), contract["calculation"]
        assert contract["certification"] in {"CERTIFIED", "CANDIDATE", "UNCERTIFIED"}
    assert not [c for c in CONTRACTS["metrics"] if c["certification"] == "CERTIFIED"], "no contract is certified without approval"


def test_requested_project_controlling_contracts_exist():
    ids = {c["metric_id"] for c in CONTRACTS["metrics"]}
    assert {"actual_cost", "open_commitments", "etc", "eac", "approved_budget", "forecast_revenue_at_completion",
            "forecast_margin_amount", "forecast_margin_pct", "billed_amount", "collected_amount", "overdue_amount",
            "planned_hours", "actual_hours", "available_capacity"} <= ids


def test_relationships_reference_defined_entities_and_no_observed_causality():
    entities = set(ENTITIES["entities"])
    for relation in RELATIONSHIPS["relationships"]:
        assert relation["from"] in entities and relation["to"] in entities, relation["type"]
        assert relation["status"] in {"OBSERVED", "HYPOTHETICAL"}
        if "EXPLAINS" in relation["type"] or "CAUSES" in relation["type"]:
            assert relation["status"] == "HYPOTHETICAL", relation["type"]
    for path in RELATIONSHIPS["bounded_paths"].values():
        assert set(path) <= entities
    required = {"Project", "WorkPackage", "Milestone", "Resource", "Skill", "Assignment", "TimesheetEntry", "BudgetVersion",
                "ForecastVersion", "PlanningAssumption", "ChangeOrder", "PurchaseCommitment", "Risk", "ReportingSnapshot"}
    assert required <= entities
