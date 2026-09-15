# BENACTA Decision System Lab: progress

Status vocabulary: `IMPLEMENTED` (code exists) · `TESTED_LOCAL` (automated tests pass locally) ·
`VERIFIED_ODOO_SANDBOX` (proven by a real write run against the Odoo sandbox) · `VERIFIED_ODOO_READ` (proven by a
real read-only run against the connected Odoo) · `NOT_VERIFIED` · `BLOCKED`.
A fixture test never proves an Odoo integration. Plan: `docs/implementation_plan.md`.

## Milestone 1: BENACTA Margin Control, margin truth and deterministic exceptions (delivered on fixtures)

Refocus of 2026-09-15: the active product is BENACTA Margin Control (`docs/repository_audit.md`,
`docs/product_backlog.md`). Every figure below comes from the synthetic dataset `demo_v2` (`demo_v1` trading company
plus the project extension); no Odoo write happened.

### Evidence (2026-09-15)

| Command | Result |
|---|---|
| `uv run pytest -q` in `apps/api` | 222 passed, 7 skipped (live tests are opt-in) |
| `uv run pytest -q tests/integration/test_margin_engine_oracle.py` | 25 passed: every oracle case (6 golden, 12 negative controls), totals 2 900 / 1 200 / 4 100 EUR, 0 exception on background orders, 11 cases and no duplicate on replay, a confirmed 150 EUR case below materiality counted but not queued, audit valid, a corrected source closes the case with the reason |
| `uv run pytest -q tests/unit/test_margin_rules.py` | 30 passed: every outcome of every rule on hand-built facts, the four baseline levels, currency and unit conversions, the comparability guard |
| `uv run pytest -q tests/integration/test_margin_service_api.py` | 5 passed: overview, queue ranking, case drill-down and lineage, reconciliation report fields, API equals service |
| `ruff check app tests migrations` | clean |
| `benacta seed-fixtures` | 12 months `RECONCILED` on `REVENUE_POSTED`, `COGS_POSTED` and `INVOICE_HEADER_LINES`; margin basis `RECONCILED_COGS`; terms loaded (24 segments, 5 policies, 1 derogation, 7 freight contracts, 1 contract price, 17 cost references); 948 evaluations: 8 `CONFIRMED_LEAKAGE`, 2 `DATA_QUALITY_ISSUE`, 18 `INSUFFICIENT_EVIDENCE` (2 for review), 2 `LEGITIMATE_EXCEPTION`, 5 `EXPLAINED_VARIANCE`, 707 `COMPLIANT`, 206 `NOT_APPLICABLE`; 11 cases |
| `benacta seed-fixtures` replayed | 0 new record versions, 0 new cases, 11 updated |
| `BENACTA_MODE=fixture benacta margin-overview --period 2026-07` | revenue 1 012 008.20, COGS 168 217.00, gross margin 843 791.20 (goods 117 191.20, goods GM 41.06 % against 41.01 % in June, within threshold); detected leakage 3 050.00, recoverable from customers 2 250.00, realised recovery `NOT_MEASURED` |
| `BENACTA_MODE=fixture benacta margin-exceptions` | 11 cases: DISC-001 1 000.00, COST-001 800.00, PRICE-001 600.00, NEG-12 500.00 and 400.00, PLIST-001 400.00, FREIGHT-001 250.00 (all `CONFIRMED_LEAKAGE`, confidence `HIGH`), then NEG-11, NEG-09, NEG-08, NEG-10 for human review; NEG-01 and NEG-02 (legitimate) absent; FREIGHT-002 (150.00, below materiality) counted in freight leakage, not queued |
| `BENACTA_MODE=fixture benacta margin-case MC-000001` | rule `DISCOUNT_CAP` v1 with formula, expected 9 500.00 against actual 8 500.00, policy `POL-DISC-STANDARD` cited, 1 order line, 1 invoice line, 1 delivery, 1 cost allocation, 1 source record version, three reconciliation checks `RECONCILED`, suggested follow-up `PENDING_REVIEW` |
| `BENACTA_MODE=fixture benacta reconciliation-report --period 2026-07` | three checks `RECONCILED`, tolerance 0.01, source timestamp, ingestion timestamp, transformation `marts.2026.09.2` |
| `BENACTA_MODE=fixture benacta verify-audit --export` | chain `VALID`, 269 events |
| V1 suite at repository root (`pytest tests/`) | 155 passed (unchanged) |

