"""The margin engine must reproduce every expected outcome of the hand-written oracle on dataset demo_v1,
raise nothing on background orders, and keep cases stable when the pipeline is replayed."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa

from app.audit.log import verify_chain
from app.fixtures.demo_dataset import build_demo_dataset
from app.ingestion.runner import FOUNDATION_MODELS, ingest
from app.ingestion.sources import FixtureSource
from app.margin import reference
from app.margin.engine import run_engine
from app.marts.build import build_marts
from app.marts.reconcile import reconcile
from app.ops.discover_odoo import load_spec
from tests.oracle import case, dec, load_oracle

LINE_RULES = {"DISCOUNT_CAP", "PRICE_BELOW_BASELINE", "COST_REFERENCE_VARIANCE"}


@pytest.fixture(scope="module")
def oracle():
    return load_oracle()


@pytest.fixture(scope="module")
def built(engine):
    dataset = build_demo_dataset()
    source = FixtureSource(dataset, source_instance=f"fixture_margin_{uuid.uuid4().hex[:8]}")
    batch = ingest(engine, source, load_spec(), models=FOUNDATION_MODELS)
    build_marts(engine, batch.batch_id)
    reconcile(engine, source, batch.batch_id)
    rows = reference.rows_from_terms(dataset.terms, owner="test", source="fixture terms")
    with engine.begin() as conn:
        reference.store_reference(conn, rows, source_instance=source.source_instance, company_id=1, source_kind="FIXTURE_TERMS", source_ref="demo_v1")
    run = run_engine(engine, batch.batch_id)
    return {"engine": engine, "snapshot": batch.batch_id, "source": source, "run": run, "dataset": dataset}


def q(built, sql: str, **params):
    with built["engine"].connect() as c:
        return c.execute(sa.text(sql), {"s": built["snapshot"], **params}).mappings().all()


def evaluation(built, rule: str, subject_type: str, order: str, product: str | None = None):
    if subject_type == "sale_order_line":
        rows = q(built, """
            select e.* from marts.fact_margin_rule_evaluation e
            join marts.fact_sales_order_line f on f.snapshot_id = e.snapshot_id and f.sale_line_id = e.subject_id
            join marts.dim_product p on p.snapshot_id = f.snapshot_id and p.product_id = f.product_id
            where e.snapshot_id = :s and e.rule_id = :r and e.subject_type = 'sale_order_line' and f.order_name = :o and p.default_code = :p""",
                 r=rule, o=order, p=product)
    elif subject_type == "sale_order":
        rows = q(built, """
            select e.* from marts.fact_margin_rule_evaluation e
            join (select distinct snapshot_id, sale_order_id, order_name from marts.fact_sales_order_line) f
              on f.snapshot_id = e.snapshot_id and f.sale_order_id = e.subject_id
            where e.snapshot_id = :s and e.rule_id = :r and e.subject_type = 'sale_order' and f.order_name = :o""", r=rule, o=order)
    else:
        rows = q(built, """
            select e.* from marts.fact_margin_rule_evaluation e
            join marts.fact_invoice_line i on i.snapshot_id = e.snapshot_id and i.invoice_line_id = e.subject_id
            where e.snapshot_id = :s and e.rule_id = :r and e.subject_type = 'invoice_line' and i.invoice_name = :o""", r=rule, o=order)
    assert len(rows) == 1, (rule, order, product, rows)
    return rows[0]


def _subject(c: dict) -> tuple[str, str, str | None]:
    subject = c["subject"]
    if subject["type"] == "sale_order_line":
        return "sale_order_line", subject["order"], subject["product"]
    if subject["type"] == "sale_order":
        return "sale_order", subject["order"], None
    return "invoice_line", subject["invoice"], None


def _check_expected(row, expected: dict) -> None:
    assert row["outcome"] == expected["status"]
    assert row["classification"] == expected["classification"]
    if "cause" in expected:
        assert row["cause"] == expected["cause"]
    for key in ("exposure_type", "component", "severity", "controllability"):
        if key in expected:
            assert row[key] == expected[key], key
    for key, column in (("expected_amount", "expected_amount"), ("actual_amount", "actual_amount"),
                        ("adverse_exposure", "adverse_exposure"), ("potential_exposure", "potential_exposure")):
        if key in expected:
            if expected[key] is None:
                assert row[column] is None, key
            elif dec(expected[key]) == 0 and expected["status"] != "VIOLATION":
                assert row[column] in (None, Decimal(0)), key  # no exposure computed on a compliant outcome
            else:
                assert row[column] == dec(expected[key]), key
    if "requires_human_review" in expected:
        assert row["requires_human_review"] is expected["requires_human_review"]


@pytest.mark.parametrize("case_id", ["DISC-001", "FREIGHT-001", "COST-001", "PRICE-001", "PLIST-001", "FREIGHT-002", "NEG-01", "NEG-02",
                                     "NEG-03", "NEG-04", "NEG-05", "NEG-06", "NEG-07", "NEG-08", "NEG-09", "NEG-10", "NEG-11"])
def test_oracle_case(built, oracle, case_id):
    c = case(oracle, case_id)
    expected = c["expected"]
    subject_type, ref, product = _subject(c)
    row = evaluation(built, expected["rule"], subject_type, ref, product)
    _check_expected(row, expected)
    if expected["status"] == "VIOLATION":
        assert row["exposure_stage"] == "INVOICED" and row["confidence"] == "HIGH"
        assert row["material"] == (row["adverse_exposure"] >= Decimal(200))
    if "baseline_level" in expected:
        assert row["evidence"]["baseline"]["level"] == expected["baseline_level"]


def test_cancelled_order_lines_are_excluded_by_every_line_rule(built):
    rows = q(built, """
        select e.rule_id, e.outcome, e.classification, e.cause from marts.fact_margin_rule_evaluation e
        join marts.fact_sales_order_line f on f.snapshot_id = e.snapshot_id and f.sale_line_id = e.subject_id
        where e.snapshot_id = :s and e.subject_type = 'sale_order_line' and f.order_name = 'BD/SO/NEG-05' order by e.rule_id""")
    assert {r["rule_id"] for r in rows} == LINE_RULES
    assert {(r["outcome"], r["classification"], r["cause"]) for r in rows} == {("EXCLUDED", "NOT_APPLICABLE", "ORDER_CANCELLED")}


def test_neg_12_two_exceptions_on_one_line_are_both_kept(built, oracle):
    expected = case(oracle, "NEG-12")["expected"]
    for item in expected["exceptions"]:
        row = evaluation(built, item["rule"], "sale_order_line", "BD/SO/NEG-12", "SC5")
        _check_expected(row, {**item, "status": "VIOLATION"})
    groups = q(built, "select overlap_group, count(*) as n from marts.fact_margin_rule_evaluation where snapshot_id = :s"
                      " and classification = 'CONFIRMED_LEAKAGE' group by 1 having count(*) > 1")
    assert len(groups) == 1 and groups[0]["n"] == 2


def test_totals_and_no_exception_on_background_orders(built, oracle):
    totals = oracle["totals"]["whole_dataset"]
    by_type = {r["exposure_type"]: r["total"] for r in q(
        built, "select exposure_type, sum(adverse_exposure) as total from marts.fact_margin_rule_evaluation where snapshot_id = :s"
               " and classification in ('CONFIRMED_LEAKAGE', 'PROBABLE_LEAKAGE') group by 1")}
    assert by_type.get("discount", Decimal(0)) == dec(totals["discount_leakage"])
    assert by_type.get("price", Decimal(0)) == dec(totals["price_leakage"])
    assert by_type.get("freight", Decimal(0)) == dec(totals["freight_leakage"])
    assert by_type["discount"] + by_type.get("price", Decimal(0)) + by_type["freight"] == dec(totals["billing_leakage"])
    assert by_type["cost"] == dec(totals["cost_variance"])
    confirmed = q(built, "select count(*) as n from marts.fact_margin_rule_evaluation where snapshot_id = :s and classification = 'CONFIRMED_LEAKAGE'")
    assert confirmed[0]["n"] == totals["confirmed_leakage_exceptions"]
    background = q(built, """
        select e.subject_ref, e.rule_id, e.classification from marts.fact_margin_rule_evaluation e
        where e.snapshot_id = :s and e.classification not in ('COMPLIANT', 'NOT_APPLICABLE', 'EXPLAINED_VARIANCE')
          and e.subject_ref not like 'BD/SO/DISC-%' and e.subject_ref not like 'BD/SO/FREIGHT-%' and e.subject_ref not like 'BD/SO/COST-%'
          and e.subject_ref not like 'BD/SO/NEG-%' and e.subject_ref not like 'BD/INV/NEG-%'
          and e.subject_ref not like 'BD/SO/PRICE-%' and e.subject_ref not like 'BD/SO/PLIST-%'""")
    assert background == [], background
    assert not q(built, "select 1 from marts.fact_margin_rule_evaluation where snapshot_id = :s and classification = 'PROBABLE_LEAKAGE'"), (
        "every violation on the fixture is backed by reconciled, fully linked evidence"
    )


def test_cases_are_created_for_actionable_outcomes_only(built, oracle):
    totals = oracle["totals"]["whole_dataset"]
    cases = q(built, "select case_ref, classification, cause, status, rule_id from decision.exception_case where source_instance = :i order by case_ref",
              i=built["source"].source_instance)
    by_class = {}
    for c in cases:
        by_class[c["classification"]] = by_class.get(c["classification"], 0) + 1
    assert by_class["CONFIRMED_LEAKAGE"] == totals["confirmed_leakage_cases"]
    below_materiality = q(built, "select subject_ref, material from marts.fact_margin_rule_evaluation where snapshot_id = :s"
                                 " and classification = 'CONFIRMED_LEAKAGE' and not material")
    assert [r["subject_ref"] for r in below_materiality] == ["BD/SO/FREIGHT-002"], "confirmed but immaterial: counted, not queued"
    assert by_class.get("DATA_QUALITY_ISSUE", 0) + by_class.get("INSUFFICIENT_EVIDENCE", 0) == totals["cases_requiring_human_review"]
    assert all(c["status"] == "NEW" for c in cases)
    assert all(c["case_ref"].startswith("MC-") for c in cases)
    legitimate = q(built, "select count(*) as n from marts.fact_margin_rule_evaluation where snapshot_id = :s and classification = 'LEGITIMATE_EXCEPTION'")
    assert legitimate[0]["n"] == totals["legitimate_exceptions"]
    assert not q(built, """select 1 from decision.exception_case c join marts.fact_margin_rule_evaluation e on e.snapshot_id = :s
                  and e.rule_id = c.rule_id and e.subject_type = c.subject_type and e.subject_id = c.subject_id
                  where c.source_instance = :i and e.classification in ('COMPLIANT', 'LEGITIMATE_EXCEPTION', 'EXPLAINED_VARIANCE', 'NOT_APPLICABLE')""",
                 i=built["source"].source_instance), "no case for a compliant, legitimate or explained evaluation"


def test_period_margin_ties_to_reconciled_facts(built):
    periods = q(built, "select * from marts.fact_margin_period where snapshot_id = :s order by period")
    assert [p["period"] for p in periods] == ["2026-06", "2026-07", "2026-08"]
    for p in periods:
        revenue = q(built, "select sum(revenue_company_ccy) as v from marts.fact_invoice_line where snapshot_id = :s and to_char(accounting_date, 'YYYY-MM') = :p", p=p["period"])[0]["v"]
        cogs = q(built, "select sum(balance) as v from marts.fact_posted_cogs_line where snapshot_id = :s and to_char(accounting_date, 'YYYY-MM') = :p", p=p["period"])[0]["v"]
        assert p["revenue"] == revenue and p["cogs"] == cogs and p["gross_margin"] == revenue - cogs
        assert p["margin_basis"] == "RECONCILED_COGS" and p["margin_status"] == "OK"
        assert p["gross_margin_pct"] == (p["gross_margin"] * 100 / p["revenue"]).quantize(Decimal("0.01"))
    july = next(p for p in periods if p["period"] == "2026-07")
    assert (july["discount_leakage"], july["price_leakage"], july["freight_leakage"], july["cost_leakage"]) == (
        Decimal("1000.00"), Decimal("1000.00"), Decimal("250.00"), Decimal("800.00"))
    assert july["recoverable_from_customer"] == Decimal("2250.00") and july["total_addressable_leakage"] == Decimal("3050.00")
    august = next(p for p in periods if p["period"] == "2026-08")
    assert (august["discount_leakage"], august["freight_leakage"], august["cost_leakage"]) == (Decimal("500.00"), Decimal("150.00"), Decimal("400.00"))
    assert sum(p["discount_leakage"] + p["price_leakage"] + p["freight_leakage"] + p["cost_leakage"] for p in periods) == Decimal("4100.00")
    assert sum(p["untraceable_revenue"] for p in periods) == Decimal("650.00")


def test_replay_keeps_cases_stable_and_is_audited(built):
    before = q(built, "select case_ref, exception_key, first_snapshot_id from decision.exception_case where source_instance = :i order by case_ref",
               i=built["source"].source_instance)
    again = run_engine(built["engine"], built["snapshot"])
    after = q(built, "select case_ref, exception_key, first_snapshot_id from decision.exception_case where source_instance = :i order by case_ref",
              i=built["source"].source_instance)
    assert after == before and again.cases_created == 0 and again.cases_updated == len(before)
    assert len(again.evaluations) == len(built["run"].evaluations)
    with built["engine"].connect() as c:
        assert verify_chain(c).valid
        actions = c.execute(sa.text("select count(*) from audit.event where action = 'margin.exceptions_computed' and object_id = :s"),
                            {"s": str(built["snapshot"])}).scalar()
    assert actions == 2


def test_evidence_bundle_carries_rule_inputs_and_thresholds(built):
    row = evaluation(built, "DISCOUNT_CAP", "sale_order_line", "BD/SO/DISC-001", "SC1")
    evidence = row["evidence"]
    assert evidence["applied_policy"]["policy_id"] == "POL-DISC-STANDARD" and evidence["allowed_discount_pct"] == "5"
    assert evidence["invoices"] and evidence["invoices"][0]["allocation_weight"] == "1"
    assert evidence["thresholds"] == row["thresholds_version"] and row["formula"]
    assert evidence["period_revenue_reconciled"] is True


def test_case_is_closed_with_a_reason_when_the_source_is_corrected(built):
    """A later snapshot where the discount was corrected closes the case with the reason, instead of deleting it."""
    engine, source = built["engine"], built["source"]
    line = next(r for r in source.dataset.records["sale.order.line"] if r["order_id"][1] == "BD/SO/DISC-001")
    original = (line["discount"], line["price_subtotal"], line["write_date"])
    line["discount"], line["price_subtotal"], line["write_date"] = 5.0, 9500.0, "2026-09-01 08:00:00"
    try:
        batch = ingest(engine, source, load_spec(), models=FOUNDATION_MODELS)
        build_marts(engine, batch.batch_id)
        reconcile(engine, source, batch.batch_id)
        run = run_engine(engine, batch.batch_id)
        assert run.cases_resolved == 1
        resolved = q(built, "select status, resolved_snapshot_id, resolved_note from decision.exception_case where source_instance = :i"
                            " and status = 'NO_LONGER_RAISED'", i=source.source_instance)
        assert len(resolved) == 1 and resolved[0]["resolved_snapshot_id"] == batch.batch_id
        assert "COMPLIANT" in resolved[0]["resolved_note"] and "WITHIN_POLICY" in resolved[0]["resolved_note"]
    finally:
        line["discount"], line["price_subtotal"], line["write_date"] = original
