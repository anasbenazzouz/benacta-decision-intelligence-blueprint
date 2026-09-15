# Evaluation plan

What is measured, how, against which ground truth, and where the result stands. Every evaluation runs from the
test suite or a command; none relies on a human reading a screen. Status words follow `docs/progress.md`.

## 1. Financial truth

| Evaluation | Method | Ground truth | Status |
|---|---|---|---|
| Revenue ties to the source for every closed period | `REVENUE_POSTED` against server aggregates (`SERVER_AGGREGATE`) on Odoo, fixture control totals on fixtures; tolerance 0.01 | the source itself | VERIFIED_ODOO_READ (20 months live), TESTED_LOCAL |
| COGS has a documented source or is declared unavailable | `COGS_POSTED`, margin basis | posted COGS items | TESTED_LOCAL; live data has no COGS and reports `UNAVAILABLE` |
| Invoice headers equal their lines | `INVOICE_HEADER_LINES` | the source's own headers | TESTED_LOCAL |
| Gross margin reproducible without a model | period KPIs recomputed from facts in tests; no model in the pipeline | facts | TESTED_LOCAL |
| Cost attribution replays Odoo valuation | FIFO replay compared with move values; `UNDETERMINED` otherwise | valued moves | TESTED_LOCAL |

## 2. Detection quality

| Evaluation | Method | Ground truth | Status |
|---|---|---|---|
| Every golden case detected with the expected amount, class and cause | `test_margin_engine_oracle.py` | `data/golden/oracle_v1.yml` (6 golden cases) | TESTED_LOCAL |
| No false positive on background orders | zero non-compliant evaluation outside the scenario orders | oracle totals | TESTED_LOCAL |
| Negative controls give their expected outcome (compliant, legitimate, explained, undetermined, unknown, conflict, excluded, unlinked) | same | 12 negative controls | TESTED_LOCAL |
| Two anomalies on one line counted once per component | NEG-12 | oracle | TESTED_LOCAL |
| Immaterial confirmed leakage counted, not queued | FREIGHT-002 | oracle | TESTED_LOCAL |
| Stable cases across snapshots; corrected source closes the case with the reason | replay and correction tests | engine | TESTED_LOCAL |
| Detection on realistic volumes (about 10 000 order lines, 3 years) | demonstration profile with its own oracle | milestone 3 | not started |

## 3. Decision and action integrity

| Evaluation | Method | Status |
|---|---|---|
| Illegal transitions, missing reasons, missing roles, stale versions refused | unit and database tests | TESTED_LOCAL |
| Decisions and actions append-only | database triggers tested | TESTED_LOCAL |
| Action executed once per external identifier; refused when not approved; guard report recorded | fake Odoo transport | TESTED_LOCAL; live NOT_VERIFIED |
| Realised recovery only from posted documents after the decision | complementary invoice test | TESTED_LOCAL |
| Audit chain valid after every step; export re-verifiable | `verify_chain`, `benacta verify-audit --export` | TESTED_LOCAL |

## 4. Interpretation boundary

| Evaluation | Method | Status |
|---|---|---|
| Payload contains computed facts and authorised passages only; the oracle is unreachable | payload test, AST scan | TESTED_LOCAL |
| Deterministic report validates against its own payload | validator on every run | TESTED_LOCAL |
| Invented numbers refused | validator test with an added amount | TESTED_LOCAL |
| Citations outside the payload refused | validator test with a forged reference | TESTED_LOCAL |
| Prompt injection through a document or a draft refused | unauthorised document never indexed; instruction-like draft refused and degraded | TESTED_LOCAL |
| Unlabelled hypotheses refused | validator test | TESTED_LOCAL |
| Graceful degradation when the provider fails or is not configured | provider raising; no key | TESTED_LOCAL |
| Faithfulness of real model drafts (share of drafts accepted by the validator, share of statements a controller confirms) | to run on the golden cases once a key exists; target: every accepted draft cites only payload references, no refused draft reaches a person | NOT_VERIFIED |

## 5. Demonstration and user acceptance

| Evaluation | Method | Status |
|---|---|---|
| The demo script runs end to end without a credential | `docs/margin_control_demo.md` commands in order | IMPLEMENTED (manual run on 2026-09-15) |
| Same figures on command line and API for one snapshot | parity test | TESTED_LOCAL |
| A CFO can answer the ten questions from the screens | cockpit walkthrough with a design partner | not started |
| Cycle-time and acceptance KPIs available | overview | TESTED_LOCAL on fixture decisions |

## 6. How to run

```bash
cd apps/api && uv run pytest -q                       # everything local
BENACTA_LIVE_ODOO=1 uv run pytest -q -m odoo_live      # read-only live checks
uv run --project apps/api benacta verify-audit --export
```
