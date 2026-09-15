# BENACTA Decision System Lab: implementation plan

Scope: V2 of this repository. The V1 Monthly Performance Review blueprint (`app.py`, `src/`, `tests/`,
`docs/implementation-plan.md`) stays intact and keeps its public demo. Status of every item lives in
`docs/progress.md`. Decisions are recorded in `docs/adr/`.

## 0. Refocus (2026-09-15): BENACTA Margin Control

The active product is **BENACTA Margin Control**: detect, investigate, decide and act on gross-margin leakage at
transaction level. Audit and rationale: `docs/repository_audit.md`. Backlog: `docs/product_backlog.md`. The sprint
plan below is kept as history; the finance journey S4 to S7 is delivered as milestones M1 to M3, and the project
controlling track (sprints B to F) is parked as an engine family.

| Milestone | Scope | State |
|---|---|---|
| M1 Margin truth and deterministic exceptions | governed terms and baseline hierarchy, margin KPIs, rule engine with classification, severity, confidence, controllability and evidence, enriched reconciliation report, CLI and API | Delivered on fixtures (`docs/progress.md`) |
| M2 Decision, action, impact | case workflow, recommendations, controlled review activity in Odoo, realised recovery, audit view | Delivered on fixtures; Odoo execution NOT_VERIFIED (`docs/progress.md`) |
| M3 Investigation, cockpit, demonstration data | LLM investigation with citations and abstention, Streamlit cockpit, three-year demonstration profile with its ground-truth manifest, evaluation plan, production gaps | Delivered on fixtures except the Odoo seed executor of the trading company (blocked on owner inputs); real model run NOT_VERIFIED |

## 1. Mission

Build the **Finance Decision Command Center on Odoo**, the first demonstrator of the BENACTA Decision System Lab.
First journey: **Gross Margin Exception and Investigation**, down to the transaction line.

Doctrine: **Code computes. AI explains. Humans decide.**

```text
Odoo -> analytical foundation -> governed financial facts -> semantics and ontology -> deterministic rules
-> signals -> AI investigation -> evidence -> recommendation -> human validation -> controlled action
-> audit and evaluation
```

The chain is a user journey, not a build order: evidence exists before investigation, audit starts at ingestion,
authorisation applies everywhere.

One application, two surfaces:

| Surface | Audience | Question it answers |
|---|---|---|
| Command Center | CFO, controller | What must I examine, understand, approve and follow up? |
| Lab (private) | Architect, auditor | Why are the figures, relations, evidence and recommendations trustworthy? |

## 2. Decisions taken in S0

| # | Decision | Record |
|---|---|---|
| D1 | Build V2 inside `benacta-decision-intelligence-blueprint`, next to V1. V1 anti-patterns keep governing V1; V2 scope is set by ADR-0001. | ADR-0001 |
| D2 | Odoo integration uses the **JSON-2 API** (`/json/2/<model>/<method>`). XML-RPC is deprecated and removed in Odoo 22. | ADR-0003 |
| D3 | The connected instance is the existing Odoo Online database (saas~19.4, Enterprise). It is read, never recreated. | ADR-0003 |
| D4 | Seeds write only to a dedicated fictional company in that database, after a human-attested backup and a passing write guard. | ADR-0003 |
| D5 | Hosted services are managed cloud: PostgreSQL with pgvector for analytics, Neo4j AuraDB for the projection. No Docker on the development VM. | ADR-0002 |
| D6 | Fixture mode and CI need no external credential: an embedded PostgreSQL with pgvector (`pgserver`) backs fixture commands and integration tests. Validated in S1 on the VM. | ADR-0002 |
| D7 | Brand colours come from the locked charter (`#122B20`, `#F1E9DA`, `#BBA06B`, `#6C9BA3`), not the approximations in the brief. | brand-system.md |
| D8 | UI in French, technical identifiers and repository documentation in English, consistent with the public repository. | this plan |

## 3. Target architecture

```text
                    +---------------------------+
 Odoo Online  --->  | connectors (JSON-2 read)  |   write path: guarded writer + outbox (S6)
 (system of record) +-------------+-------------+
                                  | batches with source_id, write_date, hash, batch_id
                                  v
                    +---------------------------+
                    | analytics PostgreSQL      |  schemas: raw, staging, marts, semantic, decision, audit
                    | (BENACTA-owned, pgvector) |
                    +------+------------+-------+
                           |            |
            semantic/*.yml |            | rebuildable projection
                           v            v
                 metrics service    Neo4j (ontology/*.yml)
                           |            |
                           +-----+------+
                                 v
                  exceptions -> investigation orchestrator (typed read-only tools, RAG)
                                 v
                  recommendations -> human decisions -> action executor (allowlist) -> Odoo
                                 v
                  append-only hash-chained audit, decision memory, evaluations
                                 v
                  FastAPI /api/v1  <---  Next.js web (Command Center + Lab)
```

