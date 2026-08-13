"""
BENACTA Source lineage and root-cause attribution.

Answers the question a controller actually asks of a variance: *where would I go
to verify this?*

A control finding says a metric moved. A root cause says **why**, backed by
source records a controller can look up in the originating system. The two are
kept apart on purpose:

  * a **root cause** is derived an analytical grouping of source records that
    share one business explanation, carrying a summed financial impact;
  * **supporting evidence** is quoted source text, which corroborates a cause
    but is not itself the cause.

The layer never asserts that a cause accounts for the whole movement. It
reports what the source records explain and what is left over, so a partial
explanation reads as partial rather than complete. That residual is the honest
part of this module.

Deterministic and offline. No AI dependency this sits above the trust
boundary alongside the finance, control and retrieval layers.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from src.domain import SEMANTIC_MODEL, SemanticMappingError, SemanticModel
from src.finance_engine import FactGrain, FinancialFact

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_RECORDS_PATH = _REPO_ROOT / "data" / "source_records.csv"
DEFAULT_TRANSACTIONS_PATH = _REPO_ROOT / "data" / "transactions.csv"
DEFAULT_BUDGET_LINES_PATH = _REPO_ROOT / "data" / "budget_lines.csv"

#: Below this, a residual is presentation noise rather than a real gap.
RESIDUAL_TOLERANCE_EUR = 0.01


@dataclass(frozen=True)
class SourceRecord:
    """
    One root-cause record: a controller-facing explanation of *why*, backed by
    enough identifying detail to find the underlying operational record.

    This is deliberately not the transaction ledger see `TransactionLine` for
    the postings that make up the Actual and Budget figures themselves. A
    source record explains a movement; a transaction *is* the movement.
    """

    source_record_id: str
    source_system: str
    source_document: str
    source_section: str
    business_object: str
    cause_id: str
    cause_title: str
    cause_explanation: str
    project_id: str | None
    project_name: str | None
    customer: str | None
    milestone_id: str | None
    milestone_name: str | None
    milestone_type: str | None
    account: str
    original_period: str
    current_period: str
    impact_eur: float
    reason: str
    owner: str | None

    @property
    def deferred(self) -> bool:
        """True when the record moved between periods rather than being new."""
        return self.original_period != self.current_period

    @property
    def subject(self) -> str:
        """The business object in one line, for a lineage heading."""
        parts = [p for p in (self.project_name, self.milestone_name) if p]
        return " · ".join(parts) if parts else self.business_object


@dataclass(frozen=True)
class TransactionLine:
    """
    One posting that contributed to a metric's Actual figure.

    The sum of transaction lines for a given account and period is defined to
    equal that account's row in `data/actuals.csv` enforced by
    `test_lineage.py::test_revenue_actual_transactions_reconcile_to_metric` and
    its siblings, not merely asserted here.
    """

    transaction_id: str
    posting_date: str
    document_number: str
    period: str
    business_unit: str
    project_id: str | None
    project_name: str | None
    customer: str | None
    milestone_id: str | None
    milestone_name: str | None
    account: str
    cost_center: str
    currency: str
    amount: float
    source_system: str
    source_model: str


@dataclass(frozen=True)
class BudgetLine:
    """
    One planning line that contributed to a metric's Budget figure.

    A budget line is not a transaction it is a plan, and some budget lines
    (the two slipped milestones) have no corresponding transaction this
    period. That asymmetry is the point: it is what the Revenue variance *is*.
    """

    budget_line_id: str
    period: str
    business_unit: str
    project_id: str | None
    project_name: str | None
    customer: str | None
    milestone_id: str | None
    milestone_name: str | None
    account: str
    cost_center: str
    currency: str
    amount: float
    budget_version: str
    source_system: str
    source_model: str


@dataclass(frozen=True)
class ReconciliationCheck:
    """
    Displayed figure vs. the sum of the underlying rows, made explicit.

    Never hidden: if `difference` is non-zero, the UI shows it rather than
    silently rounding it away.
    """

    label: str
    displayed: float | None
    source_total: float
    row_count: int

    @property
    def difference(self) -> float:
        if self.displayed is None:
            return 0.0
        return round(self.displayed - self.source_total, 2)

    @property
    def reconciled(self) -> bool:
        return abs(self.difference) <= RESIDUAL_TOLERANCE_EUR


@dataclass(frozen=True)
class RootCause:
    """A derived explanation: source records sharing one business cause."""

    cause_id: str
    title: str
    explanation: str
    impact_eur: float
    records: tuple[SourceRecord, ...]

    @property
    def documents(self) -> tuple[str, ...]:
        """The source documents a controller would open to verify this cause."""
        seen: list[str] = []
        for record in self.records:
            reference = f"{record.source_document} § {record.source_section}"
            if reference not in seen:
                seen.append(reference)
        return tuple(seen)

    @property
    def systems(self) -> tuple[str, ...]:
        seen: list[str] = []
        for record in self.records:
            if record.source_system not in seen:
                seen.append(record.source_system)
        return tuple(seen)


@dataclass(frozen=True)
class Reconciliation:
    """How much of a variance the identified causes actually account for."""

    metric_label: str
    variance: float | None
    explained: float
    causes: tuple[RootCause, ...]

    @property
    def residual(self) -> float | None:
        """The part no source record explains. Reported, never hidden."""
        if self.variance is None:
            return None
        return round(self.variance - self.explained, 2)

    @property
    def fully_explained(self) -> bool:
        residual = self.residual
        return residual is not None and abs(residual) <= RESIDUAL_TOLERANCE_EUR

    @property
    def has_causes(self) -> bool:
        return bool(self.causes)


@dataclass(frozen=True)
class LineageStep:
    """One link in the business lineage chain, business language first."""

    stage: str
    headline: str
    detail: str
    technical: str | None = None


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def _optional(value: str) -> str | None:
    value = (value or "").strip()
    return value or None


def load_source_records(
    path: Path = DEFAULT_SOURCE_RECORDS_PATH,
    model: SemanticModel = SEMANTIC_MODEL,
) -> tuple[SourceRecord, ...]:
    """
    Read the source-record extract, validating every account against the
    governed chart of accounts. A record pointing at an unknown account is a
    broken lineage, so it is rejected rather than silently carried.
    """
    records: list[SourceRecord] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for position, row in enumerate(csv.DictReader(handle), start=2):
            account = (row["account"] or "").strip()
            try:
                model.account(account)
            except SemanticMappingError as exc:
                raise SemanticMappingError(f"{path.name} line {position}: {exc}") from exc

            records.append(
                SourceRecord(
                    source_record_id=row["source_record_id"].strip(),
                    source_system=row["source_system"].strip(),
                    source_document=row["source_document"].strip(),
                    source_section=row["source_section"].strip(),
                    business_object=row["business_object"].strip(),
                    cause_id=row["cause_id"].strip(),
                    cause_title=row["cause_title"].strip(),
                    cause_explanation=row["cause_explanation"].strip(),
                    project_id=_optional(row["project_id"]),
                    project_name=_optional(row["project_name"]),
                    customer=_optional(row.get("customer", "")),
                    milestone_id=_optional(row["milestone_id"]),
                    milestone_name=_optional(row["milestone_name"]),
                    milestone_type=_optional(row.get("milestone_type", "")),
                    account=account,
                    original_period=row["original_period"].strip(),
                    current_period=row["current_period"].strip(),
                    impact_eur=round(float(row["impact_eur"]), 2),
                    reason=row["reason"].strip(),
                    owner=_optional(row.get("owner", "")),
                )
            )
    return tuple(records)


def load_transactions(
    path: Path = DEFAULT_TRANSACTIONS_PATH,
    model: SemanticModel = SEMANTIC_MODEL,
) -> tuple[TransactionLine, ...]:
    """Read the transaction-level extract behind the Actual figures."""
    lines: list[TransactionLine] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for position, row in enumerate(csv.DictReader(handle), start=2):
            account = (row["account"] or "").strip()
            try:
                model.account(account)
            except SemanticMappingError as exc:
                raise SemanticMappingError(f"{path.name} line {position}: {exc}") from exc

            lines.append(
                TransactionLine(
                    transaction_id=row["transaction_id"].strip(),
                    posting_date=row["posting_date"].strip(),
                    document_number=row["document_number"].strip(),
                    period=row["period"].strip(),
                    business_unit=row["business_unit"].strip(),
                    project_id=_optional(row["project_id"]),
                    project_name=_optional(row["project_name"]),
                    customer=_optional(row["customer"]),
                    milestone_id=_optional(row["milestone_id"]),
                    milestone_name=_optional(row["milestone_name"]),
                    account=account,
                    cost_center=row["cost_center"].strip(),
                    currency=row["currency"].strip(),
                    amount=round(float(row["amount"]), 2),
                    source_system=row["source_system"].strip(),
                    source_model=row["source_model"].strip(),
                )
            )
    return tuple(lines)


def load_budget_lines(
    path: Path = DEFAULT_BUDGET_LINES_PATH,
    model: SemanticModel = SEMANTIC_MODEL,
) -> tuple[BudgetLine, ...]:
    """Read the planning-line extract behind the Budget figures."""
    lines: list[BudgetLine] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for position, row in enumerate(csv.DictReader(handle), start=2):
            account = (row["account"] or "").strip()
            try:
                model.account(account)
            except SemanticMappingError as exc:
                raise SemanticMappingError(f"{path.name} line {position}: {exc}") from exc

            lines.append(
                BudgetLine(
                    budget_line_id=row["budget_line_id"].strip(),
                    period=row["period"].strip(),
                    business_unit=row["business_unit"].strip(),
                    project_id=_optional(row["project_id"]),
                    project_name=_optional(row["project_name"]),
                    customer=_optional(row["customer"]),
                    milestone_id=_optional(row["milestone_id"]),
                    milestone_name=_optional(row["milestone_name"]),
                    account=account,
                    cost_center=row["cost_center"].strip(),
                    currency=row["currency"].strip(),
                    amount=round(float(row["amount"]), 2),
                    budget_version=row["budget_version"].strip(),
                    source_system=row["source_system"].strip(),
                    source_model=row["source_model"].strip(),
                )
            )
    return tuple(lines)


# --------------------------------------------------------------------------- #
# Attribution
# --------------------------------------------------------------------------- #


def records_for_fact(
    fact: FinancialFact,
    records: Iterable[SourceRecord],
    model: SemanticModel = SEMANTIC_MODEL,
) -> tuple[SourceRecord, ...]:
    """
    The source records that contribute to a computed fact.

    At account grain that is the account itself; at metric grain it is every
    account whose category the metric is composed from the semantic layer
    deciding what belongs to what, exactly as it does for the figures.
    """
    scoped = [r for r in records if r.current_period == fact.period or r.original_period == fact.period]

    if fact.grain is FactGrain.ACCOUNT:
        return tuple(r for r in scoped if r.account == fact.key)

    try:
        metric = model.metric(fact.key)
    except SemanticMappingError:
        return ()

    return tuple(
        record
        for record in scoped
        if metric.sign_for(model.account(record.account).category) != 0
    )


def root_causes(records: Sequence[SourceRecord]) -> tuple[RootCause, ...]:
    """
    Group records into derived causes, largest absolute impact first.

    Grouping is what turns a list of transactions into an explanation: five
    records become "unplanned customer workshops", stated once.
    """
    grouped: dict[str, list[SourceRecord]] = {}
    for record in records:
        grouped.setdefault(record.cause_id, []).append(record)

    causes = [
        RootCause(
            cause_id=cause_id,
            title=members[0].cause_title,
            explanation=members[0].cause_explanation,
            impact_eur=round(sum(r.impact_eur for r in members), 2),
            records=tuple(sorted(members, key=lambda r: (-abs(r.impact_eur), r.source_record_id))),
        )
        for cause_id, members in grouped.items()
    ]
    return tuple(sorted(causes, key=lambda c: (-abs(c.impact_eur), c.cause_id)))


def reconcile(
    fact: FinancialFact,
    records: Iterable[SourceRecord],
    model: SemanticModel = SEMANTIC_MODEL,
) -> Reconciliation:
    """Attribute a variance to causes, and state what is left unexplained."""
    attributed = records_for_fact(fact, records, model)
    causes = root_causes(attributed)
    return Reconciliation(
        metric_label=fact.label,
        variance=fact.variance,
        explained=round(sum(cause.impact_eur for cause in causes), 2),
        causes=causes,
    )


def _accounts_for_fact(fact: FinancialFact, model: SemanticModel) -> set[str] | None:
    """
    The account codes that roll up into a fact, or None if the fact's key is
    already an account code (grain=ACCOUNT).
    """
    if fact.grain is FactGrain.ACCOUNT:
        return {fact.key}
    try:
        metric = model.metric(fact.key)
    except SemanticMappingError:
        return set()
    return {
        account.code
        for account in model.accounts
        if metric.sign_for(account.category) != 0
    }


def _traceable_accounts(
    fact: FinancialFact,
    available: set[str],
    model: SemanticModel,
) -> set[str]:
    """
    The accounts to trace, or an empty set when no honest posting-level answer
    exists for this fact.

    A figure may only be traced to postings when the row ledger can actually
    reproduce it, which requires both:

    * **Full coverage** every account composing the metric is present in the
      ledger. Partial coverage would show some of the rows behind a figure as
      though they were all of them.
    * **A uniform sign** the metric adds its accounts rather than netting
      them. A composed metric such as Gross Margin (revenue *minus* direct
      costs) cannot be reconciled by summing raw posting amounts.

    V1 elaborates only Revenue to posting grain; the other metrics resolve to
    nothing here and the cockpit says so plainly rather than presenting a
    partial ledger as complete. Widening the demo dataset is what changes this,
    not a change to the reconciliation rule.
    """
    accounts = _accounts_for_fact(fact, model)
    if not accounts or not accounts <= available:
        return set()
    if fact.grain is not FactGrain.ACCOUNT:
        try:
            metric = model.metric(fact.key)
        except SemanticMappingError:  # pragma: no cover - guarded above
            return set()
        signs = {
            metric.sign_for(account.category)
            for account in model.accounts
            if account.code in accounts
        }
        if len(signs) > 1:
            return set()
    return accounts


def has_posting_grain(
    fact: FinancialFact,
    transactions: Iterable[TransactionLine],
    model: SemanticModel = SEMANTIC_MODEL,
) -> bool:
    """Whether a figure can honestly be traced to individual postings."""
    rows = [t for t in transactions if t.period == fact.period]
    return bool(_traceable_accounts(fact, {t.account for t in rows}, model))


def transactions_for_fact(
    fact: FinancialFact,
    transactions: Iterable[TransactionLine],
    model: SemanticModel = SEMANTIC_MODEL,
) -> tuple[TransactionLine, ...]:
    """The postings that sum to a fact's Actual figure, or none if it has no traceable ledger."""
    rows = [t for t in transactions if t.period == fact.period]
    accounts = _traceable_accounts(fact, {t.account for t in rows}, model)
    rows = [t for t in rows if t.account in accounts]
    if fact.business_unit:
        rows = [t for t in rows if t.business_unit == fact.business_unit]
    return tuple(sorted(rows, key=lambda t: (t.account, t.posting_date, t.transaction_id)))


