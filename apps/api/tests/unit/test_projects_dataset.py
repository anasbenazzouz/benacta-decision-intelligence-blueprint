from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal

import pytest

from app.config import REPO_ROOT
from app.fixtures.demo_dataset import build_demo_dataset
from app.fixtures.projects_dataset import extend_with_projects
from tests.oracle import dec, load_projects_oracle


@pytest.fixture(scope="module")
def v1():
    return build_demo_dataset()


@pytest.fixture(scope="module")
def v2(v1):
    return extend_with_projects(v1)


def digest(records) -> str:
    return hashlib.sha256(json.dumps(records, sort_keys=True, default=str).encode()).hexdigest()


def test_extension_is_deterministic_and_leaves_demo_v1_untouched(v1, v2):
    assert digest(v1.records) == digest(build_demo_dataset().records)
    assert digest(v2.records) == digest(extend_with_projects(build_demo_dataset()).records)
    for model, rows in v1.records.items():
        assert v2.records[model][: len(rows)] == rows, model


def test_dataset_is_identical_across_processes_with_different_hash_seeds():
    """Set iteration order changes with PYTHONHASHSEED; a replay in a new process must not create versions."""
    script = (
        "import hashlib, json;"
        "from app.fixtures.demo_dataset import build_demo_dataset;"
        "from app.fixtures.projects_dataset import extend_with_projects;"
        "ds = extend_with_projects(build_demo_dataset());"
        "print(hashlib.sha256(json.dumps([ds.records, [(p.label, p.project_code, p.rows) for p in ds.plans]],"
        " sort_keys=True, default=str).encode()).hexdigest())"
    )
    digests = {
        subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True,  # noqa: S603 constant script
                       env={**os.environ, "PYTHONHASHSEED": seed}, cwd=REPO_ROOT / "apps" / "api").stdout.strip()
        for seed in ("1", "2", "3")
    }
    assert len(digests) == 1


def test_anchor_must_be_a_month_end():
    with pytest.raises(ValueError, match="last day of a month"):
        extend_with_projects(build_demo_dataset(anchor=date(2026, 8, 30)))


def test_portfolio_structure_matches_oracle(v2):
    oracle = load_projects_oracle()["portfolio"]
    projects = v2.records["project.project"]
    internal = [p for p in projects if not p["allow_milestones"]]
    assert len(projects) - len(internal) == oracle["delivery_projects"]
    assert len(internal) == oracle["internal_projects"]
    assert len(v2.records["hr.employee"]) == oracle["employees"]
    assert sum(1 for e in v2.records["hr.employee"] if e["x_benacta_is_external"]) == oracle["external_employees"]
    labels = {p.label for p in v2.plans if p.version_type == "FORECAST"}
    assert labels == set(oracle["forecast_labels"])


def test_generated_transactions_realise_oracle_actual_costs(v2):
    """Independent of the engine: recompute actual cost from raw records."""
    oracle = load_projects_oracle()
    cutoff = oracle["cutoff"]
    accounts = {a["id"]: a["code"] for a in v2.records["account.analytic.account"]}
    project_code = {p["id"]: accounts[p["account_id"][0]] for p in v2.records["project.project"]}
    line_project = {line["id"]: accounts[int(next(iter(line["analytic_distribution"])))]
                    for line in v2.records["purchase.order.line"] if line.get("analytic_distribution")}
    actual = defaultdict(Decimal)
    for entry in v2.records["account.analytic.line"]:
        if entry["date"] <= cutoff:
            actual[project_code[entry["project_id"][0]]] -= Decimal(str(entry["amount"]))
    for line in v2.records["account.move.line"]:
        if line.get("purchase_line_id") and line["display_type"] == "product" and line["date"] <= cutoff:
            actual[line_project[line["purchase_line_id"][0]]] += Decimal(str(line["balance"]))
    for code, expected in oracle["projects"].items():
        assert actual[code] == dec(expected["actual_cost"]), code


def test_plan_files_never_leave_labour_hours_empty(v2):
    for plan in v2.plans:
        for row in plan.rows:
            if row["cost_category"] == "LABOUR":
                assert row["planned_hours"] != "", (plan.project_code, plan.label)
