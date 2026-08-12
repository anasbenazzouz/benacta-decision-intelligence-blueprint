# BENACTA Decision Intelligence Blueprint — V1 Acceptance Criteria

> Phase 2 deliverable. V1 is done when **every** item below holds. Non-goals: `docs/implementation-plan.md` §6.

## 1. Truth layer

- [ ] `variance = actual − budget` and `variance_pct = variance / abs(budget)` exactly; `variance_pct is None` when budget = 0; no alternative implementations anywhere.
- [ ] Metric set computed: Revenue, Gross Margin, Operating Expenses, EBITDA + component metrics (External Contractors, Materials, Personnel, Travel).
- [ ] Dataset reconciles to the story targets: Revenue €4,720,000 vs €5,000,000 (−€280k / −5.6%); contractors ≈ +€120k; procurement ≈ −€85k; travel ≈ +€38k / ≈ +31%; one account with actuals and no budget line; EBITDA ≈ −€200k. Gross Margin and EBITDA reconcile arithmetically from components (tested, not hand-asserted).
- [ ] Facts are direction-aware (favorable/unfavorable derives from `MetricDefinition.higher_is_better`).
- [ ] Same inputs → identical outputs (determinism test); `CALC_VERSION` present on every fact's audit trail.
- [ ] All data entirely fictional, Euros, no real-company resemblance.

## 2. Business Semantic Layer

- [ ] Raw rows are mapped to BusinessUnit → CostCenter → Account objects; metrics defined over `AccountCategory`, not column names scattered through code.
- [ ] The cockpit uses the semantic layer visibly (per-BU revenue drill-down; direction-aware favorability) — it must add explanatory value, not exist decoratively.
- [ ] Executive docs say **Business Semantic Layer**; only technical docs may say *lightweight ontology*.

## 3. Controls

- [ ] Rules fire exactly at their thresholds: `ABS_MATERIALITY` (|variance| ≥ €100k → HIGH), `REL_MATERIALITY` (|pct| ≥ 10% ∧ |variance| ≥ €25k → MEDIUM), `MISSING_BUDGET` (→ MEDIUM). Boundary cases tested (99,999.99 / 100,000).
- [ ] Every alert carries severity, metric, rule, value, threshold, direction, and a **business message** readable by a CFO.
- [ ] The story produces 8 ranked alerts; the executive **attention list** is the top 5 (`attention_list`), ranked HIGH → LOW with unfavorable before favorable at equal severity. The full set stays available to the audit trail — presentation scope, never a filter on what the controls found.
- [ ] The favorable procurement variance appears (LOW, favorable) and the deferred project costs appear (MEDIUM, favorable): governed truth reports good news too. Favorable breaches rank one severity level below the equivalent unfavorable breach.
- [ ] Materiality thresholds are also written in `finance_policy.md` and retrievable as evidence.

## 4. Context & retrieval

- [ ] Five context documents exist and tell the same story as the data.
- [ ] Retrieval returns document, section, snippet, score, **matched_terms**; ranking is deterministic; a known query returns the known best section (tested).
- [ ] The revenue issue retrieves the milestone note; the travel issue retrieves the travel policy; the HIGH severity explanation can cite `finance_policy.md`.
- [ ] No vector database, no embeddings, no opaque scoring.

## 5. Interpretation (trust boundary)

- [ ] `DEMO_MODE=true` (default): full pipeline works with **no API key**; commentary is template-based, built only from computed facts + retrieved evidence.
- [ ] **`test_financial_truth_is_independent_from_llm` passes**: truth pipeline complete with interpretation disabled; `domain`/`finance_engine`/`control_engine`/`retrieval` have no import path to `commentary` or any LLM SDK.
- [ ] No number appears in commentary that is absent from input facts (tested for demo mode; structurally instructed + validated for LLM mode).
- [ ] Commentary output is structured (summary, drivers, evidence, open_questions, suggested_follow_up, confidence) and always carries its mode (DEMO / LLM+model).
- [ ] With `DEMO_MODE=false` and no key: visible graceful fallback to demo, never a crash.
- [ ] No unsupported causal claims: every "why" statement links to evidence or is phrased as an open question.

