"""BENACTA Margin Control cockpit: the CFO experience over the same service layer as the command line and the API.

Six views: executive overview, exception queue, exception case, decision workspace, impact tracking, audit.
Every figure on screen is computed by code from the analytics database; the cockpit never recomputes and never
talks to Odoo except through the guarded action executor. Identity is the pilot identity (a name and declared
roles), not authentication.

Run: `uv run --project apps/api --extra cockpit streamlit run apps/cockpit/margin_control.py` or `benacta demo`.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import sqlalchemy as sa
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from app.config import Mode, get_settings  # noqa: E402
from app.db.engine import analytics_engine  # noqa: E402
from app.margin.actions import execute_review_activity, plan_review_activity  # noqa: E402
from app.margin.decisions import DecisionError, decide, parse_actor  # noqa: E402
from app.margin.investigation import investigate  # noqa: E402
from app.margin.llm import provider_from_settings  # noqa: E402
from app.margin.service import (  # noqa: E402
    case_audit,
    exception_case,
    exception_queue,
    impact_register,
    margin_overview,
)
from app.marts.reconcile import reconciliation_report  # noqa: E402
from app.ops.pipeline import FIXTURE_SOURCE_INSTANCE, latest_snapshot  # noqa: E402

# Locked charter palette (.claude/benacta/brand-system.md): colour is information, never decoration.
GREEN, PORCELAIN, CHAMPAGNE, BLUE, BLUE_GREY, STONE = "#122B20", "#F1E9DA", "#BBA06B", "#6C9BA3", "#536875", "#7C898B"
CHAMPAGNE_TEXT, BLUE_TEXT, FAVOURABLE, UNFAVOURABLE = "#8F7440", "#54808A", "#4F6B4F", "#A05743"
VIEWS = ("Executive overview", "Exception queue", "Exception case", "Decision workspace", "Impact tracking", "Audit view")
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=Source+Serif+4:ital,wght@0,400;1,400&display=swap');
html, body, [class*="css"] {{ font-family: 'Instrument Sans', sans-serif; color: {GREEN}; }}
.stApp {{ background: {PORCELAIN}; }}
#MainMenu, footer, header {{ visibility: hidden; }}
section[data-testid="stSidebar"] {{ background: {GREEN}; color: {PORCELAIN}; }}
section[data-testid="stSidebar"] * {{ color: {PORCELAIN} !important; }}
.ba-band {{ border-bottom: 1px solid {CHAMPAGNE}; padding: 0.6rem 0 0.8rem 0; margin-bottom: 1.2rem; }}
.ba-kicker {{ font-size: 0.72rem; letter-spacing: 0.16em; text-transform: uppercase; color: {STONE}; font-weight: 500; }}
.ba-kicker.ai {{ color: {BLUE_TEXT}; }}
.ba-title {{ font-family: 'Source Serif 4', serif; font-size: 1.9rem; margin: 0.1rem 0 0 0; color: {GREEN}; }}
.ba-tile {{ background: white; border: 1px solid #e3dccb; border-radius: 4px; padding: 0.8rem 1rem; }}
.ba-tile .label {{ font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase; color: {STONE}; }}
.ba-tile .value {{ font-size: 1.5rem; font-weight: 600; color: {GREEN}; }}
.ba-tile .note {{ font-size: 0.8rem; color: {BLUE_GREY}; }}
.ba-fav {{ color: {FAVOURABLE}; }} .ba-unfav {{ color: {UNFAVOURABLE}; }} .ba-neutral {{ color: {BLUE_GREY}; }}
.ba-ai {{ border-left: 3px solid {BLUE}; padding: 0.4rem 0.9rem; background: #eef3f4; margin: 0.4rem 0; }}
.ba-fact {{ border-left: 3px solid {GREEN}; padding: 0.3rem 0.9rem; margin: 0.3rem 0; background: white; }}
.ba-quote {{ font-family: 'Source Serif 4', serif; font-style: italic; color: {GREEN}; }}
.ba-tag {{ display: inline-block; font-size: 0.7rem; letter-spacing: 0.1em; text-transform: uppercase; padding: 0.1rem 0.5rem;
           border: 1px solid {CHAMPAGNE}; color: {CHAMPAGNE_TEXT}; border-radius: 2px; margin-right: 0.3rem; }}
</style>
"""


