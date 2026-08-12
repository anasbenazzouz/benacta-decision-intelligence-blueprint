# BENACTA — Source Analysis
## Phase 0 · Source Ingestion · Decision Intelligence Blueprint

> Status: **complete** · No production code written.
> Method: every supplied file read in full. The brand charter PDF contains no embedded text (vector-outlined export), so it was rendered at 10× zoom and transcribed tile by tile. All values below are taken **verbatim from the supplied sources**, which are treated as the source of truth.

---

## 1. Source inventory

| File | Type | Content | Status |
|---|---|---|---|
| `00_START_HERE_BENACTA.md` † | Process | Setup order, gate sequence, public asset system | Read |
| `01_MASTER_BRIEF_BENACTA.md` † | Master brief | Positioning, philosophy, doctrine, V1 scope, deliverables, QA | Read |
| `02_EXECUTION_PLAYBOOK_CLAUDE_CODE.md` † | Process | Phase-by-phase execution plan, release gates | Read |
| `source/README.md` | Process | Folder conventions | Read |
| `source/brand/Graphical_Design_Final.pdf` | **Brand charter** | "BENACTA — Visual Identity System · Master Définitif" — 10 numbered sections, locked | Read (full transcription) |
| `source/brand/BENACTA Logo Pack -Dark.png` | Brand asset | Primary lockup on Deep Heritage Green | Read |
| `source/brand/BENACTA Logo Pack -Light.png` | Brand asset | Primary lockup on Warm Porcelain | Read |
| `source/architecture-note/An LLM should never own your numbers_Final.pdf` | **Architecture Note #001** | Full note (1 page, `FIN-AI-001`) | Read |
| `source/architecture-note/An LLM should never own your numbers.png` | Note export | Identical content to the PDF (LinkedIn version) | Read, verified identical |
| `source/reference/` | — | Empty (`.gitkeep` only) | Noted — no extra positioning docs supplied |

† Local build-process memos, untracked by design — they describe how the project was constructed, not what it is. Everything they contributed that governs the project has been distilled into `.claude/benacta/*` and `docs/`.

---

## 2. BENACTA positioning

BENACTA designs and builds **AI-Native Decision Systems** at the intersection of Enterprise AI, Decision Intelligence, data, business logic, workflows and human judgment.

**Canonical positioning block** (use verbatim):

> **BENACTA**
> Enterprise AI · Decision Intelligence
> **AI-Native Decision Systems**
> Turning enterprise data into decisions and action.
> **Built on Truth. Designed for Decisions.**

- **Finance is the wedge, not the brand.** Initial domains: Finance, Operations, Performance Management, Planning, Enterprise Workflows. BENACTA is broader than Finance.
- BENACTA is **not**: an AI chatbot agency, a RAG agency, a generic automation agency, a dashboard/Power BI consultancy, an "AI agents everywhere" company, a ChatGPT-wrapper builder.
- Audience: CEO / CFO / COO / Finance Director first; CIO / Enterprise Architect / AI & Data Engineer second. Author identity on public assets: **Anas Benazzouz — BENACTA · AI Engineering · Finance & Operations**.
- Character: premium, editorial, institutional, enterprise, understated, architectural. "Private-bank note, not SaaS."

### Slogan hierarchy (do not mix roles)

| Statement | Role | Where |
|---|---|---|
| **Built on Truth. Designed for Decisions.** | Brand tagline | Logo lockup, closing pages, footers |
| **Engineer the truth. Augment the judgment.** | Brand motto / Principle 01 | Note #001 closing line, cover/close exergues |
| **Code computes. AI explains. Humans decide.** | Core doctrine | Doctrine statements, Page 4 of the Blueprint, README |
| **An LLM should never own your numbers. It should explain them.** | Thesis of Architecture Note #001 | Note title, README opening, Blueprint cover quote |
| **Don't start with AI. Start with the decision.** | Method principle (05) | Blueprint close, method sections |
| **AI proposes. Systems validate. Humans decide.** | Editorial statement (charter composition example) | Editorial statement cards only |

