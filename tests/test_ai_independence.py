"""
The trust boundary, enforced.

This is the philosophically load-bearing test file for BENACTA. The claim the
whole project makes — *code computes, AI explains, humans decide* — is only
credible if the financial truth layer keeps working, unchanged, when the AI
layer is removed entirely.

Two independent proofs:

1. Structural — the deterministic modules have no import path to any LLM SDK or
   to the interpretation layer. Verified by parsing the source, so it holds even
   for code paths the tests never execute.

2. Behavioural — with those imports actively blocked at the import system level,
   the truth layer is re-imported from scratch and produces byte-identical
   results: the same facts, the same controls, the same materiality.

If either fails, the architecture is not what the documents claim.
"""

from __future__ import annotations

import ast
import importlib
import importlib.abc
import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parent.parent / "src"

#: Everything above the trust boundary. Nothing here may depend on an LLM.
#: Retrieval belongs on this side: it selects and quotes existing text with a
#: transparent score, and generates nothing.
DETERMINISTIC_MODULES = (
    "domain",
    "finance_engine",
    "control_engine",
    "retrieval",
    "lineage",
)

#: Import roots that would indicate the truth layer had grown an AI dependency.
FORBIDDEN_ROOTS = frozenset(
    {
        "anthropic",
        "openai",
        "cohere",
        "mistralai",
        "ollama",
        "transformers",
        "langchain",
        "langchain_core",
        "langchain_community",
        "llama_index",
        "google",  # google.generativeai
        "vertexai",
        "sentence_transformers",
        "chromadb",
        "faiss",
        "pinecone",
        "qdrant_client",
        "weaviate",
    }
)

#: The interpretation layer itself (built in a later phase). The truth layer must
#: never import it — the dependency only ever points the other way.
INTERPRETATION_MODULES = frozenset({"src.commentary", "commentary"})


# --------------------------------------------------------------------------- #
# 1. Structural proof
# --------------------------------------------------------------------------- #