# --------------------------------------------------------------------------- data access
@st.cache_resource
def _engine():
    settings = get_settings()
    override = os.environ.get("BENACTA_COCKPIT_DATABASE_URL")
    return analytics_engine(settings, url=override) if override else analytics_engine(settings)


def _snapshot() -> uuid.UUID:
    settings = get_settings()
    instance = FIXTURE_SOURCE_INSTANCE if settings.benacta_mode is Mode.FIXTURE else settings.odoo_source_instance
    engine = _engine()
    try:
        return latest_snapshot(engine, instance)
    except RuntimeError:
        with engine.connect() as conn:  # no snapshot for the configured instance: show the latest available and say so
            snapshot = conn.execute(sa.text("select batch_id from raw.ingestion_batch where status = 'SUCCEEDED' order by batch_seq desc limit 1")).scalar()
        if snapshot is None:
            raise
        st.sidebar.warning(f"No snapshot for instance {instance}; showing the latest available snapshot.")
        return snapshot


def _read(fn, *args, **kwargs):
    with _engine().connect() as conn:
        return fn(conn, *args, **kwargs)


def _write(fn, *args, **kwargs):
    with _engine().begin() as conn:
        return fn(conn, *args, **kwargs)


def _money(value: Any) -> str:
    if value is None:
        return "unavailable"
    try:
        return f"{Decimal(str(value)):,.2f}"
    except Exception:  # noqa: BLE001 - display only
        return str(value)


def _tile(label: str, value: str, note: str = "", tone: str = "") -> None:
    st.markdown(f'<div class="ba-tile"><div class="label">{label}</div><div class="value {tone}">{value}</div><div class="note">{note}</div></div>',
                unsafe_allow_html=True)


def _band(kicker: str, title: str, ai: bool = False) -> None:
    st.markdown(f'<div class="ba-band"><div class="ba-kicker{" ai" if ai else ""}">{kicker}</div><div class="ba-title">{title}</div></div>',
                unsafe_allow_html=True)


# --------------------------------------------------------------------------- sidebar
def sidebar() -> tuple[str, Any]:
    st.sidebar.markdown(f'<div style="font-family:Source Serif 4,serif;font-size:1.4rem;">BENACTA</div>'
                        f'<div class="ba-kicker" style="color:{CHAMPAGNE} !important;">Margin Control · pilot</div><br/>', unsafe_allow_html=True)
    view = st.sidebar.radio("View", VIEWS, label_visibility="collapsed")
    st.sidebar.markdown("---")
    st.sidebar.markdown('<div class="ba-kicker">Pilot identity (declared, not authenticated)</div>', unsafe_allow_html=True)
    user = st.sidebar.text_input("Your identifier", value=st.session_state.get("actor_id", "FIN-01"))
    roles = st.sidebar.multiselect("Roles", ["analyst", "project_controller", "finance_approver", "admin"],
                                   default=st.session_state.get("actor_roles", ["finance_approver"]))
    st.session_state["actor_id"], st.session_state["actor_roles"] = user, roles
    settings = get_settings()
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Mode {settings.benacta_mode.value} · every figure calculated by code · AI drafts require controller approval")
    return view, parse_actor(user, roles) if user and roles else None


