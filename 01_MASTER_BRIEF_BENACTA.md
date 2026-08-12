# BENACTA — Decision Intelligence Blueprint
## Master Brief for Claude Code

> **Purpose:** Build the first public reference implementation of the BENACTA Decision Intelligence architecture, with Finance as the first vertical slice.
>
> **Core doctrine:**  
> **CODE COMPUTES. AI EXPLAINS. HUMANS DECIDE.**
>
> **Broader system direction:**  
> **DATA → BUSINESS OBJECTS → TRUTH → CONTEXT → INTERPRETATION → DECISION → ACTION → OUTCOME**

---

# 0. Your role

You are working as the founding product, architecture, engineering and executive communication team for **BENACTA**.

Act simultaneously as:

- Enterprise AI Solution Architect
- Decision Intelligence Architect
- Finance Transformation Architect
- Enterprise Software Architect
- Senior Python Engineer
- Product Designer
- Information Designer
- Technical Writer
- Executive Communication Designer

This is **not** a generic coding exercise.

You are helping formalize the first reference implementation of BENACTA's core intellectual and product direction.

---

# 1. First: inspect all supplied project materials

Before writing code, inspect the entire repository.

Pay particular attention to all files placed under `/source`, including:

- BENACTA graphical charter / brand guidelines
- BENACTA Architecture Note #001
- logos
- fonts referenced by the brand guide
- positioning documents
- architecture diagrams
- screenshots
- PDFs
- images
- markdown files
- any previous strategic notes

Treat those supplied materials as the **source of truth** for:

- brand identity
- visual hierarchy
- terminology
- architecture philosophy
- tone
- positioning
- editorial style

Do **not** replace their philosophy with generic AI-consulting language.

Do **not** start coding before understanding them.

If something is missing, infer conservatively and document the assumption.

---

# 2. Create the persistent BENACTA Claude context first

Before implementation, create or enrich the project-level Claude context.

If a `CLAUDE.md` already exists:

- preserve useful instructions
- merge rather than overwrite
- remove contradictions only when justified by the supplied BENACTA source materials

Create this knowledge structure:

```text
CLAUDE.md

.claude/
└── benacta/
    ├── positioning.md
    ├── decision-intelligence.md
    ├── architecture-principles.md
    ├── brand-system.md
    ├── content-system.md
    ├── vocabulary.md
    └── anti-patterns.md
```

The objective is that **future Claude Code sessions understand BENACTA without needing the whole philosophy to be restated**.

---

# 3. BENACTA positioning

BENACTA is **not** positioned as:

- an AI chatbot agency
- a RAG agency
- a generic automation agency
- a dashboard consultancy
- a Power BI consultancy
- an "AI agents everywhere" company
- a ChatGPT-wrapper builder

BENACTA designs and builds:

# AI-NATIVE DECISION SYSTEMS

at the intersection of:

- Enterprise AI
- Decision Intelligence
- Data
- Business Logic
- Workflows
- Human Judgment

Initial domains include:

- Finance
- Operations
- Performance Management
- Planning
- Enterprise Workflows

Finance is a strong entry point / wedge.

**BENACTA is broader than Finance.**

Core positioning:

> **BENACTA**  
> Enterprise AI · Decision Intelligence  
> **AI-Native Decision Systems**  
> Turning enterprise data into decisions and action.  
> **Built on Truth. Designed for Decisions.**

---

# 4. BENACTA Decision Intelligence philosophy

The core problem BENACTA addresses is **not**:

> "How do we add an LLM to enterprise data?"

It is:

> **"How do we engineer the path from enterprise truth to business decision and action?"**

The system connects:

```text
DATA
↓
BUSINESS MEANING
↓
RULES
↓
ANALYSIS
↓
CONTEXT
↓
AI INTERPRETATION
↓
DECISION
↓
WORKFLOW
↓
ACTION
↓
FEEDBACK
```

This is the conceptual foundation of BENACTA.

Store it explicitly in `.claude/benacta/decision-intelligence.md`.

---

# 5. Foundry-like inspiration — conceptual only

BENACTA is inspired by selected enterprise architecture principles visible in platforms such as **Palantir Foundry / AIP**.

This does **not** mean:

- copying Palantir
- copying its UI
- copying its branding
- claiming affiliation
- claiming BENACTA is "a Palantir clone"
- reproducing Foundry terminology everywhere
- rebuilding a massive horizontal data platform

The inspiration is architectural:

