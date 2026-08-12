"""
BENACTA — AI Interpretation Layer.

This is the only module below the trust boundary, and the only one permitted to
talk to a language model. It receives computed facts, control alerts and
retrieved evidence — all produced upstream — and returns a *draft* explanation
that a human must approve before it means anything.

What it may never do:

  * compute, recompute or adjust a figure
  * introduce a number that is not in the facts or the quoted evidence
  * assert a cause the evidence does not support

The last two are not left to good intentions. `verify_no_invented_numbers` is
production code, not a test helper: the LLM path runs it on its own output and
falls back to the deterministic demo commentary if it fails. That is a
faithfulness check in miniature, in the spirit of Architecture Note #001.

DEMO_MODE=true (the default) uses controlled templates and needs no API key.
"""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping, Sequence

from src.control_engine import ControlAlert, Severity
from src.finance_engine import FinancialFact, VarianceDirection
from src.retrieval import Evidence

try:  # optional dependency — the application is fully functional without it
    import anthropic
except ImportError:  # pragma: no cover - exercised by environments without the SDK
    anthropic = None

#: Used only when DEMO_MODE=false and a key is available.
DEFAULT_MODEL = os.environ.get("BENACTA_MODEL", "claude-opus-5")

_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

_NUMBER_PATTERN = re.compile(r"\d[\d,]*(?:\.\d+)?")


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class InterpretationMode(str, Enum):
    DEMO = "DEMO"
    LLM = "LLM"


@dataclass(frozen=True)
class CommentaryRequest:
    """Everything the interpretation layer is allowed to see."""

    fact: FinancialFact
    alert: ControlAlert | None = None
    evidence: tuple[Evidence, ...] = ()
    supporting_facts: tuple[FinancialFact, ...] = ()
    #: Business unit key -> name, so commentary reads "Projects", not "BU-PRJ".
    #: Supplied from the semantic layer; the facts themselves carry only keys.
    unit_names: Mapping[str, str] = field(default_factory=dict)

    def unit_label(self, fact: FinancialFact) -> str:
        if not fact.business_unit:
            return "Group"
        return self.unit_names.get(fact.business_unit, fact.business_unit)


@dataclass(frozen=True)
class Commentary:
    """A governed draft. Not truth, and not a decision."""

    summary: str
    drivers: tuple[str, ...]
    evidence: tuple[Evidence, ...]
    open_questions: tuple[str, ...]
    suggested_follow_up: tuple[str, ...]
    confidence: Confidence
    mode: InterpretationMode
    model: str | None = None
    fallback_reason: str | None = None

    @property
    def generated_text(self) -> tuple[str, ...]:
        """The prose this layer wrote — as opposed to evidence it quoted."""
        return (self.summary, *self.drivers, *self.open_questions, *self.suggested_follow_up)


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #


def _format_eur(amount: float) -> str:
    rounded = round(abs(amount), 2)
    if rounded == int(rounded):
        return f"€{rounded:,.0f}"
    return f"€{rounded:,.2f}"


def _format_period(period: str) -> str:
    try:
        year, month = period.split("-")
        return f"{_MONTHS[int(month) - 1]} {year}"
    except (ValueError, IndexError):
        return period


def _first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return parts[0].strip() if parts else text.strip()


# --------------------------------------------------------------------------- #
# The no-invented-numbers guard
# --------------------------------------------------------------------------- #


def _numbers_in(text: str) -> set[float]:
    values: set[float] = set()
    for match in _NUMBER_PATTERN.findall(text):
        try:
            values.add(abs(float(match.replace(",", ""))))
        except ValueError:  # pragma: no cover - defensive
            continue
    return values


