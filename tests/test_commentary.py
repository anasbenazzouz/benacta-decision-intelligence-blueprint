"""
Interpretation layer — AI explains, it does not compute.

The load-bearing test here is `test_demo_commentary_invents_no_numbers`: whatever
the interpretation layer writes, every figure in it must already exist in the
computed facts or in the quoted evidence. The same guard runs in production on
the LLM path, so these tests also prove the fallback works.
"""

from __future__ import annotations

import pytest

from src.commentary import (
    AnthropicProvider,
    Commentary,
    CommentaryRequest,
    Confidence,
    DemoProvider,
    InterpretationMode,
    allowed_numbers,
    build_payload,
    resolve_provider,
    verify_no_invented_numbers,
)
from src.control_engine import evaluate
from src.finance_engine import FactGrain, fact_for, run_truth_layer
from src.retrieval import load_corpus, retrieve_for_alert


@pytest.fixture(scope="module")
def pipeline_inputs():
    _, facts = run_truth_layer()
    alerts = evaluate(facts)
    corpus = load_corpus()
    return facts, alerts, corpus


def request_for(pipeline_inputs, metric, grain=FactGrain.METRIC):
    facts, alerts, corpus = pipeline_inputs
    alert = next(a for a in alerts if a.metric == metric)
    fact = fact_for(facts, metric, grain=grain)
    return CommentaryRequest(
        fact=fact,
        alert=alert,
        evidence=retrieve_for_alert(alert, corpus),
        supporting_facts=tuple(
            f
            for f in facts
            if f.grain is FactGrain.METRIC_BY_BUSINESS_UNIT and f.key == metric
        ),
    )


# --------------------------------------------------------------------------- #
# The no-invented-numbers invariant
# --------------------------------------------------------------------------- #


def test_demo_commentary_invents_no_numbers(pipeline_inputs):
    facts, alerts, corpus = pipeline_inputs
    provider = DemoProvider()

    for alert in alerts[:5]:
        grain = FactGrain.ACCOUNT if alert.account else FactGrain.METRIC
        request = request_for(pipeline_inputs, alert.metric, grain=grain)
        commentary = provider.generate(request)

        ok, offenders = verify_no_invented_numbers(
            commentary.generated_text, allowed_numbers(request)
        )
        assert ok, f"{alert.metric} commentary invented {offenders}"


def test_the_guard_actually_catches_an_invented_number(pipeline_inputs):
    """Guards the test above: a permissive guard would prove nothing."""
    request = request_for(pipeline_inputs, "revenue")
    ok, offenders = verify_no_invented_numbers(
        ("Revenue was €1,234,567 below budget.",), allowed_numbers(request)
    )
    assert not ok
    assert 1234567.0 in offenders


def test_computed_figures_and_quoted_evidence_are_both_permitted(pipeline_inputs):
    request = request_for(pipeline_inputs, "revenue")
    allowed = allowed_numbers(request)

    assert 4_720_000.0 in allowed  # actual
    assert 5_000_000.0 in allowed  # budget
    assert 280_000.0 in allowed  # variance
    assert 5.6 in allowed  # variance as a percentage
    assert 100_000.0 in allowed  # the threshold it breached


# --------------------------------------------------------------------------- #
# Demo provider content
# --------------------------------------------------------------------------- #


def test_summary_states_the_computed_movement(pipeline_inputs):
    commentary = DemoProvider().generate(request_for(pipeline_inputs, "revenue"))
    assert "€280,000 below budget" in commentary.summary
    assert "-5.6%" in commentary.summary
    assert "€4,720,000" in commentary.summary
    assert "July 2026" in commentary.summary


def test_causal_language_is_attributed_not_asserted(pipeline_inputs):
    commentary = DemoProvider().generate(request_for(pipeline_inputs, "revenue"))
    assert "associates" in commentary.summary
    assert "requires controller confirmation" in commentary.summary
    # Every driver either quotes a source or restates computed figures.
    assert commentary.drivers


def test_drivers_include_the_business_unit_drill_down(pipeline_inputs):
    commentary = DemoProvider().generate(request_for(pipeline_inputs, "revenue"))
    joined = " ".join(commentary.drivers)
    assert "BU-PRJ" in joined and "BU-SVC" in joined
    assert "€3,090,000" in joined


def test_evidence_is_carried_through_untouched(pipeline_inputs):
    request = request_for(pipeline_inputs, "revenue")
    commentary = DemoProvider().generate(request)
    assert commentary.evidence == request.evidence


def test_follow_up_is_a_suggestion_never_a_decision(pipeline_inputs):
    commentary = DemoProvider().generate(request_for(pipeline_inputs, "revenue"))
    assert commentary.suggested_follow_up == (
        "Review milestone recognition with Project Finance.",
    )
    text = " ".join(commentary.generated_text).lower()
    assert "ai decision" not in text
    assert "we have decided" not in text


def test_missing_budget_commentary_explains_it_cannot_be_assessed(pipeline_inputs):
    commentary = DemoProvider().generate(
        request_for(pipeline_inputs, "628400", grain=FactGrain.ACCOUNT)
    )
    assert "no budget line" in commentary.summary
    assert "cannot be assessed" in commentary.summary
    assert any("budget line" in step for step in commentary.suggested_follow_up)