# --------------------------------------------------------------------------- views
def view_overview(snapshot: uuid.UUID) -> None:
    periods = _read(margin_overview, snapshot)["periods"]
    options = sorted({p["period"] for p in periods}, reverse=True)
    period = st.selectbox("Period", options, index=0)
    o = _read(margin_overview, snapshot, period)
    k = o["kpis"]
    _band("Executive overview · calculated by code · not generated", f"Gross margin, {period}")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _tile("Revenue", _money(k["revenue"]), f"goods {_money(k['revenue_goods'])} · services {_money(k['revenue_services'])}")
    with c2:
        _tile("Cost of goods sold", _money(k["cogs"]), f"basis {', '.join(o['margin_basis'])}")
    with c3:
        _tile("Gross margin", _money(k["gross_margin"]), f"{k['gross_margin_pct'] or 'n/a'} % of revenue")
    with c4:
        delta = k["goods_gross_margin_pct_delta_points"]
        tone = "ba-unfav" if k["deteriorating"] else ("ba-fav" if delta and Decimal(delta) > 0 else "ba-neutral")
        _tile("Goods gross margin %", f"{k['goods_gross_margin_pct'] or 'n/a'} %",
              f"{'deteriorating' if k['deteriorating'] else 'within threshold'} · {delta or 'n/a'} points vs {o['previous_period'] or 'previous'}", tone)
    st.caption(k["margin_pct_basis"])
    st.markdown("&nbsp;")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _tile("Detected leakage", _money(k["detected_leakage"]), "confirmed and probable")
    with c2:
        _tile("Recoverable from customers", _money(k["recoverable_from_customer"]), "billing component")
    with c3:
        _tile("Approved recovery", _money(k["approved_recovery"]), f"{k['decisions_taken']} decision(s), acceptance {k['recommendation_acceptance_rate_pct'] or 'n/a'} %")
    with c4:
        _tile("Realised recovery", _money(k["realised_recovery"]), k["recovery_status"])
    st.markdown("&nbsp;")
    left, right = st.columns([3, 2])
    with left:
        st.markdown('<div class="ba-kicker">Margin bridge · illustrative</div>', unsafe_allow_html=True)
        if o["waterfall"]:
            st.table([{"Step": w["step"], "EUR": _money(w["amount"])} for w in o["waterfall"]])
        else:
            st.info("Margin unavailable for this period: the cost of goods sold is not defensible.")
    with right:
        st.markdown('<div class="ba-kicker">Exceptions requiring attention</div>', unsafe_allow_html=True)
        _tile("Material", str(k["exceptions_material"]), "confirmed or probable leakage above materiality")
        _tile("For review", str(k["exceptions_review"]), "insufficient evidence or data quality")
    st.markdown('<div class="ba-kicker">Where the leakage is</div>', unsafe_allow_html=True)
    tabs = st.tabs(["By cause", "By customer", "By product", "By order"])
    for tab, key in zip(tabs, ("causes", "customers", "products", "orders"), strict=True):
        with tab:
            rows = o["drivers"][key]
            st.table([{**{kk: vv for kk, vv in r.items() if kk != "adverse_exposure"}, "EUR": _money(r["adverse_exposure"])} for r in rows] or
                     [{"note": "nothing detected in this period"}])
    with st.expander("Trace to source: reconciliation of the period"):
        report = reconciliation_report(_engine(), snapshot, period)
        st.caption(f"Transformation {report['transformation_version']} · source {report['source_timestamp']} · ingested {report['ingestion_timestamp']}")
        st.table([{"Check": c["check_id"], "Status": c["status"], "Independence": c["independence"], "Source": _money(c["source_total"]),
                   "Analytical": _money(c["analytical_total"]), "Difference": _money(c["difference"])} for c in report["checks"]])


def view_queue(snapshot: uuid.UUID) -> None:
    _band("Exception queue · ranked by materiality, class and severity", "What requires a decision")
    queue = _read(exception_queue, snapshot, include_resolved=False)
    if not queue:
        st.info("No open exception.")
        return
    st.dataframe([{"Case": q["case_ref"], "Subject": q["subject_ref"], "Class": q["classification"], "Cause": q["cause"],
                   "Exposure EUR": _money(q["adverse_exposure"]) if q["adverse_exposure"] else (f"≤ {_money(q['potential_exposure'])}" if q["potential_exposure"] else "n/a"),
                   "Severity": q["severity"], "Confidence": q["confidence"], "Controllability": q["controllability"], "Owner": q["owner"] or "",
                   "Status": q["status"], "Recommendation": q["recommendation_status"] or "", "Age (days)": q["age_days"],
                   "Suggested follow-up": q["suggested_follow_up"]} for q in queue], use_container_width=True, hide_index=True)
    refs = [q["case_ref"] for q in queue]
    chosen = st.selectbox("Open a case", refs, index=refs.index(st.session_state.get("case_ref")) if st.session_state.get("case_ref") in refs else 0)
    if st.button("Open the exception case"):
        st.session_state["case_ref"] = chosen
        st.session_state["view_override"] = "Exception case"
        st.rerun()


def _pick_case(snapshot: uuid.UUID) -> dict[str, Any] | None:
    queue = _read(exception_queue, snapshot, include_resolved=True)
    refs = [q["case_ref"] for q in queue]
    if not refs:
        st.info("No case yet: run `benacta seed-fixtures`.")
        return None
    default = st.session_state.get("case_ref") if st.session_state.get("case_ref") in refs else refs[0]
    ref = st.selectbox("Case", refs, index=refs.index(default))
    st.session_state["case_ref"] = ref
    return _read(exception_case, snapshot, ref)


