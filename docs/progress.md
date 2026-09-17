# BENACTA Decision System Lab: progress

Status vocabulary: `IMPLEMENTED` (code exists) · `TESTED_LOCAL` (automated tests pass locally) ·
`VERIFIED_ODOO_SANDBOX` (proven by a real write run against the Odoo sandbox) · `VERIFIED_ODOO_READ` (proven by a
real read-only run against the connected Odoo) · `NOT_VERIFIED` · `BLOCKED`.
A fixture test never proves an Odoo integration. Plan: `docs/implementation_plan.md`.

## Odoo write path: trading-company seed executor (2026-09-16, IMPLEMENTED, NOT_VERIFIED)

The owner asked on 2026-09-16 for the connected instance (`benacta.odoo.com/benacta`, Odoo saas~19.4, company
`Benacta`, the only one) to carry the demonstration data as if it had been entered there. The instance already has
the five required modules, USD active, a French chart, no `benacta_demo` external identifier, and some existing
documents of its own (31 sale orders, 52 journal entries, 38 payments on 2026-09-16), which the pipeline will read
alongside the seed.

| Item | Status | Where |
|---|---|---|
| Executor of the trading company (`demo_v1`): categories with FIFO and automated valuation, price lists, partners, products, purchase orders confirmed and received, sale orders confirmed or cancelled, deliveries validated (one partial with a backorder), invoices created from the orders through Odoo's wizard, one credit note through the reversal wizard, one invoice without order, all dated as in the dataset and named `BD/SO/...`, `BD/PO/...`; external identifiers under `benacta_demo` for replay | IMPLEMENTED, TESTED_LOCAL (dry run and refusals against a fake transport), NOT_VERIFIED | `app/ops/seed_odoo.py` |
| Shared seeder base (external identifiers, adoption of twins, batching, line mapping) used by the project seeder too | TESTED_LOCAL | `app/ops/odoo_seed_base.py`, `app/ops/seed_projects.py` |
| Dry run reads the instance facts the executor relies on (units model, valuation fields, stock accounts, tax, warehouse, anglo-saxon flag) and reports what is missing | IMPLEMENTED | `benacta seed-odoo` without `--confirm` |
| Policy register of the seeded company written for `benacta load-policies` in connected mode | IMPLEMENTED | `data/policies/margin_policy_register.yml` (ignored by git) |
| Default suite | 254 passed, 16 skipped | `uv run pytest -q` |

What the first confirmed run still needs, all owner decisions taken outside this session:

1. `.env`: `ODOO_WRITES_ENABLED=true`, `ODOO_BACKUP_ATTESTED_AT` (ISO date within 7 days) and `ODOO_BACKUP_REFERENCE`
   (the downloaded backup, or an explicit waiver text for a throw-away instance). The session's permission layer
   refused these edits on 2026-09-16, so they stay with the owner.
2. Two shared settings the executor changes on the instance and reports: anglo-saxon accounting on the company
   (cost of goods sold posted with the invoice, which `COGS_POSTED` needs) and the unit of measure "Dozens".
3. The guarded writer's method allowlist must admit five document workflows on their own model only:
   `stock.picking.button_validate`, `stock.backorder.confirmation.process`, `sale.advance.payment.inv.create_invoices`,
   `account.move.reversal.reverse_moves`, `sale.order.action_cancel` (`MODEL_METHODS` in `app/connectors/odoo.py`,
   with a unit test that every other model still refuses them). Without it the executor stops at the first
   receipt with `WriteNotAllowed`, which is the intended behaviour of the guard.

Then, in order: `benacta seed-odoo --confirm`, `benacta ingest`, `benacta marts`, `benacta reconcile`,
`benacta load-policies`, `benacta exceptions`, `benacta margin-overview`, one `margin-decide` and one
`margin-act --confirm`, and the status words move to `VERIFIED_ODOO_SANDBOX` where the run proves them.

## Milestone 3c: three-year demonstration company and its ground truth (delivered on fixtures)

### Evidence (2026-09-15)

