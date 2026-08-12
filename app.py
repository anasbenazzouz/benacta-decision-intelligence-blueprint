"""
BENACTA — Decision Cockpit.

    streamlit run app.py

The default view is built for a CEO or CFO and answers six questions in order:
what happened, why, what requires attention, what could we do next, what
evidence supports this, and who approves or owns the next step.

It is deliberately not a dashboard and deliberately not a chat window. There is
no free-text box to interrogate, because the point of a decision system is that
the questions worth asking have already been asked, and answered with evidence a
controller can sign.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="BENACTA — Decision Cockpit",
    page_icon=str(Path(__file__).parent / "assets" / "generated" / "benacta-primary-dark.png"),
    layout="wide",
    initial_sidebar_state="expanded",
)

from src import theme  # noqa: E402
from src.approval import ReviewState  # noqa: E402
from src.commentary import demo_mode_enabled  # noqa: E402
from src.control_engine import attention_list  # noqa: E402
from src.decision_log import DecisionStatus  # noqa: E402
from src.domain import COMPANY_NAME  # noqa: E402
from src.finance_engine import (  # noqa: E402
    CALC_VERSION,
    FactGrain,
    classify_direction,
    facts_at_grain,
)
from src.lineage import (  # noqa: E402
    business_lineage,
    budget_lines_to_csv,
    export_filename,
    reconcile,
    reconcile_actual,
    reconcile_budget,
    transactions_for_fact,
    transactions_to_csv,
    variance_reconciliation,
)
from src.pipeline import build_session  # noqa: E402

VIEWS = ("Executive Decision Cockpit", "Architecture", "Audit Trail")

#: The owner proposed alongside a suggested follow-up and pre-filled in the
#: decision form. A suggestion only — a human assigns every owner.
DEFAULT_OWNER_SUGGESTION = "Project Finance"


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #


def seed_demo_state(session) -> None:
    """
    Carry one issue through to a recorded action so the decision log is not
    empty on first load. The headline revenue issue is deliberately left as a
    live draft, so the review workflow can be walked in the demonstration.
    """
    seeded = next(
        (item for item in session.items if item.alert.metric == "travel"), None
    )
    if seeded is None:
        return
    session.submit_for_review(seeded.issue_id)
    session.approve(
        seeded.issue_id,
        "A. Controller",
        "Consistent with the travel policy; workshops were customer-driven.",
    )
    session.assign_action(
        seeded.issue_id,
        actor="A. Controller",
        owner="Cost Center Manager · Projects",
        next_step="Confirm workshop travel against policy and open the missing budget line.",
        due_date=date(2026, 8, 21),
    )


def get_session():
    if "session" not in st.session_state:
        session = build_session()
        seed_demo_state(session)
        st.session_state.session = session
        st.session_state.selected = session.items[0].issue_id
        # The moment this session's pipeline actually ran — shown in the hero
        # status rail as the data-freshness statement.
        st.session_state.data_as_of = datetime.now()
    st.session_state.setdefault("panel_open", True)
    return st.session_state.session


def jsonable(value):
    if is_dataclass(value) and not isinstance(value, type):
        return {k: jsonable(v) for k, v in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [jsonable(v) for v in value]
    return value


def code_block(payload) -> None:
    st.code(json.dumps(jsonable(payload), indent=2, ensure_ascii=False), language="json")


def md(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #


def sidebar(session) -> str:
    with st.sidebar:
        # One-shot slide when the panel was explicitly reopened; the flag is
        # popped so a normal rerun never replays the animation.
        if st.session_state.pop("panel_anim", False):
            md(theme.panel_open_animation_css())

        if st.button("‹  Close panel", key="close_panel", use_container_width=True):
            st.session_state.panel_open = False
            st.rerun()

        if theme.LOGO_DARK.exists():
            st.image(str(theme.LOGO_DARK), width=210)
        md(
            '<div class="ba-label" style="opacity:0.62;margin:6px 0 22px 0">'
            "Enterprise AI · Decision Intelligence</div>"
        )
        view = st.radio("View", VIEWS, label_visibility="collapsed", key="nav_view")
        st.markdown("---")
        st.text_input("Signed in as", value="A. Controller", key="reviewer")
        refreshed = st.session_state.get("data_as_of")
        freshness = (
            f"<br>Data refreshed {refreshed.strftime('%d %b %Y · %H:%M')}"
            if refreshed
            else ""
        )
        md(
            f'<div class="ba-caption" style="color:rgba(241,233,218,0.66);margin-top:18px">'
            f"Period {session.period}<br>Calculation version {CALC_VERSION}<br>"
            f"Demo mode {'on' if demo_mode_enabled() else 'off'}{freshness}</div>"
        )
        md(
            f'<div class="ba-caption" style="color:rgba(241,233,218,0.5);margin-top:16px;'
            f'font-style:italic">{session.provider_reason}</div>'
        )
        md(
            '<div class="ba-caption" style="color:rgba(241,233,218,0.5);margin-top:22px">'
            "Fictional demonstration data.</div>"
        )
    return view


# --------------------------------------------------------------------------- #
# View A — Executive Decision Cockpit
# --------------------------------------------------------------------------- #


_REVIEW_PHRASE = {
    ReviewState.DRAFT: "in draft",
    ReviewState.AWAITING_REVIEW: "awaiting review",
    ReviewState.APPROVED: "approved",
    ReviewState.REVISION_REQUESTED: "in revision",
}


def _hero_status(session) -> list[tuple[str, str]]:
    """
    The hero's quiet status rail — the two to four facts that make the page
    read as a live review environment, all derived from session truth.
    """
    refreshed = st.session_state.get("data_as_of")
    review_counts = [
        (phrase, sum(1 for item in session.items if item.review.state is state))
        for state, phrase in _REVIEW_PHRASE.items()
    ]
    review = " · ".join(f"{n} {phrase}" for phrase, n in review_counts if n)
    return [
        ("Last refresh", refreshed.strftime("%d %b %Y · %H:%M") if refreshed else "—"),
        ("Control findings", f"{len(session.items)} of {len(session.alerts)} in attention"),
        ("Controller review", review or "—"),
    ]


def render_cockpit(session) -> None:
    entrance = not st.session_state.get("entrance_done", False)
    md(
        theme.header_band(
            "Monthly Performance Review",
            f"{theme.period_label(session.period)} Performance",
            f"{COMPANY_NAME} · Group · all figures in Euro",
            status_rows=_hero_status(session),
            live_label="Governed data · current",
            chain=("Data", "Truth", "Context", "Decision", "Action"),
            entrance=entrance,
        )
    )

    # ---- 01 What happened ---------------------------------------------- #
    md(theme.section("01", "What happened", "calculated by code · not generated"))
    md(theme.kpi_band(session.headline, entrance=entrance))

    trace_cols = st.columns(4)
    for col, fact in zip(trace_cols, session.headline):
        with col:
            if st.button("Trace to source ↗", key=f"trace_kpi_{fact.key}"):
                render_trace_dialog(session, fact, item=session.item_for_metric(fact.key))

    # ---- 02 What requires attention ------------------------------------ #
    ranked = attention_list(session.alerts)
    md(
        theme.section(
            "02",
            "What requires attention",
            f"{len(ranked)} of {len(session.alerts)} control findings, ranked",
        )
    )

    for item in session.items:
        if st.button(
            theme.attention_label(item.alert),
            key=f"att_{item.issue_id}",
            use_container_width=True,
        ):
            st.session_state.selected = item.issue_id

    selected = session.item(st.session_state.selected)
    md(theme.attention_styles(session.items, f"att_{selected.issue_id}"))

    render_issue(session, selected)
    render_decision_log(session)
    md(theme.footer_band())


def _account_label(session, code: str | None) -> str:
    if not code:
        return "—"
    try:
        return f"{code} · {session.model.account(code).name}"
    except KeyError:
        return code


def _cost_center_label(session, code: str | None) -> str:
    if not code:
        return "—"
    try:
        return f"{code} · {session.model.cost_center(code).name}"
    except KeyError:
        return code


def _transaction_row(session, t) -> dict:
    return {
        "Posting date": t.posting_date,
        "Document": t.document_number,
        "Business unit": session.unit_names.get(t.business_unit, t.business_unit),
        "Project": t.project_name or "—",
        "Customer": t.customer or "—",
        "Milestone": t.milestone_name or "—",
        "Account": _account_label(session, t.account),
        "Cost center": _cost_center_label(session, t.cost_center),
        "Amount (EUR)": t.amount,
    }


def _budget_line_row(session, b) -> dict:
    return {
        "Business unit": session.unit_names.get(b.business_unit, b.business_unit),
        "Project": b.project_name or "—",
        "Customer": b.customer or "—",
        "Milestone": b.milestone_name or "—",
        "Account": _account_label(session, b.account),
        "Cost center": _cost_center_label(session, b.cost_center),
        "Amount (EUR)": b.amount,
        "Budget version": b.budget_version,
    }


@st.dialog("Trace to source", width="large")
def render_trace_dialog(session, fact, *, item=None, focus_cause=None) -> None:
    """
    Progressive drill-through from a headline figure to the rows behind it.

    Opened either from a KPI card (`item` and `focus_cause` both None — every
    attributed cause and the full transaction ledger for the metric are
    shown), or from one specific root cause under an issue (`focus_cause` set
    — the lineage narrows to that cause, everything else stays scoped to the
    metric it belongs to). Both paths land on the same four tabs: summary
    first, structured rows on demand, never raw JSON by default.
    """
    attribution = reconcile(fact, session.source_records, session.model)
    causes = (focus_cause,) if focus_cause is not None else attribution.causes
    variance_check, _variance_ok = variance_reconciliation(fact)

    if focus_cause:
        context_line = f"Root cause · {focus_cause.title}"
    elif causes:
        context_line = f"{len(causes)} attributed root cause{'' if len(causes) == 1 else 's'}"
    else:
        context_line = "No attributed root cause"

    # Scannable header: the metric leads, the three figures line up as a
    # compact key/value column, provenance and status read as one quiet line.
    variance_value = (
        f'<span style="color:{theme.direction_color(fact.direction.value)}">'
        f"{theme.money(fact.variance)}</span>"
        if fact.variance is not None
        else "—"
    )
    figure_rows = "".join(
        f'<tr><td class="k">{key}</td><td class="v">{value}</td></tr>'
        for key, value in (
            ("Actual", theme.money(fact.actual)),
            ("Budget", theme.money(fact.budget)),
            ("Variance", variance_value),
        )
    )
    status = theme.reconciliation_status(variance_check) if fact.budget is not None else ""
    md(
        f'<div class="ba-h2" style="margin:2px 0 10px 0">{fact.label} · '
        f"{theme.period_label(fact.period)}</div>"
        f'<table class="ba-kv" style="max-width:360px">{figure_rows}</table>'
        f'<div style="display:flex;align-items:center;gap:18px;margin:14px 0 2px 0">'
        f'{status}<span class="ba-caption">{context_line}</span></div>'
    )

    tab_lineage, tab_transactions, tab_sources, tab_audit = st.tabs(
        ["Lineage", "Financial Transactions", "Source Records", "Audit"]
    )

    # ---- Tab 1 — Lineage ------------------------------------------------- #
    with tab_lineage:
        if not causes:
            md(
                '<div class="ba-body ba-stone" style="margin-top:16px">No source records '
                f"attribute {fact.label} to a specific cause. The Financial Transactions and "
                "Audit tabs still show the underlying data for this figure.</div>"
            )
        for cause in causes:
            if len(causes) > 1:
                md(f'<div class="ba-h3" style="margin:22px 0 10px 0">{cause.title}</div>')
            tx_rows = transactions_for_fact(fact, session.transactions, session.model)
            steps = business_lineage(
                cause=cause,
                fact=fact,
                transactions=tx_rows,
                model=session.model,
                rule_name=item.alert.rule_name if item else None,
                threshold_label=item.alert.threshold_label if item else None,
                severity=item.alert.severity.value if item else None,
                interpretation_mode=item.commentary.mode.value if item else None,
                confidence=item.commentary.confidence.value if item else None,
                review_label=item.review.label if item else "No control finding",
                reviewer=item.review.reviewer if item else None,
                issue_status=item.issue.status_label if item else "N/A",
                owner=item.issue.owner if item else None,
                next_step=item.issue.next_step if item else None,
                calc_version=CALC_VERSION,
            )
            md(theme.lineage_chain(steps))

    # ---- Tab 2 — Financial Transactions ----------------------------------- #
    with tab_transactions:
        md(
            '<div class="ba-label ba-stone" style="margin:16px 0 10px 0">Financial truth</div>'
        )
        truth_rows = [
            ("Actual source total", theme.money(fact.actual)),
            ("Budget source total", theme.money(fact.budget)),
            ("Deterministic variance", theme.money(fact.variance)),
        ]
        md(
            '<table class="ba-kv" style="max-width:420px">'
            + "".join(
                f'<tr><td class="k">{k}</td><td class="v">{v}</td></tr>' for k, v in truth_rows
            )
            + "</table>"
        )
        md(
            f'<div style="margin-top:10px">{theme.reconciliation_status(variance_check)}'
            f'<span class="ba-caption"> — checked against actual − budget; variance is '
            f"a calculation, not a posting.</span></div>"
        )

        basis = st.radio(
            "Basis", ("Actual", "Budget"), horizontal=True, key=f"basis_{fact.fact_id}"
        )

        if basis == "Actual":
            source_rows, check = reconcile_actual(fact, session.transactions, session.model)
            pairs = [(row, _transaction_row(session, row)) for row in source_rows]
            to_csv = transactions_to_csv
            kind = "actual_transactions"
            noun = "posting"
        else:
            source_rows, check = reconcile_budget(fact, session.budget_lines, session.model)
            pairs = [(row, _budget_line_row(session, row)) for row in source_rows]
            to_csv = budget_lines_to_csv
            kind = "budget_lines"
            noun = "budget line"

        if not pairs:
            md(
                '<div class="ba-body ba-stone" style="margin-top:8px">No transaction-level '
                f"ledger has been built for {fact.label} yet. Revenue is currently the only "
                "metric elaborated to posting grain; see Source Records for the drivers "
                "behind this figure.</div>"
            )
        else:
            # Simple control-room filters — never an analytics workbench. They
            # narrow what is SHOWN; the reconciliation line below always
            # covers the full, unfiltered set.
            unit_col, account_col, search_col = st.columns([1.1, 1.5, 1.4])
            with unit_col:
                units = sorted({display["Business unit"] for _, display in pairs})
                unit = st.selectbox(
                    "Business unit", ["All"] + units, key=f"flt_bu_{fact.fact_id}"
                )
            with account_col:
                accounts = sorted({display["Account"] for _, display in pairs})
                account = st.selectbox(
                    "Account", ["All"] + accounts, key=f"flt_acc_{fact.fact_id}"
                )
            with search_col:
                query = st.text_input(
                    "Search",
                    key=f"flt_q_{fact.fact_id}",
                    placeholder="Project, customer, document…",
                )

            filtered = pairs
            if unit != "All":
                filtered = [(r, d) for r, d in filtered if d["Business unit"] == unit]
            if account != "All":
                filtered = [(r, d) for r, d in filtered if d["Account"] == account]
            if query.strip():
                needle = query.strip().lower()
                filtered = [
                    (r, d)
                    for r, d in filtered
                    if any(needle in str(value).lower() for value in d.values())
                ]

            if filtered:
                st.dataframe(
                    [d for _, d in filtered], use_container_width=True, hide_index=True
                )
            else:
                md(
                    '<div class="ba-body ba-stone" style="margin:8px 0">'
                    "No rows match the current filter.</div>"
                )

            filtered_note = ""
            if len(filtered) != len(pairs):
                shown_total = round(sum(r.amount for r, _ in filtered), 2)
                filtered_note = (
                    f'<div class="ba-caption" style="margin-bottom:4px">Filter active — '
                    f"showing {len(filtered)} of {len(pairs)} rows · "
                    f"{theme.money(shown_total)}</div>"
                )
            md(
                f'<div style="margin:14px 0 6px 0">{filtered_note}'
                f'<span class="ba-caption">{check.row_count} {noun}'
                f'{"" if check.row_count == 1 else "s"} · '
                f"source total {theme.money(check.source_total)} · "
                f"difference to KPI {theme.money(check.difference)}&nbsp;&nbsp;</span>"
                f"{theme.reconciliation_status(check)}</div>"
            )

            filename = export_filename(
                prefix="benacta", metric_key=fact.key, period=fact.period, kind=kind
            )
            st.download_button(
                "Download CSV",
                data=to_csv([r for r, _ in filtered]),
                file_name=filename,
                mime="text/csv",
                key=f"dl_{kind}_{fact.fact_id}",
            )

    # ---- Tab 3 — Source Records ------------------------------------------- #
    with tab_sources:
        if not causes or not any(c.records for c in causes):
            md(
                '<div class="ba-body ba-stone" style="margin-top:16px">No root-cause source '
                f"records exist for {fact.label}.</div>"
            )
        for cause in causes:
            for record in cause.records:
                md(theme.source_record_card(record))

    # ---- Tab 4 — Audit ----------------------------------------------------- #
    with tab_audit:
        records = session.audit.for_issue(item.issue_id) if item else []
        last_step = (
            records[-1].timestamp.strftime("%Y-%m-%d %H:%M:%S UTC") if records else "—"
        )
        md('<div style="margin-top:16px">')
        audit_rows = [
            ("Fact ID", fact.fact_id),
            ("Calculation version", CALC_VERSION),
            (
                "Control rule",
                f"{item.alert.rule_name} ({item.alert.rule_id})" if item else "No rule fired",
            ),
            ("Evidence used", f"{len(item.evidence)} records" if item else "0 records"),
            (
                "Interpretation mode",
                f"{item.commentary.mode.value} · confidence {item.commentary.confidence.value.lower()}"
                if item
                else "—",
            ),
            ("Reviewer", item.review.reviewer or "Not yet reviewed" if item else "—"),
            ("Review state", item.review.label if item else "—"),
            ("Decision status", item.issue.status_label if item else "—"),
            ("Action owner", item.issue.owner or "Not yet assigned" if item else "—"),
            ("Last recorded step", last_step),
        ]
        md(
            '<table class="ba-kv">'
            + "".join(
                f'<tr><td class="k">{k}</td><td class="v" style="text-align:left">{v}</td></tr>'
                for k, v in audit_rows
            )
            + "</table></div>"
        )

        if item:
            md(
                f'<div class="ba-caption" style="margin-top:14px">{len(records)} audit '
                f"record{'' if len(records) == 1 else 's'} for {item.issue_id}, "
                "timestamped and in sequence.</div>"
            )
            with st.expander("Show technical detail"):
                code_block(
                    {
                        "fact_id": fact.fact_id,
                        "calculation_version": CALC_VERSION,
                        "cause_ids": [c.cause_id for c in causes],
                        "source_record_ids": [
                            r.source_record_id for c in causes for r in c.records
                        ],
                        "audit_records": [
                            {
                                "sequence": r.sequence,
                                "step": r.step.value,
                                "timestamp": r.timestamp.isoformat(),
                            }
                            for r in records
                        ],
                    }
                )
        else:
            md(
                '<div class="ba-caption" style="margin-top:14px">No control finding was '
                "raised for this metric this period, so there is no review or decision "
                "trail to show.</div>"
            )


def render_issue(session, item) -> None:
    fact = item.fact
    commentary = item.commentary
    reconciliation = item.reconciliation

    # ---- 03 Why · root cause analysis ----------------------------------- #
    md(theme.section("03", "Why · root cause analysis", f"{item.issue_id} · {fact.label}"))

    left, right = st.columns([3, 2], gap="large")
    with left:
        # The interpretation reads as the secondary, evidence-informed
        # narrative; the derived root cause below carries the stronger type.
        # The business question is "what is the cause?", not "what did the
        # AI write?" — the hierarchy says so.
        md(
            f'<div class="ba-ai">'
            f'<div class="ba-label tag">AI-generated interpretation · '
            f"confidence {commentary.confidence.value.lower()}</div>"
            f'<div class="ba-body" style="margin-top:12px">{commentary.summary}</div>'
            f"</div>"
        )

        if reconciliation and reconciliation.has_causes:
            for cause in reconciliation.causes:
                direction = classify_direction(
                    cause.impact_eur, higher_is_better=fact.higher_is_better
                ).value
                share = (
                    abs(cause.impact_eur) / abs(fact.variance)
                    if fact.variance
                    else None
                )
                md(theme.root_cause_block(cause, direction, share))
                if st.button(
                    "Trace to source ↗",
                    key=f"trace_{item.issue_id}_{cause.cause_id}",
                ):
                    render_trace_dialog(session, fact, item=item, focus_cause=cause)
        else:
            md(
                '<div class="ba-body ba-stone" style="margin-top:20px">No source records '
                "attribute this movement to a specific cause. The interpretation rests on "
                "the retrieved context alone.</div>"
            )

        if commentary.open_questions:
            md('<div class="ba-label ba-stone" style="margin:28px 0 10px 0">Open questions</div>')
            for question in commentary.open_questions:
                md(
                    f'<div class="ba-body" style="margin-bottom:10px;padding-left:16px;'
                    f'text-indent:-16px">·&nbsp;&nbsp;{question}</div>'
                )

    with right:
        md('<div class="ba-label ba-stone" style="margin-bottom:12px">The figures</div>')
        rows = [
            ("Actual", theme.money(fact.actual)),
            ("Budget", theme.money(fact.budget)),
            ("Variance", theme.money(fact.variance)),
            ("Variance %", theme.percent(fact.variance_pct)),
        ]
        table = "".join(
            f'<tr><td class="k">{key}</td><td class="v">{value}</td></tr>'
            for key, value in rows
        )
        md(f'<table class="ba-kv">{table}</table>')
        md(
            f'<div class="ba-caption" style="margin-top:14px">'
            f"Control rule · {item.alert.rule_name}<br>"
            f"Threshold · {item.alert.threshold_label}</div>"
        )

        render_unit_reconciliation(session, fact)
        render_cause_reconciliation(fact, reconciliation)

    # ---- 04 Evidence ---------------------------------------------------- #
    md(
        theme.section(
            "04",
            "What evidence supports this",
            "quoted source text · corroborates the cause, is not the cause",
        )
    )
    if item.evidence:
        for evidence in item.evidence:
            md(theme.evidence_block(evidence))
    else:
        md('<div class="ba-body ba-stone">No supporting business context was retrieved.</div>')

    # ---- 05 What could we do next --------------------------------------- #
    md(theme.section("05", "What could we do next", "a proposal for a human, not a decision"))
    for index, step in enumerate(commentary.suggested_follow_up):
        md(f'<div class="ba-body-lg">— {step}</div>')
        if index == 0:
            owner_meta = (
                f"Owner · {item.issue.owner}"
                if item.issue.owner
                else f"Owner suggestion · {DEFAULT_OWNER_SUGGESTION}"
            )
            md(
                f'<div class="ba-caption" style="margin:4px 0 16px 21px">'
                f"{owner_meta} &nbsp;·&nbsp; Reason · {_follow_up_reason(item)}</div>"
            )

    # ---- 06 Who approves ------------------------------------------------ #
    md(theme.section("06", "Who approves · who owns the next step", "human control"))
    render_controls(session, item)


def render_unit_reconciliation(session, fact) -> None:
    """Business-unit contributions that visibly add up to the headline variance."""
    units = [u for u in session.business_unit_facts(fact.key) if u.variance is not None]
    if not units:
        return

    names = session.unit_names
    rows = [
        (
            names.get(unit.business_unit or "", unit.business_unit or "Group"),
            unit.variance,
            theme.direction_color(
                classify_direction(
                    unit.variance, higher_is_better=fact.higher_is_better
                ).value
            ),
        )
        for unit in sorted(units, key=lambda u: u.variance or 0)
    ]
    md(
        '<div class="ba-label ba-stone" style="margin:28px 0 10px 0">'
        "Contribution by business unit</div>"
    )
    md(theme.reconciliation_table(rows, f"Total · {fact.label}", fact.variance))


def render_cause_reconciliation(fact, reconciliation) -> None:
    """What the identified causes explain, and what they do not."""
    if not reconciliation or not reconciliation.has_causes:
        return

    rows = [
        (
            cause.title,
            cause.impact_eur,
            theme.direction_color(
                classify_direction(
                    cause.impact_eur, higher_is_better=fact.higher_is_better
                ).value
            ),
        )
        for cause in reconciliation.causes
    ]
    md(
        '<div class="ba-label ba-stone" style="margin:28px 0 10px 0">'
        "Attributed to source records</div>"
    )
    md(
        theme.reconciliation_table(
            rows,
            f"Total · {fact.label}",
            fact.variance,
            residual_label="Other movements, not attributed",
            residual_value=reconciliation.residual,
        )
    )


def _follow_up_reason(item) -> str:
    """Why this follow-up exists, phrased from the control finding's own facts."""
    alert = item.alert
    if alert.variance is None:
        return f"{alert.label} recorded with no budget line"
    position = "below" if alert.variance < 0 else "above"
    return (
        f"{alert.severity.value} finding · {alert.label} "
        f"{theme.money_compact(abs(alert.variance))} {position} budget"
    )