```text
DATA
→ BUSINESS OBJECTS / SEMANTIC MODEL
→ BUSINESS LOGIC
→ DECISION CONTEXT
→ DECISION
→ ACTION
→ FEEDBACK
```

Internalize the following ideas.

## 5.1 Governed data foundation

Enterprise sources remain traceable.

Examples:

- ERP
- CRM
- EPM
- data warehouse / lakehouse
- documents
- operational systems
- APIs

## 5.2 Business / semantic layer

Raw tables are not decisions.

Represent understandable business objects such as:

- Customer
- Project
- Invoice
- Cost Center
- Account
- Contract
- Forecast
- Budget
- Business Unit
- Supplier

Represent simple relationships between them.

For this reference project:

- use Python models / dataclasses / Pydantic or structured JSON
- keep it lightweight
- do not build an ontology platform

The objective is to prove the concept:

> **RAW DATA ≠ BUSINESS MEANING**

## 5.3 Deterministic business logic

Critical business facts are calculated with:

- code
- rules
- SQL-like transformations
- policies
- controls

They are **not generated by an LLM**.

## 5.4 Decision context

Combine:

- facts
- history
- documents
- policies
- events
- business relationships

## 5.5 AI interpretation

AI may:

- retrieve
- summarize
- explain
- compare
- identify context
- draft narratives
- surface questions
- surface options

AI does **not** own enterprise truth.

## 5.6 Human / governance layer

Humans retain:

- approval
- judgment
- responsibility
- escalation
- accountability

## 5.7 Operational layer

A Decision Intelligence System should go beyond dashboards.

Insights should connect to:

- tasks
- approvals
- workflows
- notifications
- investigations
- scenario review
- actions

## 5.8 Feedback loop

Capture:

- decision
- action
- outcome
- feedback

The long-term loop is:

```text
DATA → DECISION → ACTION → OUTCOME → LEARNING
```

---

# 6. Core BENACTA architectural doctrine

Store these principles prominently in `.claude`.

## Principle 01
**ENGINEER THE TRUTH. AUGMENT THE JUDGMENT.**

## Principle 02
**CODE COMPUTES. AI EXPLAINS. HUMANS DECIDE.**

## Principle 03
**AN LLM SHOULD NEVER OWN YOUR NUMBERS. IT SHOULD EXPLAIN THEM.**

## Principle 04
**THE LLM IS NOT THE SYSTEM. IT IS ONE COMPONENT OF THE SYSTEM.**

## Principle 05
**DO NOT START WITH AI. START WITH THE DECISION.**

## Principle 06
**ARCHITECTURE BEFORE TOOLS.**

## Principle 07
**AI AT THE EDGE. CONTROL AT THE CORE.**

## Principle 08
**EVERY IMPORTANT OUTPUT MUST BE TRACEABLE.**

## Principle 09
**INSIGHT WITHOUT ACTION IS INCOMPLETE.**

## Principle 10
**ENTERPRISE AI MUST CONNECT TRUTH, CONTEXT, JUDGMENT AND ACTION.**

---

# 7. BENACTA reference architecture

Use this as the conceptual architecture:

```text
                    CEO / CFO / COO
                           │
                           ▼
                DECISION EXPERIENCE
              ┌──────────────────────┐
              │ What happened?       │
              │ Why?                 │
              │ What happens next?   │
              │ What needs attention?│
              │ What can we do?      │
              └──────────┬───────────┘
                         │
                         ▼
                  DECISION ENGINE
                         │
          ┌──────────────┼──────────────┐
          │              │              │
       FINANCE       OPERATIONS      PERFORMANCE
          │              │              │
          └──────────────┬──────────────┘
                         │
             BUSINESS / SEMANTIC LAYER
                         │
                 Business Objects
                 Metrics & Rules
                 Relationships
                         │
             ┌───────────┴───────────┐
             │                       │
     DETERMINISTIC CORE        KNOWLEDGE LAYER
     calculations              documents
     controls                  policies
     metrics                   history
     reconciliations           context
             │                       │
             └───────────┬───────────┘
                         │
                 AI INTERPRETATION
                         │
                   HUMAN CONTROL
                         │
                 WORKFLOW / ACTION
                         │
                    AUDIT TRAIL
                         │
                 FEEDBACK / OUTCOME
```

Do **not** implement all of this.

The project is a **thin, complete vertical slice** through this architecture.

---

# 8. Project to build

Repository name:

# `benacta-decision-intelligence-blueprint`

Suggested description:

> **A reference implementation for governed AI-native decision systems — where code computes, AI explains, and humans decide.**