Stack: FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL + pgvector, Neo4j, Next.js with TypeScript.
A persistent worker processes ingestion, investigation and action jobs through a PostgreSQL outbox.
No Kubernetes, no streaming platform.

### Connections

Five connections, five separate variable groups (`apps/api/app/config.py`):

| Connection | Variables | Rule |
|---|---|---|
| Odoo direct read | `ODOO_READ_DSN` | Only where offered and authorised. Not offered by Odoo Online. |
| Odoo business API | `ODOO_URL`, `ODOO_DB`, `ODOO_USERNAME`, `ODOO_API_KEY` | Reads through `OdooReader` allowlist. Writes only through the guarded writer. |
| Analytics database | `ANALYTICS_DATABASE_URL`, `ANALYTICS_DB_EXPECTED_NAME` | Only migration target. Static and live checks refuse an Odoo database. |
| Ontology projection | `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` | Rebuildable, never financial truth. |
| Language models | `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `EMBEDDING_MODEL` | Server side only. |

### Modes

| Mode | Odoo | LLM | Writes |
|---|---|---|---|
| `fixture` | none, versioned fixtures | none, deterministic report labelled "sans LLM" | none |
| `odoo_sandbox` | connected, read | optional | only through the write guard |
| production | rejected by configuration | | |

Without Neo4j, metrics keep working and the graph view states that it is unavailable.

## 4. Odoo facts that shape the design

Full evidence: `docs/odoo_discovery.md`, regenerated by `benacta discover-odoo`.

- `stock.valuation.layer` does not exist on saas~19.4. Valuation is read from `stock.move`.
- `delivery` is not installed. FREIGHT-001 uses a rebillable freight service line plus a contract clause.
- `sale_margin` is not installed. No line-level cost snapshot exists in Odoo.
- Existing categories are standard cost with periodic valuation, no product is storable and no COGS item is posted.
  Existing data therefore supports revenue and discount analysis only; margin on it is a management proxy and
  COST-001 on it is UNDETERMINED.
- Order lines and invoice lines are linked many-to-many through `sale_order_line_invoice_rel`.
- One company, one active currency, e-invoicing modules installed but not registered.
- None of the existing posted invoice lines is linked to an order line (S1 live ingestion). Order-level
  exceptions are demonstrated on the seeded sandbox company only.

## 5. Write-back and seed safety

`odoo_write_guard` (`apps/api/app/connectors/guards.py`) evaluates every condition and reports each one:

1. `BENACTA_MODE=odoo_sandbox`
2. `ODOO_WRITES_ENABLED=true`
3. target `host/db` present in `ODOO_SANDBOX_ALLOWLIST`
4. `ODOO_SANDBOX_COMPANY` set and not a protected company
5. that company verified on the live instance
6. backup attested within `ODOO_BACKUP_MAX_AGE_DAYS` with a file reference

Odoo Online backups are downloaded by a human from the database manager; code cannot verify them, so the
attestation is recorded as a human statement, not as a verified fact.
Seeds additionally disable tracking and notifications, use non-deliverable addresses, verify that the sandbox
company is not registered for e-invoicing, touch only `BENACTA_DEMO_*` objects with stable external identifiers,
and never mutate posted invoices (a new versioned batch instead).

## 6. Sprint plan

Each sprint follows diagnosis, implementation and stress test, correction and validation. Each ships code, tests,
a reproducible demo, known limits and a content brief in `private/sprints/`.

| Sprint | Outcome | Evidence required to close |
|---|---|---|
| S0 | Discovery, architecture, contracts, connection safety | live discovery report, guard tests, connector tests |
| S1 | Step 2 Data Feeding: sandbox company, 90-day deterministic dataset, three golden cases and negative controls, analytics schemas and idempotent ingestion, reconciliation statuses | seed twice without duplicates, oracle independent from engine, `VERIFIED_ODOO_SANDBOX` only after a real run |
| S2 | Executable semantic layer (`semantic/*.yml`), metrics API used by UI and tools, Metric Contract view | same metric value through UI route and tool for the same snapshot |
| S3 | Ontology (`ontology/*.yml`), Neo4j projection, bounded traversals, permissions, subgraph view | graph and relational parity tests, cross-company traversal refused |
| S4 | Exception engine, `marts.fact_sales_margin_exceptions`, deterministic Command Center | 1 000 / 250 / 800 EUR on goldens, legitimate cases not flagged, no double counting |
| S5 | Document corpus, hybrid retrieval, sourced investigation with abstention | citation validity, numeric claim checks, injection document refused |
| S6 | Human decisions, maker-checker, sandbox action (review activity in Odoo), hash-chained audit, decision memory | unapproved execution refused, stale decision returns 409, tamper detected |
| S7 | Evaluations, Playwright end to end, CFO demo script, production gaps | full journey recorded on desktop and narrow viewport |

### 6.1 Project controlling track (sprints A to F)

Added on 2026-09-14: the lab evolves from a trading company to a synthetic engineering and projects company.
Separation of Odoo, the analytical foundation, planning and spreadsheet entry: ADR-0004. Model and conventions:
`docs/project_controlling_model.md`. Use cases: `data/catalog/use_cases_v2.yml`.

One journey runs through every sprint: budget and forecast, costs, time and commitments, ETC and EAC, margin erosion,
explainable status report, late milestone billing, receivables, investigation, human decision. Every view reads the
same metric service for the same snapshot and plan versions.

| Sprint | Outcome | Evidence required to close | State |
|---|---|---|---|
| A | Requirements mapped, ADR, 50 use cases, extended model, synthetic company and oracle | requirements classed confirmed / proposed / to validate, oracle unreachable from code, deterministic dataset | Delivered |
| B | Project company written into the Odoo sandbox through the API: projects, tasks, milestones, employees, time, purchases, invoices, payments | seed twice without duplicates, `VERIFIED_ODOO_SANDBOX`, live marts equal the fixture oracle | Blocked: sandbox company, backup, `hr_timesheet` |
| C | Planning: versions, CSV import with error report, workflow and locks; EAC, ETC, commitments, margin conventions | locked version refuses edits in the database, empty cell never zero, no double counting | First slice delivered |
| D | Versioned PSR, margin erosion, investigation with abstention, proposals pending review; Portfolio and Project Workspace views | published PSR immutable, investigation cites only computed facts, UI and CLI show the same numbers | Engine delivered, UI to build |
| E | Resources Monitoring (capacity, assignments, chargeable and productive hours) and Flash Report (month, year to date, forecast, to go) | ratios reconcile to time entries, internal hours classified, flash totals equal portfolio totals | Next |
| F | Treasury and overdues view, Planning view, cross-view consistency checks, integrated CFO and project controller demo | parity test across all six views, demo recorded on desktop and narrow viewport | Not started |

The finance track S2 to S7 continues after F and reuses its components (contracts, investigation, maker-checker,
audit). The UI for sprints D to F is the Next.js web application planned in section 3.

## 7. Deviations from the brief, adapted to this repository

| Brief | Here | Why |
|---|---|---|
| `tests/{unit,integration,...}` at repository root | `apps/api/tests/{unit,integration,...}` | Root `tests/` belongs to V1 and runs in its own environment. |
| Docker Compose | managed cloud services, local API and web processes | No Docker on the development VM, 8 GB of memory (ADR-0002). |
| `make` targets | `Makefile` delegating to the `benacta` CLI | `make` is absent on the Windows VM; the CLI runs everywhere. |
| `stock.valuation.layer` candidate | `stock.move` valuation fields | Model removed on the connected version. |
| Carriers | freight service product | `delivery` not installed; installation needs approval. |
| `docs/sprints/Sxx_content_brief.md` | `private/sprints/Sxx_content_brief.md` | Launch and LinkedIn material is kept out of the public repository (`private/` is excluded locally). |
| Project budgets in Odoo | `planning` schema in the analytics database; Odoo budget report only as a later one-way export | Odoo 19 budgets are per account, without work package, period version or approval workflow (ADR-0004). |
| Time entries from Odoo | fixtures shaped like `hr_timesheet` records | The Timesheets app is not installed on the connected instance; installing it needs approval. |
| Real company data in the demo | synthetic company, people and contracts only | The public demo never uses client or employer data. |

## 8. Open items owned by the user

| Item | Needed by | Minimal parameter |
|---|---|---|
| Create the managed PostgreSQL project with pgvector | S1 | `ANALYTICS_DATABASE_URL` pointing at a database named `benacta_analytics` |
| Create the Neo4j AuraDB Free instance | S3 | `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` |
| Create the fictional company in Odoo, or authorise its creation by the seed | S1 | `ODOO_SANDBOX_COMPANY` |
| Download a backup from the Odoo database manager and attest it | S1, before any write | `ODOO_BACKUP_ATTESTED_AT`, `ODOO_BACKUP_REFERENCE` |
| Confirm that adding a company does not change the Odoo subscription | S1 | none |
| Provide an LLM key for real investigation runs | S5 | `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` |
| Decide on shared Odoo settings: activate USD, create the `Dozens` unit | S1 seed | none; otherwise NEG-07 and NEG-06 stay fixture-only |
| Create a read-only bot user for automated ingestion | before S1 scheduled runs | a second API key |
| Authorise installing the Timesheets app (`hr_timesheet`) after checking the subscription impact | sprint B | none |