---

## 3. Decision Intelligence philosophy

The core problem is **not** "How do we add an LLM to enterprise data?" but:

> **"How do we engineer the path from enterprise truth to business decision and action?"**

**The canonical chain** (store everywhere, never abbreviate away):

```text
DATA → BUSINESS OBJECTS → TRUTH → CONTEXT → INTERPRETATION → DECISION → ACTION → OUTCOME
```

Expanded system view: DATA → BUSINESS MEANING → RULES → ANALYSIS → CONTEXT → AI INTERPRETATION → DECISION → WORKFLOW → ACTION → FEEDBACK. Long-term loop: DATA → DECISION → ACTION → OUTCOME → LEARNING.

**The ten architectural principles** (master brief §6):

1. Engineer the truth. Augment the judgment.
2. Code computes. AI explains. Humans decide.
3. An LLM should never own your numbers. It should explain them.
4. The LLM is not the system. It is one component of the system.
5. Do not start with AI. Start with the decision.
6. Architecture before tools.
7. AI at the edge. Control at the core.
8. Every important output must be traceable.
9. Insight without action is incomplete.
10. Enterprise AI must connect truth, context, judgment and action.

Progression beyond dashboards: REPORTING ("What happened?") → ANALYTICS ("Why?") → PREDICTION ("What may happen?") → **DECISION INTELLIGENCE ("What requires a decision?")** → ACTION ("What do we do next?").

Long-term direction (a reusable Decision Intelligence layer): **CONNECT → MODEL → UNDERSTAND → AUGMENT → ACT → GOVERN → LEARN.** Strategy: start with high-value decision workflows, prove value, build reusable components, expand the decision graph over time.

---

## 4. Architecture Note #001 — analysis

**Title:** "An LLM should never own your numbers. *It should explain them.*"
**Subtitle:** "The current state, the target architecture, and the conditions that decide whether it succeeds."
**Architecture ID:** `BENACTA / CONTROLLED INTELLIGENCE ARCHITECTURE · FIN-AI-001`

### 4.1 Information hierarchy (reuse this editorial structure)

1. Header band: BA monogram + "ARCHITECTURE NOTE · N° 001" in tracked caps.
2. Serif display thesis; second line in italic champagne.
3. **01 / Current state vs 02 / Target state · AI-augmented** — a ✗/✓ table across five rows (Data collection, Figures, Commentary, Traceability, Management access), each target row tagged with its mechanism in italic (*data pipeline, deterministic engine, LLM + evals, audit trail, governed copilot*).
4. **03 / Target architecture** — layered diagram (below).
5. Chain line: `RULES → CODE · KNOWLEDGE → RETRIEVAL · INTERPRETATION → AI · ACCOUNTABILITY → HUMAN`.
6. Motto: **Engineer the truth. Augment the judgment.**
7. **04 / Six design principles** in a 2×3 grid with Roman numerals.
8. **05 / Proof and benchmarks** — four sourced KPI stats.
9. Footer band (dark green): CTA "Comment **BLUEPRINT**…", author identity, logo.

### 4.2 Target architecture (the layer stack V1 must mirror conceptually)

```text
ERP·GENERAL LEDGER (read-only) · BUDGET & FORECAST (files·EPM) · DOCS & POLICIES (history & notes)
        ↓ EXTRACT
DETERMINISTIC FINANCE ENGINE — "code computes every figure" — THE VALUE CORE
        (VARIANCE ENGINE · ANOMALY DETECTION)
─ ─ ─ TRUST BOUNDARY · computed facts only · facts above, interpretation below ─ ─ ─
AI KNOWLEDGE LAYER — "retrieves, interprets, drafts · never owns the numbers"
        (COMMENTARY LLM ← RAG ← VECTOR STORE)
        ↓ governed draft · faithfulness evals
CONTROLLER SIGN-OFF — human-in-the-loop        (rejected, with feedback ↺)
        ↓ APPROVED
FLASH REPORT (automated·day one) · MONTHLY PACK (variances + commentary) · COPILOT (governed tools·read-only)
[right rail: AUDIT TRAIL · EVERY STEP LOGGED]
```