def _workflow_stages(item) -> list[tuple[str, str]]:
    """
    The review chain as stepper stages. Current stage is filled — champagne
    only when the stage IS the action; the vocabulary is the fixed UI state
    vocabulary, never invented.
    """
    review = item.review.state
    status = item.issue.status

    if status is DecisionStatus.CLOSED:
        current = 4
    elif status is DecisionStatus.ACTION_REQUIRED:
        current = 3
    elif review is ReviewState.APPROVED:
        current = 2
    elif review in (ReviewState.AWAITING_REVIEW, ReviewState.REVISION_REQUESTED):
        current = 1
    else:
        current = 0

    labels = ["AI draft", "Controller review", "Approved", "Action required", "Closed"]
    if review is ReviewState.REVISION_REQUESTED:
        labels[1] = "Revision requested"

    stages = []
    for index, label in enumerate(labels):
        if index < current:
            state = "done"
        elif index == current:
            state = "current-warm" if index == 3 else "current"
        else:
            state = "todo"
        stages.append((label, state))
    return stages


def render_controls(session, item) -> None:
    review = item.review
    issue = item.issue
    reviewer = st.session_state.get("reviewer") or "A. Controller"

    md(theme.workflow_chips(_workflow_stages(item)))

    left, right = st.columns([2, 3], gap="large")

    with left:
        md('<div class="ba-label ba-stone" style="margin-bottom:10px">Interpretation</div>')
        md(theme.status_chip(review.label))
        md('<div class="ba-label ba-stone" style="margin:22px 0 10px 0">Decision issue</div>')
        md(theme.status_chip(issue.status_label))
        if review.reviewer:
            md(
                f'<div class="ba-caption" style="margin-top:16px">'
                f"Reviewed by {review.reviewer}</div>"
            )

    with right:
        if review.state is ReviewState.DRAFT:
            md(
                '<div class="ba-body" style="margin-bottom:14px">This interpretation is '
                "a draft. Nothing is published until a controller approves it.</div>"
            )
            if st.button("Send for controller review", key="primary_submit"):
                session.submit_for_review(item.issue_id, reviewer)
                st.rerun()

        elif review.state is ReviewState.AWAITING_REVIEW:
            comment = st.text_area(
                "Reviewer comment",
                key=f"comment_{item.issue_id}",
                placeholder="Required when requesting a revision.",
                height=90,
            )
            approve, revise = st.columns(2)
            with approve:
                if st.button("Approve", key="primary_approve", use_container_width=True):
                    session.approve(item.issue_id, reviewer, comment or None)
                    st.rerun()
            with revise:
                if st.button("Request revision", key="revise", use_container_width=True):
                    if not comment.strip():
                        st.warning("A revision request must say what needs revising.")
                    else:
                        session.request_revision(item.issue_id, reviewer, comment)
                        st.rerun()

        elif review.state is ReviewState.REVISION_REQUESTED:
            last = review.history[-1]
            md(
                f'<div class="ba-body" style="margin-bottom:14px">Revision requested by '
                f"{last.actor}: “{last.comment}”</div>"
            )
            if st.button("Resubmit redraft", key="primary_resubmit"):
                session.resubmit(item.issue_id, reviewer)
                st.rerun()

        elif issue.status is DecisionStatus.APPROVED:
            md(
                '<div class="ba-body" style="margin-bottom:14px">Approved. Record the '
                "decision by assigning an owner and a next step.</div>"
            )
            owner = st.text_input(
                "Owner", value=DEFAULT_OWNER_SUGGESTION, key=f"owner_{item.issue_id}"
            )
            next_step = st.text_input(
                "Next step",
                value=item.commentary.suggested_follow_up[0]
                if item.commentary.suggested_follow_up
                else "",
                key=f"next_{item.issue_id}",
            )
            due = st.date_input("Due date", value=date(2026, 8, 14), key=f"due_{item.issue_id}")
            if st.button("Record decision and assign owner", key="primary_action"):
                if not owner.strip() or not next_step.strip():
                    st.warning("An action requires both an owner and a next step.")
                else:
                    session.assign_action(
                        item.issue_id,
                        actor=reviewer,
                        owner=owner,
                        next_step=next_step,
                        due_date=due,
                    )
                    st.rerun()

        elif issue.status is DecisionStatus.ACTION_REQUIRED:
            md(
                f'<div class="ba-body">Owner · <strong>{issue.owner}</strong><br>'
                f"Next step · {issue.next_step}<br>"
                f"Due · {issue.due_date}</div>"
            )
            if st.button("Close issue", key="close"):
                session.close(item.issue_id, actor=reviewer, note="Follow-up completed.")
                st.rerun()

        elif issue.status is DecisionStatus.CLOSED:
            md('<div class="ba-body">This issue is closed.</div>')