def budget_lines_for_fact(
    fact: FinancialFact,
    budget_lines: Iterable[BudgetLine],
    model: SemanticModel = SEMANTIC_MODEL,
) -> tuple[BudgetLine, ...]:
    """The planning lines that sum to a fact's Budget figure, or none if it has no traceable ledger."""
    rows = [b for b in budget_lines if b.period == fact.period]
    accounts = _traceable_accounts(fact, {b.account for b in rows}, model)
    rows = [b for b in rows if b.account in accounts]
    if fact.business_unit:
        rows = [b for b in rows if b.business_unit == fact.business_unit]
    return tuple(sorted(rows, key=lambda b: (b.account, b.budget_line_id)))


def reconcile_actual(
    fact: FinancialFact,
    transactions: Iterable[TransactionLine],
    model: SemanticModel = SEMANTIC_MODEL,
) -> tuple[tuple[TransactionLine, ...], ReconciliationCheck]:
    """The transaction rows behind a fact's Actual, and whether they match it."""
    rows = transactions_for_fact(fact, transactions, model)
    total = round(sum(row.amount for row in rows), 2)
    return rows, ReconciliationCheck(
        label=f"{fact.label} Actual",
        displayed=fact.actual,
        source_total=total,
        row_count=len(rows),
    )


def reconcile_budget(
    fact: FinancialFact,
    budget_lines: Iterable[BudgetLine],
    model: SemanticModel = SEMANTIC_MODEL,
) -> tuple[tuple[BudgetLine, ...], ReconciliationCheck]:
    """The planning rows behind a fact's Budget, and whether they match it."""
    rows = budget_lines_for_fact(fact, budget_lines, model)
    total = round(sum(row.amount for row in rows), 2)
    return rows, ReconciliationCheck(
        label=f"{fact.label} Budget",
        displayed=fact.budget,
        source_total=total,
        row_count=len(rows),
    )