| Command | Result |
|---|---|
| `BENACTA_FULL_PROFILE=1 uv run pytest -q tests/unit/test_full_profile.py` | 5 passed in 202 s: deterministic across two builds, referential integrity (every line, item, move and payment resolves; every entry balances; only the freight service and the missing-cost scenario products lack a receipt), realistic distributions (seasonality, growth, four currencies, customer concentration and long tails, payment states, refunds, backorders, quarterly cost drift), ground truth separate from the records and equal to the committed manifest |
| `BENACTA_FULL_PROFILE=1 uv run pytest -q tests/integration/test_full_profile_pipeline.py` | 4 passed in 217 s: 36 months `RECONCILED` on the three checks; every one of the 80 injected scenarios gives its expected outcome, class, cause and amount; no confirmed or probable leakage outside the injected scenarios; cases equal the manifest; leakage totals by type equal the manifest; goods gross-margin percentage of year three at least one point below year two; the overview of the anchor month shows revenue and leakage drivers |
| `uv run --project apps/api benacta seed-fixtures --profile full` then `uv run --project apps/api python scripts/verify_full_profile.py` | 72 276 evaluations (COMPLIANT 59 462, CONFIRMED_LEAKAGE 43, DATA_QUALITY_ISSUE 10, EXPLAINED_VARIANCE 179, INSUFFICIENT_EVIDENCE 6, LEGITIMATE_EXCEPTION 924, NOT_APPLICABLE 11 652), 41 cases created, 36 periods; the script prints `full profile verified` (36 periods reconciled, 80 scenarios checked, 41 cases, goods margin year 2 39.12 % to year 3 36.22 %) and exits 0 |
| Timings on the two-core development VM (8 GB) | generate about 65 s, whole seed about 7 min for about 130 000 records; each opt-in gate about 3.5 min and about 3 GB, one at a time in the foreground; a replay adds no version and no case |
| `uv run pytest -q` in `apps/api` (default suite, profile gates skipped) and `uv run ruff check app tests migrations` | 253 passed, 16 skipped; lint clean |
| `scripts/export_ground_truth.py` | `data/golden/demo_full_manifest_v1.json`: 505 customers, 100 suppliers, 213 products, 9 548 orders, 20 907 order lines, 5 798 purchase orders with 8 872 lines, 9 719 invoices, 76 568 journal items, 26 749 stock moves, 8 208 payments; 80 scenarios, 43 confirmed leakage evaluations, 41 cases, leakage by type cost 9 263.92, discount 21 721.81, freight 1 896.00, price 7 203.56 EUR; four scenario families place one instance in the anchor month |

### Items

| Item | Status | Where |
|---|---|---|
| Demonstration profile generator on the same lineage as `demo_v1` (Odoo shapes, same ingestion, marts and rules): families with margin profiles, customer sizes, segments, countries and currencies, seasonality, growth, year-three mix shift and volume push, just-in-time purchasing in two waves a month at quarterly reference costs with drift and FIFO valuation of every delivery, price lists and contract prices, partial deliveries, refunds, payment terms and late payments, open pipeline at the anchor | TESTED_LOCAL (opt-in gates) | `app/fixtures/full_profile.py`, `docs/seed_data_specification.md` |
| Ground-truth manifest apart from the records, exported by a script outside application code, versioned and checked equal to the generator's output | TESTED_LOCAL | `data/golden/demo_full_manifest_v1.json`, `scripts/export_ground_truth.py` |
| Rule `PRODUCT_MAPPING` (order line whose product or unit of measure cannot be resolved) for scenario 12 | TESTED_LOCAL | `app/margin/rules.py` |
| Profile switch: `benacta seed-fixtures --profile full`, `BENACTA_FIXTURE_PROFILE` read by the views, the API and the cockpit | TESTED_LOCAL | `app/config.py`, `app/ops/pipeline.py`, `app/cli.py` |
| Opt-in gates (`BENACTA_FULL_PROFILE=1`) documented in the evaluation plan | IMPLEMENTED | `docs/evaluation_plan.md` |
| Verification of the seeded profile against the manifest without a second database (exit 0 when verified) | TESTED_LOCAL | `scripts/verify_full_profile.py` |

### Findings from this milestone