def render_decision_log(session) -> None:
    md(theme.section("07", "Decision log", "issue · interpretation · reviewer · action"))

    rows = []
    for item in session.items:
        last = item.review.history[-1] if item.review.history else None
        stamp = last.timestamp.strftime("%Y-%m-%d %H:%M UTC") if last else "—"
        rows.append(
            f"<tr>"
            f'<td style="white-space:nowrap"><strong>{item.issue_id}</strong></td>'
            f"<td>{item.fact.label}</td>"
            f'<td class="ba-caption">{item.review.label}</td>'
            f'<td class="ba-caption">{item.review.reviewer or "—"}</td>'
            f'<td>{item.issue.next_step or "—"}</td>'
            f'<td class="ba-caption">{item.issue.owner or "—"}</td>'
            f"<td>{theme.status_chip(item.issue.status_label)}</td>"
            f'<td class="sec" style="white-space:nowrap">{stamp}</td>'
            f"</tr>"
        )

    md(
        '<table class="ba-log"><thead><tr>'
        "<th>Issue</th><th>Metric</th><th>Interpretation</th><th>Reviewer</th>"
        '<th>Decision · next step</th><th>Owner</th><th>Status</th><th class="sec">Updated</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table>'
    )


# --------------------------------------------------------------------------- #
# View B — Architecture
# --------------------------------------------------------------------------- #