def allowed_numbers(request: CommentaryRequest) -> set[float]:
    """
    Every number the interpretation layer is permitted to write.

    That is: the computed figures it was given, the control threshold it
    breached, the period itself, and any number appearing verbatim in the
    retrieved evidence — a figure quoted from a source document with
    attribution is reported, not invented.
    """
    values: set[float] = set()

    def add_ratio(value: float | None) -> None:
        """A ratio may appear as itself or as a rounded percentage (-18.8%)."""
        if value is None:
            return
        values.add(abs(value))
        values.update(round(abs(value) * 100, dp) for dp in (0, 1, 2))

    for fact in (request.fact, *request.supporting_facts):
        for value in (fact.actual, fact.budget, fact.variance):
            if value is not None:
                values.add(abs(value))
        add_ratio(fact.variance_pct)

    if request.alert is not None and request.alert.threshold is not None:
        # A threshold is either money (€100,000) or a ratio (10%).
        threshold = request.alert.threshold
        values.add(abs(threshold))
        if abs(threshold) <= 1:
            add_ratio(threshold)

    for part in request.fact.period.split("-"):
        try:
            values.add(abs(float(part)))
        except ValueError:  # pragma: no cover - defensive
            continue

    for evidence in request.evidence:
        # The snippet and the reference it is attributed to are both quoted
        # source text — a document titled "… FY26" contributes its own numbers.
        values |= _numbers_in(evidence.snippet)
        values |= _numbers_in(evidence.document)
        values |= _numbers_in(evidence.section)

    return values


def verify_no_invented_numbers(
    texts: Iterable[str], allowed: Iterable[float]
) -> tuple[bool, tuple[float, ...]]:
    """Return (ok, offending values) for generated prose."""
    permitted = {round(abs(value), 2) for value in allowed}
    offenders: list[float] = []
    for text in texts:
        for number in _numbers_in(text):
            if round(number, 2) not in permitted:
                offenders.append(number)
    return (not offenders, tuple(sorted(set(offenders))))


# --------------------------------------------------------------------------- #
# Provider interface
# --------------------------------------------------------------------------- #


class CommentaryProvider(ABC):
    """Small seam so the AI layer can be swapped or removed entirely."""

    name: str

    @abstractmethod
    def generate(self, request: CommentaryRequest) -> Commentary:
        """Draft an interpretation of one computed movement."""


# --------------------------------------------------------------------------- #
# Demo provider — the default, no API key required
# --------------------------------------------------------------------------- #

#: Follow-ups a controller would actually recognise, per movement.
_FOLLOW_UPS: dict[str, str] = {
    "revenue": "Review milestone recognition with Project Finance.",
    "ebitda": "Review the drivers of the EBITDA shortfall with the business unit controllers.",
    "gross_margin": "Review margin drivers with Project Finance and Procurement.",
    "external_contractors": (
        "Review external engineering capacity and the open recruitment with the budget holder."
    ),
    "travel": "Confirm the unplanned workshop travel against the travel policy with the cost center manager.",
    "direct_materials": "Confirm whether the procurement saving is sustainable or a timing difference.",
    "direct_project_costs": (
        "Confirm with Project Finance that the deferred project costs follow the milestones into August."
    ),
}