def _imported_names(module_name: str) -> set[str]:
    """Every module name imported by a src module, without executing it."""
    tree = ast.parse((SRC_DIR / f"{module_name}.py").read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative: from . import x  /  from .x import y
                base = f"src.{node.module}" if node.module else "src"
                names.add(base)
                if node.module is None:
                    names.update(f"src.{alias.name}" for alias in node.names)
            elif node.module:
                names.add(node.module)
    return names


def _local_dependencies(names: set[str]) -> set[str]:
    return {
        name.split(".", 1)[1]
        for name in names
        if name.startswith("src.") and name.count(".") == 1
    }


def _transitive_imports(start: tuple[str, ...]) -> dict[str, set[str]]:
    """Walk the local dependency graph so indirect AI imports cannot hide."""
    seen: dict[str, set[str]] = {}
    queue = list(start)
    while queue:
        module = queue.pop()
        if module in seen:
            continue
        if not (SRC_DIR / f"{module}.py").exists():
            continue
        names = _imported_names(module)
        seen[module] = names
        queue.extend(_local_dependencies(names) - seen.keys())
    return seen


def test_deterministic_modules_do_not_import_any_llm_sdk():
    graph = _transitive_imports(DETERMINISTIC_MODULES)
    assert set(DETERMINISTIC_MODULES) <= graph.keys()

    for module, names in graph.items():
        roots = {name.split(".")[0] for name in names}
        offending = roots & FORBIDDEN_ROOTS
        assert not offending, f"src/{module}.py imports {sorted(offending)}"


def test_deterministic_modules_do_not_import_the_interpretation_layer():
    for module, names in _transitive_imports(DETERMINISTIC_MODULES).items():
        offending = names & INTERPRETATION_MODULES
        assert not offending, f"src/{module}.py imports {sorted(offending)}"


def test_importing_the_truth_layer_pulls_in_no_llm_sdk():
    for module in DETERMINISTIC_MODULES:
        importlib.import_module(f"src.{module}")
    loaded_roots = {name.split(".")[0] for name in sys.modules}
    assert not (loaded_roots & FORBIDDEN_ROOTS)


# --------------------------------------------------------------------------- #
# 2. Behavioural proof
# --------------------------------------------------------------------------- #


class _BlockedImportFinder(importlib.abc.MetaPathFinder):
    """Makes the blocked modules genuinely unimportable, as if uninstalled."""

    def __init__(self, blocked: frozenset[str]) -> None:
        self._blocked = blocked

    def find_spec(self, fullname, path=None, target=None):  # noqa: D102, ANN001
        if fullname in self._blocked or fullname.split(".")[0] in self._blocked:
            raise ImportError(
                f"{fullname} is unavailable: the AI layer is disabled for this test"
            )
        return None


def _project(facts) -> list[tuple]:
    """Compare facts across separate module instances by value, not identity."""
    return [
        (
            fact.key,
            fact.grain.value,
            fact.business_unit,
            fact.actual,
            fact.budget,
            fact.variance,
            fact.variance_pct,
            fact.direction.value,
            fact.materiality.value,
        )
        for fact in facts
    ]


def _project_alerts(alerts) -> list[tuple]:
    return [
        (
            alert.rule_id,
            alert.severity.value,
            alert.metric,
            alert.value,
            alert.direction.value,
            alert.business_message,
        )
        for alert in alerts
    ]


def _run_truth_layer_with_ai_blocked():
    """Re-import and run the truth layer with every AI import made impossible."""
    finder = _BlockedImportFinder(frozenset(FORBIDDEN_ROOTS | INTERPRETATION_MODULES))
    preserved = {k: v for k, v in sys.modules.items() if k == "src" or k.startswith("src.")}

    for name in list(sys.modules):
        if name == "src" or name.startswith("src."):
            del sys.modules[name]
    sys.meta_path.insert(0, finder)
    try:
        finance_engine = importlib.import_module("src.finance_engine")
        control_engine = importlib.import_module("src.control_engine")

        ledger, facts = finance_engine.run_truth_layer()
        alerts = control_engine.evaluate(facts)
        return ledger, facts, alerts, finance_engine
    finally:
        sys.meta_path.remove(finder)
        for name in list(sys.modules):
            if name == "src" or name.startswith("src."):
                del sys.modules[name]
        sys.modules.update(preserved)


def test_financial_truth_is_independent_from_llm():
    """
    With the AI layer disabled, the system still produces the complete truth:
    business objects, actuals, budgets, variances, variance percentages,
    materiality and control alerts — identical to a normal run.
    """
    from src.control_engine import evaluate
    from src.finance_engine import run_truth_layer

    reference_ledger, reference_facts = run_truth_layer()
    reference_alerts = evaluate(reference_facts)

    ledger, facts, alerts, engine = _run_truth_layer_with_ai_blocked()

    # Business objects survive the round trip.
    assert len(ledger.actuals) == len(reference_ledger.actuals)
    assert {entry.account.code for entry in ledger.actuals} == {
        entry.account.code for entry in reference_ledger.actuals
    }

    # The numbers are not merely present — they are unchanged.
    assert _project(facts) == _project(reference_facts)
    assert _project_alerts(alerts) == _project_alerts(reference_alerts)

    # And the headline truth is still the truth.
    revenue = engine.fact_for(facts, "revenue")
    assert revenue.actual == 4_720_000.00
    assert revenue.budget == 5_000_000.00
    assert revenue.variance == -280_000.00
    assert revenue.variance_pct == pytest.approx(-0.056)
    assert revenue.materiality.value == "HIGH"

    assert alerts, "controls must still fire with no AI layer present"
    assert alerts[0].metric == "revenue"
    assert alerts[0].severity.value == "HIGH"


def test_the_blocking_mechanism_actually_blocks():
    """Guards the test above: if blocking silently failed, it would prove nothing."""
    finder = _BlockedImportFinder(frozenset({"anthropic"}))
    sys.meta_path.insert(0, finder)
    try:
        with pytest.raises(ImportError):
            importlib.import_module("anthropic")
    finally:
        sys.meta_path.remove(finder)


def test_truth_layer_needs_no_api_key(monkeypatch):
    for variable in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEMO_MODE"):
        monkeypatch.delenv(variable, raising=False)

    from src.control_engine import evaluate
    from src.finance_engine import run_truth_layer

    _, facts = run_truth_layer()
    assert len(facts) > 0
    assert len(evaluate(facts)) > 0
