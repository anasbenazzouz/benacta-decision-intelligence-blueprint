"""
BENACTA — command-line demonstration of the Decision Intelligence loop.

    TRUTH → CONTEXT → INTERPRETATION → REVIEW → DECISION → ACTION → AUDIT

Runs the same pipeline the executive cockpit will use. No API key required.

    python scripts/demo_decision_loop.py
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# On Windows, a non-interactive stdout (piped, redirected, or a legacy-codepage
# terminal) falls back to the system codepage rather than UTF-8, and this
# script's rule lines and typography (em dashes, curly quotes, arrows) then
# raise UnicodeEncodeError. Forcing UTF-8 keeps `python scripts/demo_decision_loop.py`
# runnable as written on every platform.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.commentary import demo_mode_enabled  # noqa: E402
from src.control_engine import attention_list  # noqa: E402
from src.domain import COMPANY_NAME  # noqa: E402
from src.pipeline import build_session  # noqa: E402

RULE = "─" * 78


def heading(step: str, title: str) -> None:
    print(f"\n{RULE}\n{step}  {title}\n{RULE}")


def money(value: float | None) -> str:
    if value is None:
        return "—"
    sign = "-" if value < 0 else ""
    return f"{sign}€{abs(value):,.0f}"


def main() -> int:
    session = build_session()

    print(RULE)
    print(f"{COMPANY_NAME} — Monthly Performance Review · {session.period}")
    print(f"Demo mode: {demo_mode_enabled()} · {session.provider_reason}")
    print(RULE)

    # ---- TRUTH ---------------------------------------------------------- #
    heading("TRUTH", "Computed by code from the general ledger and budget")
    print(f"{'':22}{'Actual':>14}{'Budget':>14}{'Variance':>14}{'Var %':>9}")
    for fact in session.headline:
        pct = f"{fact.variance_pct:+.1%}" if fact.variance_pct is not None else "—"
        print(
            f"{fact.label:<22}{money(fact.actual):>14}{money(fact.budget):>14}"
            f"{money(fact.variance):>14}{pct:>9}"
        )

    # ---- CONTROLS ------------------------------------------------------- #
    heading("ATTENTION", "Transparent control rules, ranked")
    for index, alert in enumerate(attention_list(session.alerts), start=1):
        print(f"{index}. [{alert.severity.value:<6}] {alert.business_message}")
    hidden = len(session.alerts) - len(attention_list(session.alerts))
    if hidden:
        print(f"   (+{hidden} further alerts retained in the control output)")

    item = session.items[0]

    # ---- CONTEXT -------------------------------------------------------- #
    heading("CONTEXT", f"Evidence retrieved for {item.issue_id} — {item.fact.label}")
    for evidence in item.evidence:
        print(f"· {evidence.reference}   (relevance {evidence.score:.2f})")
        print(f"  matched: {', '.join(evidence.matched_terms[:8])}")
        print(f"  “{evidence.snippet[:150]}…”\n")

    # ---- INTERPRETATION ------------------------------------------------- #
    heading("INTERPRETATION", f"AI draft · mode={item.commentary.mode.value} · "
                              f"confidence={item.commentary.confidence.value}")
    print(item.commentary.summary)
    print("\nDrivers")
    for driver in item.commentary.drivers:
        print(f"  · {driver}")
    print("\nOpen questions")
    for question in item.commentary.open_questions:
        print(f"  · {question}")
    print("\nSuggested follow-up")
    for step in item.commentary.suggested_follow_up:
        print(f"  · {step}")
    print(f"\n[{item.review.label}] — not published until a controller approves.")

    # ---- REVIEW --------------------------------------------------------- #
    heading("REVIEW", "Human control")
    session.submit_for_review(item.issue_id)
    print(f"Submitted for review           → {item.review.label}")

    session.request_revision(
        item.issue_id, "A. Controller", "Quantify the August recovery before publishing."
    )
    print(f"Revision requested             → {item.review.label}")
    print("  Rejection is a designed path, not a failure.")

    session.resubmit(item.issue_id)
    session.approve(item.issue_id, "A. Controller", "Consistent with the milestone register.")
    print(f"Approved by {item.review.reviewer:<18} → {item.review.label}")

    # ---- DECISION / ACTION ---------------------------------------------- #
    heading("DECISION → ACTION", "Insight without action is incomplete")
    session.assign_action(
        item.issue_id,
        actor="A. Controller",
        owner="Project Finance",
        next_step="Review milestone recognition for MS-2214 and MS-2231.",
        due_date=date(2026, 8, 14),
    )
    issue = item.issue
    print(f"Issue     {issue.issue_id} — {issue.title}")
    print(f"Owner     {issue.owner}")
    print(f"Next step {issue.next_step}")
    print(f"Due       {issue.due_date}")
    print(f"Status    {issue.status_label}")

    # ---- AUDIT ---------------------------------------------------------- #
    heading("AUDIT", f"Lineage for {issue.issue_id} — every step logged")
    for record in session.audit.for_issue(issue.issue_id):
        detail = {k: v for k, v in record.detail.items() if v is not None}
        summary = ", ".join(f"{k}={v}" for k, v in list(detail.items())[:3])
        print(f"{record.sequence:>3}. {record.step.value:<24} {summary[:90]}")

    export = session.export_audit(Path("outputs") / "audit_trail.json")
    print(f"\nFull audit trail exported to {export}")
    print(f"Calculation version recorded on every fact: {item.fact.calc_version}")

    print(f"\n{RULE}\nCODE COMPUTES.  AI EXPLAINS.  HUMANS DECIDE.\n{RULE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