Margin annotations state business outcomes, not tech: *no more re-keying, no manual entries · every figure computed, none invented · commentary in hours, not days · approved before it ships · answers at the speed of questions.*

### 4.3 Six design principles for AI-augmented finance

I. **CFO sponsorship** — a finance transformation, not an IT side-project; the sponsor sits in finance.
II. **One process first** — prove it on one cycle (e.g. the monthly close) in 6–8 weeks, then scale.
III. **Architecture before tools** — fix the boundaries first (code computes, AI drafts, humans decide), then select tools.
IV. **Auditability by design** — every figure traces to its source; trust is the currency of adoption, and of auditors.
V. **Team in the loop** — augment controllers, never bypass them; today's validators become tomorrow's adopters.
VI. **Measure vs baseline** — run evals against the current process: accuracy, cycle time, cost. Proof over demos.

### 4.4 Benchmarks (only reusable **with these sources**)

- **58%** of finance functions already use AI, up 21 pts in one year — Gartner, CFO & Finance AI Survey, Sept. 2024
- **42%** of finance work is automatable: capacity moves to analysis — McKinsey & Company
- **−45%** cost gap: top-quartile finance costs 0.55% of revenue vs ~1% median — PwC, Finance Effectiveness Benchmarking 2024
- **≤ 5 days** monthly close for top-quartile performers — APQC, Open Standards Benchmarking
- The "€100M-revenue company ≈ €450k a year" figure is explicitly labeled **illustrative** — keep that label if reused. Never invent new statistics.

---

## 5. Exact visual / brand system (from `Graphical_Design_Final.pdf` — "Master Définitif")

The charter opens with its own governing rule: **"Le système, verrouillé. Les futurs designers sélectionnent, ils ne réinterprètent pas."** — *The system is locked. Future designers select; they do not reinterpret.*

### 5.1 Logo system

- **Lockup anatomy:** BA monogram (B champagne, A mineral blue, serif) → BENACTA wordmark in tracked caps → horizontal rules flanking the **triangular signature** → tagline "BUILT ON TRUTH. DESIGNED FOR DECISIONS." (TRUTH in blue, DECISIONS in champagne).
- **Locked correction:** the triangle is **optically centered on the complete primary lockup** (axis x = 400). The old "align on the final A" rule is removed. "The triangular BENACTA signature is optically centered on the complete primary lockup. It acts as the central architectural punctuation between the wordmark and the brand promise."
- **Primary dark:** on background **#122B20 only**.
- **Primary light (official):** direct chromatic translation — B, triangle and DECISIONS in deep champagne **#8F7440**; A and TRUTH in **#54808A** (because #BBA06B and #6C9BA3 do not hold text contrast on porcelain); wordmark and tagline in heritage green.
- **Responsive family:**
  - PRIMARY — min 140 px (tagline legible)
  - SECONDARY (monogram + wordmark) — banners, headers, co-branding · min 90 px
  - Below 40 px → monogram only
  - MONOGRAM (BA) — avatar, favicon, app · min 16 px
  - SIGNATURE (triangle) — section marker, node, watermark · **one occurrence per page**
  - WORDMARK (BENACTA) — running text, footers, mentions
- **Protection zone:** the triangle's height on all 4 sides.
- **Authorized backgrounds:** dark #122B20 only; light porcelain #F1E9DA or white; monochrome (ink #122B20 or white) for embossing/stamps/single-color. Never on a busy photo, never on blue.
- **Forbidden:** stretching, tilting, drop shadows, outlines, gradients, shiny metallic gold, recoloring outside the palette, off-centering the triangle, enlarging the triangle beyond +20% of its calibrated size.

