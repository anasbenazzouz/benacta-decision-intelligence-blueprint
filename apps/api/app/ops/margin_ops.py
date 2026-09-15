"""Command line views of Margin Control: overview, exception queue, case, reconciliation report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import REPO_ROOT, Mode, Settings
from app.db.engine import analytics_engine
from app.margin.service import exception_case, exception_queue, margin_overview
from app.marts.reconcile import reconciliation_report
from app.ops.pipeline import FIXTURE_SOURCE_INSTANCE, latest_snapshot

EXPORTS = REPO_ROOT / ".benacta" / "exports"


def _instance(settings: Settings) -> str:
    return FIXTURE_SOURCE_INSTANCE if settings.benacta_mode is Mode.FIXTURE else settings.odoo_source_instance


def _export(name: str, content: Any) -> Path:
    EXPORTS.mkdir(parents=True, exist_ok=True)
    path = EXPORTS / name
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def _amount(value: str | None) -> str:
    return "UNAVAILABLE" if value is None else f"{float(value):,.2f}"


def run_overview(settings: Settings, period: str | None) -> int:
    engine = analytics_engine(settings)
    try:
        with engine.connect() as conn:
            overview = margin_overview(conn, latest_snapshot(engine, _instance(settings)), period)
    finally:
        engine.dispose()
    if overview.get("status") == "NO_DATA":
        print("no margin periods computed; run `benacta exceptions` first")
        return 1
    k = overview["kpis"]
    print(f"Gross margin {overview['period']} (EUR excl. taxes) | status {overview['status']} | basis {', '.join(overview['margin_basis'])}")
    print(f"  revenue {_amount(k['revenue']):>14}   COGS {_amount(k['cogs']):>14}   gross margin {_amount(k['gross_margin']):>14}"
          f"   GM% {k['gross_margin_pct'] or 'UNAVAILABLE'}")
    if k["revenue_services"] and float(k["revenue_services"]):
        print(f"  of which services {_amount(k['revenue_services']):>14} (no cost of goods posted on services; goods revenue {_amount(k['revenue_goods'])})")
    print(f"  goods gross margin {_amount(k['goods_gross_margin']):>12}   goods GM% {k['goods_gross_margin_pct'] or 'UNAVAILABLE'}"
          f"   ({k['margin_pct_basis']})")
    if k["previous_goods_gross_margin_pct"] is not None:
        print(f"  previous period {overview['previous_period']}: goods GM% {k['previous_goods_gross_margin_pct']} -> delta"
              f" {k['goods_gross_margin_pct_delta_points']} points ({'DETERIORATING' if k['deteriorating'] else 'within threshold'};"
              f" threshold {k['deterioration_threshold_points']} points)")
    print(f"  detected leakage {_amount(k['detected_leakage'])} | recoverable from customers {_amount(k['recoverable_from_customer'])}"
          f" | addressable {_amount(k['total_addressable_leakage'])} | untraceable revenue {_amount(k['untraceable_revenue'])}")
    print(f"  realised recovery: {k['recovery_status']}")
    print(f"  exceptions: {k['exceptions_material']} material, {k['exceptions_review']} for review")
    if overview["waterfall"]:
        print("  margin bridge:")
        for step in overview["waterfall"]:
            print(f"    {step['step']:32} {_amount(step['amount']):>14}")
    for name in ("causes", "customers", "products", "orders"):
        rows = overview["drivers"][name]
        if rows:
            print(f"  top {name} by adverse exposure:")
            for r in rows[:5]:
                label = r.get("cause") or r.get("customer") or r.get("product") or r.get("order")
                extra = f" [{r['exposure_type']}, {r['controllability']}]" if name == "causes" else ""
                print(f"    {label:40} {_amount(r['adverse_exposure']):>12}  ({r['exceptions']} exception(s)){extra}")
    print(f"exported {_export(f'margin_overview_{overview['period']}.json', overview).relative_to(REPO_ROOT)}")
    return 0


def run_queue(settings: Settings, period: str | None, classification: str | None, limit: int) -> int:
    engine = analytics_engine(settings)
    try:
        with engine.connect() as conn:
            snapshot = latest_snapshot(engine, _instance(settings))
            queue = exception_queue(conn, snapshot, period=period, classification=classification, limit=limit)
    finally:
        engine.dispose()
    print(f"Exception queue ({len(queue)} shown){f' for {period}' if period else ''}")
    print(f"{'case':10} {'subject':34} {'classification':22} {'cause':30} {'exposure':>12} {'sev':6} {'conf':6} {'ctrl':22} {'status':8} age")
    for q in queue:
        exposure = q["adverse_exposure"] or (f"<= {q['potential_exposure']}" if q["potential_exposure"] else "n/a")
        print(f"{q['case_ref']:10} {q['subject_ref'][:34]:34} {q['classification']:22} {q['cause']:30} {exposure:>12} {q['severity']:6}"
              f" {q['confidence']:6} {q['controllability']:22} {q['status']:8} {q['age_days']}d")
    print(f"exported {_export('margin_exceptions.json', queue).relative_to(REPO_ROOT)}")
    return 0


def run_case(settings: Settings, case_ref: str) -> int:
    engine = analytics_engine(settings)
    try:
        with engine.connect() as conn:
            case = exception_case(conn, latest_snapshot(engine, _instance(settings)), case_ref)
    finally:
        engine.dispose()
    if case is None:
        print(f"no case {case_ref}")
        return 1
    ev, c = case["evaluation"], case["case"]
    print(f"{c['case_ref']} {c['subject_ref']} | {ev['classification']} | {ev['cause']} | status {c['status']} | owner {c['owner'] or 'unassigned'}")
    print(f"  rule {ev['rule_id']} v{ev['rule_version']}: {case['rule']['name']}")
    print(f"  formula: {ev['formula']}")
    print(f"  expected {ev['expected_amount']} | actual {ev['actual_amount']} | adverse exposure {ev['adverse_exposure']}"
          f" | potential {ev['potential_exposure']} | stage {ev['exposure_stage']} ({ev['currency_code']})")
    print(f"  severity {ev['severity']} | confidence {ev['confidence']} | controllability {ev['controllability']} | material {ev['material']}")
    print(f"  reason: {case['evidence'].get('reason')}")
    for check in case["period_reconciliation"]:
        print(f"  reconciliation {check['check_id']:22} {check['status']:12} ({check['independence']})")
    print(f"  drill-down: {len(case['drill_down'].get('order_lines', []))} order line(s), {len(case['drill_down'].get('invoice_lines', []))} invoice line(s),"
          f" {len(case['drill_down'].get('deliveries', []))} delivery move(s), {len(case['drill_down'].get('cost_allocations', []))} cost allocation(s)")
    print(f"  lineage: {len(case['lineage'])} source record version(s)")
    for r in case["related_evaluations_same_subject"]:
        if r["classification"] not in ("COMPLIANT", "NOT_APPLICABLE"):
            print(f"  also on this subject: {r['rule_id']} {r['classification']} {r['cause']} {r['adverse_exposure']}")
    print(f"  {case['suggested_follow_up']['label']}: {case['suggested_follow_up']['text']} [{case['suggested_follow_up']['status']}]")
    print(f"exported {_export(f'margin_case_{c['case_ref']}.json', case).relative_to(REPO_ROOT)}")
    return 0


def run_reconciliation_report(settings: Settings, period: str | None) -> int:
    engine = analytics_engine(settings)
    try:
        report = reconciliation_report(engine, latest_snapshot(engine, _instance(settings)), period)
    finally:
        engine.dispose()
    print(f"Reconciliation report | snapshot {report['snapshot_id']} | transformation {report['transformation_version']}")
    print(f"  source timestamp {report['source_timestamp']} | ingested {report['ingestion_timestamp']} | margin basis {report['margin_basis']}")
    for p, status in report["period_status"].items():
        print(f"  period {p}: {status}")
    print(f"  {'period':8} {'check':22} {'status':12} {'independence':22} {'source total':>16} {'analytical':>16} {'difference':>12} tol")
    for c in report["checks"]:
        print(f"  {c['period']:8} {c['check_id']:22} {c['status']:12} {c['independence']:22} {_amount(c['source_total']):>16}"
              f" {_amount(c['analytical_total']):>16} {_amount(c['difference']):>12} {c['tolerance']}")
    print(f"exported {_export(f'reconciliation_{period or 'all'}.json', report).relative_to(REPO_ROOT)}")
    return 0