### Items

| Item | Status | Where |
|---|---|---|
| Repository audit, focused backlog, use-case portfolio classification (7 `ACTIVE`, 13 `ENGINE_FAMILY`, 20 `ROADMAP`, 10 `OPPORTUNITY`) | IMPLEMENTED | `docs/repository_audit.md`, `docs/product_backlog.md`, `data/catalog/use_cases_v2.yml` |
| Governed commercial terms with provenance, business keys, fixture and register loaders | TESTED_LOCAL | migration `0004_margin_control`, `app/margin/reference.py`, `data/policies/` |
| Price list ingestion and dimensions; partner reference and assigned price list | TESTED_LOCAL | `app/ingestion/runner.py`, `app/marts/build.py` |
| Price baseline hierarchy (contract, customer price list, product list price, historical comparable with dispersion guard, unavailable) | TESTED_LOCAL | `app/margin/baseline.py` |
| Rules `DISCOUNT_CAP`, `PRICE_BELOW_BASELINE`, `FREIGHT_REBILL`, `COST_REFERENCE_VARIANCE`, `INVOICE_WITHOUT_SALE_LINK` with versions, formulas, evidence bundles, six decision classes, severity, confidence, controllability, materiality | TESTED_LOCAL | `app/margin/rules.py`, `docs/margin_rule_catalogue.md` |
| Engine: evaluations per snapshot, stable cases across snapshots, `NO_LONGER_RAISED` with reason, gross margin per period with basis and leakage | TESTED_LOCAL | `app/margin/engine.py` |
| Margin KPIs and contracts (revenue, COGS, gross margin, percentage, four leakage types, addressable, recoverable, approved and realised recovery) | TESTED_LOCAL (structure) | `app/margin/kpis.py`, `semantic/metrics.yml` |
| Reconciliation report with tolerance, timestamps, transformation version, invoice header check | TESTED_LOCAL | `app/marts/reconcile.py`, `docs/reconciliation_specification.md` |
| Read side: overview with deterioration signal and bridge, ranked queue, case with drill-down and lineage; CLI and API | TESTED_LOCAL | `app/margin/service.py`, `app/ops/margin_ops.py`, `app/main.py` |
| Ground-truth catalogue: 15 of 18 scenarios covered by the oracle (contract price, price-list mismatch and partial freight added), the rest scheduled | TESTED_LOCAL | `docs/ground_truth_catalogue.md`, `data/golden/oracle_v1.yml` (v2) |
| Demonstration script and local setup | IMPLEMENTED | `docs/margin_control_demo.md` |
| Rules against the connected Odoo | NOT_VERIFIED | order lines of the connected instance carry no invoice links and no COGS; the engine would report untraceable revenue there; the sandbox seed has not run |
| Decisions, actions, impact | not started | milestone 2 |
| AI investigation, cockpit, demonstration profile, Odoo seed run | not started | milestone 3 |

### Findings from this milestone

- Lump-sum project contract lines have no meaningful unit price: the historical baseline flagged nine of them as
  probable leakage. The comparable baseline now requires a dispersion (median absolute deviation over median) at or
  below 15 %; those lines report "no defensible baseline" and raise no case.
- Blending service revenue without posted cost into the gross-margin percentage made the percentage follow the sales
  mix (84 % in July, 42 % in August). The deterioration signal now reads the goods percentage; service revenue is
  shown separately with its reason.
- A case that stops being raised because a rule or a threshold changed must not read as "corrected at the source":
  the closing status records the new classification, the rule version and the threshold set.

### Known limits

- Thresholds (`data/policies/margin_thresholds.yml`) are demonstration settings, not financial standards.
- Currency effects are not isolated as a bridge line yet; foreign-currency lines are compared at the order-date rate.
- Freight recharge is assessed per order; consolidated shipments are not modelled.
- Cost variance needs FIFO attribution to receipts and a frozen reference; other costing methods stay undetermined.
- Every margin figure of this milestone is `TESTED_LOCAL`. The Odoo integration remains `VERIFIED_ODOO_READ` for
  revenue reconciliation only.

## Sprint A (requirements and mapping) and the first C/D slice (project controlling), delivered before the refocus

Every figure below comes from the synthetic dataset `demo_v2` (fictional company, people and contracts).

### Evidence (2026-09-14)