### 5.2 Official palette — "colour is information, never decoration"

| Color | Hex | RGB | CMYK ≈ | Meaning / use | Forbidden |
|---|---|---|---|---|---|
| **Deep Heritage Green** | `#122B20` | 18 43 32 | 78/45/65/72 | Systems, governance, foundation. Master background. Pairs: porcelain, champagne, mineral blue | As text on dark ground; large fills on light pages |
| **Warm Porcelain** | `#F1E9DA` | 241 233 218 | 5/7/15/0 | Truth, information, clarity. Light background; text on dark. Pairs: all | As text on porcelain or white |
| **Mineral Intelligence Blue** | `#6C9BA3` | 108 155 163 | 58/26/32/5 | AI, reasoning, agents. The A, kickers, agent blocks. Functional text on light: **`#54808A`** | Decorative use without AI meaning |
| **Antique Champagne** | `#BBA06B` | 187 160 107 | 27/33/65/6 | Decision, value, action. B, wordmark, signature, conclusions. Text on light: **`#8F7440`** | Large fills, metallic effects, **>10% of a composition** |
| **Heritage Blue-Grey** | `#536875` | 83 104 117 | 70/50/38/15 | Data, infrastructure, secondary diagram hierarchy | — |
| **Stone** | `#7C898B` | 124 137 139 | 55/38/38/8 | Annotations, legends, metadata | Never for key content |
| **Sand** | `#D6BE98` | 214 190 152 | 16/23/44/0 | Soft editorial accent, rare block backgrounds | Usage **< 3%** |

### 5.3 Typography — three roles

