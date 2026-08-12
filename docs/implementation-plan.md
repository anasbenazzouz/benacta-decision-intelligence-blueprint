# BENACTA Decision Intelligence Blueprint — V1 Implementation Plan

> Phase 2 deliverable. Governing doctrine: `CLAUDE.md`, `.claude/benacta/*`. Source analysis: `docs/source-analysis.md`.

## 1. V1 in one sentence (the gate)

> A small monthly-performance Decision System that computes financial truth deterministically, retrieves business context, drafts an explanation, requires human review, and records the resulting action.

Anything that makes V1 bigger than this sentence is out of scope.

## 2. What V1 proves

```text
SOURCE DATA → BUSINESS OBJECTS → DETERMINISTIC METRICS → CONTROL/ANOMALY
→ CONTEXT RETRIEVAL → AI INTERPRETATION → HUMAN REVIEW → DECISION/FOLLOW-UP → AUDIT TRAIL
```

One use case: **Monthly Performance Review**, July FY26, fictional company, Euros, `DEMO_MODE=true` end-to-end with no API key. The trust boundary is real and testable: `test_financial_truth_is_independent_from_llm`.

## 3. The reference scenario (single coherent story)

**Company:** *Meridian Industrial Group* (fictional) — mid-sized industrial & project engineering company, ~€60M annual revenue, project-based. Two business units: **Projects** and **Service & Maintenance**. All data entirely fictional; no real client resemblance.

**July FY26 story (drives every screen, document and test):**

| Thread | Movement | Cause (in context docs) |
|---|---|---|
| Revenue | **−€280k / −5.6%** (Actual €4.72M vs Budget €5.00M) | Two customer project milestones (Projects BU) shifted from July into August |
| External contractors (direct) | **+€120k** unfavorable | Temporary engineering capacity constraints |
| Materials / procurement | **−€85k** favorable | Softer input prices; partially protects gross margin |
| Milestone-linked direct costs | ≈ **−€180k** favorable | Costs shifted into August with the milestones |
| Travel | **+€38k / ≈ +31%** unfavorable | Unplanned customer workshops (relative breach, modest absolute) |
| Workshop logistics account | ≈ **+€22k**, **no budget line** | Account created in July → missing-budget control fires |
| Net effect | Gross Margin ≈ **−€135k**; OpEx ≈ **+€65k**; **EBITDA ≈ −€200k** | The arithmetic reconciles by construction |

Exact row-level data is built in the truth phase and **must reconcile to these targets** (they are restated as acceptance criteria).

**Alerts the story produces (8, ranked — verified in Phase 3):**
1. HIGH — Revenue −€280k (milestone shift)
2. HIGH — EBITDA −€200k (composite effect)
3. HIGH — Gross Margin −€135k
4. HIGH — External contractors +€120k
5. MEDIUM — Travel +€38k / +31% (relative breach; policy question)
6. MEDIUM — Customer Workshop Logistics: no budget line (governance gap)
7. MEDIUM — Direct project costs −€180k (favorable, deferred with the milestones)
8. LOW — Direct materials −€85k / −10.6% (favorable, procurement)

The executive **attention list** is the top 5; the full set remains available to the audit trail. Gross Margin firing was not in this plan's first draft — it is correct behaviour (a −€135k miss exceeds the €100k threshold) and suppressing it to match a document would have been the wrong fix. Favorable breaches rank one severity level below the equivalent unfavorable breach, so governed truth reports both directions without good news outranking bad.

## 4. Layer-by-layer scope

### 4.1 Business Semantic Layer — `src/domain.py`
- Stdlib **dataclasses + Enums** (no Pydantic — nothing here validates untrusted input; fewer dependencies).
- Objects: `BusinessUnit`, `CostCenter`, `Account` (with `AccountCategory`), `MetricDefinition`, `FinancialFact`, `ControlAlert`, `Evidence`, `Commentary`, `DecisionIssue`, `AuditRecord`.
- Relationships: BusinessUnit → CostCenters → Accounts; MetricDefinition maps AccountCategories to metrics with a **direction** (`higher_is_better`) so favorability is business meaning, not presentation; FinancialFact belongs to a Metric (and optionally a BusinessUnit); ControlAlert references a FinancialFact; Evidence supports a Commentary; DecisionIssue references alert + commentary.
- Row→object mapping lives here: this file **is** the "raw data ≠ business meaning" proof. The brief's `Variance` object is folded into `FinancialFact` (actual, budget, variance, variance_pct, materiality) — one object, one truth.
- Metric set: Revenue · Gross Margin (= Revenue − Direct Costs) · Operating Expenses (= personnel + travel + facilities + other opex) · EBITDA (= GM − OpEx) · plus component metrics (External Contractors, Direct Materials, Direct Project Costs, Personnel, Travel, Facilities, Other OpEx) for controls and drill-down — eleven in total. Cockpit headline shows 4 KPIs; the engine computes the full set.

