# Repository audit: from Decision System Lab to BENACTA Margin Control

Date: 2026-09-15. Scope: the whole repository, read before any change. Status words follow `docs/progress.md`:
`IMPLEMENTED`, `TESTED_LOCAL`, `VERIFIED_ODOO_READ`, `VERIFIED_ODOO_SANDBOX`, `NOT_VERIFIED`, `BLOCKED`.
A fixture test never proves an Odoo integration.

## 1. Current state

Two applications share the repository.

| Part | What it is | Evidence on 2026-09-15 |
|---|---|---|
| V1 (`app.py`, `src/`, `tests/`, `data/*.csv`) | Streamlit Monthly Performance Review on CSV data, public demo, LLM optional behind `DemoProvider` / `AnthropicProvider` | `pytest tests/`: 155 passed |
| V2 (`apps/api`, `data/{mappings,golden,discovery,catalog}`, `semantic/`, `ontology/`, `docs/adr`) | FastAPI + PostgreSQL "Decision System Lab" on Odoo 19 (JSON-2): ingestion, marts, reconciliation, project controlling engine, CLI | `uv run pytest -q`: 161 passed, 7 skipped (live tests opt-in); `ruff check`: clean |

### V2 components and their real status

| Component | Where | Status | Notes |
|---|---|---|---|
| Odoo discovery (read-only, regenerated report) | `app/ops/discover_odoo.py`, `docs/odoo_discovery.md` | VERIFIED_ODOO_READ | saas~19.4+e, one company, JSON-2 |
| Odoo read connector with allowlist, stable pagination | `app/connectors/odoo.py` | VERIFIED_ODOO_READ | 36 models read live |
| Odoo guarded writer, configuration command | `app/connectors/odoo.py`, `app/ops/odoo_configure.py` | VERIFIED_ODOO_SANDBOX (configuration only) | live instance shows `hr_timesheet` installed, USD active, 9 `x_benacta_*` fields |
| Project company seed executor | `app/ops/seed_projects.py` | NOT_VERIFIED | never run with `--confirm`: 0 `benacta_demo` external ids on the instance; guard blocks on `ODOO_WRITES_ENABLED` and backup attestation |
| Trading company seed (S1 golden cases) | `app/ops/seed_odoo.py` | dry-run only | plans 9 operations, no executor |
| Idempotent versioned ingestion (hash, watermark, deletions, resume) | `app/ingestion/` | TESTED_LOCAL, VERIFIED_ODOO_READ | 31 models; `product.pricelist(.item)` mapped but not ingested |
| Canonical marts: dimensions, order lines, invoice lines, posted COGS, stock moves, FIFO cost attribution, sale-invoice bridge without fan-out | `app/marts/build.py`, migration 0001 | TESTED_LOCAL | live data: 64 of 64 invoice lines have no order link, no posted COGS |
| Reconciliation with status and independence | `app/marts/reconcile.py` | TESTED_LOCAL, VERIFIED_ODOO_READ | revenue `RECONCILED` live for 20 months against server aggregates; COGS `UNAVAILABLE` live; no source or ingestion timestamps, no transformation version in the report |
| Append-only hash-chained audit with trigger and JSONL export | `app/audit/log.py` | TESTED_LOCAL | tamper-evident, not immutable (documented) |
| Deterministic fixture `demo_v1` (90 days, 21 customers, 5 suppliers, 120 orders) with 3 golden cases and 12 negative controls | `app/fixtures/demo_dataset.py` | TESTED_LOCAL | business terms (discount policies, derogations, freight contracts, cost references) exist only in memory; never persisted or governed |
| Hand-written oracle, unreachable from application code (AST test) | `data/golden/oracle_v1.yml` | TESTED_LOCAL | expected exposures 1 000 / 250 / 800 EUR not yet computed by any engine |
| Project controlling extension `demo_v2`: 20 projects, 40 people, timesheets, plans, PSR, erosion decomposition, deterministic investigation, portfolio | `app/fixtures/projects_dataset.py`, `app/controlling/`, `app/planning/`, migrations 0002 and 0003 | TESTED_LOCAL | a second, parallel product track (sprints A to F) |
| Semantic layer | `semantic/metrics.yml` | TESTED_LOCAL (structure) | 26 project controlling contracts, none certified; no margin contracts |
| Ontology | `ontology/*.yml` | TESTED_LOCAL (structure only) | no projection deployed, no Neo4j |
| Margin exception engine, KPI service | none | not started | plan sprint S4 |
| AI investigation on margin, RAG | none | not started | V2 has no LLM provider interface; V1 has one |
| Decision workflow (approve, reject, assign, defer), controlled action, impact tracking | `decision.recommendation` table only (`PENDING_REVIEW`) | not started | no transitions, no action executor, no `mail.activity` write |
| Frontend for V2 | none | not started | CLI and JSON exports only |
| API | `app/main.py` | health and readiness only | |
| Security and evaluation tests (prompt injection, RAG authorisation, LLM schema) | none | not started | |

