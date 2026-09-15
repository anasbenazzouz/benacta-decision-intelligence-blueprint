# BENACTA Margin Control: local setup and demonstration script

State on 2026-09-15: milestones 1, 2 and 3a delivered (governed data, deterministic rules, evidence, reconciliation
report, decisions, controlled action, impact, audit, investigation on governed documents; command line and API). The
cockpit and the demonstration profile follow. Every figure below comes from the synthetic company `demo_v2` (fictional customers,
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

The cockpit shows the same figures on six screens (executive overview, exception queue, exception case, decision
workspace, impact tracking, audit view):

```bash
uv sync --project apps/api --extra cockpit
uv run --project apps/api benacta demo          # http://127.0.0.1:8501
```

Declare a pilot identity in the sidebar (identifier and roles); the workspace refuses what the roles do not allow.

## 2. The story (about six minutes, command line or cockpit)

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

### Step 4b. Ask for the investigation

```bash
uv run --project apps/api benacta margin-investigate MC-000001
```

Point at the order of the answer: observed facts, each with its reference (rule, order line, invoice line, cost
allocation, reconciliation checks); the governed policy passages cited with owner, version and effective date; one
hypothesis, labelled and never promoted to a fact; the missing evidence, the questions, the trade-off; a draft
recommendation that a finance approver must approve. Without a model key the report is deterministic and says so;
with `--llm` and a configured model, the draft goes through the same validator (no invented number, no citation
outside the payload, no instruction-like text) and falls back to this report when refused.

### Step 5. Decide, as a named person

```bash
uv run --project apps/api benacta margin-decide MC-000001 --decision ASSIGN --actor AN-01 --role analyst --assign-to AN-02 --expected-version 1
uv run --project apps/api benacta margin-decide MC-000001 --decision APPROVE --actor AN-01 --role analyst
uv run --project apps/api benacta margin-decide MC-000001 --decision APPROVE --actor FIN-01 --role finance_approver --expected-version 2 --comment "recover through a complementary invoice"
uv run --project apps/api benacta margin-decide MC-000007 --decision REJECT --actor FIN-01 --role finance_approver --reason "policy renewal in progress; discount accepted for this order"
```

Point at: the analyst can assign but not approve; the approval names the approver and the version it was taken on
(a stale version is refused); a refusal needs a reason; every decision is appended, never edited.

### Step 6. Act, in a controlled way

```bash
uv run --project apps/api benacta margin-act MC-000001 --actor FIN-01 --role finance_approver
uv run --project apps/api benacta margin-act MC-000001 --actor FIN-01 --role finance_approver --confirm
```

Point at: the dry run shows exactly what would be written (a review activity on the sale order, with the case, the
rule, the amounts and the reason) and its external identifier. In fixture mode the request is recorded as
`PLANNED`; on the connected sandbox the same command passes the write guard, creates the activity once, and refuses
any duplicate.

### Step 7. Track the result

```bash
uv run --project apps/api benacta margin-impact
uv run --project apps/api benacta margin-audit MC-000001
uv run --project apps/api benacta margin-overview --period 2026-07
```

Point at: estimated recovery against realised recovery, measured only from posted documents after the decision
(`NOT_MEASURED` until one exists); the audit of the case from the rule version to the approver and the action, every
event hash-chained; the overview's approved and realised recovery, acceptance rate and cycle times.

### Step 8. What comes next

Milestone 3: the AI-assisted investigation on the same evidence (drafts that follow the same approval path), the
cockpit, and the three-year demonstration company.

## 3. What this demonstration does not claim

- Fixture mode proves the engine, not the Odoo integration. The connected Odoo has been read (revenue reconciled
  against server aggregates), never seeded with these orders; order-level exceptions are `NOT_VERIFIED` against
  Odoo until the sandbox seed runs.
- Thresholds are demonstration settings, not financial standards.
- Recovery is measured only from posted documents dated after a decision; on the demonstration data it stays
  `NOT_MEASURED` until such a document exists.
- The controlled action has never run against the connected Odoo: `NOT_VERIFIED` until the owner enables writes
  and attests a backup.
- No language model has been called for real: the model path is exercised through a fake transport and validated
  drafts; the demonstration runs the deterministic investigation.
