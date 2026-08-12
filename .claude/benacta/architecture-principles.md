# BENACTA — Architecture Principles

> Binding doctrine. Consult before any architectural decision, module boundary change, or AI-integration choice.

## The ten principles

1. **ENGINEER THE TRUTH. AUGMENT THE JUDGMENT.**
2. **CODE COMPUTES. AI EXPLAINS. HUMANS DECIDE.**
3. **AN LLM SHOULD NEVER OWN YOUR NUMBERS. IT SHOULD EXPLAIN THEM.**
4. **THE LLM IS NOT THE SYSTEM. IT IS ONE COMPONENT OF THE SYSTEM.**
5. **DO NOT START WITH AI. START WITH THE DECISION.**
6. **ARCHITECTURE BEFORE TOOLS.**
7. **AI AT THE EDGE. CONTROL AT THE CORE.**
8. **EVERY IMPORTANT OUTPUT MUST BE TRACEABLE.**
9. **INSIGHT WITHOUT ACTION IS INCOMPLETE.**
10. **ENTERPRISE AI MUST CONNECT TRUTH, CONTEXT, JUDGMENT AND ACTION.**

## The trust boundary (load-bearing)

From Architecture Note #001 (`BENACTA / CONTROLLED INTELLIGENCE ARCHITECTURE · FIN-AI-001`):

- Only **computed facts** cross the boundary: *facts above, interpretation below*.
- The AI Knowledge Layer **retrieves, interprets, drafts — never owns the numbers**.
- AI output is a **governed draft** subject to Controller Sign-off (human-in-the-loop); rejection is a designed path (*rejected, with feedback*).
- Every step is logged: **Audit Trail · every step logged**.
- The AI layer must be fully removable: `test_financial_truth_is_independent_from_llm` proves actual, budget, variance, variance %, controls, materiality and business objects all work with AI disabled.

## Reference layer stack (conceptual — V1 implements a thin slice)

```text
SOURCES            ERP·General Ledger (read-only) · Budget & Forecast (files·EPM) · Docs & Policies
                   ↓ extract
DETERMINISTIC      Finance engine — "code computes every figure" — THE VALUE CORE
CORE               (variance engine · anomaly detection · controls · reconciliations)
── ─ ─ ─ ─ ─ ─ ─  TRUST BOUNDARY · computed facts only ─ ─ ─ ─ ─ ─ ─ ──
KNOWLEDGE /        retrieval over documents, policies, history, context
AI LAYER           commentary drafting from facts + evidence
                   ↓ governed draft
HUMAN CONTROL      controller review · approval · accountability
                   ↓ approved
WORKFLOW / ACTION  issues → owner → next step → status
AUDIT              lineage from every output back to source, rule, evidence, reviewer
FEEDBACK           decision → action → outcome → learning
```

Chain form: `RULES → CODE · KNOWLEDGE → RETRIEVAL · INTERPRETATION → AI · ACCOUNTABILITY → HUMAN`.

## Six design principles for AI-augmented finance (Note #001 §04)

I. **CFO sponsorship** — a finance transformation, not an IT side-project; the sponsor sits in finance.
II. **One process first** — prove it on one cycle (e.g. the monthly close) in 6–8 weeks, then scale.
III. **Architecture before tools** — fix the boundaries first: code computes, AI drafts, humans decide. Then select tools.
IV. **Auditability by design** — every figure traces to its source; trust is the currency of adoption, and of auditors.
V. **Team in the loop** — augment controllers, never bypass them; today's validators become tomorrow's adopters.
VI. **Measure vs baseline** — run evals against the current process: accuracy, cycle time, cost. Proof over demos.

## Foundry-like inspiration — conceptual only

The pattern internalized from platforms such as Palantir Foundry / AIP:

```text
DATA → BUSINESS OBJECTS / SEMANTIC MODEL → BUSINESS LOGIC → DECISION CONTEXT → DECISION → ACTION → FEEDBACK
```

Ideas retained: governed data foundation · business/semantic layer (**raw data ≠ business meaning**) · deterministic business logic · decision context · AI interpretation without ownership of truth · human/governance layer · operational layer beyond dashboards · feedback loop.

**Hard limits:** no Palantir branding, UI imitation, logos, screenshots or implied affiliation; no "Palantir clone" framing; no Foundry terminology sprayed everywhere; no horizontal platform build. Public executive framing: **"From tables to business objects."** Executive term: **Business Semantic Layer**; technical documents may say **lightweight ontology**.

## Deterministic core — fixed contracts

```python
variance = actual - budget
variance_pct = variance / abs(budget) if budget != 0 else None
```

- Control rules are transparent and explainable (not ML): |variance| > €100,000 · variance % > 10% · missing budget · material cost increase · unusual period movement. Each returns severity, metric, rule, value, business_message.
- Financial facts are structured objects (metric, actual, budget, variance, variance_pct, materiality). **The LLM consumes these objects and never recomputes from raw rows.**
- The AI commentary layer receives only: computed facts, control alerts, retrieved context. It must never invent numbers, never recalculate, never claim unsupported causality; it distinguishes evidence from inference, states when evidence is insufficient, exposes confidence, and returns structured output (summary, drivers, evidence, open_questions, suggested_follow_up, confidence).
- Retrieval is transparent (keyword / TF-IDF / simple scoring) and returns document, section, snippet, relevance score — the user must always see **why the system said what it said**. No vector database in V1.
- Human workflow: `DRAFT → AWAITING_REVIEW → APPROVED / REVISION_REQUESTED`; issues carry owner, next step, status. **AI drafts. Humans approve.**

## V1 scope discipline

V1 is a **thin, complete vertical slice**: one use case (Monthly Performance Review), fictional mid-sized industrial/project-based company, Python + Streamlit + Pandas, `DEMO_MODE=true` fully functional without an API key. The elegance of V1 comes from proving the architecture with minimal implementation. Everything V1 must NOT contain is listed in `anti-patterns.md`.
