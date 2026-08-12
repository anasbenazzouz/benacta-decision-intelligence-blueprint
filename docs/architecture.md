# BENACTA Decision Intelligence Blueprint — V1 Architecture

> Phase 2 deliverable. Doctrine: `.claude/benacta/architecture-principles.md`. Scope: `docs/implementation-plan.md`.

## 1. Business view

```text
ENTERPRISE DATA          actuals & budget (ERP mock: CSV)
↓
BUSINESS MEANING         business units · cost centers · accounts · metric definitions
↓
DETERMINISTIC TRUTH      every figure computed by code — reproducible, versioned
↓
CONTROL                  transparent materiality rules surface what needs attention
↓
CONTEXT                  management notes, milestones, policies — retrieved with visible reasons
↓
INTERPRETATION           AI drafts an explanation from facts + evidence (never owns numbers)
↓
HUMAN DECISION           controller reviews, approves or sends back — accountability stays human
↓
ACTION                   issue → owner → next step → status
↓
OUTCOME / AUDIT          every step logged; lineage from any statement back to its sources
```

## 2. Technical view

```text
data/actuals.csv · data/budget.csv          data/context/*.md
        │                                          │
        ▼                                          │
┌─ src/domain.py ────────────────────────┐         │
│ BUSINESS SEMANTIC LAYER                │         │
│ BusinessUnit · CostCenter · Account    │         │
│ MetricDefinition (direction-aware)     │         │
│ row → business-object mapping          │         │
└───────────────┬────────────────────────┘         │
                ▼                                  │
┌─ src/finance_engine.py ────────────────┐         │
│ DETERMINISTIC CORE — THE VALUE CORE    │         │
│ FinancialFact: actual · budget ·       │         │
│ variance · variance_pct · materiality  │         │
│ CALC_VERSION recorded                  │         │
└───────────────┬────────────────────────┘         │
                ▼                                  │
┌─ src/control_engine.py ────────────────┐         │
│ ControlAlert: severity · rule · value  │         │
│ · business_message                     │         │
└───────────────┬────────────────────────┘         │
                │              ┌─ src/retrieval.py ┴──────────┐
                │              │ Evidence: document · section │
                │              │ · snippet · score ·          │
                │              │ matched_terms                │
                │              └───────────────┬──────────────┘
════════════════╪══════════════════════════════╪══════ TRUST BOUNDARY ══
 computed facts only · facts above, interpretation below
                ▼                              ▼
┌─ src/commentary.py ─────────────────────────────────────────┐
│ AI INTERPRETATION (demo templates | optional LLM provider)  │
│ Commentary: summary · drivers · evidence · open_questions   │
│ · suggested_follow_up · confidence                          │
└───────────────┬─────────────────────────────────────────────┘
                ▼
┌─ src/approval.py ───────────┐   ┌─ src/decision_log.py ─────┐
│ DRAFT → AWAITING_REVIEW →   │ → │ OPEN · UNDER REVIEW ·     │
│ APPROVED|REVISION_REQUESTED │   │ APPROVED · ACTION         │
│ reviewer · timestamp        │   │ REQUIRED · CLOSED         │
└───────────────┬─────────────┘   │ owner · next step         │
                │                 └─────────────┬─────────────┘
                ▼                               ▼
┌─ src/audit.py ──────────────────────────────────────────────┐
│ AUDIT TRAIL · EVERY STEP LOGGED                             │
│ source → calc version → rule → evidence → mode → reviewer   │
│ → decision → timestamps                                     │
└─────────────────────────────────────────────────────────────┘
                ▼
app.py — Executive Decision Cockpit (default) · Architecture view · Audit Trail view
```

## 3. The trust boundary (the architecture's central claim)

**Above the boundary (deterministic):** `domain.py`, `finance_engine.py`, `control_engine.py`, `retrieval.py`. These modules produce all numbers and all evidence. They import no LLM SDK and never import `commentary.py`. Retrieval sits above the boundary because it selects and quotes existing text with a transparent score — it generates nothing.

**Below the boundary (probabilistic):** `commentary.py` only. It receives `FinancialFact`s, `ControlAlert`s and `Evidence` — already computed, already selected — and returns a draft. It cannot reach the CSVs, cannot recompute, and its output is quarantined until a human approves it.

**Enforcement:**
- Structural: `test_financial_truth_is_independent_from_llm` asserts the deterministic modules have no import path to `commentary` or any LLM SDK.
- Behavioral: the same test runs the full truth pipeline with the interpretation layer absent and asserts facts, controls, materiality and business objects are complete and correct.
- Output invariant: every number in demo commentary must already exist in its input facts (tested); the LLM provider is instructed identically and validated structurally.
- UI: computed figures are labeled as calculated by code; commentary is labeled "AI-generated interpretation · Controller approval required".

