"""Verify the demonstration profile in the development database against its ground-truth manifest.

Runs after `benacta seed-fixtures --profile full` and performs the checks of the opt-in pytest gate without
building a second database: every month reconciled, every injected scenario detected as expected, no confirmed or
probable leakage outside the scenarios, cases and totals equal to the manifest, year-three margin deterioration.
Exit code 0 when every check passes. Application code never reads the manifest; this script lives outside it.

Run: `uv run --project apps/api python scripts/verify_full_profile.py`
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

import sqlalchemy as sa

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from app.config import Mode, get_settings  # noqa: E402
from app.db.engine import analytics_engine  # noqa: E402
from app.ops.pipeline import FIXTURE_INSTANCES, latest_snapshot  # noqa: E402

MANIFEST = REPO_ROOT / "data" / "golden" / "demo_full_manifest_v1.json"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    settings = get_settings().model_copy(update={"benacta_mode": Mode.FIXTURE})
    engine = analytics_engine(settings)
    instance = FIXTURE_INSTANCES["full"]
    failures: list[str] = []
    try:
        snapshot = latest_snapshot(engine, instance)
        with engine.connect() as conn:
            def rows(sql: str, **params):
                return conn.execute(sa.text(sql), {"s": snapshot, **params}).mappings().all()

            recon = rows("select check_id, status, period from marts.reconciliation_result where snapshot_id = :s")
            bad = [r for r in recon if r["status"] != "RECONCILED"]
            periods = {r["period"] for r in recon}
            if bad or len(periods) < 36:
                failures.append(f"reconciliation: {len(bad)} check(s) not reconciled over {len(periods)} period(s)")
            for scenario in manifest["scenarios"]:
                subject, rule, expected = scenario["subject"], scenario["rule"], scenario["expected"]
                if subject["type"] == "sale_order_line":
                    found = rows("""select e.* from marts.fact_margin_rule_evaluation e
                        join marts.fact_sales_order_line f on f.snapshot_id = e.snapshot_id and f.sale_line_id = e.subject_id
                        join marts.dim_product p on p.snapshot_id = f.snapshot_id and p.product_id = f.product_id
                        where e.snapshot_id = :s and e.rule_id = :r and e.subject_type = 'sale_order_line' and f.order_name = :o and p.default_code = :p""",
                                 r=rule, o=subject["order"], p=subject["product"])
                elif subject["type"] == "sale_order":
                    found = rows("""select e.* from marts.fact_margin_rule_evaluation e
                        join (select distinct snapshot_id, sale_order_id, order_name from marts.fact_sales_order_line) f
                          on f.snapshot_id = e.snapshot_id and f.sale_order_id = e.subject_id
                        where e.snapshot_id = :s and e.rule_id = :r and e.subject_type = 'sale_order' and f.order_name = :o""", r=rule, o=subject["order"])
                else:
                    found = rows("""select e.* from marts.fact_margin_rule_evaluation e
                        join marts.fact_invoice_line i on i.snapshot_id = e.snapshot_id and i.invoice_line_id = e.subject_id
                        where e.snapshot_id = :s and e.rule_id = :r and e.subject_type = 'invoice_line' and i.invoice_name = :o""", r=rule, o=subject["invoice"])
                if len(found) != 1:
                    failures.append(f"{scenario['scenario_id']}: {len(found)} evaluation(s) found")
                    continue
                row = found[0]
                for key, column in (("status", "outcome"), ("classification", "classification"), ("cause", "cause")):
                    if row[column] != expected[key]:
                        failures.append(f"{scenario['scenario_id']} {key}: expected {expected[key]} got {row[column]}")
                for key in ("adverse_exposure", "potential_exposure"):
                    if expected[key] is not None and row[key] != Decimal(expected[key]):
                        failures.append(f"{scenario['scenario_id']} {key}: expected {expected[key]} got {row[key]}")
            injected = {s["subject"].get("order") or s["subject"].get("invoice") for s in manifest["scenarios"]}
            outside = [r for r in rows("""select subject_ref, rule_id, cause, adverse_exposure from marts.fact_margin_rule_evaluation
                where snapshot_id = :s and classification in ('CONFIRMED_LEAKAGE', 'PROBABLE_LEAKAGE')""")
                       if r["subject_ref"].split(" / ")[0] not in injected]
            if outside:
                failures.append(f"{len(outside)} confirmed or probable leakage(s) outside the injected scenarios, e.g. {dict(outside[0])}")
            cases = rows("select count(*) as n from decision.exception_case where source_instance = :i", i=instance)[0]["n"]
            if cases != manifest["expected_totals"]["cases_from_scenarios"]:
                failures.append(f"cases: expected {manifest['expected_totals']['cases_from_scenarios']} got {cases}")
            totals = {r["exposure_type"]: r["total"] for r in rows(
                "select exposure_type, sum(adverse_exposure) as total from marts.fact_margin_rule_evaluation where snapshot_id = :s"
                " and classification = 'CONFIRMED_LEAKAGE' group by 1")}
            for kind, amount in manifest["expected_totals"]["leakage_by_type"].items():
                if totals.get(kind) != Decimal(amount):
                    failures.append(f"leakage {kind}: expected {amount} got {totals.get(kind)}")
            periods_rows = rows("select period, revenue_goods, cogs from marts.fact_margin_period where snapshot_id = :s order by period")

            def goods_pct(rs):
                revenue = sum(r["revenue_goods"] for r in rs)
                return (revenue - sum(r["cogs"] for r in rs)) * 100 / revenue

            year2, year3 = goods_pct(periods_rows[12:24]), goods_pct(periods_rows[24:36])
            if year2 - year3 < Decimal(manifest["period_signal"]["min_drop_points"]):
                failures.append(f"period signal: goods margin year 2 {year2:.2f} %, year 3 {year3:.2f} %")
            print(f"snapshot {snapshot}: {len(periods)} periods reconciled, {len(manifest['scenarios'])} scenarios checked, {cases} cases,"
                  f" goods margin year 2 {year2:.2f} % -> year 3 {year3:.2f} %")
    finally:
        engine.dispose()
    for failure in failures:
        print(f"FAIL {failure}")
    print("full profile verified" if not failures else f"{len(failures)} failure(s)")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