def _statements(report: dict[str, Any]) -> None:
    for s in report["statements"]:
        refs = ", ".join(s.get("refs", []))
        css = "ba-ai" if s["type"] == "HYPOTHESIS" else "ba-fact"
        support = f" <span class='ba-quote'>({s['support']})</span>" if s.get("support") else ""
        st.markdown(f'<div class="{css}"><span class="ba-tag">{s["type"].replace("_", " ")}</span>{s["text"]}{support}'
                    f'<div class="note" style="font-size:0.75rem;color:{STONE};">{refs}</div></div>', unsafe_allow_html=True)


def view_case(snapshot: uuid.UUID) -> None:
    case = _pick_case(snapshot)
    if case is None:
        return
    ev, c = case["evaluation"], case["case"]
    _band(f"Exception case · {c['case_ref']} · {ev['classification'].replace('_', ' ').lower()}", c["subject_ref"])
    a, b, d, e = st.columns(4)
    with a:
        _tile("Adverse exposure", _money(ev["adverse_exposure"]) if ev["adverse_exposure"] else f"≤ {_money(ev['potential_exposure'])}", f"stage {ev['exposure_stage'] or 'n/a'}")
    with b:
        _tile("Expected vs actual", f"{_money(ev['expected_amount'])} / {_money(ev['actual_amount'])}", ev["currency_code"])
    with d:
        _tile("Severity · confidence", f"{ev['severity']} · {ev['confidence']}", f"material: {'yes' if ev['material'] else 'no'}")
    with e:
        _tile("Controllability", ev["controllability"].replace("_", " ").lower(), ev["cause"].replace("_", " ").lower())
    st.markdown(f'<div class="ba-fact"><b>What happened.</b> {case["evidence"].get("reason")}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ba-fact"><b>Rule.</b> {case["rule"]["name"]} (v{ev["rule_version"]}, thresholds {ev["thresholds_version"]}): '
                f'<code>{ev["formula"]}</code></div>', unsafe_allow_html=True)
    tabs = st.tabs(["Transactions", "Evidence", "Reconciliation", "Investigation", "Recommendation", "Lineage"])
    drill = case["drill_down"]
    with tabs[0]:
        for label, key in (("Order lines", "order_lines"), ("Invoice lines", "invoice_lines"), ("Deliveries", "deliveries"),
                           ("Cost allocations", "cost_allocations"), ("Receipts", "receipts"), ("Posted cost of goods sold", "posted_cogs")):
            rows = drill.get(key) or ([drill["invoice_line"]] if key == "invoice_lines" and drill.get("invoice_line") else [])
            if rows:
                st.markdown(f'<div class="ba-kicker">{label}</div>', unsafe_allow_html=True)
                st.dataframe(rows, use_container_width=True, hide_index=True)
    with tabs[1]:
        st.json({k: v for k, v in case["evidence"].items() if k not in ("invoices",)})
        if case["related_evaluations_same_subject"]:
            st.markdown('<div class="ba-kicker">Other rules on the same subject</div>', unsafe_allow_html=True)
            st.table(case["related_evaluations_same_subject"])
    with tabs[2]:
        st.table([{"Check": r["check_id"], "Status": r["status"], "Independence": r["independence"], "Difference": _money(r["difference"])}
                  for r in case["period_reconciliation"]])
    with tabs[3]:
        inv = case["investigation"]
        col1, col2 = st.columns([1, 3])
        with col1:
            use_llm = st.checkbox("Use the configured model", value=False, help="Without a key the deterministic investigation runs; drafts are validated")
            if st.button("Run the investigation"):
                provider = provider_from_settings(get_settings()) if use_llm else None
                try:
                    _write(investigate, snapshot, c["case_ref"], provider=provider)
                finally:
                    if provider is not None:
                        provider.close()
                st.rerun()
        with col2:
            if inv is None:
                st.info("No investigation yet.")
            else:
                _band(inv["human_control"], inv["label"], ai=True)
                st.markdown(f'<div class="ba-ai"><b>{inv["report"]["summary"]}</b> · confidence {inv["report"]["confidence"]}</div>', unsafe_allow_html=True)
                _statements(inv["report"])
                rec = inv["report"]["draft_recommendation"]
                st.markdown(f'<div class="ba-ai"><span class="ba-tag">Draft recommendation</span>{rec["title"]}. {rec["rationale"]}</div>', unsafe_allow_html=True)
                for limit in inv["report"]["limits"]:
                    st.caption(f"Limit: {limit}")
                if inv.get("fallback_reason"):
                    st.warning(f"Model draft refused, deterministic report shown: {inv['fallback_reason']}")
    with tabs[4]:
        rec = case["recommendation"]
        if rec:
            _tile(f"Recommendation v{rec['version']} · {rec['status']} · {rec['source'].replace('_', ' ').lower()}", rec["title"],
                  f"estimated recovery {_money(rec['estimated_recovery'])} ({rec['recovery_basis'].replace('_', ' ').lower()}) · requires {rec['requires_role']}")
            st.write(rec["rationale"])
            st.caption("A proposal for a person. Decide in the decision workspace.")
        if case["impact"]:
            i = case["impact"]
            st.caption(f"Impact: estimated {_money(i['estimated_recovery'])}, realised {_money(i['realised_recovery'])} [{i['realisation_status']}] {i['reason'] or ''}")
    with tabs[5]:
        st.dataframe(case["lineage"], use_container_width=True, hide_index=True)


