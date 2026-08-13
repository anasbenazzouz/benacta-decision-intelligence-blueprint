"""
BENACTA the Decision Intelligence loop, assembled.

    TRUTH → CONTEXT → INTERPRETATION → REVIEW → DECISION → ACTION → AUDIT

This module owns the wiring and nothing else: no calculation, no rules, no
retrieval logic, no prompt. It exists so the command-line demonstration and the
executive cockpit drive the *same* pipeline rather than two versions of it that
drift apart.

Everything that changes state goes through this object, so the audit trail can
never fall out of step with what actually happened.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Sequence

from src.approval import ReviewRecord
from src.audit import AuditStep, AuditTrail
from src.commentary import (
    Commentary,
    CommentaryProvider,
    CommentaryRequest,
    resolve_provider,
)
from src.control_engine import ControlAlert, attention_list, evaluate
from src.decision_log import DecisionIssue, DecisionLog, DecisionStatus
from src.domain import SEMANTIC_MODEL, SemanticModel
from src.finance_engine import (
    CALC_VERSION,
    DEFAULT_ACTUALS_PATH,
    DEFAULT_BUDGET_PATH,
    DEFAULT_PERIOD,
    FactGrain,
    FinancialFact,
    Ledger,
    fact_for,
    facts_at_grain,
    headline_facts,
    run_truth_layer,
)
from src.lineage import (
    DEFAULT_BUDGET_LINES_PATH,
    DEFAULT_SOURCE_RECORDS_PATH,
    DEFAULT_TRANSACTIONS_PATH,
    BudgetLine,
    Reconciliation,
    SourceRecord,
    TransactionLine,
    load_budget_lines,
    load_source_records,
    load_transactions,
    reconcile,
)
from src.retrieval import DEFAULT_CONTEXT_DIR, Evidence, Section, load_corpus, retrieve_for_alert

#: How many ranked alerts get an interpretation drafted.
DEFAULT_INTERPRETATION_LIMIT = 5


@dataclass
class DecisionItem:
    """One issue, with everything the cockpit needs to show about it."""

    issue: DecisionIssue
    alert: ControlAlert
    fact: FinancialFact
    evidence: tuple[Evidence, ...]
    commentary: Commentary
    review: ReviewRecord
    #: Derived root causes and what they leave unexplained.
    reconciliation: Reconciliation | None = None

    @property
    def issue_id(self) -> str:
        return self.issue.issue_id


@dataclass
class DecisionSession:
    """The state of one monthly performance review."""

    period: str
    ledger: Ledger
    facts: tuple[FinancialFact, ...]
    alerts: tuple[ControlAlert, ...]
    corpus: tuple[Section, ...]
    log: DecisionLog
    audit: AuditTrail
    provider_name: str
    provider_reason: str
    source_records: tuple[SourceRecord, ...] = ()
    transactions: tuple[TransactionLine, ...] = ()
    budget_lines: tuple[BudgetLine, ...] = ()
    items: list[DecisionItem] = field(default_factory=list)
    model: SemanticModel = SEMANTIC_MODEL

    @property
    def unit_names(self) -> dict[str, str]:
        return {unit.key: unit.name for unit in self.model.business_units}

    # -- inspection ------------------------------------------------------- #

    @property
    def headline(self) -> tuple[FinancialFact, ...]:
        return headline_facts(self.facts, self.model)

    @property
    def attention(self) -> tuple[DecisionItem, ...]:
        """Ranked items requiring attention the cockpit's main list."""
        return tuple(self.items)

    def item(self, issue_id: str) -> DecisionItem:
        for item in self.items:
            if item.issue_id == issue_id:
                return item
        raise KeyError(f"No decision item {issue_id!r}")

    def item_for_metric(self, metric_key: str) -> DecisionItem | None:
        """
        The decision item for a company-level metric, if a control finding
        raised one. Several headline KPIs Operating Expenses in the
        reference story never breach materiality and therefore have no
        item; callers must handle that as a real, expected case, not an error.
        """
        for item in self.items:
            if item.fact.key == metric_key and item.fact.grain is FactGrain.METRIC:
                return item
        return None

    def business_unit_facts(self, metric_key: str) -> tuple[FinancialFact, ...]:
        return tuple(
            fact
            for fact in facts_at_grain(self.facts, FactGrain.METRIC_BY_BUSINESS_UNIT)
            if fact.key == metric_key
        )

    # -- human control ---------------------------------------------------- #

    def submit_for_review(self, issue_id: str, actor: str = "system") -> None:
        item = self.item(issue_id)
        event = item.review.submit_for_review(actor)
        item.issue.advance(DecisionStatus.UNDER_REVIEW, actor=actor, note="Sent for controller review.")
        self.audit.record(
            AuditStep.REVIEW_SUBMITTED,
            issue_id=issue_id,
            refs={"fact_id": item.fact.fact_id},
            state=event.to_state,
            actor=actor,
        )

    def approve(self, issue_id: str, reviewer: str, comment: str | None = None) -> None:
        item = self.item(issue_id)
        event = item.review.approve(reviewer, comment)
        item.issue.advance(
            DecisionStatus.APPROVED, actor=reviewer, note=comment or "Commentary approved."
        )
        self.audit.record(
            AuditStep.REVIEW_DECIDED,
            issue_id=issue_id,
            refs={"fact_id": item.fact.fact_id},
            state=event.to_state,
            reviewer=reviewer,
            comment=comment,
        )

    def request_revision(self, issue_id: str, reviewer: str, comment: str) -> None:
        item = self.item(issue_id)
        event = item.review.request_revision(reviewer, comment)
        self.audit.record(
            AuditStep.REVIEW_DECIDED,
            issue_id=issue_id,
            refs={"fact_id": item.fact.fact_id},
            state=event.to_state,
            reviewer=reviewer,
            comment=comment,
        )

    def resubmit(self, issue_id: str, actor: str = "system") -> None:
        """Send a redrafted interpretation back to the controller."""
        item = self.item(issue_id)
        event = item.review.resubmit(actor)
        self.audit.record(
            AuditStep.REVIEW_SUBMITTED,
            issue_id=issue_id,
            refs={"fact_id": item.fact.fact_id},
            state=event.to_state,
            actor=actor,
        )

    # -- decision and action ---------------------------------------------- #

    def assign_action(
        self,
        issue_id: str,
        *,
        actor: str,
        owner: str,
        next_step: str,
        due_date: date | None = None,
        note: str | None = None,
    ) -> None:
        item = self.item(issue_id)
        item.issue.advance(
            DecisionStatus.ACTION_REQUIRED,
            actor=actor,
            note=note,
            owner=owner,
            next_step=next_step,
            due_date=due_date,
        )
        self.audit.record(
            AuditStep.ACTION_ASSIGNED,
            issue_id=issue_id,
            refs={"fact_id": item.fact.fact_id},
            owner=owner,
            next_step=next_step,
            due_date=due_date,
            actor=actor,
        )

    def close(self, issue_id: str, *, actor: str, note: str | None = None) -> None:
        item = self.item(issue_id)
        item.issue.advance(DecisionStatus.CLOSED, actor=actor, note=note)
        self.audit.record(
            AuditStep.ISSUE_CLOSED,
            issue_id=issue_id,
            refs={"fact_id": item.fact.fact_id},
            actor=actor,
            note=note,
        )

    def export_audit(self, path: Path) -> Path:
        return self.audit.export(path)


