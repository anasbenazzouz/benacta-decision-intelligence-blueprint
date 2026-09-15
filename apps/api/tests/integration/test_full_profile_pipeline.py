"""The whole pipeline on the three-year demonstration profile, checked against its ground-truth manifest.

Opt-in (`BENACTA_FULL_PROFILE=1`): ingesting about 130 000 records, building the marts, reconciling 36 months and
running the rules takes minutes on the embedded database.
"""

from __future__ import annotations

import time
import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa

from app.fixtures.full_profile import build_full_profile, ground_truth
from app.ingestion.runner import FOUNDATION_MODELS, ingest
from app.ingestion.sources import FixtureSource
from app.margin import reference
from app.margin.engine import run_engine
from app.margin.service import margin_overview
from app.marts.build import build_marts
from app.marts.reconcile import reconcile
from app.ops.discover_odoo import load_spec

pytestmark = pytest.mark.full_profile


@pytest.fixture(scope="module")
def built(engine):
    timings = {}
    t = time.time()
    dataset = build_full_profile()
    timings["generate"] = time.time() - t
    source = FixtureSource(dataset, source_instance=f"fixture_full_{uuid.uuid4().hex[:8]}")
    t = time.time()
    batch = ingest(engine, source, load_spec(), models=(*FOUNDATION_MODELS, "account.payment"))
    timings["ingest"] = time.time() - t
    t = time.time()
    build_marts(engine, batch.batch_id)
    timings["marts"] = time.time() - t
    t = time.time()
    results = reconcile(engine, source, batch.batch_id)
    timings["reconcile"] = time.time() - t
    with engine.begin() as conn:
        reference.store_reference(conn, reference.rows_from_terms(dataset.terms, owner="test", source="fixture"),
                                  source_instance=source.source_instance, company_id=1, source_kind="FIXTURE_TERMS", source_ref="demo_full")
    t = time.time()
    run = run_engine(engine, batch.batch_id)
    timings["rules"] = time.time() - t
    return {"engine": engine, "snapshot": batch.batch_id, "source": source, "manifest": ground_truth(dataset), "reconciliation": results,
            "run": run, "timings": timings}


def q(built, sql: str, **params):
    with built["engine"].connect() as c:
        return c.execute(sa.text(sql), {"s": built["snapshot"], **params}).mappings().all()


def test_every_month_reconciles(built):
    statuses = {(r.check_id, r.status) for r in built["reconciliation"]}
    assert statuses == {("REVENUE_POSTED", "RECONCILED"), ("COGS_POSTED", "RECONCILED"), ("INVOICE_HEADER_LINES", "RECONCILED")}
    assert len({r.period for r in built["reconciliation"]}) >= 36
    print({k: round(v, 1) for k, v in built["timings"].items()})


def _evaluation(built, scenario):
    subject, rule = scenario["subject"], scenario["rule"]
    if subject["type"] == "sale_order_line":
        rows = q(built, """
            select e.* from marts.fact_margin_rule_evaluation e
            join marts.fact_sales_order_line f on f.snapshot_id = e.snapshot_id and f.sale_line_id = e.subject_id
            join marts.dim_product p on p.snapshot_id = f.snapshot_id and p.product_id = f.product_id
            where e.snapshot_id = :s and e.rule_id = :r and e.subject_type = 'sale_order_line' and f.order_name = :o and p.default_code = :p""",
                 r=rule, o=subject["order"], p=subject["product"])
    elif subject["type"] == "sale_order":
        rows = q(built, """
            select e.* from marts.fact_margin_rule_evaluation e
            join (select distinct snapshot_id, sale_order_id, order_name from marts.fact_sales_order_line) f
              on f.snapshot_id = e.snapshot_id and f.sale_order_id = e.subject_id
            where e.snapshot_id = :s and e.rule_id = :r and e.subject_type = 'sale_order' and f.order_name = :o""", r=rule, o=subject["order"])
    else:
        rows = q(built, """
            select e.* from marts.fact_margin_rule_evaluation e
            join marts.fact_invoice_line i on i.snapshot_id = e.snapshot_id and i.invoice_line_id = e.subject_id
            where e.snapshot_id = :s and e.rule_id = :r and e.subject_type = 'invoice_line' and i.invoice_name = :o""", r=rule, o=subject["invoice"])
    assert len(rows) == 1, (scenario["scenario_id"], rows)
    return rows[0]