The project must demonstrate:

```text
SOURCE DATA
↓
BUSINESS OBJECTS
↓
DETERMINISTIC METRICS
↓
CONTROL / ANOMALY
↓
CONTEXT RETRIEVAL
↓
AI INTERPRETATION
↓
HUMAN REVIEW
↓
DECISION / FOLLOW-UP
↓
AUDIT TRAIL
```

Use **Finance** as the first vertical example.

Use case:

# MONTHLY PERFORMANCE REVIEW

The fictional company should resemble a mid-sized industrial / project-based organization.

---

# 9. Executive-first design requirement

A CEO or CFO must benefit from this project without looking at code.

The default experience must **not** lead with:

- embeddings
- vectors
- prompts
- JSON
- RAG internals
- Python classes
- API payloads

The default experience answers:

1. **WHAT HAPPENED?**
2. **WHY?**
3. **WHAT REQUIRES ATTENTION?**
4. **WHAT ARE THE POSSIBLE NEXT STEPS?**
5. **WHAT EVIDENCE SUPPORTS THIS?**
6. **WHO APPROVED THIS?**

Example:

```text
JULY PERFORMANCE REVIEW

Revenue

Actual              €4.72M
Budget              €5.00M
Variance            -€280K
Variance             -5.6%

WHAT HAPPENED?

Revenue finished €280k below budget.

WHY?

Two customer project milestones expected in July
shifted into August.

WHAT REQUIRES ATTENTION?

HIGH PRIORITY

Revenue variance exceeds the company's
€100k materiality threshold.

SUGGESTED FOLLOW-UP

Review milestone recognition with Project Finance.

EVIDENCE

✓ General Ledger
✓ FY26 Budget
✓ Project Milestone Note

AI-generated interpretation
Controller approval required.

[ REQUEST REVISION ] [ APPROVE ]
```

This must feel like a miniature **Decision System**, not a chatbot.

---

# 10. Application technology

Build the prototype with:

- Python
- Streamlit
- Pandas

Keep dependencies intentionally small.

LLM integration is **optional**.

The entire application must work without any API key.

Use:

```text
DEMO_MODE=true
```

In demo mode:

- deterministic finance engine works normally
- semantic/business object layer works normally
- control engine works normally
- retrieval works normally
- approval works normally
- audit works normally
- commentary is produced with controlled templates based on retrieved evidence

If an API key is provided later, optionally enable real LLM commentary.

Keep the model provider behind a small interface.

Do not overengineer provider abstraction.

---

# 11. Two main application experiences

## View A — Executive Decision Cockpit

Default.

Audience:

- CEO
- CFO
- COO
- Finance Director

## View B — Architecture / Engineering

Audience:

- CIO
- CTO
- Enterprise Architect
- AI Engineer
- Data Engineer
- Finance Transformation

A third optional technical inspection tab may expose raw payloads and audit details, but it must not dominate the default experience.

---

# 12. Executive Decision Cockpit

Create a polished Streamlit interface.

## 12.1 Performance

Display:

- Revenue
- Gross Margin
- Operating Expenses
- EBITDA

For each:

- Actual
- Budget
- Variance €
- Variance %

## 12.2 Attention

Show 3–5 issues ranked:

- HIGH
- MEDIUM
- LOW

## 12.3 Why

For a selected variance, show concise explanation.

## 12.4 Evidence

Display the exact business sources used.

## 12.5 Possible next step

Never label it "AI Decision".

Prefer:

- Suggested follow-up
- Decision option
- Question to investigate

## 12.6 Human control

Statuses:

- AI DRAFT
- CONTROLLER REVIEW
- APPROVED
- REVISION REQUESTED

## 12.7 Decision log

Show:

- issue
- interpretation
- reviewer
- decision / next step
- owner
- status
- timestamp

---

# 13. Business semantic layer

Introduce a small business-object layer.

Do not overengineer.

Possible models:

- `BusinessUnit`
- `CostCenter`
- `Account`
- `Metric`
- `Variance`
- `ManagementNote`
- `DecisionIssue`

Relationships:

```text
BusinessUnit
  has CostCenters

CostCenter
  has Accounts

Metric
  belongs to BusinessUnit

Variance
  affects Metric

ManagementNote
  provides context for Variance

DecisionIssue
  references Variance
```

Use **Business Semantic Layer** in executive documentation.

You may use **lightweight ontology** in technical documentation.

The concept to demonstrate is:

> **RAW DATA ≠ BUSINESS MEANING**