def variance_reconciliation(fact: FinancialFact) -> tuple[ReconciliationCheck, bool]:
    """
    The deterministic calculation, checked against itself.

    Not a second computation `variance = actual - budget` is computed exactly
    once, in `finance_engine.compute_variance`. This re-derives it from the
    fact's own actual/budget fields and confirms the fact agrees with its own
    arithmetic, so a future refactor that breaks the invariant fails loudly
    here rather than only in a UI screenshot.
    """
    if fact.budget is None or fact.variance is None:
        check = ReconciliationCheck(
            label=f"{fact.label} Variance", displayed=None, source_total=0.0, row_count=0
        )
        return check, True
    recomputed = round(fact.actual - fact.budget, 2)
    check = ReconciliationCheck(
        label=f"{fact.label} Variance",
        displayed=fact.variance,
        source_total=recomputed,
        row_count=1,
    )
    return check, check.reconciled


# --------------------------------------------------------------------------- #
# CSV export
# --------------------------------------------------------------------------- #


def _rows_to_csv(rows: Sequence, headers: Sequence[str]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([getattr(row, header) for header in headers])
    return buffer.getvalue()


#: Column order for the exported transaction CSV business-meaningful fields
#: only, matching what the Financial Transactions tab displays.
TRANSACTION_CSV_COLUMNS: tuple[str, ...] = (
    "transaction_id",
    "posting_date",
    "document_number",
    "period",
    "business_unit",
    "project_id",
    "project_name",
    "customer",
    "milestone_id",
    "milestone_name",
    "account",
    "cost_center",
    "currency",
    "amount",
    "source_system",
    "source_model",
)

BUDGET_LINE_CSV_COLUMNS: tuple[str, ...] = (
    "budget_line_id",
    "period",
    "business_unit",
    "project_id",
    "project_name",
    "customer",
    "milestone_id",
    "milestone_name",
    "account",
    "cost_center",
    "currency",
    "amount",
    "budget_version",
    "source_system",
    "source_model",
)


def transactions_to_csv(rows: Sequence[TransactionLine]) -> str:
    """Exactly the rows shown in the Financial Transactions tab, as CSV text."""
    return _rows_to_csv(rows, TRANSACTION_CSV_COLUMNS)


def budget_lines_to_csv(rows: Sequence[BudgetLine]) -> str:
    return _rows_to_csv(rows, BUDGET_LINE_CSV_COLUMNS)


def export_filename(
    *, prefix: str, metric_key: str, period: str, kind: str, extension: str = "csv"
) -> str:
    """A professional, predictable filename a controller can save and share."""
    safe_metric = metric_key.replace(" ", "_").lower()
    return f"{prefix}_{safe_metric}_{kind}_{period}.{extension}"


def contribution_breakdown(
    unit_facts: Sequence[FinancialFact],
    total: FinancialFact,
    unit_names: dict[str, str] | None = None,
) -> tuple[tuple[str, float | None], ...]:
    """
    Business-unit contributions plus the total, for an explicit reconciliation.

    Returned as ordered pairs so the caller can render "Projects −€310k,
    Service & Maintenance +€30k, Total −€280k" and let the reader add it up.
    """
    names = unit_names or {}
    rows = [
        (names.get(fact.business_unit or "", fact.business_unit or "Group"), fact.variance)
        for fact in unit_facts
    ]
    rows.sort(key=lambda pair: (pair[1] is None, pair[1] if pair[1] is not None else 0))
    rows.append((f"Total · {total.label}", total.variance))
    return tuple(rows)


# --------------------------------------------------------------------------- #
# Business lineage
# --------------------------------------------------------------------------- #


def _eur(value: float | None) -> str:
    """Sign leads, then the symbol the same convention as the cockpit."""
    if value is None:
        return " "
    return f"{'-' if value < 0 else ''}€{abs(value):,.0f}"


def business_lineage(
    *,
    cause: RootCause,
    fact: FinancialFact,
    transactions: Sequence[TransactionLine] = (),
    #: Whether this fact has a posting-level ledger at all. Distinguishes
    #: "nothing was posted" from "this metric is not carried to posting grain",
    #: which are different statements and must not share a caption.
    posting_grain: bool = True,
    rule_name: str | None,
    threshold_label: str | None,
    severity: str | None,
    interpretation_mode: str | None,
    confidence: str | None,
    review_label: str,
    reviewer: str | None,
    issue_status: str,
    owner: str | None,
    next_step: str | None,
    calc_version: str,
    model: SemanticModel = SEMANTIC_MODEL,
) -> tuple[LineageStep, ...]:
    """
    The chain a controller walks backwards, in business language.

        source record → business object → financial transaction → financial metric
        → control finding → root cause / interpretation → decision issue → action

    Technical metadata rides alongside each step but never leads.
    """
    record_ids = ", ".join(r.source_record_id for r in cause.records)
    objects = ", ".join(dict.fromkeys(r.business_object for r in cause.records))
    subjects = ", ".join(dict.fromkeys(r.subject for r in cause.records))

    if transactions:
        tx_total = round(sum(t.amount for t in transactions), 2)
        tx_headline = (
            f"{len(transactions)} posting{'' if len(transactions) == 1 else 's'} · "
            f"{_eur(tx_total)}"
        )
        # Summarised by main account, never listed posting by posting the
        # full ledger lives in the Financial Transactions tab and is not
        # duplicated into the chain.
        by_account: dict[str, float] = {}
        for line in transactions:
            by_account[line.account] = round(
                by_account.get(line.account, 0.0) + line.amount, 2
            )
        top = sorted(by_account.items(), key=lambda pair: -abs(pair[1]))[:3]
        names = []
        for code, _total in top:
            try:
                names.append(f"{code} · {model.account(code).name}")
            except SemanticMappingError:
                names.append(code)
        remainder = len(by_account) - len(top)
        accounts_line = "; ".join(names) + (
            f"; +{remainder} more" if remainder > 0 else ""
        )
        tx_detail = (
            f"Main accounts: {accounts_line}. "
            "Full posting list in the Financial Transactions tab."
        )
    elif posting_grain:
        tx_headline = "No postings this period"
        tx_detail = (
            "This is what the variance means: the plan assumed a posting here "
            "that did not occur."
        )
    else:
        # Absence of rows is not absence of activity: this metric simply has no
        # posting-level ledger in the reference dataset. Saying "no postings"
        # here would misreport a scope limit as a business fact.
        tx_headline = "Not elaborated to posting grain"
        tx_detail = (
            f"{fact.label} is composed from other accounts, which this reference "
            "dataset does not carry down to individual postings. The Source Records "
            "tab holds the evidence behind this movement."
        )

    steps = [
        LineageStep(
            "Source record",
            f"{len(cause.records)} record{'' if len(cause.records) == 1 else 's'} "
            f"in {', '.join(cause.systems)}",
            "; ".join(f"{r.source_record_id} · {r.reason}" for r in cause.records),
            f"documents: {'; '.join(cause.documents)}",
        ),
        LineageStep(
            "Business object",
            objects or " ",
            subjects or " ",
            f"record ids: {record_ids}",
        ),
        LineageStep(
            "Financial transaction",
            tx_headline,
            tx_detail,
            None,
        ),
        LineageStep(
            "Financial metric",
            f"{fact.label} · {fact.period}",
            f"Actual {_eur(fact.actual)} against a budget of {_eur(fact.budget)} · "
            f"variance {_eur(fact.variance)}"
            if fact.budget is not None and fact.variance is not None
            else f"Actual {_eur(fact.actual)} · no budget line for this account",
            f"fact id: {fact.fact_id} · calculation version {calc_version}",
        ),
        LineageStep(
            "Control finding",
            f"{rule_name or 'No rule fired'}"
            + (f" · {severity}" if severity else ""),
            f"threshold {threshold_label}" if threshold_label else " ",
            None,
        ),
        LineageStep(
            "Root cause / interpretation",
            cause.title,
            f"{cause.explanation} Drafted "
            f"{('by ' + interpretation_mode.lower()) if interpretation_mode else ''}"
            f"{(' · confidence ' + confidence.lower()) if confidence else ''}"
            " the interpretation explains the computed figures; it does not produce them.",
            None,
        ),
        LineageStep(
            "Decision issue",
            f"{review_label} · {issue_status}",
            f"Reviewed by {reviewer}" if reviewer else "Awaiting controller review.",
            None,
        ),
        LineageStep(
            "Action",
            f"Owner {owner}" if owner else "No owner assigned yet",
            f"Next step: {next_step}" if next_step else "No action recorded yet.",
            None,
        ),
    ]
    return tuple(steps)