## 6. Human review & decision/action

- [ ] Approval state machine enforces `DRAFT → AWAITING_REVIEW → APPROVED | REVISION_REQUESTED`; illegal transitions raise; reviewer, timestamp, comment recorded (tested).
- [ ] Nothing is presented as final until APPROVED; drafts are visibly labeled "AI-generated interpretation · Controller approval required".
- [ ] An issue can be carried to ACTION REQUIRED with owner + next step (Gate D); one seeded example exists on first load; a full live walkthrough is possible in the UI.
- [ ] Next steps are labeled Suggested follow-up / Decision option / Question to investigate — never "AI Decision".

## 7. Audit trail

- [ ] For any cockpit statement, the Audit Trail view shows: source files, calc version, metric calculation, control rule, evidence retrieved, interpretation mode (+model if LLM), reviewer, decision status, next step, timestamps.
- [ ] Audit records are appended for every pipeline step and exportable as JSON to `outputs/`.

## 8. Executive Decision Cockpit (Gate E)

- [ ] Default view answers, in order: What happened? Why? What requires attention? Possible next steps? Evidence? Who approved?
- [ ] KPI band: Revenue, Gross Margin, Operating Expenses, EBITDA — each with Actual, Budget, Variance €, Variance %.
- [ ] Zero AI-engineering vocabulary on the default view (no RAG, embeddings, vectors, prompts, JSON, tokens).
- [ ] No chat box; not a generic dashboard; a CFO who doesn't know what RAG means understands the value in ≤ 2 minutes (human checkpoint).
- [ ] Charter-compliant visual system (palette, type roles, no forbidden aesthetics); generic Streamlit look suppressed where feasible; residual limits documented in `ui-qa.md`.

## 9. Architecture view (Gate F)

- [ ] Layer stack rendered with the trust boundary explicit, in charter diagram grammar (double-stroke deterministic, mineral-blue AI, porcelain human approval, exactly one champagne action node).
- [ ] Each layer described in executive language **and** technical language.
- [ ] Live trace: the revenue issue shown flowing through every layer with real payloads.
- [ ] Raw payload inspection exists but does not dominate (expander/tab).

## 10. Tests (Gate A)

- [ ] All tests pass with no API key present in the environment.
- [ ] Coverage of: variance/pct correctness · missing/zero budget · story reconciliation · control thresholds & severities · retrieval determinism & evidence fields · approval + decision transitions (legal & illegal) · audit completeness · AI independence (behavioral + structural) · no-invented-numbers.

## 11. Repository & hygiene (Gate H)

- [ ] `requirements.txt` minimal (streamlit, pandas; anthropic optional); `.env.example` with `DEMO_MODE=true`; `.gitignore` covers `outputs/`, `.env`, caches.
- [ ] No secrets, no real client data, no personal absolute paths, no dead code, no generated junk, no credibility-undermining TODOs.
- [ ] LICENSE placeholder with a note for the owner to choose before public release.
- [ ] Documented commands run as written (tests + app launch).
- [ ] Nothing pushed to any remote.

## 12. Story & doctrine coherence (Gates B, C, G)

- [ ] The app, README and (later) PDF tell the **same** July FY26 story with the same numbers.
- [ ] Every explanation shows supporting sources; unsupported causality absent (Gate B).
- [ ] Review/approval visible; accountability explicit (Gate C).
- [ ] App and PDF visually belong to BENACTA; Blueprint and Architecture Note #001 feel like one family (Gate G — visual QA loop mandatory before declaring the PDF done).
- [ ] Project never overclaims autonomy or production readiness; conceptually consistent with Architecture Note #001.

## 13. Definition of done (V1)

All boxes above checked **and** the playbook Phase 10 red team (CFO / Enterprise Architect / AI Engineer / Brand Director) returns no P0/P1 findings **and** final QA (master brief §36, items 1–20) completed.