LAYERS = [
    (
        "Business Semantic Layer",
        "Raw ledger rows are given business meaning before anything is calculated.",
        "Dataclass model of business units, cost centers, accounts and metric definitions; "
        "extract rows are validated against it and rejected on mismatch.",
    ),
    (
        "Deterministic Core",
        "Every number remains reproducible, and is produced the same way every time.",
        "Variance and materiality computed in Python from the semantic model; "
        "calculation version recorded on every fact.",
    ),
    (
        "Control Layer",
        "Transparent rules decide what a controller should look at, and say why.",
        "Absolute and relative materiality plus budget-coverage rules; one alert per "
        "fact, carrying rule id, threshold and direction.",
    ),
    (
        "Knowledge & Context Layer",
        "The system finds the note or policy that explains the movement.",
        "Keyword retrieval over sectioned markdown; returns document, section, snippet, "
        "relevance and the matched terms.",
    ),
    (
        "AI Interpretation",
        "A draft explanation is written from the figures and the evidence.",
        "Provider interface over template or LLM commentary; output validated so no "
        "figure absent from the facts or evidence can survive.",
    ),
    (
        "Human Control",
        "A controller remains accountable for anything published.",
        "Approval state machine; illegal transitions raise, revision is a designed path.",
    ),
    (
        "Decision & Action",
        "An insight becomes an owned next step with a due date.",
        "Issue lifecycle requiring an owner and a next step before an action is recorded.",
    ),
    (
        "Audit Trail",
        "Any statement can be walked back to its source.",
        "Append-only records per pipeline step, keyed by fact id and issue id, "
        "exportable as JSON.",
    ),
]


