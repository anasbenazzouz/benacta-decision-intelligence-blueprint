# Production-readiness gap assessment

What separates the pilot from a production deployment, by area, with the state on 2026-09-15. "Pilot" means the
demonstration on the embedded database and, where marked, read-only runs against the connected Odoo.

| Area | Pilot state | Gap to production |
|---|---|---|
| Source integration | Odoo 19 JSON-2 read path verified live (36 models); writes designed and guarded, executed only against a fake transport | run the sandbox seed and the review-activity action with an attested backup; a read-only bot user for ingestion; API key rotation; scheduled ingestion with monitoring; handling of Odoo record rules per company |
| Data foundation | embedded PostgreSQL with pgvector; versioned raw layer; snapshot-scoped marts; hash-chained audit | managed PostgreSQL (`benacta_analytics`) with backups, roles separating application and migration, retention of raw versions, partitioning of `raw.source_record_version` at volume |
| Reconciliation | revenue, COGS and invoice headers per month with tolerance, timestamps and versions | sign-off workflow for a closed period; automatic blocking of publication on `UNRECONCILED`; multi-company and multi-currency company consolidation |
| Rules and thresholds | five versioned rules, thresholds in a file stamped on every evaluation | threshold governance (who changes, approval, effective dates); rule versions with change logs; back-testing on history when a rule changes |
| Baselines | contract prices and cost references in BENACTA tables, price lists from Odoo | ownership of the policy register in Finance; import from the contract system; effective-dated changes with maker-checker |
| Decisions and actions | append-only decisions, one guarded action (review activity), impact from posted documents | user directory integration; per-user Odoo identity for activities; more action types (draft complementary invoice, derogation request) each with its own guard and idempotency; notifications |
| Investigation | deterministic report; model drafts validated and degraded; governed corpus of four documents | a real model run and its evaluation; corpus ownership and refresh; retrieval quality review; cost and latency budgets; prompt and output retention policy |
| Cockpit | Streamlit on loopback, declared identity | authentication and authorisation; hosting; accessibility review; visual QA loop of the charter; screenshots for documentation |
| API | FastAPI on loopback, pilot identity headers | TLS, authentication, rate limits, versioned contracts, OpenAPI published |
| Security | secrets never rendered; allowlists; guards; append-only journals | secret management; network isolation; signed audit checkpoints or WORM storage; vulnerability scanning; logging without personal data |
| Operations | command line and tests | health and readiness beyond configuration; alerting on failed batches and unreconciled periods; runbooks; capacity planning (the demonstration profile takes minutes end to end on a two-core VM) |
| Data protection | synthetic data only | data classification of customer and supplier names, retention, access logging, processing agreements |
| Portability | canonical marts and business-keyed terms; Odoo mapping in one file | a second connector (SAP, Dynamics or a warehouse) to prove the boundary; connector conformance tests on the mapping contract |

## What would make the pilot a paid pilot

1. A design partner's sandbox with an attested backup, so the seed and the action run for real and the status
   words move from `TESTED_LOCAL` to `VERIFIED_ODOO_SANDBOX`.
2. Their commercial terms in the policy register and their thresholds in the threshold file, reviewed by Finance.
3. One closed period reconciled on their data, with the report signed by their controller.
4. A model key for the investigation and a short evaluation of drafts against the validator on their cases.
5. The cockpit walked through by their CFO against the ten questions of the definition of done.