- Realistic data found two defects the small fixture could not: the freight rule compared a EUR clause with
  freight invoiced in GBP or CHF without converting (42 false alarms, fixed in the rule with a unit test), and the
  generator priced foreign-currency orders with EUR figures (289 false alarms, fixed in the generator: prices in the
  customer's currency at the order-date rate).
- The customer that carries the conflicting-policies scenario cannot also carry a policy-gap scenario: the
  conflict outranks the gap. The manifest now separates them.
- Valuing deliveries at the quarter's cost while the marts replay FIFO over the receipt layers broke down as soon as
  purchasing became realistic (two waves a month with a safety stock): the replayed cost no longer matched the recorded
  move value and about 15 000 lines fell to `MISSING_COST`. The generator now values each delivery from the layers it
  consumes, in the marts' replay order, and buys just in time so that every layer is consumed within its half-month.
- A delivery in the quarter after its order is valued at the new receipt cost while the reference is frozen on the
  order date: the rule reported 200 immaterial cost variances on background lines, all correct. The profile keeps
  deliveries within the cost quarter of their order; a real pilot would tune the cost tolerance or the reference date.
- Scenario orders of customers on a freight rebill clause must carry their freight line, or the freight rule raises
  them as well (11 such orders, one of them material). A credit note dated after the anchor opened a 37th period.

### Known limits

- The profile runs on the embedded database; its Odoo seed is not written (blocked on the owner inputs listed
  under milestone 2).
- Purchases stay in EUR; supplier currencies, lead-time variance, stock locations and stock counts are not modelled.
- The gates take about seven minutes each on the development VM, need about 3 GB free and stay opt-in.
- No stock is carried between half-months, so cost variances only come from the injected scenarios.

## Milestone 3b: CFO cockpit (delivered on fixtures)

### Evidence (2026-09-15)

| Command | Result |
|---|---|
| `uv run pytest -q tests/integration/test_cockpit_smoke.py` | 2 passed: every view renders headlessly on the fixture database (Streamlit `AppTest`), the cockpit imports no oracle and no writer |
| `uv sync --project apps/api --extra cockpit && benacta demo` | cockpit on 127.0.0.1:8501 over the same service functions as the command line and the API |

### Items

| Item | Status | Where |
|---|---|---|
| Executive overview: revenue with goods and services split, COGS with basis, gross margin, goods margin percentage with the deterioration signal, leakage tiles, approved and realised recovery, margin bridge, drivers, reconciliation trace | TESTED_LOCAL (smoke) | `apps/cockpit/margin_control.py` |
| Exception queue ranked with class, cause, exposure, severity, confidence, controllability, owner, status, recommendation, age, suggested follow-up | TESTED_LOCAL (smoke) | same |
| Exception case: what happened, rule and formula, transactions, evidence, reconciliation, investigation (run button, deterministic or model with the human-control label), recommendation, lineage | TESTED_LOCAL (smoke) | same |
| Decision workspace: declared identity, decisions with reasons, refusals shown, dry-run and guarded execution of the review activity, decision and action history | TESTED_LOCAL (smoke) | same |
| Impact tracking and audit view with JSON export | TESTED_LOCAL (smoke) | same |
| Visual system from the locked charter (Deep Heritage Green, Warm Porcelain, Antique Champagne scarce, Mineral Blue only for AI-labelled blocks, Instrument Sans, one serif for statements) | IMPLEMENTED | same |

### Known limits

- The cockpit opens the analytics database directly (same process); it does not go through the HTTP API.
- No screenshot in the repository yet; the visual QA loop of the doctrine runs before any public capture.
- Streamlit is an optional extra; the API and the command line never need it.

## Milestone 3a: AI-assisted investigation on governed documents (delivered on fixtures)

### Evidence (2026-09-15)

| Command | Result |
|---|---|
| `uv run pytest -q` in `apps/api` | 250 passed, 7 skipped (live tests are opt-in) |
| `uv run pytest -q tests/unit/test_margin_investigation.py` | 7 passed: unauthorised and malformed documents refused at indexing, shipped corpus complete, retrieval with citations and effective dates, deterministic report validates against its payload, validator refuses invented numbers, unknown citations, injected instructions and unlabelled hypotheses, model provider request shape, no provider without configuration |
| `uv run pytest -q tests/integration/test_margin_investigation_db.py` | 7 passed: payload of computed facts and authorised passages only, deterministic investigation stored and shown on the case, a valid model draft becomes recommendation version 2 `LLM_DRAFT` pending review, an injected or invented draft and a failing provider degrade to the deterministic report with the reason recorded, a decided case keeps its recommendation, unauthorised fixture documents never cited, API route |
| `benacta seed-fixtures` | 4 governed documents indexed, 0 refused |
| `BENACTA_MODE=fixture benacta margin-investigate MC-000001` | mode `DETERMINISTIC_NO_LLM`, label "sans LLM": observed facts cite the rule, the order line, the invoice line, the cost allocation and the three reconciliation checks; one labelled hypothesis; three passages of the commercial policy cited with owner, version and effective date; missing evidence, questions, trade-off; draft recommendation requiring a finance approver |
| `benacta margin-investigate MC-000001 --llm` without a key | deterministic investigation, message that no model is configured |
| Real model run | NOT_VERIFIED: no `LLM_API_KEY` configured; the Anthropic provider is exercised through a fake transport only |

### Items

| Item | Status | Where |
|---|---|---|
| Governed document corpus with front matter (identifier, title, source, owner, effective date, version, authorisation); unauthorised or malformed documents refused at indexing; registry with content hash | TESTED_LOCAL | `data/documents/margin/`, `app/margin/documents.py`, migration `0006_governed_documents` |
| Transparent retrieval: keyword scoring by section, citation `doc:<id>#<section>`, matched terms, effective-date filter; no embeddings | TESTED_LOCAL | `app/margin/documents.py` |
| Investigation payload: evaluation, metrics, transactions, rule, reconciliation, related evaluations, passages; allowed numbers and references derived from it; the oracle is unreachable | TESTED_LOCAL | `app/margin/investigation.py` |
| Deterministic provider ("sans LLM") producing observed facts, labelled hypotheses, missing evidence, questions, trade-offs and a draft recommendation, every statement referenced | TESTED_LOCAL | same |
| Validator: schema, numbers only from the payload, references only from the payload, hypotheses with support, instruction-like text refused, requires_role | TESTED_LOCAL | same |
| Language model provider (Anthropic Messages API through httpx, no SDK), system prompt with the boundary, JSON-only parsing; graceful degradation to deterministic with the reason recorded | TESTED_LOCAL (fake transport) | `app/margin/llm.py` |
| A validated draft becomes a `LLM_DRAFT` recommendation version pending review, only while the case is open; the estimated amount never changes | TESTED_LOCAL | `app/margin/investigation.py` |
| CLI `margin-investigate [--llm]`, `index-documents`; API `POST /api/v1/margin/exceptions/{case_ref}/investigate`; case view carries the latest investigation | TESTED_LOCAL | `app/ops/margin_ops.py`, `app/main.py` |

### Known limits

- No real model run yet; the evaluation of drafts against the validator on real outputs starts when a key exists.
- Retrieval is keyword-based by design; a passage is cited when its terms match, not when its meaning does.
- The deterministic hypotheses are one sentence per cause; the model draft may be richer but is bound by the same validator.

## Milestone 2: decisions, controlled action and impact (delivered on fixtures)

Every figure below comes from the synthetic dataset `demo_v2`; the Odoo side of the action was exercised against a
fake JSON-2 transport only. No Odoo write happened; the executor stays `NOT_VERIFIED` against the connected instance.

### Evidence (2026-09-15)

| Command | Result |
|---|---|
| `uv run pytest -q` in `apps/api` | 236 passed, 7 skipped (live tests are opt-in) |
| `uv run pytest -q tests/integration/test_margin_workflow.py` | 8 passed: every case carries one pending recommendation; assign, refused approval by an analyst, stale version refused, approval with impact `NOT_MEASURED`, illegal re-approval refused; decisions append-only (update and delete refused by the database); reject, reopen, request evidence, defer, comment; fixture-mode action `PLANNED` never `EXECUTED`; against a fake Odoo: guard blocked before any write, `EXECUTED` with `mail.activity` and external identifier, duplicate refused before any call, case `ACTIONED`, audit chain valid; realised recovery measured from a complementary invoice posted after the decision (1 000.00, variance 0.00); API `401`, `403`, `404`, `409`, `422`, `201`, dry run and planned action, audit and impact routes |
| `uv run pytest -q tests/unit/test_margin_decisions.py` | 6 passed: state machine, preconditions refused before any database access, actor parsing, recommendation templates and hashes |
| `ruff check app tests migrations` | clean |
| `benacta seed-fixtures` | 11 cases, 11 recommendations `CREATED` (`DETERMINISTIC_TEMPLATE`), impacts none yet |
| `benacta margin-decide MC-000001 --decision ASSIGN --actor AN-01 --role analyst --assign-to AN-02 --expected-version 1` | `NEW -> OPEN`, version 2 |
| `... --decision APPROVE --actor AN-01 --role analyst` | refused: requires the finance_approver role |
| `... --decision APPROVE --actor FIN-01 --role finance_approver --expected-version 1` | refused: case at version 2 |
| `... --decision APPROVE --actor FIN-01 --role finance_approver --expected-version 2` | `OPEN -> APPROVED`, version 3, estimated recovery 1 000.00 |
| `benacta margin-decide MC-000007 --decision REJECT --actor FIN-01 --role finance_approver --reason ...` | `NEW -> REJECTED` with the reason recorded |
| `benacta margin-act MC-000001 --actor FIN-01 --role finance_approver` | dry run: review activity on `sale.order#35`, external id `margin_action__MC-000001__REVIEW_ACTIVITY`, nothing recorded |
| `benacta margin-act MC-000001 ... --confirm` (fixture mode) | `PLANNED / FIXTURE_MODE`: request recorded, nothing executed, case stays `APPROVED` |
| `benacta margin-impact` | 1 approved case, estimated 1 000.00, realised `NOT_MEASURED` (no posted document after the decision yet) |
| `benacta margin-audit MC-000001` | evaluation (rule v1, thresholds demo/v1), recommendation v1 `APPROVED`, decisions ASSIGN and APPROVE with actors and roles, action `PLANNED`, impact, 1 source record version, 4 hash-chained audit events |
| `benacta margin-overview --period 2026-07` | approved recovery 1 000.00, realised 0.00 (0 of 1 measured), 1 decision, acceptance rate 100 %, detection to decision 0.0 h |
| V1 suite at repository root | 155 passed (unchanged) |

### Items

| Item | Status | Where |
|---|---|---|
| Recommendation per case: deterministic template by cause, estimated recovery only for the billing component, versioned and superseded when the evidence changes, frozen once decided | TESTED_LOCAL | `app/margin/decisions.py`, `decision.margin_recommendation` |
| Decision state machine: approve, reject, request evidence, assign, defer, comment, reopen, close; reasons required; approver role for approve, reject, close; company scope; optimistic concurrency on the case version; append-only record; audit events | TESTED_LOCAL | `app/margin/decisions.py`, migration `0005_decision_workflow` |
| Controlled action: review activity (`mail.activity`) on the source document, guarded, idempotent by external identifier, dry run by default, every attempt recorded with the guard report | TESTED_LOCAL (fake Odoo) | `app/margin/actions.py` |
| Controlled action against the connected Odoo | NOT_VERIFIED | needs `ODOO_WRITES_ENABLED=true` and an attested backup; nothing executed |
| Impact: estimated at approval, realised only from posted invoice lines dated after the decision, variance, evidence; cost variances `NOT_MEASURABLE` | TESTED_LOCAL | `app/margin/impact.py`, `decision.case_impact` |
| Overview KPIs: approved and realised recovery, acceptance rate, detection to decision and decision to action times | TESTED_LOCAL | `app/margin/service.py` |
| Audit view per case: evaluations across snapshots with rule and threshold versions, recommendation versions, decisions, actions, impact, lineage, hash-chained events; JSON export | TESTED_LOCAL | `benacta margin-audit`, `GET /api/v1/margin/exceptions/{case_ref}/audit` |
| API write routes with pilot identity headers; contracts documented | TESTED_LOCAL | `app/main.py`, `docs/api_contracts.md` |
| Security and permissions notes | IMPLEMENTED | `docs/security_notes.md` |

### Known limits

- Identity is declared by the caller (command line flags, API headers): enough for maker-checker on a laptop, not
  authentication (`docs/security_notes.md`).
- Realised recovery is measured from complementary invoice lines linked to the subject; a correction of the order
  before invoicing (avoidance) is not yet measured as recovery.
- The activity is created for the API user; per-owner Odoo users are not mapped.
- The recommendation is a template per cause; the AI-assisted investigation of milestone 3 will draft richer ones
  through the same table and approval path.

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
| Seed executor writing the sandbox company | IMPLEMENTED on 2026-09-16, TESTED_LOCAL (fake transport), NOT_VERIFIED on the instance | `app/ops/seed_odoo.py`, see the section "Odoo write path" |
| Golden cases in Odoo | NOT_VERIFIED | depends on the executor's first confirmed run |
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