### 4.2 Deterministic truth — `src/finance_engine.py`
- Loads `data/actuals.csv` + `data/budget.csv` (pandas), maps rows through the semantic layer, aggregates per metric (company level; per-BU for Revenue drill-down).
- Fixed contracts: `variance = actual − budget`; `variance_pct = variance / abs(budget)` (None if budget == 0). Missing budget → fact flagged, no fake zero-division.
- Output: list of `FinancialFact` — the only numbers the rest of the system may use. Calculation version constant (`CALC_VERSION`) recorded for audit.

### 4.3 Controls — `src/control_engine.py`
- Transparent rules as data (id, name, threshold, severity policy, message template):
  - `ABS_MATERIALITY` — |variance| ≥ €100,000 → HIGH
  - `REL_MATERIALITY` — |variance_pct| ≥ 10% and |variance| ≥ €25,000 → MEDIUM
  - `MISSING_BUDGET` — actuals without a budget line → MEDIUM
  - Favorable breaches are reported with direction-aware business messages (ranked below unfavorable at equal severity).
- Thresholds also appear in `data/context/finance_policy.md`, so retrieval can cite the policy that explains *why* an item is material — lineage from alert to written policy.
- Dropped from V1 (deliberate): "unusual period movement" (needs multi-period history; single-period slice) and a separate "material cost increase" rule (covered by the two materiality rules applied to direction-aware cost metrics).