- **Role 1 · HERITAGE — Libre Caslon Display.** Reserved for the logo. BA monogram only. Never in running text.
- **Role 2 · ENTERPRISE — Instrument Sans.** The entire system. Bold → technical titles · SemiBold → sections · Medium → labels, nav, nodes · Regular → body. **No Light weight.**
- **Role 3 · EDITORIAL — a single serif family, statements only.** Major statements, quotes, editorial heroes. **Never in diagrams.** The charter marks the choice "à valider" with three candidates:
  1. **Source Serif 4** — "European financial edition, designed to cohabit with grotesques: **my recommendation**"
  2. Spectral — sharper, almost documentary; excellent on screen; slightly cold
  3. Newsreader — warm, quality press; a touch too literary for architecture
  → **Working assumption (conservative): Source Serif 4** (the charter's own recommendation). See §9.

### 5.4 Web type hierarchy (fluid desktop / tablet / mobile · line-height / tracking)

| Style | Desktop | Tablet | Mobile | Leading / tracking |
|---|---|---|---|---|
| Display — serif éditorial | 64 | 48 | 36 | 1.12 / −0.01em |
| H1 — Sans Bold | 44 | 36 | 29 | 1.15 / −0.015em |
| H2 — SemiBold | 30 | 26 | 23 | 1.25 / −0.01em |
| H3 — Medium | 21 | 19 | 18 | 1.35 / 0 |
| Body large — Regular | 19 | 18 | 17 | 1.6 / 0 |
| Body — Regular | 16 | 16 | 15 | 1.65 / 0 |
| Label — Medium caps | 12 | 12 | 11 | 1.3 / +0.16em |
| Caption — Regular | 13 | 13 | 12 | 1.5 / 0 |
| Button — Medium | 15 | 15 | 15 | 1 / +0.06em |
| KPI — SemiBold | 40 | 34 | 28 | 1.05 / −0.01em |
| Quote — serif éditorial | 26 | 23 | 20 | 1.4 / 0 |

Fluid scale via `clamp()` between mobile and desktop bounds (charter example — H1: `clamp(29px, 2.3vw + 20px, 44px)`). **Display serves the editorial serif when the content is a statement; otherwise use H1 Sans.**

### 5.5 Carousel typography (1080 × 1350, phone-readable)

Hero headline 88–96 px Bold −0.02em · Section headline 60–68 Bold −0.02em · Statement 76–88 Bold −0.02em · Body 28–32 Regular/Medium, 1.4 · Number/KPI 96–120 SemiBold · Label/kicker 22–24 Medium caps +0.18em · Diagram label ≥ 20 Medium caps +0.1em · Footnote ≥ 22 Regular, Stone · Publication header 22 Medium +0.2em · Page number 22 Regular, Stone.
**Absolute floor: 20 px at 1080 scale. Any text that does not survive 25% zoom is enlarged, simplified or removed.**

### 5.6 Infographic typography (controlled density — Instrument Sans exclusive)

Title 34–40 Bold · Section 22 SemiBold · Node title 15–17 SemiBold · Node description 12–13 Regular · Connector label 10–11 Medium caps +0.08em · Annotation 12 Regular, Stone · KPI 40–52 SemiBold · Source/footnote 10–11 Regular, Stone · Legend 11 Medium · Process step 14 SemiBold caps +0.12em · System name 13 SemiBold caps · Technology name 13 Medium.
**The editorial serif almost never appears in a technical diagram — at most one conclusion line under the schema.**

### 5.7 Architecture grammar — READ → REASON → CONTROL → ACT

Node styling is semantic (the charter demonstrates it with example systems):

| Node type | Style |
|---|---|
| System of record (e.g. SAP S/4HANA) | Green, thin outline |
| Data / semantic models (e.g. Fabric) | Blue-grey, thick left edge |
| AI (e.g. Foundry · Agent · RAG) | Mineral blue, tinted background · MCP links dotted |
| Business rules · deterministic | **Double-stroke border** |
| Human approval | **Solid porcelain fill** — "the judgment" |
| Action · write-back | **Solid champagne fill** — **unique: one per diagram** |

Line legend: **data flow** = solid · **reasoning / tool call** = dashed · **controlled action** = champagne stroke.

### 5.8 Composition rules

- Large typography, generous negative space.
- Warm light surfaces or deep dark surfaces; **max 2 background colors per publication**.
- Serif moments rare and controlled.
- Architectural hairlines 1–1.5 px.
- Asymmetry is embraced when it serves hierarchy.
- **Zero:** gradients, glassmorphism, AI glow, decorative icons, rounded-card overload.
- Editorial statement pattern (charter example): dark green card · kicker "BENACTA · ENTERPRISE AI NOTES — 001" in tracked champagne caps · serif statement with semantic color emphasis ("AI proposes." porcelain / "Systems validate." blue / "Humans decide." champagne) · triangle signature bottom-left · wordmark bottom-right.

---

## 6. Foundry-like architectural inspiration — conceptual only

The inspiration taken from platforms such as Palantir Foundry / AIP is **the architecture pattern, nothing else**:

```text
DATA → BUSINESS OBJECTS / SEMANTIC MODEL → BUSINESS LOGIC → DECISION CONTEXT → DECISION → ACTION → FEEDBACK
```

Internalized ideas: governed data foundation (traceable sources) · business/semantic layer (**raw data ≠ business meaning**) · deterministic business logic (never LLM-generated) · decision context (facts + history + documents + policies + events + relationships) · AI interpretation (retrieve, summarize, explain, compare, draft, question — never own truth) · human/governance layer (approval, judgment, accountability) · operational layer (insights connect to tasks, approvals, workflows, actions) · feedback loop (decision → action → outcome → learning).

**Hard boundaries:** no Palantir branding, UI imitation, logo, screenshots or implied affiliation; no "Palantir clone" claims; no Foundry terminology sprayed everywhere; no massive horizontal platform build. Public executive material uses BENACTA's own framing: **"From tables to business objects."** Executive term: **Business Semantic Layer**; technical documents may say **lightweight ontology**. Foundry may be referenced in technical material, sparingly.

---

## 7. Terminology

**Core vocabulary (use consistently):** Decision Intelligence · AI-Native Decision Systems · Controlled Intelligence · Decision Cockpit · Deterministic Core · Knowledge Layer · Business Semantic Layer · Trust Boundary · Human-in-the-Loop · Audit Trail · Decision Workflow.

**From Note #001:** Controlled Intelligence Architecture · Deterministic Finance Engine · The Value Core · Variance Engine · Anomaly Detection · AI Knowledge Layer · Commentary LLM · governed draft · faithfulness evals · Controller Sign-off · Flash Report · Monthly Pack · governed copilot · "computed facts only" · "facts above, interpretation below" · "every step logged".

**State vocabularies:**
- Commentary/approval workflow: `DRAFT → AWAITING_REVIEW → APPROVED / REVISION_REQUESTED` (UI labels: AI DRAFT · CONTROLLER REVIEW · APPROVED · REVISION REQUESTED).
- Decision issue: `OPEN · UNDER REVIEW · APPROVED · ACTION REQUIRED · CLOSED` (+ owner, next step, due date).

**Language rules:**
- Never label AI output "AI Decision". Use **Suggested follow-up**, **Decision option**, **Question to investigate**.
- Always mark generated interpretation (e.g. "AI-generated interpretation · Controller approval required").
- Avoid excessive: *agentic, autonomous, multi-agent, copilot, prompt engineering, LLM-first*. ("Governed copilot" exists in Note #001 as an artifact name; V1 UI avoids the word.)
- Executive layer never leads with: embeddings, vectors, prompts, JSON, RAG internals, Python classes, API payloads.
- Two-layer language everywhere feasible — e.g. Executive: "Every number remains reproducible." / Technical: "Metrics are calculated deterministically in Python."
- The default experience answers six questions: **What happened? Why? What requires attention? What are the possible next steps? What evidence supports this? Who approved this?**

---

## 8. Constraints

### Scope (V1 = thin, complete vertical slice)
- Use case: **Monthly Performance Review**, Finance vertical, fictional mid-sized industrial / project-based company, amounts in Euros.
- Storyline (coherent, non-random): revenue below plan (two project milestones shifted to August) · travel over budget (unplanned customer workshops) · external contractors over budget (temporary engineering capacity constraints) · gross margin partly protected by lower procurement costs. Reference numbers: Revenue actual €4.72M vs budget €5.00M → −€280k / −5.6%, HIGH materiality.
- Pipeline to demonstrate: SOURCE DATA → BUSINESS OBJECTS → DETERMINISTIC METRICS → CONTROL/ANOMALY → CONTEXT RETRIEVAL → AI INTERPRETATION → HUMAN REVIEW → DECISION/FOLLOW-UP → AUDIT TRAIL.
- Two experiences: **View A — Executive Decision Cockpit** (default; CEO/CFO/COO/Finance Director) and **View B — Architecture/Engineering** (CIO/CTO/architects/engineers); optional third technical-inspection tab, never dominant.
- Cockpit KPIs: Revenue, Gross Margin, Operating Expenses, EBITDA (each: actual, budget, variance €, variance %); engine may compute the wider set (External Costs, Personnel Costs, Travel) feeding 3–5 ranked attention items (HIGH/MEDIUM/LOW).

### Technical
- Python + Streamlit + Pandas; intentionally few dependencies.
- `DEMO_MODE=true`: the **entire** application works with no API key — deterministic engine, semantic layer, controls, retrieval, approval, audit all normal; commentary from controlled, evidence-based templates. Optional real LLM behind a small provider interface (not overengineered).
- Retrieval: deliberately simple and transparent (keyword / TF-IDF / simple scoring) returning document, section, snippet, relevance score — no vector DB in V1. The user must always see *why the system said what it said*.
- Deterministic formulas fixed: `variance = actual − budget`; `variance_pct = variance / abs(budget)` (None when budget = 0). Control rules transparent: |variance| > €100,000; variance % > 10%; missing budget; material cost increase; unusual period movement — returning severity, metric, rule, value, business_message.
- The LLM receives only computed facts + control alerts + retrieved context; it never recomputes, never invents numbers, never claims unsupported causality; distinguishes evidence from inference; states insufficiency; structured output (summary, drivers, evidence, open_questions, suggested_follow_up, confidence).
- Tests must include `tests/test_ai_independence.py::test_financial_truth_is_independent_from_llm` — the truth layer fully functional with AI disabled. This test is philosophically load-bearing.

### Explicit non-goals (V1)
No full ERP, Foundry clone, ontology engine, multi-agent swarms, Kafka, Kubernetes, microservices, enterprise IAM, real SAP integration, event buses, no-code builders, React/Next.js frontend, workflow engines, or vector infrastructure. *The elegance of V1 comes from proving the architecture with minimal implementation.*

### Process & hygiene
- Fictional data only; never real client data. No secrets, no absolute local paths, no junk, no dead code. LICENSE: placeholder + owner chooses before public release. **Never push to a remote unless explicitly instructed.**
- The Blueprint PDF (8–10 pages, designed HTML/CSS source retained) must belong to the same editorial family as Note #001, with a mandatory visual QA loop (render → inspect every page → compare to charter and Note #001 → fix → re-render).

---

## 9. Contradictions, ambiguities and assumptions

| # | Observation | Resolution (conservative) |
|---|---|---|
| A1 | **Palette/typography evolution.** Older BENACTA materials (existing brand doctrine, website) use green `#134939`, gold `#EEBA2B`, Cormorant Garamond/Inter. The supplied charter is titled **"Master Définitif"** and states the system is locked. | The supplied charter **wins for this project**: `#122B20` / `#F1E9DA` / `#6C9BA3` / `#BBA06B` (+ secondary colors) and Libre Caslon Display / Instrument Sans / editorial serif. This matches the brief's instruction: supplied files are the source of truth. |
| A2 | **Editorial serif "à valider"** — the charter leaves the choice open across three candidates but marks Source Serif 4 as "my recommendation". | Assume **Source Serif 4** unless the owner overrides. (Note #001's rendered serif is visually consistent with this class of face.) |
| A3 | **Note #001 shows RAG + Vector Store; the brief forbids vector infrastructure in V1.** | No conflict of principle: Note #001 depicts the *client target-state architecture*; V1 is a minimal reference implementation of the same boundaries. V1 keeps the Trust Boundary and AI Knowledge Layer concepts but implements retrieval as transparent keyword/TF-IDF scoring. Documentation may show the target architecture while stating what V1 implements. |
| A4 | **Charter names concrete vendor tech (SAP S/4HANA, Fabric, Foundry·Agent·RAG)** in the architecture-grammar section. | These are node-styling exemplars for diagrams, not integration instructions and not endorsements to reproduce. V1 uses generic labels (ERP mock / CSV, semantic layer, retrieval). |
| A5 | **Charter is written in French; deliverables are executive-facing.** | All public V1 deliverables (app, README, PDF) in **English** — consistent with Note #001, the logo tagline, and the personal-LinkedIn-in-English convention. The charter's rules apply regardless of language. |
| A6 | **Multiple slogans could blur.** | Slogan hierarchy fixed in §2; never mix roles on the same surface (e.g. the cover uses the thesis + tagline; doctrine pages use "Code computes…"). |
| A7 | **KPI list differs between brief §12.1 (4 KPIs) and §14 (6 metrics).** | Cockpit headline shows the 4 KPIs; the engine computes the wider metric set, which feeds controls and attention items. |
| A8 | **Repo tree in brief §23 shows `data/context/policies.md`, while §16 lists `travel_policy.md` and `finance_policy.md`.** | Minor; the brief says "adapt intelligently". Decide at implementation-plan time; favor a few clearly named policy documents. |
| A9 | **Logo assets supplied only as full-lockup PNGs** (dark/light); no SVG, no isolated monogram/triangle/wordmark files, no font files. | Non-blocking. Fonts are obtainable (Libre Caslon Display, Instrument Sans, Source Serif 4 are on Google Fonts). Derive monogram/signature crops carefully from the packs or faithfully reconstruct per charter geometry; keep originals under `assets/source-brand-assets/`. Flag to owner for eventual official SVGs. |
| A10 | **`source/reference/` is empty.** | No additional positioning documents exist beyond brief + charter + Note #001. Proceed on these three pillars; do not invent supplementary doctrine. |
| A11 | **Benchmarks.** Only the four sourced statistics from Note #001 may be reused, with their citations; derived figures keep the "illustrative" label. Zero invented statistics anywhere. | Hard rule carried into README, PDF, app copy. |
| A12 | **"Copilot" appears in Note #001 while the brief discourages the word.** | "Governed copilot" is acceptable as a named artifact when quoting/echoing Note #001; V1 product UI avoids the term. |

**Genuine blockers: none.** Everything required for Phase 1 (project brain) and Phase 2 (architecture plan) is present and internally consistent.

---

## 10. The ten most important rules inferred

1. **Code computes. AI explains. Humans decide.** Every number is produced by the deterministic core; the LLM never computes, recomputes or alters a figure, and a named human keeps approval and accountability.
2. **The Trust Boundary is explicit and load-bearing:** computed facts only cross it — facts above, interpretation below. AI receives structured facts, alerts and retrieved context; its output is a governed draft, never truth. `test_financial_truth_is_independent_from_llm` proves it.
3. **Start with the decision, not with AI.** Everything is organized around DATA → BUSINESS OBJECTS → TRUTH → CONTEXT → INTERPRETATION → DECISION → ACTION → OUTCOME, and the executive surface answers the six questions (what happened / why / attention / next steps / evidence / who approved).
4. **Raw data ≠ business meaning.** A lightweight Business Semantic Layer gives data meaning before AI touches anything. Foundry inspiration is conceptual only — publicly framed as "from tables to business objects", never as affiliation.
5. **Every important output is traceable.** Evidence lineage, audit trail, every step logged; statistics only with real sources; derived numbers labeled illustrative.
6. **Insight without action is incomplete.** A reviewed issue becomes owner + next step + status. This is a Decision System — not a dashboard, and never a chatbot.
7. **Two languages, one system.** Executive layer with zero AI-engineering vocabulary; technical layer for architects. Never label AI output a "decision" — it suggests follow-ups; humans decide.
8. **The brand charter is locked — select, don't reinterpret.** Exact palette (#122B20 · #F1E9DA · #6C9BA3/#54808A · #BBA06B/#8F7440 · #536875 · #7C898B · #D6BE98); Instrument Sans for the system, editorial serif for rare statements only, Libre Caslon Display for the logo only; color is information, never decoration.
9. **Semantic color grammar and scarcity:** green = foundation/governance, porcelain = truth/judgment, mineral blue = AI/reasoning only, champagne = decision/action (accents only, ≤10% of a composition, one action node per diagram). Zero gradients, glassmorphism, AI glow, decorative icons, rounded-card overload.
10. **V1 is a thin, complete, demo-first vertical slice.** Fully functional with no API key, minimal dependencies, no vector DB / agents / platform-building; the app, README and PDF must feel like one editorial family with Architecture Note #001 and tell the same story.

---

*Phase 0 complete. Next gate (per playbook): Phase 1 — create the persistent BENACTA project brain (`CLAUDE.md` + `.claude/benacta/*`). Awaiting instruction.*
