# BENACTA Margin Control: product backlog

Active product: **BENACTA Margin Control**, a Finance decision system that helps industrial Finance teams detect,
investigate, decide and act on gross-margin leakage at transaction level. Audit and rationale:
`docs/repository_audit.md`. The 50 use cases in `data/catalog/use_cases_v2.yml` are the long-term opportunity
portfolio; only the items below are being built.

The journey the backlog serves:

```text
Odoo transaction -> governed analytical data -> reconciled financial metric -> deterministic margin anomaly
-> transaction-level evidence -> AI-assisted investigation -> recommendation -> human approval or refusal
-> controlled action -> audit trail -> realised financial impact
```

## Milestone 1: margin truth and deterministic exceptions (delivered 2026-09-15)

| # | Item | Done when |
|---|---|---|
| 1.1 | Governed reference data: customer segments, discount policies, derogations, freight contracts, contract prices, cost references, loaded from the fixture terms or from the policy register `data/policies/` | tables in schema `semantic`, versioned, with owner, source and effective dates |
| 1.2 | Ingest `product.pricelist` and `product.pricelist.item`; price baseline hierarchy (contract price, customer price list, product price list, historical comparable, unavailable) | every confirmed line resolves a baseline with its level or `UNAVAILABLE` |
| 1.3 | Margin KPI service: revenue, COGS, gross margin, gross-margin percentage by period, customer, product, order; margin basis and availability | values equal the reconciled facts; unavailable when COGS is not defensible at the grain |
| 1.4 | Rule engine: `DISCOUNT_CAP`, `PRICE_BELOW_BASELINE`, `FREIGHT_REBILL`, `COST_REFERENCE_VARIANCE`, `INVOICE_WITHOUT_SALE_LINK`; materiality thresholds; six outcome classes; severity, confidence, controllability; evidence bundle; rule version and formula | oracle: DISC-001 1 000, FREIGHT-001 250, COST-001 800, NEG-12 500 and 400, totals 1 750 / 1 200 / 2 950; 0 exception on background orders |
| 1.5 | Exception cases with stable identity across snapshots, first detection date and age | replaying the pipeline creates no duplicate case |
| 1.6 | Reconciliation report per closed period: source totals, analytical totals, difference, tolerance, status, explanation, source timestamp, ingestion timestamp, transformation version; invoice header versus lines check | JSON export per period |
| 1.7 | CLI `margin-overview`, `margin-exceptions`, `margin-case`, `reconciliation-report`; API `/api/v1/margin/*` and `/api/v1/reconciliation` | same numbers through CLI and API for the same snapshot |
| 1.8 | Documents: rule and KPI catalogue, reconciliation specification, ground-truth catalogue mapping the 18 scenarios, metric contracts in `semantic/metrics.yml` | catalogue tests pass |

## Milestone 2: decision, action, impact (delivered on fixtures 2026-09-15; Odoo execution NOT_VERIFIED)

| # | Item | Done when |
|---|---|---|
| 2.1 | Decision workflow on a case: approve, reject, request more evidence, assign, defer; refusal reason and comments; owner and status | illegal transitions refused; stale decision refused (version check) |
| 2.2 | Recommendation per exception (deterministic template in M2, AI draft in M3) with expected impact | every recommendation can be approved or refused |
| 2.3 | Controlled action: create a review activity (`mail.activity`) on the Odoo document, sandbox only, through the write guard and writer, idempotent by external identifier, logged | duplicate execution refused; unapproved execution refused |
| 2.4 | Impact tracking: committed, executed, estimated recovery, realised recovery from later reconciled documents, variance | realised recovery measured only from posted documents, otherwise not measured |
| 2.5 | Audit view and export: lineage, rule version, decisions, actions, timestamps, identity | JSONL export verified |

## Milestone 3: investigation, cockpit, demonstration data

| # | Item | Done when |
|---|---|---|
| 3.1 | LLM provider interface in V2: typed payload of computed facts, schema-validated output, invented-number and citation checks, deterministic fallback labelled | delivered 2026-09-15 (`docs/progress.md`, milestone 3a); real model run NOT_VERIFIED |
| 3.2 | Governed document corpus (source, owner, effective date, authorisation, version) with transparent retrieval and citations; injection document refused | delivered 2026-09-15 |
| 3.3 | Streamlit cockpit: executive overview, exception queue, exception case, decision workspace, impact tracking, audit view | delivered 2026-09-15 (`benacta demo`, headless smoke test) |
| 3.4 | Demonstration seed profile: about 3 fiscal years, 500 customers, 100 suppliers, 200 products, seasonality, cost drift, FX, late payments, refunds, ground-truth scenarios in a separate manifest | delivered 2026-09-15 (`benacta seed-fixtures --profile full`, opt-in tests) |
| 3.5 | Odoo seed executor for the trading company (development profile first), replaying safely | `VERIFIED_ODOO_SANDBOX` only after a real run |
| 3.6 | Evaluation plan, security and permissions notes, production-readiness gap assessment, seed specification, architecture, README setup and demo instructions | delivered 2026-09-15 (`docs/evaluation_plan.md`, `docs/security_notes.md`, `docs/production_readiness.md`, `docs/seed_data_specification.md`, `docs/margin_control_architecture.md`) |

## Parked (engine families and opportunities)

- Project controlling track (sprints B to F): engine kept, not scheduled.
- Neo4j projection, Next.js web application: not scheduled.
- Every use case whose `portfolio` is `ROADMAP` or `OPPORTUNITY` in the catalogue.
