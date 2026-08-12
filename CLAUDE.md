# BENACTA — Decision Intelligence Blueprint

Reference implementation of the BENACTA Decision Intelligence architecture. Finance is the first vertical slice; BENACTA is broader than Finance.

**The one-sentence test for every change:**
> BENACTA demonstrates how governed enterprise truth becomes context, human judgment and action — without making the LLM the system of record.

If a feature, sentence or pixel does not strengthen that sentence, it does not belong in V1.

## Core doctrine

**CODE COMPUTES. AI EXPLAINS. HUMANS DECIDE.**

```text
DATA → BUSINESS OBJECTS → TRUTH → CONTEXT → INTERPRETATION → DECISION → ACTION → OUTCOME
```

The LLM never computes, recomputes or alters a number. It receives computed facts, control alerts and retrieved context, and drafts interpretation that a human approves. The trust boundary — *computed facts only; facts above, interpretation below* — is load-bearing and is proven by `tests/test_ai_independence.py::test_financial_truth_is_independent_from_llm`.

## Mandatory reading before making changes

Before **any** architectural, visual, editorial or vocabulary change, read the relevant doctrine file. Do not change BENACTA architecture or visual doctrine without explicit justification grounded in these files or in `/source`.

| File | Owns |
|---|---|
| `.claude/benacta/positioning.md` | What BENACTA is / is not, audience, slogan hierarchy |
| `.claude/benacta/decision-intelligence.md` | Philosophy, canonical chain, long-term direction |
| `.claude/benacta/architecture-principles.md` | The 10 principles, trust boundary, reference architecture, Foundry-inspiration limits |
| `.claude/benacta/brand-system.md` | Exact visual system from the supplied charter (colors, type, logo, diagram grammar) |
| `.claude/benacta/content-system.md` | Editorial system: executive-first structure, README/PDF rules, Note #001 patterns |
| `.claude/benacta/vocabulary.md` | Product vocabulary, state vocabularies, executive vs technical language |
| `.claude/benacta/anti-patterns.md` | Everything forbidden — check before adding features, copy or styling |

Ground truth beneath all of the above: the supplied materials in `/source` (brand charter, Architecture Note #001, logo packs) and their full transcription/analysis in `docs/source-analysis.md`. If doctrine files and `/source` ever disagree, `/source` wins.

## Hard project rules

- **Demo-first:** `DEMO_MODE=true` — the entire app works with no API key. LLM integration is optional, behind a small provider interface.
- **Fictional data only.** Never real client data. Amounts in Euros. One coherent management story (see `docs/source-analysis.md` §8).
- **No invented statistics.** Only the four sourced benchmarks from Architecture Note #001, with citations; derived figures labeled "illustrative".
- **Never push to a remote** unless explicitly instructed. No secrets, no absolute local paths, no dead code.
- **The brand charter is locked.** Select from it; never reinterpret it. Exact values in `.claude/benacta/brand-system.md`.
- Stack: Python + Streamlit + Pandas, intentionally few dependencies. V1 non-goals are listed in `.claude/benacta/anti-patterns.md`.

## Process

Work proceeds in gated phases defined in `02_EXECUTION_PLAYBOOK_CLAUDE_CODE.md`. Do only the current phase; run the relevant checks before stopping. Master requirements: `01_MASTER_BRIEF_BENACTA.md`.
