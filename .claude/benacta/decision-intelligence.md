# BENACTA — Decision Intelligence Philosophy

> Binding doctrine. This is the conceptual foundation of BENACTA. Consult before any architectural design or narrative decision.

## The core problem

The question BENACTA answers is **not**:

> "How do we add an LLM to enterprise data?"

It is:

> **"How do we engineer the path from enterprise truth to business decision and action?"**

## The canonical chain

```text
DATA → BUSINESS OBJECTS → TRUTH → CONTEXT → INTERPRETATION → DECISION → ACTION → OUTCOME
```

Expanded system view:

```text
DATA
↓ BUSINESS MEANING
↓ RULES
↓ ANALYSIS
↓ CONTEXT
↓ AI INTERPRETATION
↓ DECISION
↓ WORKFLOW
↓ ACTION
↓ FEEDBACK
```

Long-term loop: **DATA → DECISION → ACTION → OUTCOME → LEARNING.**

## Beyond dashboards

```text
REPORTING            "What happened?"
↓ ANALYTICS          "Why?"
↓ PREDICTION         "What may happen?"
↓ DECISION           "What requires a decision?"
  INTELLIGENCE
↓ ACTION             "What do we do next?"
```

A Decision Intelligence System goes beyond dashboards: insights connect to tasks, approvals, workflows, notifications, investigations, scenario review and actions. **Insight without action is incomplete.**

## Layer responsibilities

- **Code** — facts, metrics, controls, rules. Deterministic, reproducible, tested.
- **AI** — retrieve, summarize, explain, compare, identify context, draft narratives, surface questions and options. AI does **not** own enterprise truth.
- **Humans** — judgment, approval, responsibility, escalation, accountability.

## Long-term direction — a reusable Decision Intelligence layer

- **CONNECT** — ERP, EPM, CRM, data platforms, documents, APIs
- **MODEL** — business objects, relationships, metrics, rules, semantic definitions
- **UNDERSTAND** — events, exceptions, variances, drivers, scenarios
- **AUGMENT** — retrieval, AI interpretation, simulation, decision support
- **ACT** — approvals, tasks, workflows, operational actions
- **GOVERN** — permissions, lineage, auditability, human accountability
- **LEARN** — decision history, outcomes, feedback

The architecture may take inspiration from enterprise decision/data platforms such as Foundry/AIP, but BENACTA develops its **own focused, pragmatic and composable architecture** (boundaries in `architecture-principles.md`).

Strategy:

> **START WITH HIGH-VALUE DECISION WORKFLOWS.**
> **PROVE VALUE.**
> **BUILD REUSABLE COMPONENTS.**
> **EXPAND THE DECISION GRAPH OVER TIME.**

## The closing idea every deliverable must communicate

> **ENTERPRISE AI SHOULD NOT REPLACE THE SYSTEM OF TRUTH.**
> **IT SHOULD TURN GOVERNED TRUTH INTO BETTER DECISIONS AND ACTIONS.**