### Real, mocked, incomplete, duplicated or disconnected

- Real and verified: Odoo read path, discovery, live revenue reconciliation, instance configuration writes.
- Real but fixture-only: marts, cost attribution, project controlling, planning workflow.
- Incomplete: project seed executor (written, never executed), trading seed (planner only), the `mail.activity`
  action named in the mapping but never written.
- Disconnected: fixture business terms (in memory only); `product.pricelist` mapping without ingestion; the 50 use
  cases drive two tracks at once.
- Duplicated: none in code. Two vocabularies coexist for approval states (V1 and V2), by decision (ADR-0001).

## 2. Gaps against the Margin Control specification

| Specification | Gap |
|---|---|
| Governed reference data and baseline hierarchy for expected prices and costs | no persisted policies, contract prices, price lists or cost references; no hierarchy implemented |
| Deterministic decision engine (KPIs, rules, materiality, cause classification, severity, confidence, controllability, evidence bundle, rule versions) | absent |
| Six outcome classes (confirmed, probable, explained, legitimate, data quality, insufficient evidence) | absent |
| 18 ground-truth scenarios | 3 golden cases and 12 negative controls cover about 11 of them; price-list, contract price, partial freight, mix, volume, timing, wrong analytic account and management-approved exception are missing |
| Reconciliation report per closed period with tolerance, timestamps and transformation version | partial: status, independence, difference only |
| AI-assisted investigation on margin, governed documents, citations, abstention | absent in V2 |
| Decision workflow, controlled action, impact tracking, audit view | absent |
| CFO views (overview, queue, case, decision workspace, impact, audit) | absent |
| Two seed profiles (development, full demonstration) and a realistic 3-year industrial company in Odoo | development profile exists (`demo_v1` + `demo_v2`); no demonstration profile; nothing seeded in Odoo |
| Security tests, evaluation plan, production-readiness gap assessment | absent |
| Use cases classified as opportunities, engine families or roadmap | catalogue has Build / Extend / Conference / Hold, all treated as backlog |

## 3. Components to preserve

Everything verified or tested is kept and reused:

- Odoo connector, guards, writer, configuration command, discovery.
- Ingestion, staging function, marts, cost attribution, bridge, reconciliation, audit chain.
- Fixture `demo_v1` and its oracle, extended rather than replaced: they already isolate every scenario and are the
  ground truth of milestone 1.
- Embedded PostgreSQL harness, test isolation, oracle unreachability test.
- The project controlling engine and planning schema: kept intact as an engine family (metric service with
  `UNKNOWN`, maker-checker, immutable published reports, investigation with abstention). They are not driven by the
  active backlog.
- V1 unchanged, including its LLM provider pattern (payload builder, invented-number check, degradation) which
  milestone 3 reuses in V2.
- Doctrine files, brand charter, editorial rules.

## 4. Components to simplify or postpone

| Component | Decision |
|---|---|
| Project controlling track (sprints B to F: Odoo project seed, resources, flash report, treasury, planning UI) | postponed; engine kept, no new work until Margin Control ships |
| Neo4j projection | postponed; relational traversal is enough for the pilot |
| Next.js web application | replaced for the pilot by a Streamlit Margin Control cockpit on the existing stack, reading the same service layer as the API |
| Trading seed planner (`seed_odoo.py`) | folded into one seed executor for the trading company in milestone 3 |
| 50 use cases | kept as the opportunity portfolio; reclassified (`portfolio` field), not a backlog |

## 5. The next three milestones

| Milestone | Outcome | Evidence to close |
|---|---|---|
| M1 Margin truth and deterministic exceptions | governed reference data with the baseline hierarchy; margin KPI service; rule engine with materiality, classification, severity, confidence, controllability and evidence bundles; enriched reconciliation report; CLI and API read routes | oracle exposures 1 000 / 250 / 800 EUR computed by the engine; no exception on background orders; every negative control returns its expected outcome; reconciliation report carries tolerance, timestamps and transformation version |
| M2 Decision, action, impact | exception cases with owner and lifecycle; decisions approve, reject, request evidence, assign, defer with reasons; one controlled action (review activity in Odoo) idempotent and guarded; impact tracking estimated versus realised; audit export | state machine tests; duplicate execution refused; stale decision refused; unapproved execution refused; realised recovery measured only from reconciled documents |
| M3 Investigation, cockpit, demonstration data | LLM investigation with schema validation, citations to metrics, transactions, rules and governed documents, abstention and deterministic fallback; Streamlit CFO cockpit with the six views; demonstration seed profile (3 years, seasonality, cost drift, FX) with 18 ground-truth scenarios; Odoo seed executor for the trading company; evaluation plan; production-readiness gaps | CFO demo script runs end to end without an API key; injection document refused; live Odoo run labelled `VERIFIED_ODOO_SANDBOX` only after a real execution |

Milestone 1 starts now on the existing reconciled foundation. Nothing in it depends on writing to Odoo.
