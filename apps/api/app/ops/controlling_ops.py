"""Command line views of project controlling: portfolio, status report, margin investigation."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.config import REPO_ROOT, Mode, Settings
from app.controlling.investigation import investigate_margin_erosion, save_investigation
from app.controlling.portfolio import portfolio_overview
from app.controlling.psr import build_psr_content, save_draft
from app.controlling.seed_plans import CONTROLLER
from app.db.engine import analytics_engine
from app.fixtures.demo_dataset import DEFAULT_ANCHOR
from app.ops.pipeline import latest_snapshot

EXPORTS = REPO_ROOT / ".benacta" / "exports"


def _context(settings: Settings, cutoff: str | None) -> tuple[date, str]:
    if settings.benacta_mode is Mode.FIXTURE:
        return (date.fromisoformat(cutoff) if cutoff else DEFAULT_ANCHOR), "fixture_demo_v2"
    if not cutoff:
        raise SystemExit("--cutoff is required outside fixture mode")
    return date.fromisoformat(cutoff), settings.odoo_source_instance


def _export(name: str, content: dict) -> Path:
    EXPORTS.mkdir(parents=True, exist_ok=True)
    path = EXPORTS / name
    path.write_text(json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def run_portfolio(settings: Settings, cutoff: str | None, business_unit: str | None) -> int:
    day, instance = _context(settings, cutoff)
    engine = analytics_engine(settings)
    try:
        with engine.connect() as conn:
            overview = portfolio_overview(conn, latest_snapshot(engine, instance), day, business_unit)
    finally:
        engine.dispose()
    print(f"Portfolio at {overview['cutoff']} (EUR excl. taxes, overdue incl. taxes)")
    print(f"{'project':8} {'BU':10} {'revenue@compl':>14} {'EAC':>13} {'margin':>12} {'m%':>6} {'overdue':>11}  exceptions")
    for row in overview["projects"]:
        print(f"{row['project_code']:8} {row['business_unit'] or '':10} {row['forecast_revenue_at_completion'] or 'UNKNOWN':>14} "
              f"{row['eac'] or 'UNKNOWN':>13} {row['forecast_margin_amount'] or 'UNKNOWN':>12} {row['forecast_margin_pct'] or '':>6} "
              f"{row['overdue_amount']:>11}  {', '.join(row['exceptions'])}")
    totals = overview["totals"]
    print(f"totals: revenue {totals['forecast_revenue_at_completion']}, EAC {totals['eac']}, margin {totals['forecast_margin_amount']}"
          f" ({totals['forecast_margin_pct']}%), overdue {totals['overdue_amount']}; excluded (EAC unknown): "
          f"{', '.join(totals['projects_excluded_unknown_eac']) or 'none'}")
    print(f"exported {_export(f'portfolio_{day:%Y-%m}.json', overview).relative_to(REPO_ROOT)}")
    return 0


def run_psr(settings: Settings, project: str, cutoff: str | None, save: bool) -> int:
    day, instance = _context(settings, cutoff)
    engine = analytics_engine(settings)
    try:
        with engine.begin() as conn:
            snapshot = latest_snapshot(engine, instance)
            content = build_psr_content(conn, snapshot, project, day)
            psr_id = save_draft(conn, CONTROLLER, content) if save else None
    finally:
        engine.dispose()
    cost, revenue, execution = content["costs_and_forecast"], content["contract_and_revenue"], content["execution"]
    print(f"PSR {project} {content['identity']['name']} | period {content['report']['period']} | status DRAFT (not approved)")
    print(f"  forecast {content['versions']['forecast']['label'] if content['versions']['forecast'] else 'NONE'}"
          f" | budget {content['versions']['approved_budget']['label'] if content['versions']['approved_budget'] else 'NONE'}")
    for label, item in (("revenue at completion", revenue["revised_contract_value"]), ("approved budget", cost["approved_budget"]),
                        ("actual cost", cost["actual_cost"]), ("open commitments", cost["open_commitments"]), ("ETC", cost["etc"]),
                        ("EAC", cost["eac"]), ("margin at completion", cost["forecast_margin_amount"]),
                        ("billed", revenue["billed"]), ("collected (incl. taxes)", revenue["collected_ttc"]),
                        ("declared physical progress %", execution["physical_progress_pct"]),
                        ("cost consumption %", execution["cost_consumption_ratio"])):
        print(f"  {label:30} {item['value'] or item['status']}" + (f"  ({item['reason']})" if item["status"] != "OK" and item["reason"] else ""))
    print(f"  exceptions: {', '.join(e['code'] for e in execution['exceptions']) or 'none'}")
    print(f"  data quality: {content['data_quality']['status']}")
    if psr_id:
        print(f"  saved draft {psr_id}; publication requires a different approver")
    print(f"exported {_export(f'psr_{project}_{day:%Y-%m}.json', content).relative_to(REPO_ROOT)}")
    return 0


def run_investigation(settings: Settings, project: str, cutoff: str | None, save: bool) -> int:
    day, instance = _context(settings, cutoff)
    engine = analytics_engine(settings)
    try:
        with engine.begin() as conn:
            snapshot = latest_snapshot(engine, instance)
            report = investigate_margin_erosion(conn, snapshot, project, day)
            investigation_id = save_investigation(conn, report) if save else None
    finally:
        engine.dispose()
    print(f"{report['question']} {project} ({report['label']}) -> {report['status']}")
    if report["status"] == "ABSTAINED":
        print(f"  abstention: {report['abstention_reason']}")
    for item in report["observations"]:
        print(f"  [fact] {item['text']}")
    for item in report["hypotheses"]:
        print(f"  [hypothesis] {item['text']} ({item['support']})")
    for item in report["limits"]:
        print(f"  [limit] {item}")
    for item in report["proposed_actions"]:
        print(f"  [proposal {item['status']}] {item['text']}")
    if investigation_id:
        print(f"  saved investigation {investigation_id} with proposals pending review")
    print(f"exported {_export(f'investigation_{project}_{day:%Y-%m}.json', report).relative_to(REPO_ROOT)}")
    return 0
