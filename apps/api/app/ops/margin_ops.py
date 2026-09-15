"""Command line views of Margin Control: overview, exception queue, case, reconciliation report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import REPO_ROOT, Mode, Settings
from app.db.engine import analytics_engine
from app.margin.actions import execute_review_activity, plan_review_activity
from app.margin.decisions import DecisionError, decide, parse_actor
from app.margin.investigation import investigate, report_text
from app.margin.llm import provider_from_settings
from app.margin.service import case_audit, exception_case, exception_queue, impact_register, margin_overview
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
    print(f"  approved recovery {_amount(k['approved_recovery'])} | realised recovery {_amount(k['realised_recovery'])} ({k['recovery_status']})")
    print(f"  decisions taken {k['decisions_taken']} | acceptance rate {k['recommendation_acceptance_rate_pct'] or 'n/a'}%"
          f" | detection to decision {k['avg_hours_detection_to_decision'] or 'n/a'} h | decision to action {k['avg_hours_decision_to_action'] or 'n/a'} h")
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
    print(f"{'case':10} {'subject':30} {'classification':22} {'cause':28} {'exposure':>10} {'sev':6} {'conf':6} {'ctrl':22} {'status':18} {'owner':10} age")
    for q in queue:
        exposure = q["adverse_exposure"] or (f"<= {q['potential_exposure']}" if q["potential_exposure"] else "n/a")
        print(f"{q['case_ref']:10} {q['subject_ref'][:30]:30} {q['classification']:22} {q['cause']:28} {exposure:>10} {q['severity']:6}"
              f" {q['confidence']:6} {q['controllability']:22} {q['status']:18} {(q['owner'] or '-')[:10]:10} {q['age_days']}d")
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
    rec = case["recommendation"]
    if rec:
        print(f"  Recommendation v{rec['version']} [{rec['status']}]: {rec['title']} (estimated recovery {rec['estimated_recovery'] or 'n/a'},"
              f" basis {rec['recovery_basis']}, requires {rec['requires_role']})")
    for d in case["decisions"]:
        print(f"  decision {d['decision_type']:16} by {d['actor']:12} {d['status_before']} -> {d['status_after']} at {d['decided_at'][:19]}"
              f"{' reason: ' + d['reason'] if d['reason'] else ''}")
    for a in case["actions"]:
        print(f"  action {a['action_key']} {a['status']:9} target {a['target_system']} {a['target_model']}#{a['target_res_id']}{' ' + a['error'] if a['error'] else ''}")
    if case["impact"]:
        i = case["impact"]
        print(f"  impact: estimated {i['estimated_recovery'] or 'n/a'} | realised {i['realised_recovery'] or 'n/a'} [{i['realisation_status']}] {i['reason'] or ''}")
    print(f"exported {_export(f'margin_case_{c['case_ref']}.json', case).relative_to(REPO_ROOT)}")
    return 0


def run_decide(settings: Settings, case_ref: str, decision_type: str, actor: str, roles: list[str], *, reason: str | None, comment: str | None,
               assigned_to: str | None, defer_until: str | None, expected_version: int | None) -> int:
    from datetime import date

    engine = analytics_engine(settings)
    try:
        with engine.begin() as conn:
            result = decide(conn, parse_actor(actor, roles), case_ref, decision_type.upper(), expected_version=expected_version, reason=reason,
                            comment=comment, assigned_to=assigned_to, defer_until=date.fromisoformat(defer_until) if defer_until else None)
    except DecisionError as exc:
        print(f"refused: {exc}")
        return 2
    finally:
        engine.dispose()
    print(f"{result.case_ref}: {result.decision_type} by {actor} -> {result.status_before} -> {result.status_after} (version {result.version}, decision {result.decision_id})")
    return 0


def run_act(settings: Settings, case_ref: str, actor: str, roles: list[str], *, confirm: bool) -> int:
    engine = analytics_engine(settings)
    try:
        with engine.begin() as conn:
            plan = plan_review_activity(conn, case_ref)
            print(f"{plan.case_ref}: review activity on {plan.target_model}#{plan.target_res_id} (external id {plan.external_id})")
            print(f"  summary: {plan.vals['summary']}")
            print(f"  deadline: {plan.vals['date_deadline']}")
            if not confirm:
                print("  dry run: nothing recorded, nothing executed. Run again with --confirm.")
                return 0
            result = execute_review_activity(conn, settings, parse_actor(actor, roles), case_ref)
    except DecisionError as exc:
        print(f"refused: {exc}")
        return 2
    finally:
        engine.dispose()
    print(f"  {result.status}: {result.detail}" + (f" {result.response}" if result.response else ""))
    return 0 if result.status in ("EXECUTED", "PLANNED") else 2


def run_impact(settings: Settings) -> int:
    engine = analytics_engine(settings)
    try:
        with engine.connect() as conn:
            rows = impact_register(conn, _instance(settings))
    finally:
        engine.dispose()
    print(f"Impact register ({len(rows)} approved case(s))")
    print(f"{'case':10} {'subject':30} {'status':10} {'estimated':>11} {'realised':>11} {'variance':>11} {'measurement':14} reason")
    for r in rows:
        print(f"{r['case_ref']:10} {r['subject_ref'][:30]:30} {r['status']:10} {_amount(r['estimated_recovery']):>11} {_amount(r['realised_recovery']):>11}"
              f" {_amount(r['variance']):>11} {r['realisation_status']:14} {r['reason'] or ''}")
    print(f"exported {_export('margin_impact.json', rows).relative_to(REPO_ROOT)}")
    return 0


def run_audit(settings: Settings, case_ref: str) -> int:
    engine = analytics_engine(settings)
    try:
        with engine.connect() as conn:
            audit = case_audit(conn, case_ref)
    finally:
        engine.dispose()
    if audit is None:
        print(f"no case {case_ref}")
        return 1
    c = audit["case"]
    print(f"Audit {c['case_ref']} {c['subject_ref']} | status {c['status']} | version {c['version']} | first detected {c['first_detected_at'][:19]}")
    for e in audit["evaluations"]:
        print(f"  evaluation snapshot seq {e['batch_seq']} ({e['transformation_version']}): {e['rule_id']} v{e['rule_version']} {e['thresholds_version']}"
              f" -> {e['outcome']} {e['classification']} {e['adverse_exposure'] or ''}")
    for r in audit["recommendations"]:
        print(f"  recommendation v{r['version']} [{r['status']}] {r['source']}: {r['title']} (hash {r['payload_hash'][:12]})")
    for d in audit["decisions"]:
        print(f"  decision {d['decision_type']} by {d['actor']} ({', '.join(d['actor_roles'])}) {d['status_before']} -> {d['status_after']} at {d['decided_at'][:19]}")
    for a in audit["actions"]:
        print(f"  action {a['status']} {a['target_system']} {a['target_model']}#{a['target_res_id']} by {a['actor']} at {a['created_at'][:19]}")
    if audit["impact"]:
        print(f"  impact {audit['impact']['realisation_status']}: estimated {audit['impact']['estimated_recovery']}, realised {audit['impact']['realised_recovery']}")
    print(f"  lineage: {len(audit['lineage'])} source record version(s); audit events: {len(audit['audit_events'])}")
    for ev in audit["audit_events"]:
        print(f"    #{ev['sequence']} {ev['occurred_at'][:19]} {ev['actor']:28} {ev['action']:28} {ev['event_hash'][:12]}")
    print(f"exported {_export(f'margin_audit_{c['case_ref']}.json', audit).relative_to(REPO_ROOT)}")
    return 0


def run_investigate(settings: Settings, case_ref: str, *, use_llm: bool) -> int:
    provider = provider_from_settings(settings) if use_llm else None
    if use_llm and provider is None:
        print("no language model configured (LLM_PROVIDER=anthropic, LLM_MODEL, LLM_API_KEY): running the deterministic investigation")
    engine = analytics_engine(settings)
    try:
        with engine.begin() as conn:
            result = investigate(conn, latest_snapshot(engine, _instance(settings)), case_ref, provider=provider)
    finally:
        engine.dispose()
        if provider is not None:
            provider.close()
    print(f"Investigation {result['investigation_id']} for {case_ref}")
    print(report_text(result))
    if result["documents_refused"]:
        print(f"  documents refused at indexing: {result['documents_refused']}")
    print(f"exported {_export(f'margin_investigation_{case_ref}.json', result).relative_to(REPO_ROOT)}")
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