class DemoProvider(CommentaryProvider):
    """
    Template-based interpretation, assembled only from facts and evidence.

    Deterministic and offline. Every figure it writes comes from the request;
    every causal statement is attributed to the document it came from.
    """

    name = "demo"

    def generate(self, request: CommentaryRequest) -> Commentary:
        fact = request.fact
        evidence = request.evidence

        return Commentary(
            summary=self._summary(request),
            drivers=self._drivers(request),
            evidence=evidence,
            open_questions=self._open_questions(request),
            suggested_follow_up=self._follow_ups(request),
            confidence=self._confidence(evidence),
            mode=InterpretationMode.DEMO,
        )

    # -- sections --------------------------------------------------------- #

    def _summary(self, request: CommentaryRequest) -> str:
        fact = request.fact
        period = _format_period(fact.period)

        if fact.variance is None or fact.budget is None:
            summary = (
                f"{fact.label} recorded {_format_eur(fact.actual)} of actuals in "
                f"{period} with no budget line, so the movement cannot be assessed "
                f"against plan."
            )
        else:
            position = "below" if fact.variance < 0 else "above"
            pct = f" ({fact.variance_pct:+.1%})" if fact.variance_pct is not None else ""
            summary = (
                f"{fact.label} finished {_format_eur(fact.variance)} {position} budget"
                f"{pct} in {period}, at {_format_eur(fact.actual)} against a plan of "
                f"{_format_eur(fact.budget)}."
            )

        if request.evidence:
            top = request.evidence[0]
            summary += (
                f" Retrieved business context associates the movement with "
                f"{top.reference}; the association is indicative and requires "
                f"controller confirmation."
            )
        else:
            summary += (
                " No supporting business context was retrieved, so the driver is "
                "not established."
            )
        return summary

    def _drivers(self, request: CommentaryRequest) -> tuple[str, ...]:
        drivers: list[str] = []

        for support in request.supporting_facts:
            if support.variance is None or support.budget is None:
                continue
            unit = request.unit_label(support)
            drivers.append(
                f"{unit}: {_format_eur(support.actual)} against a plan of "
                f"{_format_eur(support.budget)} "
                f"({'-' if support.variance < 0 else '+'}{_format_eur(support.variance)})."
            )

        for item in request.evidence:
            drivers.append(f"{_first_sentence(item.snippet)} — {item.reference}.")

        return tuple(drivers)

    def _open_questions(self, request: CommentaryRequest) -> tuple[str, ...]:
        fact = request.fact
        questions: list[str] = []

        if not request.evidence:
            questions.append(
                f"No business context was retrieved for the {fact.label} movement. "
                f"Which owner can explain it?"
            )
        elif fact.variance is not None:
            questions.append(
                f"Does the retrieved context fully account for the "
                f"{_format_eur(fact.variance)} movement, or are further drivers "
                f"outstanding?"
            )

        if fact.direction is VarianceDirection.FAVORABLE:
            questions.append(
                "Is the favourable movement a timing difference that will reverse "
                "in a later period?"
            )

        if fact.budget is None:
            questions.append(
                "Which budget owner should open or reallocate the budget line for "
                "this account?"
            )

        return tuple(questions)

    def _follow_ups(self, request: CommentaryRequest) -> tuple[str, ...]:
        fact = request.fact

        if fact.budget is None:
            return (
                "Open or reallocate a budget line for this account before the next close.",
            )

        follow_up = _FOLLOW_UPS.get(
            fact.key,
            f"Review the {fact.label} movement with the responsible budget holder.",
        )
        return (follow_up,)

    def _confidence(self, evidence: Sequence[Evidence]) -> Confidence:
        """Confidence tracks evidence coverage — nothing else."""
        if not evidence:
            return Confidence.LOW
        if len(evidence) >= 2 and evidence[0].score >= 0.5:
            return Confidence.HIGH
        return Confidence.MEDIUM


# --------------------------------------------------------------------------- #
# Optional LLM provider
# --------------------------------------------------------------------------- #

_SYSTEM_PROMPT = """\
You are drafting finance commentary for a monthly performance review at a \
mid-sized industrial group. A qualified controller reviews and approves \
everything you write before it is published.

The figures have already been computed by a deterministic finance engine. Your \
role is to explain them, never to produce them.

Rules:
- Never invent, recalculate, adjust or extrapolate a number. Use only figures \
present in the supplied facts, or figures quoted verbatim from the supplied \
evidence.
- Never assert a cause the evidence does not support. Attribute every causal \
statement to the document it came from, and phrase unproven links as \
association rather than causation.
- Distinguish evidence from inference. Anything not established by the supplied \
material belongs in open_questions.
- If the evidence is insufficient, say so plainly and set confidence to LOW.
- A suggested follow-up is a proposal for a human, never a decision or an \
instruction. Never describe your output as a decision.
- Write for a CFO: concise, specific, no AI or engineering vocabulary.
"""

COMMENTARY_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "drivers": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "suggested_follow_up": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
    },
    "required": [
        "summary",
        "drivers",
        "open_questions",
        "suggested_follow_up",
        "confidence",
    ],
    "additionalProperties": False,
}


def build_payload(request: CommentaryRequest) -> dict:
    """The complete, and only, input the model receives."""

    def fact_payload(fact: FinancialFact) -> dict:
        return {
            "metric": fact.label,
            "period": fact.period,
            "business_unit": request.unit_label(fact) if fact.business_unit else None,
            "actual": fact.actual,
            "budget": fact.budget,
            "variance": fact.variance,
            "variance_pct": fact.variance_pct,
            "direction": fact.direction.value,
            "materiality": fact.materiality.value,
        }

    payload: dict = {
        "currency": "EUR",
        "computed_fact": fact_payload(request.fact),
        "supporting_facts": [fact_payload(f) for f in request.supporting_facts],
        "retrieved_evidence": [
            {
                "document": e.document,
                "section": e.section,
                "snippet": e.snippet,
                "relevance": e.score,
            }
            for e in request.evidence
        ],
    }
    if request.alert is not None:
        payload["control_alert"] = {
            "rule": request.alert.rule_name,
            "severity": request.alert.severity.value,
            "threshold": request.alert.threshold_label,
            "message": request.alert.business_message,
        }
    return payload