def test_favorable_movement_asks_whether_it_will_reverse(pipeline_inputs):
    commentary = DemoProvider().generate(
        request_for(pipeline_inputs, "direct_project_costs")
    )
    assert any("reverse" in question for question in commentary.open_questions)


def test_confidence_tracks_evidence_coverage(pipeline_inputs):
    facts, alerts, _ = pipeline_inputs
    bare = CommentaryRequest(fact=fact_for(facts, "revenue"), evidence=())
    assert DemoProvider().generate(bare).confidence is Confidence.LOW
    assert "No supporting business context" in DemoProvider().generate(bare).summary

    supported = DemoProvider().generate(request_for(pipeline_inputs, "revenue"))
    assert supported.confidence in (Confidence.MEDIUM, Confidence.HIGH)


def test_demo_commentary_is_deterministic(pipeline_inputs):
    request = request_for(pipeline_inputs, "revenue")
    assert DemoProvider().generate(request) == DemoProvider().generate(request)


# --------------------------------------------------------------------------- #
# The model receives facts, never the ledger
# --------------------------------------------------------------------------- #


def test_payload_contains_only_computed_facts_and_evidence(pipeline_inputs):
    payload = build_payload(request_for(pipeline_inputs, "revenue"))

    assert set(payload) <= {
        "currency",
        "computed_fact",
        "supporting_facts",
        "retrieved_evidence",
        "control_alert",
    }
    assert payload["computed_fact"]["variance"] == -280_000.0
    # No raw ledger, no source rows, no file paths.
    serialised = str(payload)
    assert "actuals.csv" not in serialised
    assert "cost_center" not in serialised


# --------------------------------------------------------------------------- #
# The LLM path is governed, and degrades safely
# --------------------------------------------------------------------------- #


class _StubResponse:
    def __init__(self, text, stop_reason="end_turn"):
        self.stop_reason = stop_reason
        self.content = [type("Block", (), {"type": "text", "text": text})()]


class _StubClient:
    """Stands in for anthropic.Anthropic — no network, no key."""

    def __init__(self, text, stop_reason="end_turn"):
        response = _StubResponse(text, stop_reason)
        self.messages = type("Messages", (), {"create": lambda _self, **_kw: response})()


_CLEAN_OUTPUT = """
{"summary": "Revenue finished €280,000 below budget (-5.6%) at €4,720,000.",
 "drivers": ["Projects revenue was €3,090,000 against a plan of €3,400,000."],
 "open_questions": ["Are the August acceptance dates confirmed?"],
 "suggested_follow_up": ["Review milestone recognition with Project Finance."],
 "confidence": "MEDIUM"}
"""

_INVENTED_OUTPUT = """
{"summary": "Revenue finished €280,000 below budget, a €1,234,567 annual impact.",
 "drivers": [], "open_questions": [], "suggested_follow_up": [],
 "confidence": "HIGH"}
"""


def test_valid_llm_output_is_accepted(pipeline_inputs):
    provider = AnthropicProvider(model="claude-opus-5", client=_StubClient(_CLEAN_OUTPUT))
    commentary = provider.generate(request_for(pipeline_inputs, "revenue"))

    assert commentary.mode is InterpretationMode.LLM
    assert commentary.model == "claude-opus-5"
    assert commentary.fallback_reason is None


def test_invented_numbers_are_rejected_and_the_draft_falls_back(pipeline_inputs):
    provider = AnthropicProvider(model="claude-opus-5", client=_StubClient(_INVENTED_OUTPUT))
    commentary = provider.generate(request_for(pipeline_inputs, "revenue"))

    assert commentary.mode is InterpretationMode.DEMO
    assert "1,234,567.00" in commentary.fallback_reason
    assert "€280,000 below budget" in commentary.summary  # the deterministic draft


def test_a_refusal_falls_back_rather_than_failing(pipeline_inputs):
    provider = AnthropicProvider(
        model="claude-opus-5", client=_StubClient(_CLEAN_OUTPUT, stop_reason="refusal")
    )
    commentary = provider.generate(request_for(pipeline_inputs, "revenue"))
    assert commentary.mode is InterpretationMode.DEMO
    assert "LLM call failed" in commentary.fallback_reason


def test_malformed_llm_output_falls_back(pipeline_inputs):
    provider = AnthropicProvider(model="claude-opus-5", client=_StubClient("not json"))
    commentary = provider.generate(request_for(pipeline_inputs, "revenue"))
    assert commentary.mode is InterpretationMode.DEMO
    assert commentary.fallback_reason


# --------------------------------------------------------------------------- #
# Provider resolution
# --------------------------------------------------------------------------- #


def test_demo_mode_is_the_default(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    provider, reason = resolve_provider()
    assert isinstance(provider, DemoProvider)
    assert "DEMO_MODE" in reason


def test_no_api_key_degrades_visibly_instead_of_failing(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    provider, reason = resolve_provider()
    assert isinstance(provider, DemoProvider)
    assert "demo commentary" in reason