def render_architecture(session) -> None:
    md(
        theme.header_band(
            "Architecture · Engineering",
            "Controlled Intelligence Architecture",
            "Where the deterministic layer ends and interpretation begins",
        )
    )

    md(theme.section("01", "The layer stack", "code computes · AI explains · humans decide"))
    document, height = theme.architecture_document()
    components.html(document, height=height, scrolling=False)

    md(theme.section("02", "Layer responsibilities", "executive and technical reading"))
    rows = "".join(
        f"<tr><td style='width:22%'><strong>{name}</strong></td>"
        f"<td style='width:39%' class='ba-body'>{executive}</td>"
        f"<td style='width:39%' class='ba-caption'>{technical}</td></tr>"
        for name, executive, technical in LAYERS
    )
    md(
        '<table class="ba-log"><thead><tr><th>Layer</th><th>Executive</th>'
        f'<th>Technical</th></tr></thead><tbody>{rows}</tbody></table>'
    )

    md(theme.section("03", "The trust boundary", "the architecture's central claim"))
    md(
        '<div class="ba-body-lg" style="max-width:760px">Only computed facts cross the '
        "boundary. The interpretation layer receives figures, control findings and quoted "
        "evidence; it cannot reach the ledger and cannot recalculate. Disabling it removes "
        "commentary and changes nothing else — the figures, the controls and the materiality "
        "are identical, which the test suite asserts both structurally and behaviourally."
        "</div>"
    )
    md(
        f'<div class="ba-caption" style="margin-top:14px">'
        f"tests/test_ai_independence.py :: test_financial_truth_is_independent_from_llm</div>"
    )

    md(theme.section("04", "Live trace", "the selected issue through every layer"))
    item = session.item(st.session_state.selected)
    trace(session, item)