---

# 14. Deterministic finance engine

Create:

```text
src/finance_engine.py
```

Calculate:

- actual
- budget
- variance
- variance_pct

Formula:

```python
variance = actual - budget

variance_pct = (
    variance / abs(budget)
    if budget != 0
    else None
)
```

Potential metrics:

- Revenue
- Gross Margin
- External Costs
- Personnel Costs
- Travel
- EBITDA

Create structured financial-fact objects.

Example:

```json
{
  "metric": "Revenue",
  "actual": 4720000,
  "budget": 5000000,
  "variance": -280000,
  "variance_pct": -0.056,
  "materiality": "HIGH"
}
```

The LLM consumes this object.

The LLM must **never recompute financial truth from raw source rows**.

---

# 15. Control engine

Create:

```text
src/control_engine.py
```

Use transparent rules such as:

- absolute variance > €100,000
- variance % > 10%
- missing budget
- material cost increase
- unusual period movement

Return:

- severity
- metric
- rule
- value
- business_message

The objective is explainability, not ML sophistication.

---

# 16. Knowledge / context layer

Provide fictional documents under:

```text
data/context/
```

Examples:

- `management_notes.md`
- `project_milestones.md`
- `forecast_assumptions.md`
- `travel_policy.md`
- `finance_policy.md`

Keep retrieval deliberately simple.

No vector database is required in V1.

Possible implementation:

- keyword matching
- TF-IDF
- simple transparent scoring

Return:

- document
- section
- snippet
- relevance score

The user must always be able to see:

> **WHY THE SYSTEM SAID WHAT IT SAID**

---

# 17. AI commentary layer

Create:

```text
src/commentary.py
```

AI receives only:

- computed facts
- materiality/control alerts
- retrieved context

The AI must be instructed to:

- never invent numbers
- never recalculate figures
- never alter computed figures
- never claim unsupported causality
- distinguish evidence from inference
- state when evidence is insufficient
- remain concise
- use CFO-appropriate language

Structured output:

```json
{
  "summary": "...",
  "drivers": ["..."],
  "evidence": ["..."],
  "open_questions": ["..."],
  "suggested_follow_up": ["..."],
  "confidence": "HIGH"
}
```

"Suggested follow-up" is not an autonomous decision.

---

# 18. Human-in-the-loop workflow

Create:

```text
src/approval.py
```

Statuses:

- DRAFT
- AWAITING_REVIEW
- APPROVED
- REVISION_REQUESTED

Store:

- reviewer
- timestamp
- status
- comment

Core message:

> **AI drafts. Humans approve.**

---

# 19. Decision / action layer

Do not stop at commentary.

A reviewed issue can have:

Statuses:

- OPEN
- UNDER REVIEW
- APPROVED
- ACTION REQUIRED
- CLOSED

Optional fields:

- OWNER
- NEXT STEP
- DUE DATE

Example:

```text
Issue:
Revenue below budget

Decision:
Investigate delayed project milestones.

Owner:
Project Finance

Status:
ACTION REQUIRED
```

This demonstrates:

> **INSIGHT → DECISION → ACTION**

without building a full workflow engine.

---

# 20. Auditability

Create:

```text
src/audit.py
```

Every important output should allow inspection of:

- input source
- calculation version
- metric calculation
- control rule triggered
- context retrieved
- AI or demo mode
- model if applicable
- human reviewer
- decision status
- next step
- timestamp

Make an Audit Trail view.

---

# 21. Fictional demo data

Use fictional data only.

Never use real client data.

Create:

```text
data/actuals.csv
data/budget.csv
```

Possible columns:

- period
- business_unit
- cost_center
- account
- account_category
- amount

Use Euros.

Create one coherent management story.

Suggested storyline:

- Revenue below plan because two project milestones shifted to August
- Travel above budget because of unplanned customer workshops
- External contractors above budget because of temporary engineering capacity constraints
- Gross margin partly protected by lower procurement costs

Do not generate meaningless random values.

---

# 22. BENACTA visual system

Read the supplied BENACTA graphical charter first.

The charter is the source of truth.

Do not invent a new brand.

Expected character:

- premium
- editorial
- institutional
- enterprise
- understated
- architectural

Likely visual language from supplied assets may include:

- deep forest green
- warm beige / ivory
- muted gold
- desaturated blue

But use the **exact values from the supplied charter**.

Avoid:

- AI purple gradients
- neon
- cyberpunk
- generic SaaS aesthetics
- excessive glassmorphism
- robot imagery
- gratuitous rounded-card dashboards

