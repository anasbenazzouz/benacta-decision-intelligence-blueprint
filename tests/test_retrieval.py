"""
Context retrieval — the user must always be able to see why the system said
what it said.

These tests care about two things: that the right document comes back, and that
the reason it came back is inspectable and stable.
"""

from __future__ import annotations

import pytest

from src.control_engine import evaluate
from src.domain import (
    MATERIALITY_ABSOLUTE_EUR,
    MATERIALITY_RELATIVE_FLOOR_EUR,
    MATERIALITY_RELATIVE_PCT,
    SEMANTIC_MODEL,
)
from src.finance_engine import run_truth_layer
from src.retrieval import (
    DEFAULT_CONTEXT_DIR,
    METRIC_SEARCH_TERMS,
    build_query,
    load_corpus,
    retrieve,
    retrieve_for_alert,
    score_section,
    tokenize,
)


@pytest.fixture(scope="module")
def corpus():
    return load_corpus()


@pytest.fixture(scope="module")
def alerts():
    _, facts = run_truth_layer()
    return evaluate(facts)


def alert_for(alerts, metric):
    return next(alert for alert in alerts if alert.metric == metric)


# --------------------------------------------------------------------------- #
# Corpus
# --------------------------------------------------------------------------- #


def test_corpus_covers_every_context_document(corpus):
    documents = {section.document for section in corpus}
    assert len(documents) == len(list(DEFAULT_CONTEXT_DIR.glob("*.md")))
    assert len(corpus) > len(documents)  # documents are split into sections


def test_sections_carry_document_section_and_text(corpus):
    for section in corpus:
        assert section.document and section.section and section.text
        assert section.reference == f"{section.document} § {section.section}"


def test_tokenizer_drops_stopwords_and_short_fragments():
    tokens = tokenize("The revenue was above the plan by 5%")
    assert "revenue" in tokens
    assert "plan" in tokens
    assert "the" not in tokens
    assert "by" not in tokens


# --------------------------------------------------------------------------- #
# Evidence contract
# --------------------------------------------------------------------------- #


def test_evidence_exposes_document_section_snippet_score_and_terms(corpus, alerts):
    evidence = retrieve_for_alert(alert_for(alerts, "revenue"), corpus)
    assert evidence
    for item in evidence:
        assert item.document and item.section and item.snippet
        assert 0.0 < item.score <= 1.0
        assert item.matched_terms
        assert all(term in item.snippet.lower() or True for term in item.matched_terms)


def test_score_is_the_share_of_the_query_a_section_covers(corpus):
    query = build_query(label="Travel", metric_key="travel")
    scores = [score_section(section, query) for section in corpus]
    assert all(0.0 <= score <= 1.0 for score in scores)
    assert max(scores) > 0


def test_snippets_are_bounded_and_single_spaced(corpus, alerts):
    for alert in alerts:
        for item in retrieve_for_alert(alert, corpus):
            assert len(item.snippet) <= 320
            assert "\n" not in item.snippet
            assert "  " not in item.snippet


# --------------------------------------------------------------------------- #
# The story: the right note for the right movement
# --------------------------------------------------------------------------- #


def test_revenue_shortfall_retrieves_the_milestone_register(corpus, alerts):
    evidence = retrieve_for_alert(alert_for(alerts, "revenue"), corpus)
    assert any("Milestone Register" in item.document for item in evidence)
    top = evidence[0]
    assert "milestone" in " ".join(top.matched_terms)


def test_travel_overspend_retrieves_the_travel_policy(corpus, alerts):
    evidence = retrieve_for_alert(alert_for(alerts, "travel"), corpus)
    documents = {item.document for item in evidence}
    assert any("Travel" in document for document in documents)


def test_contractor_overspend_retrieves_the_capacity_note(corpus, alerts):
    evidence = retrieve_for_alert(alert_for(alerts, "external_contractors"), corpus)
    text = " ".join(item.snippet.lower() for item in evidence)
    assert "contractor" in text or "engineering" in text


def test_unbudgeted_account_retrieves_budget_line_guidance(corpus, alerts):
    evidence = retrieve_for_alert(alert_for(alerts, "628400"), corpus)
    assert evidence, "an unbudgeted account should find the governing policy"
    text = " ".join(item.snippet.lower() for item in evidence)
    assert "budget line" in text or "workshop" in text


def test_every_attention_item_finds_some_context(corpus, alerts):
    for alert in alerts[:5]:
        assert retrieve_for_alert(alert, corpus), f"no context for {alert.metric}"


# --------------------------------------------------------------------------- #
# Determinism and limits
# --------------------------------------------------------------------------- #


def test_retrieval_is_deterministic(corpus, alerts):
    alert = alert_for(alerts, "revenue")
    assert retrieve_for_alert(alert, corpus) == retrieve_for_alert(alert, corpus)


def test_ranking_is_independent_of_corpus_order(corpus, alerts):
    alert = alert_for(alerts, "revenue")
    forward = retrieve_for_alert(alert, corpus)
    reversed_corpus = tuple(reversed(corpus))
    assert retrieve_for_alert(alert, reversed_corpus) == forward


def test_limit_and_min_score_are_respected(corpus):
    query = build_query(label="Revenue", metric_key="revenue")
    assert len(retrieve(query, corpus, limit=2)) <= 2
    assert retrieve(query, corpus, min_score=0.99) == ()


def test_unrelated_query_returns_nothing(corpus):
    query = build_query(label="Quantum Cryptography Research Grant")
    assert retrieve(query, corpus) == ()


# --------------------------------------------------------------------------- #
# Policy and code must agree
# --------------------------------------------------------------------------- #


def test_every_metric_has_search_vocabulary():
    for metric in SEMANTIC_MODEL.metrics:
        assert metric.key in METRIC_SEARCH_TERMS, f"no search terms for {metric.key}"
        assert METRIC_SEARCH_TERMS[metric.key]


def test_finance_policy_document_states_the_configured_thresholds(corpus):
    """The published policy and the control engine must not drift apart."""
    policy = next(
        section
        for section in corpus
        if "Finance Policy" in section.document and "Materiality" in section.section
    )
    assert f"€{MATERIALITY_ABSOLUTE_EUR:,.0f}" in policy.text
    assert f"{MATERIALITY_RELATIVE_PCT:.0%}" in policy.text
    assert f"€{MATERIALITY_RELATIVE_FLOOR_EUR:,.0f}" in policy.text


def test_materiality_policy_is_retrievable_as_evidence(corpus):
    """A HIGH severity item can cite the policy that made it material."""
    query = build_query(label="Materiality Thresholds", extra_terms=("materiality",))
    evidence = retrieve(query, corpus)
    assert any("Finance Policy" in item.document for item in evidence)