class AnthropicProvider(CommentaryProvider):
    """
    Real LLM commentary, behind the same interface as the demo provider.

    The model gets computed facts and quoted evidence — never the ledger. Its
    output is validated before it is accepted; on any failure the deterministic
    demo commentary is returned instead, with the reason recorded for the audit
    trail.
    """

    name = "anthropic"

    def __init__(self, model: str = DEFAULT_MODEL, client=None) -> None:
        if anthropic is None and client is None:  # pragma: no cover - guarded upstream
            raise RuntimeError("The 'anthropic' package is not installed.")
        self.model = model
        self._client = client or anthropic.Anthropic()
        self._fallback = DemoProvider()

    def generate(self, request: CommentaryRequest) -> Commentary:
        try:
            data = self._call(request)
        except Exception as exc:  # noqa: BLE001 - any failure must degrade safely
            return self._degrade(request, f"LLM call failed: {type(exc).__name__}")

        generated = (
            data["summary"],
            *data["drivers"],
            *data["open_questions"],
            *data["suggested_follow_up"],
        )
        ok, offenders = verify_no_invented_numbers(generated, allowed_numbers(request))
        if not ok:
            return self._degrade(
                request,
                "LLM output contained figures absent from the computed facts and "
                f"evidence: {', '.join(f'{n:,.2f}' for n in offenders)}",
            )

        return Commentary(
            summary=data["summary"],
            drivers=tuple(data["drivers"]),
            evidence=request.evidence,
            open_questions=tuple(data["open_questions"]),
            suggested_follow_up=tuple(data["suggested_follow_up"]),
            confidence=Confidence(data["confidence"]),
            mode=InterpretationMode.LLM,
            model=self.model,
        )

    def _call(self, request: CommentaryRequest) -> dict:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(build_payload(request), indent=2),
                }
            ],
            output_config={
                "format": {"type": "json_schema", "schema": COMMENTARY_SCHEMA},
                "effort": "medium",
            },
        )
        if getattr(response, "stop_reason", None) == "refusal":
            raise RuntimeError("model declined the request")
        text = next(block.text for block in response.content if block.type == "text")
        return json.loads(text)

    def _degrade(self, request: CommentaryRequest, reason: str) -> Commentary:
        commentary = self._fallback.generate(request)
        return Commentary(
            summary=commentary.summary,
            drivers=commentary.drivers,
            evidence=commentary.evidence,
            open_questions=commentary.open_questions,
            suggested_follow_up=commentary.suggested_follow_up,
            confidence=commentary.confidence,
            mode=InterpretationMode.DEMO,
            model=None,
            fallback_reason=reason,
        )


# --------------------------------------------------------------------------- #
# Provider resolution
# --------------------------------------------------------------------------- #


def demo_mode_enabled() -> bool:
    return os.environ.get("DEMO_MODE", "true").strip().lower() not in {
        "false",
        "0",
        "no",
        "off",
    }


def resolve_provider(
    *, demo_mode: bool | None = None, model: str = DEFAULT_MODEL
) -> tuple[CommentaryProvider, str]:
    """
    Choose the interpretation provider, and say why.

    Demo mode is the default and the supported public configuration. Every path
    that cannot reach a real model degrades to it visibly rather than failing.
    """
    if demo_mode is None:
        demo_mode = demo_mode_enabled()

    if demo_mode:
        return DemoProvider(), "DEMO_MODE is enabled; commentary is template-based."
    if anthropic is None:
        return DemoProvider(), "The 'anthropic' package is not installed; using demo commentary."
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return DemoProvider(), "No ANTHROPIC_API_KEY is set; using demo commentary."

    return AnthropicProvider(model=model), f"Live commentary via {model}."
