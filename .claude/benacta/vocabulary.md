# BENACTA — Vocabulary

> Binding doctrine. Consult before naming anything — modules, UI labels, statuses, docs headings, marketing copy.

## Core product vocabulary (use consistently)

Decision Intelligence · AI-Native Decision Systems · Controlled Intelligence · Decision Cockpit · Deterministic Core · Knowledge Layer · Business Semantic Layer · Trust Boundary · Human-in-the-Loop · Audit Trail · Decision Workflow.

## Architecture Note #001 vocabulary (echo when referencing the note or target architecture)

Controlled Intelligence Architecture (`FIN-AI-001`) · Deterministic Finance Engine · The Value Core · Variance Engine · Anomaly Detection · AI Knowledge Layer · Commentary LLM · governed draft · faithfulness evals · Controller Sign-off · Flash Report · Monthly Pack · governed copilot · "computed facts only" · "facts above, interpretation below" · "every step logged".

## Executive vs technical terms

| Say to executives | Say to architects/engineers |
|---|---|
| Business Semantic Layer | lightweight ontology / business-object model |
| The system finds the note that explains the movement | retrieval over context documents |
| Every number remains reproducible | deterministic Python calculations |
| A controller remains accountable | human-in-the-loop approval state machine |
| Evidence | retrieved snippets with source and relevance score |

## State vocabularies (fixed)

**Commentary / approval workflow (code):** `DRAFT → AWAITING_REVIEW → APPROVED | REVISION_REQUESTED`
**UI labels for the same states:** AI DRAFT · CONTROLLER REVIEW · APPROVED · REVISION REQUESTED
**Decision issue lifecycle:** `OPEN · UNDER REVIEW · APPROVED · ACTION REQUIRED · CLOSED` — with optional OWNER, NEXT STEP, DUE DATE.
**Materiality / severity:** HIGH · MEDIUM · LOW.
**Commentary confidence:** HIGH · MEDIUM · LOW (exposed, never hidden).

## Labeling rules

- Never label AI output **"AI Decision"**. Use: **Suggested follow-up** · **Decision option** · **Question to investigate**.
- Always mark generated interpretation: "AI-generated interpretation · Controller approval required."
- "Suggested follow-up" is not an autonomous decision — a human owns every decision and next step.

## Words to use sparingly or avoid

Avoid excessive use of: **agentic · autonomous · multi-agent · copilot · prompt engineering · LLM-first**.
- "Governed copilot" is acceptable only when quoting/echoing Architecture Note #001; the V1 product UI avoids "copilot".
- Technical AI vocabulary (RAG, embeddings, vectors, prompts, tokens) only in technical documentation and the engineering view — never in the default executive experience.
- BENACTA understands hype; it uses technologies only when architecture and business value justify them.

## Naming constants

- Repository: `benacta-decision-intelligence-blueprint`
- Repo description: "A reference implementation for governed AI-native decision systems — where code computes, AI explains, and humans decide."
- PDF: `BENACTA_Controlled_Intelligence_Blueprint.pdf` (HTML source: `controlled-intelligence-blueprint.html`)
- Use case name: **Monthly Performance Review**
- View A: **Executive Decision Cockpit** (default) · View B: **Architecture / Engineering**
- The philosophically load-bearing test: `test_financial_truth_is_independent_from_llm`
- Demo flag: `DEMO_MODE=true`