def trace(session, item) -> None:
    steps = [
        (
            "Source",
            f"{len(session.ledger.actuals)} actual rows and {len(session.ledger.budgets)} "
            f"budget rows mapped from {', '.join(session.ledger.source_files)}",
            None,
        ),
        (
            "Business Semantic Layer",
            f"{len(session.model.business_units)} business units · "
            f"{len(session.model.cost_centers)} cost centers · "
            f"{len(session.model.accounts)} accounts · "
            f"{len(session.model.metrics)} metric definitions",
            None,
        ),
        ("Deterministic Core", "Computed financial fact", item.fact),
        ("Control Layer", "Control alert", item.alert),
        ("Knowledge & Context", f"{len(item.evidence)} evidence items", item.evidence),
        (
            "AI Interpretation",
            f"mode {item.commentary.mode.value} · confidence {item.commentary.confidence.value}",
            {
                "summary": item.commentary.summary,
                "drivers": list(item.commentary.drivers),
                "open_questions": list(item.commentary.open_questions),
                "suggested_follow_up": list(item.commentary.suggested_follow_up),
                "fallback_reason": item.commentary.fallback_reason,
            },
        ),
        (
            "Human Control",
            f"{item.review.label} · reviewer {item.review.reviewer or '—'}",
            None,
        ),
        (
            "Decision & Action",
            f"{item.issue.status_label} · owner {item.issue.owner or '—'}",
            None,
        ),
        (
            "Audit Trail",
            f"{len(session.audit.for_issue(item.issue_id))} records for {item.issue_id}",
            None,
        ),
    ]

    for name, summary, payload in steps:
        md(
            f'<div style="border-left:1px solid {theme.BLUE_GREY};padding:2px 0 2px 16px;'
            f'margin:0 0 4px 0">'
            f'<div class="ba-label" style="font-size:11px">{name}</div>'
            f'<div class="ba-body" style="margin-top:4px">{summary}</div></div>'
        )
        if payload is not None:
            with st.expander(f"Inspect payload · {name}"):
                code_block(payload)


