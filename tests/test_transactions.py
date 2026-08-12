"""
Transaction-level and budget-line-level reconciliation.

Phase 6 gave every root cause a set of source records. This phase goes one
level finer: the postings and planning lines that sum to the Actual and
Budget figures themselves, so a controller can answer "show me the
transactions" and "show me the budget" — not just "show me the explanation".

The load-bearing claim is unchanged in kind, only in grain: **every number
shown as traceable must actually be traceable**, to the cent, with the
difference reported rather than rounded away when it is not.
"""

from __future__ import annotations

import csv
import io

import pytest

from src.control_engine import evaluate
from src.finance_engine import FactGrain, fact_for, run_truth_layer
from src.lineage import (
    budget_lines_for_fact,
    load_budget_lines,
    load_source_records,
    load_transactions,
    reconcile,
    reconcile_actual,
    reconcile_budget,
    transactions_for_fact,
    transactions_to_csv,
    variance_reconciliation,
)


@pytest.fixture(scope="module")
def facts():
    _, computed = run_truth_layer()
    return computed


@pytest.fixture(scope="module")
def transactions():
    return load_transactions()


@pytest.fixture(scope="module")
def budget_lines():
    return load_budget_lines()


@pytest.fixture(scope="module")
def source_records():
    return load_source_records()


# --------------------------------------------------------------------------- #
# The extract
# --------------------------------------------------------------------------- #


def test_every_transaction_maps_to_a_governed_account(transactions):
    from src.domain import SEMANTIC_MODEL

    codes = {a.code for a in SEMANTIC_MODEL.accounts}
    assert transactions
    assert all(t.account in codes for t in transactions)


def test_transactions_carry_the_fields_a_controller_needs(transactions):
    for t in transactions:
        assert t.transaction_id and t.posting_date and t.document_number
        assert t.business_unit and t.account and t.cost_center
        assert t.currency == "EUR"
        assert t.amount > 0
        assert t.source_system and t.source_model


def test_transaction_and_budget_line_ids_are_unique(transactions, budget_lines):
    tx_ids = [t.transaction_id for t in transactions]
    bl_ids = [b.budget_line_id for b in budget_lines]
    assert len(tx_ids) == len(set(tx_ids))
    assert len(bl_ids) == len(set(bl_ids))


def test_transactions_and_budget_lines_share_the_actuals_cost_center(transactions, budget_lines):
    """
    Each account has exactly one cost center in actuals.csv/budget.csv. The
    elaborated rows must agree with it — a controller cross-checking the
    coarse extract against the fine one should never find a contradiction.
    """
    expected = {"700100": "CC-4100", "700200": "CC-4200", "700300": "CC-5100", "700400": "CC-5100"}
    for t in transactions:
        assert t.cost_center == expected[t.account], t.transaction_id
    for b in budget_lines:
        assert b.cost_center == expected[b.account], b.budget_line_id


# --------------------------------------------------------------------------- #
# Actual — transactions reconcile to the metric
# --------------------------------------------------------------------------- #


def test_revenue_actual_transactions_reconcile_to_metric(facts, transactions):
    revenue = fact_for(facts, "revenue")
    rows, check = reconcile_actual(revenue, transactions)

    assert len(rows) == 14
    assert check.source_total == revenue.actual == 4_720_000.00
    assert check.difference == 0.0
    assert check.reconciled


def test_revenue_actual_transactions_reconcile_per_account(facts, transactions):
    expected = {
        "700100": 2_255_000.00,
        "700200": 835_000.00,
        "700300": 1_262_000.00,
        "700400": 368_000.00,
    }
    for account, total in expected.items():
        fact = fact_for(facts, account, grain=FactGrain.ACCOUNT)
        rows, check = reconcile_actual(fact, transactions)
        assert check.source_total == total, account
        assert check.reconciled, account
        assert fact.actual == total


