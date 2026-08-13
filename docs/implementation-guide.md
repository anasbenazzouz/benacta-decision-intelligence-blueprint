# BENACTA Implementation Guide

> For readers who want to run, extend or adapt the reference implementation. Practical, not philosophical. Architecture and data contracts: `docs/architecture.md`.

## Running it

```bash
pip install -r requirements.txt
cp .env.example .env             # DEMO_MODE=true by default
pytest -q                        # 155 passed, no API key needed
streamlit run app.py
```

`requirements-dev.txt` adds `pytest` on top of the runtime dependencies. There is no build step, no database and no external service to stand up; the whole application runs from the CSVs and markdown files in `data/`.

## How the pieces fit together

`src/pipeline.py` is the one place that wires the loop end to end (`build_session()`), so the Streamlit app (`app.py`) and the CLI demo (`scripts/demo_decision_loop.py`) always drive the same pipeline rather than two versions that could drift apart. Reading `build_session()` top to bottom is the fastest way to understand the whole system: load the ledger → compute facts → evaluate controls → load source lineage → retrieve evidence per alert → draft commentary → seed a `DecisionItem` per issue, all while writing to the audit trail.

Everything before `src/commentary.py` in the module list is deterministic and has no import path to an LLM SDK; `tests/test_ai_independence.py` enforces this rather than just documenting it. `src/commentary.py` is the only module allowed to cross that line.

## Extending the reference scenario

These are the seams a real engagement would extend (see also `docs/architecture.md` §10). Each is a small, local change; nothing here requires touching the trust boundary.

**Add a metric.** Add a `MetricDefinition` to `METRICS` in `src/domain.py`, composed of existing `AccountCategory` values with a sign and a `higher_is_better` direction. The finance engine, control engine and cockpit KPI band pick it up automatically; metrics are computed generically over the semantic model, not hand-coded per metric.

**Add a control rule.** Add a `ControlRule` to `RULES` in `src/control_engine.py` with a predicate over `FinancialFact`, a base severity and a priority (lower wins when multiple rules fire on one fact). Keep the materiality thresholds themselves in `src/domain.py`, alongside `data/context/finance_policy.md`, so the two can't drift apart; the policy document should always be able to explain *why* a rule exists.

**Add context.** Drop a new markdown file into `data/context/`, structured with `##` section headings (the retrieval layer splits on them). Add its vocabulary to `METRIC_SEARCH_TERMS` in `src/retrieval.py` if it should surface for a specific metric.

**Swap or add a commentary provider.** Implement `CommentaryProvider.generate()` (see `AnthropicProvider` in `src/commentary.py` for the reference shape: call the model, then run `verify_no_invented_numbers` on the output before accepting it, falling back to `DemoProvider` on any failure; never let a provider fail loudly into the UI). Wire it into `resolve_provider()`.

**Extend the semantic model.** New business units, cost centers or accounts go in `src/domain.py`'s `SEMANTIC_MODEL`. Extract rows referencing anything not in that model are rejected at load time (`SemanticMappingError`); that rejection is the governance working, not a bug to work around.

## Testing philosophy

Every layer has its own test file (`tests/test_finance_engine.py`, `test_controls.py`, `test_retrieval.py`, `test_lineage.py`, `test_commentary.py`, `test_workflow.py`, `test_transactions.py`), plus the cross-cutting `test_ai_independence.py`. New behavior should follow the same split: a deterministic-layer change gets a deterministic-layer test with no fixtures that touch `commentary.py`; anything touching commentary gets a no-invented-numbers assertion, not just a snapshot of the output text.

Run the full suite with `pytest -q`. If you touch `src/domain.py`, `src/finance_engine.py`, `src/control_engine.py`, `src/retrieval.py` or `src/lineage.py`, re-run `tests/test_ai_independence.py` specifically and confirm it still passes with no changes required. If it doesn't, something crossed the trust boundary, and that's a design problem, not a test to relax.

## What this guide is not

It is not a contribution guide; this is a personal reference implementation, not an open-source project accepting pull requests at this stage. It is not a deployment guide either: there is no production deployment target yet (no database, no auth, no multi-tenant story), by design. See `docs/architecture.md` §10 and the "Scope and limitations" section of the README for what would need to exist first.