The app and PDF must look like the same family as **BENACTA Architecture Note #001**.

Think:

- strategy publication
- architecture blueprint
- premium finance institution
- enterprise operating system

---

# 23. Repository structure

Target structure:

```text
benacta-decision-intelligence-blueprint/
│
├── CLAUDE.md
├── README.md
├── LICENSE
├── requirements.txt
├── .env.example
├── .gitignore
├── app.py
│
├── .claude/
│   └── benacta/
│       ├── positioning.md
│       ├── decision-intelligence.md
│       ├── architecture-principles.md
│       ├── brand-system.md
│       ├── content-system.md
│       ├── vocabulary.md
│       └── anti-patterns.md
│
├── source/
│   ├── brand/
│   ├── architecture-note/
│   └── reference/
│
├── data/
│   ├── actuals.csv
│   ├── budget.csv
│   └── context/
│       ├── management_notes.md
│       ├── project_milestones.md
│       ├── forecast_assumptions.md
│       └── policies.md
│
├── src/
│   ├── __init__.py
│   ├── domain.py
│   ├── finance_engine.py
│   ├── control_engine.py
│   ├── retrieval.py
│   ├── commentary.py
│   ├── approval.py
│   ├── decision_log.py
│   └── audit.py
│
├── tests/
│   ├── test_finance_engine.py
│   ├── test_controls.py
│   └── test_ai_independence.py
│
├── docs/
│   ├── architecture.md
│   ├── executive_blueprint.md
│   ├── controlled-intelligence-blueprint.html
│   ├── BENACTA_Controlled_Intelligence_Blueprint.pdf
│   └── implementation-guide.md
│
├── assets/
│   ├── source-brand-assets/
│   └── generated/
│
└── outputs/
```

Adapt intelligently if necessary.

Do not create complexity for its own sake.

---

# 24. README — executive first

The README must serve executives **and** engineers.

The first screen must contain no installation commands.

Start with:

```text
BENACTA

DECISION INTELLIGENCE REFERENCE ARCHITECTURE

An LLM should never own your numbers.
It should explain them.

CODE COMPUTES.
AI EXPLAINS.
HUMANS DECIDE.
```

Then:

## The problem

Most enterprise AI demonstrations begin with the model.

Finance cannot.

Financial truth must remain:

- reproducible
- controlled
- traceable
- auditable

## What this project demonstrates

1. Finance data enters a governed deterministic layer
2. Business objects give it meaning
3. Code calculates the facts
4. Controls surface material movements
5. Relevant business context is retrieved
6. AI drafts an interpretation
7. A human reviews it
8. The decision can become an action
9. Every important step is logged

## Business example

Show prominently:

```text
QUESTION

Why is revenue below budget?

TRUTH

Actual      €4.72M
Budget      €5.00M
Variance   -€280k
Variance     -5.6%

CALCULATED BY CODE ✓

CONTEXT

Two project milestones expected in July shifted into August.

AI INTERPRETATION

Revenue finished €280k below budget (-5.6%), primarily associated
with two project milestones moving into the following period.

EVIDENCE

✓ General Ledger
✓ Budget
✓ Project Milestone Note

HUMAN CONTROL

Controller approval required.

ACTION

Review milestone recognition with Project Finance.
```

Only after this executive section should the README introduce:

- architecture
- technical stack
- installation
- code structure

---

# 25. README architecture views

Use Mermaid where useful.

Provide two architecture views.

## Business view

```text
Enterprise Data
↓
Business Meaning
↓
Deterministic Truth
↓
Context
↓
Interpretation
↓
Human Decision
↓
Action
↓
Outcome
```

## Technical view

```text
CSV / ERP mock
↓
Domain models
↓
Finance engine
↓
Control engine
↓
Retrieval
↓
LLM / demo commentary
↓
Approval state
↓
Decision log / audit
```

---

# 26. Executive PDF deliverable

Produce:

# `docs/BENACTA_Controlled_Intelligence_Blueprint.pdf`

This is a premium LinkedIn lead magnet.

It must be useful even if the reader never opens GitHub.

Target audience:

- CEO
- CFO
- COO
- Finance Director
- Transformation Director
- CIO

Target length:

**8–10 pages.**

Do not simply export Markdown to a plain PDF.

Create a designed HTML/CSS source or another maintainable programmatic layout.

Also retain:

```text
docs/controlled-intelligence-blueprint.html
```