def test_revenue_actual_transactions_reconcile_per_business_unit(facts, transactions):
    for unit, expected in (("BU-PRJ", 3_090_000.00), ("BU-SVC", 1_630_000.00)):
        fact = fact_for(
            facts, "revenue", grain=FactGrain.METRIC_BY_BUSINESS_UNIT, business_unit=unit
        )
        rows, check = reconcile_actual(fact, transactions)
        assert all(row.business_unit == unit for row in rows)
        assert check.source_total == expected
        assert check.reconciled


# --------------------------------------------------------------------------- #
# Budget — planning lines reconcile to the metric
# --------------------------------------------------------------------------- #


def test_revenue_budget_lines_reconcile_to_metric(facts, budget_lines):
    revenue = fact_for(facts, "revenue")
    rows, check = reconcile_budget(revenue, budget_lines)

    assert len(rows) == 16
    assert check.source_total == revenue.budget == 5_000_000.00
    assert check.difference == 0.0
    assert check.reconciled


def test_budget_includes_the_two_slipped_milestones_with_no_matching_transaction(
    facts, transactions, budget_lines
):
    """
    This is the whole story in one test: the budget assumed MS-2214 and
    MS-2231 would post in July. They are in the budget lines. They are not in
    the transactions. That absence is the variance.
    """
    milestone_account = fact_for(facts, "700100", grain=FactGrain.ACCOUNT)
    budget_rows = budget_lines_for_fact(milestone_account, budget_lines)
    tx_rows = transactions_for_fact(milestone_account, transactions)

    slipped_ids = {"MS-2214", "MS-2231"}
    budgeted_milestones = {row.milestone_id for row in budget_rows if row.milestone_id}
    posted_milestones = {row.milestone_id for row in tx_rows if row.milestone_id}

    assert slipped_ids <= budgeted_milestones
    assert slipped_ids.isdisjoint(posted_milestones)

    slipped_budget = sum(row.amount for row in budget_rows if row.milestone_id in slipped_ids)
    assert slipped_budget == 345_000.00


# --------------------------------------------------------------------------- #
# Variance — the derived calculation, not a transaction
# --------------------------------------------------------------------------- #


def test_revenue_variance_reconciles_actual_and_budget(facts):
    revenue = fact_for(facts, "revenue")
    check, ok = variance_reconciliation(revenue)

    assert ok
    assert check.displayed == -280_000.00
    assert check.source_total == pytest.approx(revenue.actual - revenue.budget)
    assert check.difference == 0.0


def test_variance_reconciliation_holds_for_every_headline_metric(facts):
    for key in ("revenue", "gross_margin", "operating_expenses", "ebitda"):
        check, ok = variance_reconciliation(fact_for(facts, key))
        assert ok, key


def test_variance_reconciliation_is_trivially_true_with_no_budget(facts):
    """An account with no budget line has no variance to reconcile — not an error."""
    workshop = fact_for(facts, "628400", grain=FactGrain.ACCOUNT)
    check, ok = variance_reconciliation(workshop)
    assert ok
    assert check.displayed is None


# --------------------------------------------------------------------------- #
# Business-unit contribution reconciles to the group variance
# --------------------------------------------------------------------------- #


def test_business_unit_contributions_reconcile_to_revenue_variance(facts):
    revenue = fact_for(facts, "revenue")
    projects = fact_for(
        facts, "revenue", grain=FactGrain.METRIC_BY_BUSINESS_UNIT, business_unit="BU-PRJ"
    )
    service = fact_for(
        facts, "revenue", grain=FactGrain.METRIC_BY_BUSINESS_UNIT, business_unit="BU-SVC"
    )
    assert projects.variance + service.variance == pytest.approx(revenue.variance)


# --------------------------------------------------------------------------- #
# Root cause reconciles to attributed source records
# --------------------------------------------------------------------------- #


def test_root_cause_source_records_reconcile_to_attributed_impact(facts, source_records):
    revenue = fact_for(facts, "revenue")
    attribution = reconcile(revenue, source_records)
    milestone_cause = attribution.causes[0]

    assert milestone_cause.impact_eur == sum(r.impact_eur for r in milestone_cause.records)
    assert milestone_cause.impact_eur == -345_000.00