# --------------------------------------------------------------------------- #
# View C — Audit Trail
# --------------------------------------------------------------------------- #


def render_audit(session) -> None:
    md(
        theme.header_band(
            "Audit Trail",
            "Every step logged",
            "Source · calculation · rule · evidence · interpretation · reviewer · action",
        )
    )

    md(theme.section("01", "Lineage by issue", f"{len(session.audit)} records this session"))
    issue_id = st.selectbox(
        "Issue",
        [item.issue_id for item in session.items],
        index=[item.issue_id for item in session.items].index(st.session_state.selected),
        format_func=lambda i: f"{i} · {session.item(i).fact.label}",
    )

    def brief(value) -> str:
        """Collections are summarised by size; the JSON below carries the detail."""
        value = jsonable(value)
        if isinstance(value, list):
            return f"{len(value)} item{'' if len(value) == 1 else 's'}"
        if isinstance(value, dict):
            return f"{len(value)} field{'' if len(value) == 1 else 's'}"
        return str(value)

    for record in session.audit.for_issue(issue_id):
        detail = {k: v for k, v in record.detail.items() if v not in (None, [], {})}
        summary = " · ".join(f"{k} {brief(v)}" for k, v in list(detail.items())[:4])
        md(
            f'<div style="display:flex;gap:18px;padding:11px 0;'
            f'border-bottom:1px solid rgba(18,43,32,0.12)">'
            f'<div class="ba-caption" style="width:34px">{record.sequence:02d}</div>'
            f'<div class="ba-label" style="width:210px;font-size:11px">{record.step.value}</div>'
            f'<div class="ba-caption" style="flex:1">{summary[:180]}</div>'
            f'<div class="ba-caption" style="white-space:nowrap">'
            f'{record.timestamp.strftime("%H:%M:%S")}</div></div>'
        )

    md(theme.section("02", "Full record", "technical inspection"))
    with st.expander("Complete audit trail (JSON)"):
        st.code(session.audit.to_json(), language="json")

    if st.button("Export audit trail", key="primary_export"):
        path = session.export_audit(Path("outputs") / "audit_trail.json")
        st.success(f"Exported to {path}")


# --------------------------------------------------------------------------- #


def main() -> None:
    md(theme.inject_theme())
    session = get_session()

    md(theme.panel_visibility_css(st.session_state.panel_open))

    if st.session_state.panel_open:
        view = sidebar(session)
    else:
        # The panel is closed: nothing lives in st.sidebar this run, so the
        # navigation choice is read back from the same session_state key the
        # radio writes to when open. The explicit reopen control is the only
        # way back — the native collapse arrow is hidden because this build
        # renders no way to undo it once used.
        left, _ = st.columns([1, 7])
        with left:
            if st.button("☰  Menu", key="open_panel", use_container_width=True):
                st.session_state.panel_open = True
                st.session_state.panel_anim = True
                st.rerun()
        view = st.session_state.get("nav_view", VIEWS[0])
        md('<div style="height:18px"></div>')

    if view == VIEWS[0]:
        render_cockpit(session)
    elif view == VIEWS[1]:
        render_architecture(session)
    else:
        render_audit(session)

    # The one-time entrance has played; every rerun after this renders still.
    st.session_state.entrance_done = True


main()
