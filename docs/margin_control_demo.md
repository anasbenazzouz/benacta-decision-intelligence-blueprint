# BENACTA Margin Control: local setup and demonstration script

State on 2026-09-15: milestone 1 delivered (governed data, deterministic rules, evidence, reconciliation report,
command line and API). Decisions, actions and impact arrive in milestone 2; the AI-assisted investigation and the
cockpit in milestone 3. Every figure below comes from the synthetic company `demo_v2` (fictional customers,
products, people and contracts). No Odoo access and no language model are needed.

## 1. Setup (fixture mode, no credential)

Requirements: Python 3.12 and `uv`. The embedded PostgreSQL ships with the dependencies.

```bash
git clone <repository> && cd benacta-decision-intelligence-blueprint
cp .env.example .env                     # BENACTA_MODE=fixture is the default
uv sync --project apps/api
uv run --project apps/api benacta seed-fixtures
```

`seed-fixtures` migrates the embedded database, ingests the dataset, builds the marts, loads the plan versions,
reconciles every month, loads the governed commercial terms and runs the margin rules. Expected last lines:

```text
reconciliation (FIXTURE_CONTROL_TOTAL): COGS_POSTED, INVOICE_HEADER_LINES, REVENUE_POSTED RECONCILED, 12 period(s) each
margin basis: RECONCILED_COGS
reference (FIXTURE_TERMS): customer_segments=24, discount_policies=5, discount_derogations=1, freight_contracts=7, contract_prices=1, cost_references=17
margin exceptions: 948 evaluations (... CONFIRMED_LEAKAGE=8 ...); cases created=11 ...
```

Run it again: 0 new record versions, 0 new cases. Stop the embedded database with
`uv run --project apps/api benacta local-db-stop`. Checks: `cd apps/api && uv run pytest -q && uv run ruff check app tests migrations`.

Every command below reads the fixture instance (`BENACTA_MODE=fixture`, or the `.env` default). The API serves the
same figures: `uv run --project apps/api benacta serve`, then `GET /api/v1/margin/overview`, `/api/v1/margin/exceptions`,
`/api/v1/margin/exceptions/{case_ref}`, `/api/v1/margin/rules`, `/api/v1/reconciliation`.

## 2. The story (about six minutes)

### Step 1. The CFO asks whether gross margin is deteriorating

```bash
uv run --project apps/api benacta margin-overview --period 2026-07
```

Point at: revenue, COGS and gross margin for the month with their basis (`RECONCILED_COGS`, so this is a closing
figure, not a proxy); the goods gross-margin percentage and its move against the previous month; the detected
leakage (3 050.00 EUR in July), of which 2 250.00 recoverable from customers; the margin bridge from posted margin to
"margin at policy", labelled illustrative; the drivers by cause, customer, product and order.

Line to say: every number here is posted, reconciled and computed by code; the percentage is on goods with a posted
cost, because service revenue has no cost of goods sold behind it.

### Step 2. Where and who

```bash
uv run --project apps/api benacta margin-exceptions
```

Point at the ranking: material confirmed leakage first (a 1 000 EUR unauthorised discount, an 800 EUR purchase price
variance, a 600 EUR invoice below the contract price, a 400 EUR order priced on the wrong price list, a 250 EUR freight
not recharged), then the cases that need a human because the evidence is insufficient
(an expired policy, two conflicting policies, a missing cost, an invoice with no order behind it). Each row carries
its cause, controllability, confidence, owner, status and age.

Line to say: the queue is the output of published rules and thresholds, not an editorial choice; the two legitimate
exceptions of the dataset (an approved derogation, a contractual freight waiver) are not in it, and a confirmed 150 EUR
partial freight recharge below materiality is counted in the period leakage without occupying the queue.

### Step 3. Open the most important exception

```bash
uv run --project apps/api benacta margin-case MC-000001
```

Point at: the rule, its version and formula; expected against actual; the policy that applies with its source; the
drill-down to the order line, the invoice line, the delivery, the receipt and the posted cost; the reconciliation of
the period; the lineage to the raw source record versions; the "Suggested follow-up", pending review.

Line to say: a controller can re-perform this figure by hand from what is on screen.

### Step 4. Prove the period ties to the ledger

```bash
uv run --project apps/api benacta reconciliation-report --period 2026-07
uv run --project apps/api benacta verify-audit --export
```

Point at: source totals against analytical totals, tolerance, timestamps and transformation version; the invoice
headers against their lines; the audit chain `VALID`.

### Step 5. What comes next

Milestone 2: approve or refuse the suggested follow-up, assign an owner, create a review activity in Odoo through
the write guard, and measure the realised recovery from later reconciled documents. Milestone 3: the AI-assisted
investigation on the same evidence, the cockpit, and the three-year demonstration company.

## 3. What this demonstration does not claim

- Fixture mode proves the engine, not the Odoo integration. The connected Odoo has been read (revenue reconciled
  against server aggregates), never seeded with these orders; order-level exceptions are `NOT_VERIFIED` against
  Odoo until the sandbox seed runs.
- Thresholds are demonstration settings, not financial standards.
- No recovery is measured yet; the overview says `NOT_MEASURED`.