# --------------------------------------------------------------------------- #
# Construction
# --------------------------------------------------------------------------- #


def _supporting_facts(
    facts: Sequence[FinancialFact], alert: ControlAlert
) -> tuple[FinancialFact, ...]:
    """Business-unit detail for a company-level metric the semantic drill-down."""
    return tuple(
        fact
        for fact in facts_at_grain(facts, FactGrain.METRIC_BY_BUSINESS_UNIT)
        if fact.key == alert.metric and fact.budget is not None
    )


def build_session(
    *,
    period: str = DEFAULT_PERIOD,
    actuals_path: Path = DEFAULT_ACTUALS_PATH,
    budget_path: Path = DEFAULT_BUDGET_PATH,
    context_dir: Path = DEFAULT_CONTEXT_DIR,
    source_records_path: Path = DEFAULT_SOURCE_RECORDS_PATH,
    transactions_path: Path = DEFAULT_TRANSACTIONS_PATH,
    budget_lines_path: Path = DEFAULT_BUDGET_LINES_PATH,
    model: SemanticModel = SEMANTIC_MODEL,
    provider: CommentaryProvider | None = None,
    interpretation_limit: int = DEFAULT_INTERPRETATION_LIMIT,
) -> DecisionSession:
    """
    Run the loop from source data to reviewable draft decisions.

    Deterministic through the truth, control and retrieval layers. Only the
    interpretation step is provider-dependent, and its default needs no API key.
    """
    audit = AuditTrail()

    # ---- TRUTH ---------------------------------------------------------- #
    ledger, facts = run_truth_layer(actuals_path, budget_path, period=period, model=model)
    audit.record(
        AuditStep.SOURCE_LOADED,
        refs={"source_files": list(ledger.source_files)},
        actual_rows=len(ledger.actuals),
        budget_rows=len(ledger.budgets),
    )
    audit.record(
        AuditStep.FACTS_COMPUTED,
        refs={"calc_version": CALC_VERSION},
        period=period,
        fact_count=len(facts),
    )

    # ---- CONTROLS ------------------------------------------------------- #
    alerts = evaluate(facts)
    audit.record(
        AuditStep.CONTROLS_EVALUATED,
        alert_count=len(alerts),
        severities=[alert.severity.value for alert in alerts],
    )

    # ---- SOURCE LINEAGE -------------------------------------------------- #
    source_records = load_source_records(source_records_path, model)
    transactions = load_transactions(transactions_path, model)
    budget_lines = load_budget_lines(budget_lines_path, model)
    audit.record(
        AuditStep.SOURCE_LOADED,
        refs={
            "source_files": [
                source_records_path.name,
                transactions_path.name,
                budget_lines_path.name,
            ]
        },
        source_records=len(source_records),
        transactions=len(transactions),
        budget_lines=len(budget_lines),
    )

    # ---- CONTEXT + INTERPRETATION --------------------------------------- #
    corpus = load_corpus(context_dir)
    commentary_provider, reason = (
        (provider, f"Provider supplied by caller: {provider.name}.")
        if provider is not None
        else resolve_provider()
    )

    session = DecisionSession(
        period=period,
        ledger=ledger,
        facts=facts,
        alerts=alerts,
        corpus=corpus,
        log=DecisionLog(),
        audit=audit,
        provider_name=commentary_provider.name,
        provider_reason=reason,
        source_records=source_records,
        transactions=transactions,
        budget_lines=budget_lines,
        model=model,
    )

    ranked = attention_list(alerts, limit=interpretation_limit)
    if len(alerts) > len(ranked):
        audit.record(
            AuditStep.CONTROLS_EVALUATED,
            note=(
                f"{len(alerts) - len(ranked)} lower-ranked alerts were not "
                f"interpreted in this run; they remain in the control output."
            ),
        )

    for index, alert in enumerate(ranked, start=1):
        issue_id = f"ISS-{index:02d}"
        fact = _fact_for_alert(facts, alert)

        evidence = retrieve_for_alert(alert, corpus, model=model)
        audit.record(
            AuditStep.CONTEXT_RETRIEVED,
            issue_id=issue_id,
            refs={"fact_id": fact.fact_id},
            evidence=[
                {
                    "document": e.document,
                    "section": e.section,
                    "score": e.score,
                    "matched_terms": list(e.matched_terms),
                }
                for e in evidence
            ],
        )

        attribution = reconcile(fact, source_records, model)
        if attribution.has_causes:
            audit.record(
                AuditStep.SOURCE_ATTRIBUTED,
                issue_id=issue_id,
                refs={"fact_id": fact.fact_id},
                root_causes=[cause.cause_id for cause in attribution.causes],
                source_record_ids=[
                    record.source_record_id
                    for cause in attribution.causes
                    for record in cause.records
                ],
                explained=attribution.explained,
                residual=attribution.residual,
            )

        request = CommentaryRequest(
            fact=fact,
            alert=alert,
            evidence=evidence,
            supporting_facts=_supporting_facts(facts, alert),
            unit_names={unit.key: unit.name for unit in model.business_units},
        )
        commentary = commentary_provider.generate(request)
        audit.record(
            AuditStep.INTERPRETATION_DRAFTED,
            issue_id=issue_id,
            refs={"fact_id": fact.fact_id},
            mode=commentary.mode,
            model=commentary.model,
            confidence=commentary.confidence,
            fallback_reason=commentary.fallback_reason,
        )

        issue = session.log.add(
            DecisionIssue(
                issue_id=issue_id,
                title=alert.business_message,
                fact_id=fact.fact_id,
                rule_id=alert.rule_id,
                severity=alert.severity.value,
            )
        )
        audit.record(
            AuditStep.DECISION_RECORDED,
            issue_id=issue_id,
            refs={"fact_id": fact.fact_id, "rule_id": alert.rule_id},
            status=issue.status,
            severity=alert.severity,
        )

        session.items.append(
            DecisionItem(
                issue=issue,
                alert=alert,
                fact=fact,
                evidence=evidence,
                commentary=commentary,
                review=ReviewRecord(subject_id=issue_id),
                reconciliation=attribution,
            )
        )

    return session


def _fact_for_alert(
    facts: Sequence[FinancialFact], alert: ControlAlert
) -> FinancialFact:
    grain = FactGrain.ACCOUNT if alert.account else FactGrain.METRIC
    return fact_for(facts, alert.metric, grain=grain)