def test_residual_decomposes_to_real_unattributed_accounts(facts, source_records):
    """
    The +€65k left over after the milestone cause is not narrative filler: it
    is exactly account 700200 (Engineering Services) plus the whole of
    Service & Maintenance revenue — both real, both traceable via the
    Financial Transactions tab, neither currently assigned a root-cause
    narrative.
    """
    revenue = fact_for(facts, "revenue")
    attribution = reconcile(revenue, source_records)

    engineering = fact_for(facts, "700200", grain=FactGrain.ACCOUNT)
    service = fact_for(
        facts, "revenue", grain=FactGrain.METRIC_BY_BUSINESS_UNIT, business_unit="BU-SVC"
    )
    assert attribution.residual == pytest.approx(engineering.variance + service.variance)


# --------------------------------------------------------------------------- #
# Traceability existence
# --------------------------------------------------------------------------- #


def test_trace_source_records_exist(facts, source_records, transactions):
    """
    Every HIGH-severity attention item is traceable to structured rows — via
    the transaction ledger where one exists (Revenue), and via root-cause
    source records everywhere else (the cost-side causes). Both are real,
    row-level data; which one applies depends on what was built for this
    metric, not on which is more convenient to fake.
    """
    alerts = evaluate(facts)
    high = [a for a in alerts if a.severity.value == "HIGH"]
    assert high
    for alert in high:
        grain = FactGrain.ACCOUNT if alert.account else FactGrain.METRIC
        fact = fact_for(facts, alert.metric, grain=grain)
        has_transactions = bool(transactions_for_fact(fact, transactions))
        has_source_records = reconcile(fact, source_records).has_causes
        assert has_transactions or has_source_records, alert.metric


def test_revenue_is_the_only_metric_with_full_transaction_coverage(facts, transactions):
    """
    Documents the deliberate scope boundary: Revenue is elaborated to
    transaction grain because it is the flagship trace-to-source example.
    Operating Expenses (a pure cost metric) has no transaction ledger at all;
    Gross Margin and EBITDA include Revenue's accounts on their positive side,
    so they see partial coverage, but neither reconciles fully — their cost
    side remains traceable only through root-cause source records, not a
    full ledger. The test asserts the boundary rather than papering over it.
    """
    revenue = fact_for(facts, "revenue")
    rows, check = reconcile_actual(revenue, transactions)
    assert rows and check.reconciled

    opex = fact_for(facts, "operating_expenses")
    assert transactions_for_fact(opex, transactions) == ()

    for key in ("gross_margin", "ebitda"):
        fact = fact_for(facts, key)
        _, check = reconcile_actual(fact, transactions)
        assert not check.reconciled, f"{key} should NOT fully reconcile from revenue-only data"


# --------------------------------------------------------------------------- #
# CSV export
# --------------------------------------------------------------------------- #


def test_csv_export_contains_selected_transactions(facts, transactions):
    revenue = fact_for(facts, "revenue")
    rows, _ = reconcile_actual(revenue, transactions)

    csv_text = transactions_to_csv(rows)
    parsed = list(csv.DictReader(io.StringIO(csv_text)))

    assert len(parsed) == len(rows)
    assert {p["transaction_id"] for p in parsed} == {r.transaction_id for r in rows}
    assert sum(float(p["amount"]) for p in parsed) == pytest.approx(revenue.actual)


def test_csv_export_is_scoped_not_the_whole_dataset(facts, transactions):
    """The export for one account must not leak rows from other accounts."""
    engineering = fact_for(facts, "700200", grain=FactGrain.ACCOUNT)
    rows, _ = reconcile_actual(engineering, transactions)
    csv_text = transactions_to_csv(rows)
    parsed = list(csv.DictReader(io.StringIO(csv_text)))

    assert len(parsed) == 3
    assert all(p["account"] == "700200" for p in parsed)


def test_csv_export_omits_no_internal_state(facts, transactions):
    """The exported CSV is business columns only — no session/app internals."""
    revenue = fact_for(facts, "revenue")
    rows, _ = reconcile_actual(revenue, transactions)
    csv_text = transactions_to_csv(rows)
    header = csv_text.splitlines()[0]
    assert "session" not in header.lower()
    assert "reviewer" not in header.lower()