def test_every_injected_scenario_is_detected_as_expected(built):
    failures = []
    for scenario in built["manifest"]["scenarios"]:
        row = _evaluation(built, scenario)
        expected = scenario["expected"]
        checks = {"status": row["outcome"] == expected["status"], "classification": row["classification"] == expected["classification"],
                  "cause": row["cause"] == expected["cause"]}
        if expected["adverse_exposure"] is not None:
            checks["adverse_exposure"] = row["adverse_exposure"] == Decimal(expected["adverse_exposure"])
        if expected["potential_exposure"] is not None:
            checks["potential_exposure"] = row["potential_exposure"] == Decimal(expected["potential_exposure"])
        if expected["classification"] in ("CONFIRMED_LEAKAGE", "PROBABLE_LEAKAGE"):
            checks["material"] = row["material"] == expected["material"]
        for name, ok in checks.items():
            if not ok:
                failures.append(f"{scenario['scenario_id']} {name}: expected {expected.get(name)} got {row.get(name if name != 'status' else 'outcome')}")
    assert not failures, "\n".join(failures)


def test_no_exception_outside_the_injected_scenarios(built):
    injected = {s["subject"]["order"] for s in built["manifest"]["scenarios"] if s["subject"]["type"] != "invoice_line"}
    injected |= {s["subject"]["invoice"] for s in built["manifest"]["scenarios"] if s["subject"]["type"] == "invoice_line"}
    raised = q(built, """
        select e.subject_ref, e.rule_id, e.classification, e.cause, e.adverse_exposure from marts.fact_margin_rule_evaluation e
        where e.snapshot_id = :s and e.classification in ('CONFIRMED_LEAKAGE', 'PROBABLE_LEAKAGE', 'DATA_QUALITY_ISSUE', 'INSUFFICIENT_EVIDENCE')""")
    outside = [dict(r) for r in raised if r["subject_ref"].split(" / ")[0] not in injected and r["classification"] in ("CONFIRMED_LEAKAGE", "PROBABLE_LEAKAGE")]
    assert outside == [], outside[:10]
    cases = q(built, "select count(*) as n from decision.exception_case where source_instance = :i", i=built["source"].source_instance)[0]["n"]
    assert cases == built["manifest"]["expected_totals"]["cases_from_scenarios"]
    totals = {r["exposure_type"]: r["total"] for r in q(
        built, "select exposure_type, sum(adverse_exposure) as total from marts.fact_margin_rule_evaluation where snapshot_id = :s"
               " and classification = 'CONFIRMED_LEAKAGE' group by 1")}
    for kind, amount in built["manifest"]["expected_totals"]["leakage_by_type"].items():
        assert totals[kind] == Decimal(amount), kind


def test_year_three_margin_deterioration_is_visible(built):
    periods = q(built, "select period, revenue_goods, cogs from marts.fact_margin_period where snapshot_id = :s order by period")
    assert len(periods) >= 36

    def goods_pct(rows):
        revenue = sum(r["revenue_goods"] for r in rows)
        return (revenue - sum(r["cogs"] for r in rows)) * 100 / revenue

    year2, year3 = goods_pct(periods[12:24]), goods_pct(periods[24:36])
    assert year2 - year3 >= Decimal(built["manifest"]["period_signal"]["min_drop_points"]), (year2, year3)
    with built["engine"].connect() as conn:
        overview = margin_overview(conn, built["snapshot"], periods[-1]["period"])
    assert overview["kpis"]["revenue"] and overview["drivers"]["causes"]