The PDF must strictly follow the supplied BENACTA graphical charter.

---

# 27. PDF page structure

## Page 1 — Cover

**BENACTA**

# CONTROLLED INTELLIGENCE BLUEPRINT

How to introduce AI into enterprise decision-making  
without giving up control of the truth.

> **An LLM should never own your numbers.  
> It should explain them.**

**Built on Truth. Designed for Decisions.**

---

## Page 2 — From business data to business decisions

Explain in executive language:

Companies already have:

- ERP
- EPM
- CRM
- BI
- data platforms
- documents
- reports

Yet decisions still require people to:

- collect
- reconcile
- interpret
- search
- explain
- email
- approve
- follow up

The opportunity is not merely another dashboard.

It is not merely a chatbot.

It is a Decision Intelligence layer connecting:

> **DATA → CONTEXT → DECISION → ACTION**

---

## Page 3 — The Decision Intelligence System

Introduce:

```text
ENTERPRISE SYSTEMS
↓
BUSINESS / SEMANTIC LAYER
↓
DETERMINISTIC TRUTH
↓
KNOWLEDGE & CONTEXT
↓
AI INTERPRETATION
↓
HUMAN JUDGMENT
↓
WORKFLOW / ACTION
↓
AUDIT & FEEDBACK
```

Explain in executive language.

Do not overload the page with technical detail.

---

## Page 4 — Controlled Intelligence

Large typography:

# CODE COMPUTES.

# AI EXPLAINS.

# HUMANS DECIDE.

Explain responsibilities.

### Code
- Facts
- Metrics
- Controls
- Rules

### AI
- Context
- Interpretation
- Drafting
- Questions

### Humans
- Judgment
- Approval
- Accountability
- Action

---

## Page 5 — Reference use case: Monthly Performance Review

Show:

Revenue

- Actual: €4.72M
- Budget: €5.00M
- Variance: -€280k
- Variance %: -5.6%

Then:

- What happened?
- Why?
- What requires attention?
- What could we do next?
- What is the evidence?
- Who approves?

Make the page visual and executive-friendly.

---

## Page 6 — From dashboard to decision system

Create a progression:

```text
REPORTING
"What happened?"
↓
ANALYTICS
"Why?"
↓
PREDICTION
"What may happen?"
↓
DECISION INTELLIGENCE
"What requires a decision?"
↓
ACTION
"What do we do next?"
```

Show that BENACTA goes beyond dashboarding.

---

## Page 7 — Business objects before AI

Working concept:

# FROM TABLES TO BUSINESS OBJECTS

Do not use Palantir branding.

Do not imply a partnership.

Explain the enterprise design pattern:

```text
RAW DATA
↓
BUSINESS OBJECTS
↓
RULES & METRICS
↓
CONTEXT
↓
DECISION
↓
WORKFLOW
```

Example:

An invoice is not merely a row in a table.

It relates to:

- supplier
- project
- cost center
- contract
- budget
- payment status
- policy
- owner

Decision systems reason around business objects and relationships, not isolated tables.

Call this the:

**BUSINESS SEMANTIC / ONTOLOGY LAYER**

---

## Page 8 — How to start

BENACTA implementation path:

1. Pick one decision process
2. Map the data and business objects
3. Engineer the truth layer
4. Add context
5. Add AI interpretation
6. Keep humans in control
7. Connect to workflow
8. Measure outcomes

Possible baseline metrics:

- cycle time
- accuracy
- analyst capacity
- decision latency
- adoption
- exceptions
- business outcome

---

## Page 9 — Reference implementation

Show a simplified screenshot / architecture from the working project.

Explain that the reference implementation demonstrates:

- deterministic finance engine
- business semantic layer
- control engine
- context retrieval
- AI interpretation
- human approval
- workflow status
- audit trail

Add a placeholder:

> **SEE THE WORKING IMPLEMENTATION**

Include placeholders for:

- GitHub URL
- live demo URL
- QR code if appropriate

---

## Page 10 — Close

# DON'T START WITH AI.

# START WITH THE DECISION.

**BENACTA**  
AI-Native Decision Systems  
Enterprise AI · Decision Intelligence  
Finance · Operations · Performance · Workflows

**Built on Truth. Designed for Decisions.**

Include placeholders for:

- Anas Benazzouz
- LinkedIn
- Website
- GitHub

---

# 28. PDF quality rules

The PDF must feel like the same editorial system as BENACTA Architecture Note #001.

Requirements:

- premium whitespace
- strong information hierarchy
- restrained color
- brand typography
- consistent section numbering
- vector/SVG diagrams where practical
- readable at normal zoom
- no clipped text
- no overflow
- no awkward page breaks
- no rasterized small typography
- no generic AI imagery
- no obvious template feel

After rendering:

1. inspect every page visually
2. compare it to the supplied graphical charter
3. compare it to Architecture Note #001
4. fix all alignment, spacing, hierarchy and typography issues
5. render again
6. inspect again

Do not declare the PDF complete without a visual QA pass.

---

# 29. Executive vs technical language

Whenever possible, expose two layers.

Examples:

### Executive
> The system finds the policy or operational note that explains the movement.

### Technical
> Retrieval identifies relevant document sections.

---

### Executive
> Every number remains reproducible.

### Technical
> Metrics are calculated deterministically in Python.

---

### Executive
> A controller remains accountable for published commentary.

### Technical
> Human-in-the-loop approval state machine.

The project must demonstrate sophisticated architecture **without forcing executives to learn AI engineering vocabulary**.

---

# 30. Tests

Write tests proving:

- variance calculations are correct
- variance percentages are correct
- materiality rules work
- missing budget is handled
- context retrieval returns inspectable evidence
- approval state changes are deterministic

Most importantly, create:

```text
tests/test_ai_independence.py
```

Include a test clearly named:

```python
test_financial_truth_is_independent_from_llm
```

Disable the AI layer entirely.

The project must still correctly produce:

- actual
- budget
- variance
- variance %
- controls
- materiality
- business objects

This test is philosophically important for BENACTA.

---

# 31. Product vocabulary

Use consistently:

- Decision Intelligence
- AI-Native Decision Systems
- Controlled Intelligence
- Decision Cockpit
- Deterministic Core
- Knowledge Layer
- Business Semantic Layer
- Trust Boundary
- Human-in-the-Loop
- Audit Trail
- Decision Workflow

Use technical AI vocabulary only where useful.

Avoid excessive use of:

- agentic
- autonomous
- multi-agent
- copilot
- prompt engineering
- LLM-first

BENACTA understands hype.

BENACTA uses technologies only when architecture and business value justify them.

---

# 32. Long-term BENACTA direction

Store this in:

```text
.claude/benacta/decision-intelligence.md
```

The long-term conceptual direction is a reusable Decision Intelligence layer.

## CONNECT

- ERP
- EPM
- CRM
- Data Platforms
- Documents
- APIs

## MODEL

- Business objects
- Relationships
- Metrics
- Rules
- Semantic definitions

## UNDERSTAND

- Events
- Exceptions
- Variances
- Drivers
- Scenarios

## AUGMENT

- Retrieval
- AI interpretation
- Simulation
- Decision support

## ACT

- Approvals
- Tasks
- Workflows
- Operational actions

## GOVERN

- Permissions
- Lineage
- Auditability
- Human accountability

## LEARN

- Decision history
- Outcomes
- Feedback

The architecture may take inspiration from enterprise decision/data platforms such as Foundry/AIP, but BENACTA must develop its **own focused, pragmatic and composable architecture**.

Strategy:

> **START WITH HIGH-VALUE DECISION WORKFLOWS.**  
> **PROVE VALUE.**  
> **BUILD REUSABLE COMPONENTS.**  
> **EXPAND THE DECISION GRAPH OVER TIME.**

---

# 33. What not to build in V1

Do not add:

- a full ERP
- a real Foundry clone
- a complex ontology engine
- multi-agent swarms
- Kafka
- Kubernetes
- microservice meshes
- enterprise IAM
- real SAP integration
- production-grade event buses
- generic no-code builders
- complex React/Next.js frontend
- full workflow engines
- unnecessary vector infrastructure

The elegance of V1 comes from **proving the architecture with minimal implementation**.

---

# 34. GitHub quality

The repository should look credible publicly.

Create:

- clean README
- meaningful commit-ready structure
- `.gitignore`
- `.env.example`
- `LICENSE` placeholder or a note asking the owner to choose before public release
- screenshots directory
- `docs/`
- tests
- no secrets
- no generated junk committed
- no dead code
- no broken commands
- no client data

Do not push anything to a remote repository unless explicitly instructed.

---

# 35. Success criteria

A CFO should leave thinking:

> "I understand how AI can help Finance without controlling the numbers."

A CEO should leave thinking:

> "I can see how this connects data to decisions and action."

A CIO should leave thinking:

> "The architecture has sensible boundaries."

A Finance Controller should leave thinking:

> "This augments my work rather than removing my accountability."

An Enterprise Architect should leave thinking:

> "The semantic/business-object layer and trust boundary are meaningful."

An AI Engineer should leave thinking:

> "The deterministic and probabilistic responsibilities are separated cleanly."

A potential client should leave thinking:

> "BENACTA seems to understand enterprise data, Finance, AI architecture and decision workflows."

---

# 36. Final QA

Before declaring completion:

1. Run all tests.
2. Run the Streamlit application.
3. Verify Demo Mode works without an API key.
4. Verify the deterministic layer works with AI disabled.
5. Inspect every important application screen.
6. Render the PDF.
7. Visually inspect every PDF page.
8. Verify exact brand-charter adherence.
9. Verify no clipped text.
10. Verify diagrams are legible.
11. Verify the README starts with business value.
12. Verify the GitHub repository and PDF tell the same story.
13. Verify Architecture Note #001 and this implementation are conceptually consistent.
14. Verify a CFO can understand it without knowing what RAG means.
15. Verify an architect can inspect the implementation and understand its boundaries.
16. Verify the project does not overclaim autonomous AI.
17. Remove dead code.
18. Remove unnecessary abstractions.
19. Remove unnecessary dependencies.
20. Confirm no sensitive or real client data exists anywhere.

---

# 37. Final deliverables

At completion produce:

## A. Working project
A functioning Decision Intelligence reference implementation.

## B. Executive application
A polished Streamlit Decision Cockpit.

## C. Public-ready GitHub repository
Professional README and documentation.

## D. Executive PDF
`BENACTA_Controlled_Intelligence_Blueprint.pdf`

## E. Persistent Claude knowledge
`CLAUDE.md` and `.claude/benacta/*`.

## F. Architecture documentation
- business architecture
- technical architecture
- decision flow
- trust boundaries
- semantic/business-object model

## G. Test suite
Including proof that deterministic truth is independent from the AI layer.

## H. Demo data
Entirely fictional.

## I. LinkedIn / distribution package

Propose:

- the 5 strongest screenshots to capture
- GitHub repository description
- GitHub topics
- LinkedIn CTA
- message to send people who comment `BLUEPRINT`
- PDF filename
- GitHub release title
- short website description
- 3 follow-up Architecture Note ideas

---

# 38. Mandatory working method

Do **not** throw code into files immediately.

Follow this sequence.

## Step 1 — Inspect
Study all supplied source materials.

## Step 2 — Understand
Summarize your understanding of:

- BENACTA
- brand system
- Architecture Note #001
- Decision Intelligence philosophy
- Foundry-like conceptual inspiration
- V1 scope

## Step 3 — Persist the doctrine
Create/update:

- `CLAUDE.md`
- `.claude/benacta/*`

## Step 4 — Plan
Write a concise implementation plan with:

- architecture
- scope
- repo tree
- acceptance criteria
- explicit non-goals

## Step 5 — Build truth first
Implement:

- domain models
- deterministic finance engine
- controls
- tests

## Step 6 — Add context
Implement:

- management documents
- transparent retrieval
- evidence lineage

## Step 7 — Add interpretation
Implement:

- demo commentary
- optional LLM
- structured output
- uncertainty/evidence handling

## Step 8 — Add human control
Implement:

- review
- approval
- decision status
- owner
- next step
- audit trail

## Step 9 — Build executive experience
Create the Streamlit Decision Cockpit.

## Step 10 — Build architecture view
Expose business + technical architecture.

## Step 11 — Write public documentation
Create the executive-first README and supporting docs.

## Step 12 — Create the PDF
Use the supplied BENACTA brand system.

## Step 13 — Test and inspect
Run code, tests and visual QA.

## Step 14 — Review against doctrine
Ask:

> Does every part of this project reinforce the BENACTA Decision Intelligence philosophy?

## Step 15 — Finalize
Produce final handoff report.

---

# 39. Final instruction

Prioritize:

1. conceptual integrity
2. executive clarity
3. deterministic correctness
4. traceability
5. business relevance
6. visual coherence
7. simplicity
8. engineering quality

over unnecessary technical sophistication.

The finished project must communicate one idea exceptionally well:

> **ENTERPRISE AI SHOULD NOT REPLACE THE SYSTEM OF TRUTH.**
>
> **IT SHOULD TURN GOVERNED TRUTH INTO BETTER DECISIONS AND ACTIONS.**

# BENACTA

**Built on Truth. Designed for Decisions.**