## 4. Data contracts (key objects)

```python
FinancialFact:  metric, period, business_unit|None, actual, budget|None,
                variance|None, variance_pct|None, materiality  # HIGH|MEDIUM|LOW|NONE
ControlAlert:   rule_id, rule_name, severity, metric, value, threshold,
                direction,  # FAVORABLE|UNFAVORABLE
                business_message
Evidence:       document, section, snippet, score, matched_terms
Commentary:     summary, drivers[], evidence[], open_questions[],
                suggested_follow_up[], confidence, mode  # DEMO|LLM(model)
DecisionIssue:  issue_id, title, alert_ref, commentary_ref, review_state,
                status, owner|None, next_step|None, due_date|None, history[]
AuditRecord:    step, refs, mode, calc_version, actor|None, timestamp
```

Fixed formulas (never reimplemented elsewhere):

```python
variance = actual - budget
variance_pct = variance / abs(budget) if budget != 0 else None
```

## 5. State machines

**Commentary review** (`approval.py`): `DRAFT → AWAITING_REVIEW → { APPROVED | REVISION_REQUESTED }`; `REVISION_REQUESTED → AWAITING_REVIEW` (redraft). Illegal transitions raise. Every transition records reviewer, timestamp, comment.

**Decision issue** (`decision_log.py`): `OPEN → UNDER REVIEW → APPROVED → { ACTION_REQUIRED → CLOSED | CLOSED }`. `ACTION_REQUIRED` requires owner + next step. History preserved.

## 6. Lineage model

Every cockpit statement can be walked backwards:

```text
"Revenue finished €280k below budget"
  ← FinancialFact(Revenue, 2026-07)             finance_engine · CALC_VERSION
  ← rows in actuals.csv / budget.csv            (source files, row filter shown)
"HIGH PRIORITY"
  ← ControlAlert(ABS_MATERIALITY, €100k)        control_engine
  ← finance_policy.md § Materiality             retrieval (the threshold is citable text)
"milestones shifted into August"
  ← Evidence(project_milestones.md § …)         retrieval · score · matched_terms
"AI-generated interpretation"
  ← Commentary(mode=DEMO|LLM)                   commentary
"Approved"
  ← review record (reviewer · timestamp)        approval
"Review milestone recognition …"
  ← DecisionIssue (owner · next step · status)  decision_log
```

`audit.py` records each arrow; the Audit Trail view renders this chain per issue.

## 7. Application architecture

- **`app.py`** — three views via sidebar navigation; Streamlit session state holds pipeline outputs + workflow state; demo seeding gives the decision log one completed example on first load.
  - **View A — Executive Decision Cockpit (default):** KPI band (Revenue, Gross Margin, Operating Expenses, EBITDA) → Attention (ranked) → issue detail (What happened / Why / Evidence / Suggested follow-up) → human control → Decision Log. No AI vocabulary, no chat box.
  - **View B — Architecture:** the §2 diagram rendered in brand grammar (deterministic = double stroke, AI = mineral-blue tint, human approval = porcelain, one champagne action node), executive + technical caption per layer, live payload trace of the revenue issue.
  - **View C — Audit Trail (non-dominant):** lineage per issue + raw JSON inspection expanders.
- **`src/theme.py`** — charter tokens (colors, type) + CSS injection per `brand-system.md`.

## 8. Configuration

`.env` / environment: `DEMO_MODE` (default `true`), `ANTHROPIC_API_KEY` (optional; only read when `DEMO_MODE=false`). No other configuration. Missing key with `DEMO_MODE=false` → visible fallback to demo mode, never an error page.

## 9. Technology decisions

| Choice | Rationale |
|---|---|
| Python + Streamlit + Pandas only | Brief mandate; minimal dependency surface |
| Stdlib dataclasses (no Pydantic) | No untrusted-input validation need |
| Hand-rolled keyword retrieval | Transparency is the feature; no sklearn/vectors |
| Session state + JSON export (no DB) | Demo needs inspectability, not durability |
| One provider ABC, two implementations | Optional LLM without framework-building |
| `anthropic` as optional dependency | App fully functional without it (`DEMO_MODE=true`) |

## 10. Extension points (documented, not built)

The V1 seams that a real engagement would extend — proving composability without platform-building: sources (CSV → ERP/EPM read-only pipelines) · semantic layer (dataclasses → governed semantic model) · controls (rule list → control catalog) · retrieval (keyword → hybrid/vector, same Evidence contract) · provider (demo/LLM behind the same interface, plus evals) · workflow (state machines → enterprise workflow/task systems) · audit (JSON export → immutable store). The **contracts** in §4 are the stable part; implementations behind them are replaceable.