| Command | Result |
|---|---|
| `uv run pytest -q` in `apps/api` | 152 passed, 7 skipped (live tests are opt-in) |
| `uv run pytest -q tests/integration/test_project_controlling.py` | 35 passed: every oracle metric of PRJ-01 to PRJ-09 at two cutoffs, erosion decomposition, locks, maker-checker, import rejection, PSR history, investigation, cross-view parity |
| `BENACTA_LIVE_ODOO=1 uv run pytest -q -m odoo_live` | 7 passed against the connected instance (read-only), now over 36 models |
| `ruff check app tests migrations` | clean |
| `benacta seed-fixtures` | 10 401 source records, 20 projects, 7 344 time entries, 62 plan versions; revenue and COGS `RECONCILED` for 12 months (`FIXTURE_CONTROL_TOTAL`) |
| `benacta seed-fixtures` replayed twice with `PYTHONHASHSEED` 1 and 2 | 0 new versions, 62 plan versions skipped |
| `BENACTA_MODE=fixture benacta portfolio` | 15 delivery projects; revenue at completion 11 187 000, EAC 8 995 500, margin 2 191 500 (19.59 %), overdue 732 000 incl. taxes; PRJ-08 excluded from totals (EAC unknown) |
| `BENACTA_MODE=fixture benacta psr --project PRJ-02` | draft PSR matching the oracle: EAC 1 764 000, margin 236 000, declared progress 42 % next to cost consumption 47.62 % |
| `BENACTA_MODE=fixture benacta investigate --project PRJ-02` | `COMPLETED` "sans LLM": margin −164 000 = labour +124 000 (EN +1 250 h × 80, LE +200 h × 120) + subcontract +40 000, residual 0; one supported hypothesis, four limits, two proposals `PENDING_REVIEW` |
| `BENACTA_MODE=fixture benacta investigate --project PRJ-08` | `ABSTAINED` (forecast missing) |
| V1 suite at repository root | 155 passed (unchanged) |

### Items

| Item | Status | Where |
|---|---|---|
| ADR: Odoo, analytical foundation, planning, spreadsheet entry, Command Center | IMPLEMENTED | `docs/adr/0004-operational-analytical-planning-separation.md` |
| Catalogue of 50 use cases with Build / Extend / Conference / Hold, none Live | TESTED_LOCAL | `data/catalog/use_cases_v2.yml` |
| Synthetic project company: 15 delivery and 5 internal projects, 40 people, 12 months of actuals, 6 months of forecast, 3 forecast versions | TESTED_LOCAL | `app/fixtures/projects_dataset.py`, `docs/project_controlling_model.md` |
| Hand-written projects oracle, unreachable from application code | TESTED_LOCAL | `data/golden/projects_oracle_v1.yml` |
| Ingestion of 14 more Odoo models (projects, milestones, HR, skills, analytic lines, payments) | TESTED_LOCAL, VERIFIED_ODOO_READ | `app/ingestion/runner.py` (`PROJECT_MODELS`) |
| Project marts: project, work package, milestone, employee, time, commitments, vendor bills, receivables, payments, change orders | TESTED_LOCAL | `migrations/versions/0003_project_marts.py`, `app/marts/project_build.py` |
| Time entries per project read from Odoo (`hr_timesheet`) | NOT_VERIFIED | module not installed on the connected instance; fixtures use its record shape |
| Planning schema: versions, lines, assumptions, assignments; DRAFT → SUBMITTED → APPROVED → LOCKED; database triggers refuse edits of frozen versions | TESTED_LOCAL | `migrations/versions/0002_planning_and_reports.py`, `app/planning/service.py` |
| CSV import: staging, validation of every row, error report, draft version; an empty cell stays null | TESTED_LOCAL | `app/planning/importer.py`, `data/templates/plan_lines_template.csv` |
| Canonical conventions: EAC, ETC including open commitments, cost variance, revenue at completion, margin, ageing buckets, UNKNOWN instead of zero | TESTED_LOCAL | `app/controlling/metrics.py`, `semantic/metrics.yml` (26 contracts, none certified) |
| Margin erosion detection and deterministic decomposition | TESTED_LOCAL | `app/controlling/erosion.py` |
| Versioned PSR, immutable once published, maker-checker, recognised revenue `UNAVAILABLE` | TESTED_LOCAL | `app/controlling/psr.py` |
| Investigation "Pourquoi la marge à terminaison de ce projet baisse-t-elle ?" with abstention and proposals pending review | TESTED_LOCAL | `app/controlling/investigation.py` |
| Portfolio overview reading the same metric service as the PSR | TESTED_LOCAL | `app/controlling/portfolio.py` |
| Ontology extension: project entities, observed and hypothetical relationships, bounded paths | TESTED_LOCAL (structure only) | `ontology/entities.yml`, `ontology/relationships.yml` |
| CFO and project controller demo script | IMPLEMENTED | `docs/demo_project_controlling.md` |
| Project company in Odoo (sprint B) | BLOCKED | sandbox company, attested backup, `hr_timesheet` installation |
| UI: Portfolio, Project Workspace, Resources Monitoring, Flash Report, Treasury, Planning | NOT_VERIFIED | not started; CLI and JSON exports only, so no screenshots yet |
| Resources Monitoring and Flash Report metrics (sprint E) | NOT_VERIFIED | not started |
| LLM drafting of commentary | NOT_VERIFIED | deterministic mode only, labelled "sans LLM" |