### 4.4 Context — `data/context/` + `src/retrieval.py`
- Five fictional documents: `management_notes.md`, `project_milestones.md`, `forecast_assumptions.md`, `travel_policy.md`, `finance_policy.md` (brief §16 layout; adaptation from §23's single `policies.md` noted).
- Retrieval: markdown sections scored by **transparent keyword overlap** (hand-rolled, ~50 lines; no sklearn, no vectors). Query built from metric name/synonyms + business unit + direction. Returns `Evidence(document, section, snippet, score, matched_terms)` — `matched_terms` makes "why the system said what it said" literally inspectable.

### 4.5 Interpretation — `src/commentary.py`
- One small provider interface (`CommentaryProvider.generate(facts, alerts, evidence) → Commentary`), two implementations:
  - **DemoProvider (default):** controlled templates assembling summary/drivers/open questions strictly from computed facts + retrieved evidence. Confidence derived from evidence coverage. Invariant: **every number in the output exists in the input facts** (tested).
  - **AnthropicProvider (optional):** enabled only when `DEMO_MODE=false` and an API key exists; strict instructions (never invent/recompute numbers, distinguish evidence from inference, state insufficiency, CFO-appropriate language); structured JSON output validated; any failure falls back to demo. Import guarded so the SDK is an optional dependency.
- Output: `Commentary(summary, drivers, evidence, open_questions, suggested_follow_up, confidence)` — never labeled a decision.

### 4.6 Human review — `src/approval.py`
- State machine `DRAFT → AWAITING_REVIEW → APPROVED | REVISION_REQUESTED` (REVISION_REQUESTED → AWAITING_REVIEW on redraft). Illegal transitions raise. Records reviewer, timestamp, comment. UI labels per `vocabulary.md`.

### 4.7 Decision / action — `src/decision_log.py`
- `DecisionIssue`: lifecycle `OPEN · UNDER REVIEW · APPROVED · ACTION REQUIRED · CLOSED` + owner, next step, optional due date. Demonstrates INSIGHT → DECISION → ACTION without a workflow engine.
- Demo state seeding: on first load, one issue is pre-carried to ACTION REQUIRED so the decision log is meaningful immediately — the **travel** finding, owner "Cost Center Manager · Projects", due 21 Aug 2026. The headline revenue issue is deliberately left as a live draft so the review loop can be walked in a demonstration. (`app.py::seed_demo_state` is the authority for these values.)

### 4.8 Audit — `src/audit.py`
- Append-only in-session audit log (exportable JSON under `outputs/`, gitignored): for each important output — input source files, `CALC_VERSION`, metric calculation, control rule, evidence retrieved, interpretation mode (demo/LLM + model), reviewer, decision status, next step, timestamps.
- Audit Trail view reconstructs full lineage per issue: source rows → fact → rule → evidence → commentary → review → decision.

### 4.9 Executive Decision Cockpit — `app.py` (+ `src/theme.py`)
- Default view. Structure: period header → KPI band (Revenue, Gross Margin, Operating Expenses, EBITDA: actual/budget/variance €/variance %) → **Attention** (ranked HIGH/MEDIUM/LOW) → selected issue: What happened / Why / Evidence (exact sources) / Suggested follow-up → human control (status + approve/request revision) → Decision Log.
- `src/theme.py`: charter tokens (palette, type roles) + CSS injection to suppress generic Streamlit look. Brand rules from `brand-system.md`; no chat box anywhere.
- State: `st.session_state` (+ JSON export). No database.

### 4.10 Architecture / Engineering view
- Second view: the layer stack with the **trust boundary drawn explicitly** (charter architecture grammar: deterministic = double stroke, AI = mineral blue tinted, human approval = porcelain, action = single champagne node), each layer with executive + technical description, and a live trace of the revenue issue through every layer with real payloads.
- Third element (non-dominant): a technical inspection expander exposing raw fact/alert/evidence/commentary JSON and the audit records.

### 4.11 Tests — `tests/`
- `test_finance_engine.py` — variance & pct correctness, zero/missing budget, aggregation to story targets, direction/favorability, calc determinism.
- `test_controls.py` — each rule's threshold boundaries, severity mapping, favorable/unfavorable messages, deterministic ordering.
- `test_retrieval.py` — evidence returned with document/section/snippet/score/matched_terms; deterministic ranking; known query → known section.
- `test_workflow.py` — approval transitions (legal + illegal), decision lifecycle, audit record completeness for a full pipeline pass.
- `test_ai_independence.py` — **`test_financial_truth_is_independent_from_llm`**: (a) behavioral — full truth pipeline (facts, controls, materiality, business objects) runs with the commentary layer disabled/absent; (b) structural — `domain`, `finance_engine`, `control_engine` import neither `commentary` nor any LLM SDK. Plus: demo commentary contains no number absent from input facts.

### 4.12 Later workstreams (planned now, built in later phases)
- **README** — executive-first, per `content-system.md` §4 (Phase 7).
- **Blueprint PDF** — storyboard then designed HTML/CSS → PDF, per `content-system.md` §5 (Phases 8–9).
- **Docs** — `implementation-guide.md`, `demo-script.md`, `ui-qa.md`, red-team and release docs per playbook.

## 5. Challenge log — complexity removed or refused

| Candidate | Decision | Why |
|---|---|---|
| Pydantic | **Dropped** | Stdlib dataclasses suffice; no untrusted-input validation need; one fewer dependency |
| sklearn / TF-IDF lib | **Dropped** | Hand-rolled keyword scoring is smaller, fully explainable, and explainability is the point |
| Vector DB / embeddings | **Refused** | Doctrine; V1 retrieval must be transparent |
| Separate `Variance` object | **Folded** into `FinancialFact` | One object per metric-period truth; fewer moving parts |
| Multi-period dataset + trend rule | **Dropped** | Single period proves the slice; "unusual movement" rule deferred; August shift is narrative, not data |
| Database / persistence layer | **Dropped** | Session state + JSON export; a demo needs inspectability, not durability |
| Workflow engine | **Refused** | Two small state machines demonstrate INSIGHT → DECISION → ACTION |
| Provider plugin framework | **Refused** | One ABC, two implementations; brief forbids overengineered abstraction |
| Separate `semantic_layer.py` | **Merged** into `domain.py` | The mapping *is* the domain; two files would split one idea |
| Chat interface | **Refused** | Doctrine: decision system, not chatbot |
| React/Next.js, auth, IAM, Kafka, K8s, microservices, ERP connectors, ontology engine, agents | **Refused** | Master brief §33 non-goals |

**Attack check (playbook Phase 2):** Is anything unnecessary? — everything remaining maps to a layer of the doctrine chain. Is anything missing for the Decision Intelligence claim? — action layer is not vestigial (owner + next step + seeded ACTION REQUIRED issue); favorable variances surface, proving governed truth is not alarm-only; policy thresholds are citable evidence. Does the semantic layer add real explanatory value? — yes: direction-aware metric definitions and BU aggregation are business meaning that raw rows lack, and the cockpit's drill-down uses them. Can the AI layer be completely disabled without breaking financial truth? — yes, by construction and by test.

## 6. Explicit non-goals (V1)

No full ERP · no real Foundry clone · no complex ontology engine · no multi-agent systems · no Kafka · no Kubernetes · no microservices · no enterprise IAM · no real SAP/ERP integration · no production event buses · no no-code builders · no React/Next.js frontend · no full workflow engine · no vector infrastructure · no production authentication · no database · no forecasting/prediction or scenario simulation · no multi-currency, no i18n (English only) · no real-time data · no writing back to any source system (read-only by design).

## 7. Repository tree (target)

> This is the **Phase 2 target**, kept as a record of what was planned. The tree
> as built differs — `src/lineage.py` and `src/pipeline.py` were added, the demo
> dataset grew to five CSVs, and the suite grew to eight test files. The
> accurate tree is in `README.md`; where the two disagree, the README is right.

```text
benacta-decision-intelligence-blueprint/
├── CLAUDE.md
├── README.md                        # executive-first (Phase 7)
├── LICENSE                          # placeholder — owner chooses before release
├── requirements.txt                 # streamlit, pandas (+ optional: anthropic)
├── .env.example                     # DEMO_MODE=true, optional ANTHROPIC_API_KEY
├── .gitignore
├── app.py                           # Decision Cockpit · Architecture · Audit Trail
│
├── .claude/benacta/                 # doctrine (7 files, done)
├── source/                          # supplied materials (untouched)
│
├── data/
│   ├── actuals.csv                  # period, business_unit, cost_center, account, account_category, amount
│   ├── budget.csv
│   └── context/
│       ├── management_notes.md
│       ├── project_milestones.md
│       ├── forecast_assumptions.md
│       ├── travel_policy.md
│       └── finance_policy.md        # includes materiality thresholds (citable)
│
├── src/
│   ├── __init__.py
│   ├── domain.py                    # business semantic layer: objects + metric definitions + row mapping
│   ├── finance_engine.py            # deterministic truth (THE VALUE CORE)
│   ├── control_engine.py            # transparent materiality/control rules
│   ├── retrieval.py                 # transparent evidence retrieval
│   ├── commentary.py                # ── trust boundary ── demo + optional LLM interpretation
│   ├── approval.py                  # human-in-the-loop state machine
│   ├── decision_log.py              # issue → owner → next step → status
│   ├── audit.py                     # lineage: every step logged
│   └── theme.py                     # charter tokens + Streamlit CSS
│
├── tests/
│   ├── test_finance_engine.py
│   ├── test_controls.py
│   ├── test_retrieval.py
│   ├── test_workflow.py
│   └── test_ai_independence.py      # test_financial_truth_is_independent_from_llm
│
├── docs/
│   ├── source-analysis.md           # done (Phase 0)
│   ├── implementation-plan.md       # this file
│   ├── architecture.md
│   ├── acceptance-criteria.md
│   ├── implementation-guide.md      # Phase 7
│   ├── demo-script.md               # Phase 7
│   ├── controlled-intelligence-blueprint.html   # Phase 9
│   └── BENACTA_Controlled_Intelligence_Blueprint.pdf  # Phase 9
│
├── assets/
│   ├── source-brand-assets/         # copies of supplied logos
│   └── generated/                   # screenshots for README/PDF
│
└── outputs/                         # runtime exports (gitignored, .gitkeep)
```

`src/` layout note: files above the `commentary.py` line in the tree comment constitute the deterministic side of the trust boundary; `commentary.py` is the only module that may talk to an LLM.

## 8. Implementation order (maps to playbook phases)

1. **Truth first (Phase 3):** `domain.py` → fictional dataset reconciling to §3 targets → `finance_engine.py` → `control_engine.py` → their tests, incl. AI-independence.
2. **Context & loop (Phase 4):** context documents → `retrieval.py` → `commentary.py` (demo, then optional LLM) → `approval.py` → `decision_log.py` → `audit.py` → workflow tests → CLI smoke run of TRUTH → CONTEXT → INTERPRETATION → REVIEW → ACTION → AUDIT.
3. **Executive experience (Phase 5):** `theme.py` → `app.py` cockpit → architecture view → audit view.
4. **Quality pass (Phase 6):** bounded cleanup + `docs/ui-qa.md`.
5. **Public package (Phase 7):** README + guides + hygiene audit.
6. **PDF (Phases 8–9):** storyboard → HTML/CSS → PDF → visual QA loop.
7. **Red team & release prep (Phases 10–12).**

## 9. Risks & mitigations

- **Streamlit fights the brand** → `theme.py` CSS tokens early in Phase 5; accept documented limits rather than fighting every widget (note in `ui-qa.md`).
- **Demo commentary reads canned** → templates parameterized by facts + evidence snippets; open questions and confidence vary with evidence coverage.
- **Dataset doesn't reconcile** → story targets are acceptance criteria with a reconciliation test, built before the UI.
- **Scope creep** → §6 non-goals + `anti-patterns.md` checked at every phase gate.
