# BENACTA Margin Control: architecture

The Finance decision system behind the pilot: how a transaction in the system of record becomes a reconciled
figure, a deterministic exception with evidence, an investigation a person can check, a decision, a controlled
action and a measured result. The V1 blueprint architecture (`docs/architecture.md`) still describes the Monthly
Performance Review; this document describes the Margin Control product built next to it.

## 1. The chain and who owns each step

```text
Odoo (system of record)          read only, JSON-2, allowlisted methods            app/connectors/odoo.py
   -> raw versions                every record version, hash, watermark, batch      app/ingestion/
   -> canonical marts             dimensions, order lines, invoice lines, COGS,      app/marts/build.py
                                  stock moves, FIFO cost attribution, bridges
   -> reconciliation              revenue, COGS, invoice headers, per month,         app/marts/reconcile.py
                                  tolerance, timestamps, transformation version
   -> governed terms              segments, policies, derogations, freight           app/margin/reference.py
                                  clauses, contract prices, cost references          semantic.*
   -> price and cost baselines    contract > customer list > list price >            app/margin/baseline.py
                                  comparable history > unavailable
   -> deterministic rules         versioned, evidence bundles, six classes,          app/margin/rules.py
                                  severity, confidence, controllability              app/margin/engine.py
   -> cases and recommendations   stable identity, template recommendation           decision.*, app/margin/decisions.py
   -> investigation               payload of computed facts + governed passages;     app/margin/investigation.py
                                  deterministic or model draft, validated             app/margin/documents.py, llm.py
   -> human decision              approve, reject, evidence, assign, defer;           app/margin/decisions.py
                                  reasons, roles, versions, append-only
   -> controlled action           review activity in Odoo through the write guard,   app/margin/actions.py
                                  idempotent, dry run by default
   -> impact                      realised only from posted documents after           app/margin/impact.py
                                  the decision
   -> audit                       hash-chained journal, case audit view, export       app/audit/log.py, service.case_audit
   -> surfaces                    command line, API, cockpit, one service layer       app/ops/margin_ops.py, app/main.py,
                                                                                      apps/cockpit/margin_control.py
```

Doctrine: **code computes, AI explains, humans decide.** The model never touches a figure; it receives a payload
of computed facts and returns a draft that is validated and degraded when it steps outside that payload.

## 2. Trust boundary

Above the boundary: ingestion, marts, reconciliation, terms, baselines, rules, engine, decisions, actions,
impact, audit. They import no model client. Below the boundary: `app/margin/investigation.py` and
`app/margin/llm.py`. The boundary is enforced by:

- the payload (`build_payload`): computed facts, transactions, rule, reconciliation, related evaluations,
  authorised passages; the oracle and the raw database are unreachable;
- the validator (`validate_report`): numbers and references only from the payload, hypotheses labelled and
  supported, instruction-like text refused, a finance approver required for the draft recommendation;
- degradation: a refused draft or a failing provider yields the deterministic report with the reason recorded;
- the same approval path for a model draft (`LLM_DRAFT`) as for a template;
- the AST test that keeps ground truth out of application code.

## 3. Data model (analytics database)

Schemas `raw`, `staging`, `marts`, `semantic`, `decision`, `audit` (and `planning` for the parked project track).
Full dictionary: `docs/data_dictionary.md`. Every mart row is scoped by snapshot; every decision, action and
audit event is append-only; every case keeps its identity across snapshots and records why it stops being raised.

## 4. Portability

Business logic reads canonical marts and business-keyed terms (partner reference, product code), never Odoo
field names. The Odoo mapping is one file (`data/mappings/odoo_source_mapping.yml`) checked by discovery; a
second connector implements the `Source` protocol (`app/ingestion/sources.py`) and the same marts. Missing
capabilities are stated, not simulated: no posted COGS gives a management proxy, no valued receipt gives
`UNDETERMINED`, no baseline gives `UNAVAILABLE`.

## 5. Modes and evidence

| Mode | Data | Model | Writes | Status word |
|---|---|---|---|---|
| fixture `dev` | `demo_v2` on the embedded database | none, or a fake in tests | none (actions `PLANNED`) | TESTED_LOCAL |
| fixture `full` | three-year demonstration company | none, or a fake in tests | none | TESTED_LOCAL (opt-in gate) |
| odoo_sandbox, read | connected Odoo Online | optional | none | VERIFIED_ODOO_READ (revenue reconciliation, discovery) |
| odoo_sandbox, write | connected Odoo Online, sandbox company | optional | review activity through the guard | NOT_VERIFIED until a real run |

Status with evidence per milestone: `docs/progress.md`. Evaluation gates: `docs/evaluation_plan.md`. Gaps to
production: `docs/production_readiness.md`.