### Findings from this sprint

- The live run found personal to-dos without a project in Odoo 19; the fixtures had none. Work packages now skip
  them, and the synthetic dataset carries one.
- The fixture generator iterated a Python set, so two processes produced different record ids and a replay created
  new versions. Fixed, with a test running the generator under three hash seeds.
- Odoo 19 has no project budget per work package or period (`account.report.budget` is per account). Plan versions
  therefore live in BENACTA; Odoo keeps contracts, orders, time, purchases, invoices and payments (ADR-0004).
- Physical progress, recognised revenue, billed amount and cash stay four separate measures. No revenue recognition
  policy exists yet, so recognised revenue is reported as unavailable rather than derived from billing.

### Known limits

- Erosion thresholds (50 000 EUR or 2 points) and the budget overrun threshold (25 000 EUR) are demonstration
  settings, not financial standards.
- Labour cost at completion uses one agreed rate per role; individual rates and rate changes are not modelled.
- The investigation traverses relational marts; the graph projection is not deployed and no document corpus is
  indexed, so the forecast note is the only qualitative evidence.
- Controlling commands (`portfolio`, `psr`, `investigate`) need `BENACTA_MODE=fixture` or `ANALYTICS_DATABASE_URL`.

### Blockers and decisions

| Item | Blocks | Minimal parameter or decision |
|---|---|---|
| `hr_timesheet` not installed | project time from Odoo, sprint B | authorisation to install the Timesheets app (check the subscription impact first) |
| No sandbox company | seed executor, sprint B | `ODOO_SANDBOX_COMPANY`, and whether the seed may create the company |
| No attested backup | every Odoo write | `ODOO_BACKUP_ATTESTED_AT`, `ODOO_BACKUP_REFERENCE` |
| Writes disabled | every Odoo write | `ODOO_WRITES_ENABLED=true`, `ODOO_SANDBOX_ALLOWLIST=benacta.odoo.com/benacta` |
| USD inactive, no `Dozens` unit (shared settings) | NEG-07, NEG-06 and PRJ-07 in Odoo | activate USD and create the unit, or keep those cases fixture-only |
| No managed analytics database | connected-mode runs outside tests | `ANALYTICS_DATABASE_URL` (database `benacta_analytics`, pgvector) |
| No Neo4j | graph projection | `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` |
| No LLM key | drafted commentary | `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` |

## S1 Step 2 Data Feeding, golden cases, reconciled foundation (delivered)

### Evidence (2026-09-14)

| Command | Result |
|---|---|
| `uv run pytest -q` in `apps/api` | 82 passed, 7 skipped (live tests are opt-in) |
| `BENACTA_LIVE_ODOO=1 uv run pytest -q -m odoo_live` | 7 passed against the connected instance (read-only) |
| `ruff check` and `ruff format --check` on `app`, `tests`, `migrations` | clean |
| `benacta seed-fixtures` (first run) | 1 815 source records ingested, marts built, revenue and COGS `RECONCILED` for 3 months (`FIXTURE_CONTROL_TOTAL`), margin basis `RECONCILED_COGS` |
| `benacta seed-fixtures` (replay) | 0 new versions, reconciliation unchanged |
| `benacta verify-audit --export` | chain `VALID`, 42 events, JSONL exported to `.benacta/exports/` |
| Live read ingestion of the connected Odoo into an ephemeral database | 1 515 records in 9.8 s; replay 0 new versions in 7.0 s; revenue `RECONCILED` for 20 months against `SERVER_AGGREGATE`; COGS `UNAVAILABLE` for the same 20 months; margin basis `MANAGEMENT_PROXY`; 64 of 64 invoice lines have no order line link |
| `benacta seed-odoo-dry-run` | plan of 9 operations, prerequisites and risks written to `.benacta/seed_plans/`; nothing written to Odoo |
| `benacta seed-odoo` | refused by the write guard (5 of 6 checks failing); nothing written |
| V1 suite at repository root | 155 passed (unchanged) |