def view_decision(snapshot: uuid.UUID, actor) -> None:
    case = _pick_case(snapshot)
    if case is None:
        return
    c, rec = case["case"], case["recommendation"]
    _band("Decision workspace · a named person decides", f"{c['case_ref']} · status {c['status']} · version {c['version']} · owner {c['owner'] or 'unassigned'}")
    if rec:
        st.markdown(f'<div class="ba-fact"><span class="ba-tag">Recommendation v{rec["version"]} {rec["status"]}</span>{rec["title"]}. {rec["rationale"]}'
                    f'<div class="note">estimated recovery {_money(rec["estimated_recovery"])} · requires {rec["requires_role"]}</div></div>', unsafe_allow_html=True)
    if actor is None:
        st.warning("Declare your identifier and at least one role in the sidebar to decide.")
        return
    decision = st.selectbox("Decision", ["APPROVE", "REJECT", "REQUEST_EVIDENCE", "ASSIGN", "DEFER", "COMMENT", "REOPEN", "CLOSE"])
    reason = st.text_input("Reason (required to reject, defer, request evidence, reopen)")
    comment = st.text_input("Comment")
    assigned_to = st.text_input("Assign to") if decision == "ASSIGN" else None
    defer_until = st.date_input("Defer until", value=date.today()) if decision == "DEFER" else None
    if st.button(f"Record {decision}"):
        try:
            result = _write(decide, actor, c["case_ref"], decision, expected_version=c["version"], reason=reason or None, comment=comment or None,
                            assigned_to=assigned_to or None, defer_until=defer_until)
            st.success(f"{result.decision_type}: {result.status_before} → {result.status_after} (version {result.version})")
            st.rerun()
        except DecisionError as exc:
            st.error(f"Refused: {exc}")
    st.markdown('<div class="ba-kicker">Controlled action · review activity on the source document</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Plan (dry run)"):
            try:
                plan = _write(plan_review_activity, c["case_ref"])
                st.json({"target": f"{plan.target_model}#{plan.target_res_id}", "external_id": plan.external_id, "request": plan.vals})
            except DecisionError as exc:
                st.error(f"Refused: {exc}")
    with col2:
        if st.button("Execute through the write guard"):
            try:
                result = _write(execute_review_activity, get_settings(), actor, c["case_ref"])
                (st.success if result.status in ("EXECUTED", "PLANNED") else st.error)(f"{result.status}: {result.detail}")
                st.rerun()
            except DecisionError as exc:
                st.error(f"Refused: {exc}")
    if case["decisions"]:
        st.markdown('<div class="ba-kicker">Decision history</div>', unsafe_allow_html=True)
        st.table([{"When": d["decided_at"][:19], "Decision": d["decision_type"], "By": d["actor"], "Roles": ", ".join(d["actor_roles"]),
                   "From": d["status_before"], "To": d["status_after"], "Reason": d["reason"] or "", "Comment": d["comment"] or ""} for d in case["decisions"]])
    if case["actions"]:
        st.markdown('<div class="ba-kicker">Actions</div>', unsafe_allow_html=True)
        st.table([{"When": a["created_at"][:19], "Status": a["status"], "Target": f"{a['target_system']} {a['target_model']}#{a['target_res_id']}",
                   "By": a["actor"], "Note": a["error"] or ""} for a in case["actions"]])


def view_impact(snapshot: uuid.UUID) -> None:
    _band("Impact tracking · realised only from posted documents", "Estimated against realised recovery")
    settings = get_settings()
    instance = FIXTURE_SOURCE_INSTANCE if settings.benacta_mode is Mode.FIXTURE else settings.odoo_source_instance
    with _engine().connect() as conn:
        inst = conn.execute(sa.text("select source_instance from marts.snapshot where snapshot_id = :s"), {"s": snapshot}).scalar() or instance
        rows = impact_register(conn, inst)
    if not rows:
        st.info("No approved recommendation yet.")
        return
    st.dataframe([{"Case": r["case_ref"], "Subject": r["subject_ref"], "Status": r["status"], "Decided": (r["decided_at"] or "")[:10],
                   "Actioned": (r["actioned_at"] or "")[:10], "Estimated EUR": _money(r["estimated_recovery"]), "Realised EUR": _money(r["realised_recovery"]),
                   "Variance EUR": _money(r["variance"]), "Measurement": r["realisation_status"], "Evidence": ", ".join(e["invoice"] for e in r["realisation_evidence"]),
                   "Reason": r["reason"] or ""} for r in rows], use_container_width=True, hide_index=True)


def view_audit(snapshot: uuid.UUID) -> None:
    case = _pick_case(snapshot)
    if case is None:
        return
    audit = _read(case_audit, case["case"]["case_ref"])
    _band("Audit view · every step logged", f"{audit['case']['case_ref']} · {audit['case']['subject_ref']}")
    st.markdown('<div class="ba-kicker">Evaluations across snapshots</div>', unsafe_allow_html=True)
    st.table([{"Snapshot seq": e["batch_seq"], "Transformation": e["transformation_version"], "Rule": f"{e['rule_id']} v{e['rule_version']}",
               "Thresholds": e["thresholds_version"], "Outcome": e["outcome"], "Class": e["classification"], "Exposure": _money(e["adverse_exposure"]),
               "Computed": e["computed_at"][:19]} for e in audit["evaluations"]])
    st.markdown('<div class="ba-kicker">Recommendations, decisions, actions, impact</div>', unsafe_allow_html=True)
    st.table([{"Version": r["version"], "Source": r["source"], "Status": r["status"], "Title": r["title"], "Hash": r["payload_hash"][:12]} for r in audit["recommendations"]])
    if audit["decisions"]:
        st.table([{"When": d["decided_at"][:19], "Decision": d["decision_type"], "By": d["actor"], "Roles": ", ".join(d["actor_roles"]), "From": d["status_before"],
                   "To": d["status_after"], "Reason": d["reason"] or ""} for d in audit["decisions"]])
    if audit["actions"]:
        st.table([{"When": a["created_at"][:19], "Status": a["status"], "Target": f"{a['target_system']} {a['target_model']}#{a['target_res_id']}", "By": a["actor"]}
                  for a in audit["actions"]])
    if audit["impact"]:
        st.caption(f"Impact {audit['impact']['realisation_status']}: estimated {_money(audit['impact']['estimated_recovery'])}, realised {_money(audit['impact']['realised_recovery'])}")
    st.markdown('<div class="ba-kicker">Source lineage</div>', unsafe_allow_html=True)
    st.dataframe(audit["lineage"], use_container_width=True, hide_index=True)
    st.markdown('<div class="ba-kicker">Hash-chained audit events</div>', unsafe_allow_html=True)
    st.table([{"#": e["sequence"], "When": e["occurred_at"][:19], "Actor": e["actor"], "Action": e["action"], "Hash": e["event_hash"][:12]} for e in audit["audit_events"]])
    st.download_button("Export the audit of this case (JSON)", json.dumps(audit, indent=2, default=str), file_name=f"audit_{audit['case']['case_ref']}.json")


# --------------------------------------------------------------------------- main
def main() -> None:
    st.set_page_config(page_title="BENACTA Margin Control", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    view, actor = sidebar()
    if st.session_state.pop("view_override", None):
        view = "Exception case"
    try:
        snapshot = _snapshot()
    except RuntimeError as exc:
        st.error(f"No data: {exc}. Run `uv run --project apps/api benacta seed-fixtures` first.")
        return
    if view == "Executive overview":
        view_overview(snapshot)
    elif view == "Exception queue":
        view_queue(snapshot)
    elif view == "Exception case":
        view_case(snapshot)
    elif view == "Decision workspace":
        view_decision(snapshot, actor)
    elif view == "Impact tracking":
        view_impact(snapshot)
    else:
        view_audit(snapshot)


main()