Embedded PostgreSQL validated on the development VM: PostgreSQL 16.2 with pgvector 0.6.2 through `pgserver` 0.1.4.
Versions are pinned in `apps/api/uv.lock`.

### Items

| Item | Status | Where |
|---|---|---|
| Schemas raw, staging, marts, semantic, decision, audit; migration from an empty database, idempotent | TESTED_LOCAL | `apps/api/migrations/versions/0001_foundation.py` |
| Live analytics target check (database name, no Odoo tables, pgvector available) | TESTED_LOCAL | `app/db/engine.py` |
| Append-only hash-chained audit, trigger refusing update, delete and truncate, tamper detection, JSONL export | TESTED_LOCAL | `app/audit/log.py` |
| Deterministic 90-day dataset: 120 orders, 21 customers, 5 suppliers, 17 storable products, configurable anchor | TESTED_LOCAL | `app/fixtures/demo_dataset.py` |
| Golden cases DISC-001, FREIGHT-001, COST-001 and 12 negative controls in the data | TESTED_LOCAL | same |
| Hand-written versioned oracle, unreachable from application code (AST test) | TESTED_LOCAL | `data/golden/oracle_v1.yml` |
| Idempotent ingestion: hash versions, (write_date, id) watermark with overlap, deletions from id lists, per-model commit and resume | TESTED_LOCAL, VERIFIED_ODOO_READ | `app/ingestion/` |
| Dimensions, separated facts, sale-invoice bridge without fan-out, FIFO cost attribution with UNDETERMINED | TESTED_LOCAL | `app/marts/build.py` |
| Oracle facts realised by marts (all 3 goldens and the negative controls that have data facts) | TESTED_LOCAL | `tests/integration/test_marts_oracle.py` |
| Reconciliation with explicit status and independence | TESTED_LOCAL, VERIFIED_ODOO_READ | `app/marts/reconcile.py` |
| Seed plan (dry run) with prerequisites and external identifier registry check | TESTED_LOCAL, VERIFIED_ODOO_READ | `app/ops/seed_odoo.py` |
| Seed executor writing the sandbox company | BLOCKED | needs sandbox company, attested backup and the decisions below |
| Golden cases in Odoo | NOT_VERIFIED | depends on the executor |
| Exposure amounts 1 000 / 250 / 800 EUR computed by the engine | NOT_VERIFIED | S4 rule engine |
| Data dictionary | IMPLEMENTED | `docs/data_dictionary.md` |

### Findings from S1

- The connected Odoo data cannot support order-level analysis: none of its 64 posted invoice product lines is linked
  to an order line. Order-to-invoice exceptions will only be demonstrable on the seeded sandbox company.
- Live revenue reconciles to the server aggregates for every month; margin on that data remains a management proxy.
- A resource leak in the test harness (one embedded server left per test session) exhausted the VM page file. Fixed:
  test servers now stop and delete their data at session end; `benacta local-db-stop` stops the development server.

## S0 discovery, architecture, contracts, connection safety (delivered)

Odoo API `VERIFIED_ODOO_READ` (saas~19.4+e, JSON-2); discovery report `docs/odoo_discovery.md`; guards, connector
and doctor tested; ADR-0001 to ADR-0003.

## Backlog by sprint

| Sprint | State |
|---|---|
| S0 | Delivered |
| S1 | Delivered except the Odoo seed executor (blocked on sandbox prerequisites) |
| A Requirements and mapping | Delivered |
| B Project company in Odoo | Blocked (sandbox company, backup, `hr_timesheet`) |
| C Budget, forecast and EPM metrics | First slice delivered on fixtures |
| D PSR and investigation | First slice delivered on fixtures, no UI |
| E Resources Monitoring and Flash Report | Next. Needs no external access. |
| F Overdues, cross-view consistency, integrated demo | Not started (overdue metrics and a parity test exist) |
| S2 to S7 (finance journey) | S2 partly covered by `semantic/metrics.yml`; S3 to S7 not started |
