# Security and permissions notes (pilot)

What is enforced today, what is a pilot convention, and what production would need. Nothing here claims
production readiness.

## Enforced by code and tests

| Control | Where | Test |
|---|---|---|
| Odoo reads only through an allowlisted reader; any other method is refused before the network | `app/connectors/odoo.py` (`OdooReader`) | `test_odoo_connector.py` |
| Odoo writes only through `OdooWriter`, built from a passing guard, method allowlist, no `unlink`, no raw write on journal items, mail and tracking disabled, no retry | `app/connectors/odoo.py` | `test_writer_*` |
| Write guard: sandbox mode, writes enabled, allowlisted target, sandbox company named and verified live, backup attested within the allowed age | `app/connectors/guards.py` | `test_guards.py` |
| Migrations only against a database named as the analytics database, never carrying Odoo tables | `app/db/engine.py` | `test_foundation_db.py` |
| Secrets never rendered by configuration description; audit payloads refuse secret-like keys | `app/config.py`, `app/audit/log.py` | `test_config.py`, foundation tests |
| Audit journal append-only with hash chain; tamper detected on verification | `audit.event` triggers, `verify_chain` | foundation tests, `benacta verify-audit` |
| Decisions and actions append-only; one executed action per external identifier | `decision.case_decision`, `decision.case_action` triggers and unique index | `test_margin_workflow.py` |
| Role checks on decisions: approve, reject and close need `finance_approver`; every acting role must be declared; company scope checked | `app/margin/decisions.py` | `test_margin_decisions.py`, `test_margin_workflow.py` |
| Optimistic concurrency: a decision taken on a stale case version is refused (`409`) | `decide(expected_version=...)` | `test_decision_workflow_with_maker_checker_and_stale_versions` |
| Controlled action refused unless the case is approved; duplicates refused before any call; guard report recorded with every attempt | `app/margin/actions.py` | `test_action_against_a_fake_odoo_is_guarded_idempotent_and_recorded` |
| Ground truth unreachable from application code | AST scan | `test_application_code_never_reads_the_oracle` |
| Reference data keyed by business references; every row carries owner, source and validity | `semantic.*` | `test_reference_*` in the oracle tests |

## Pilot conventions (not security controls)

- Identity: the command line takes `--actor` and `--role`; the API takes `X-Benacta-Actor` and `X-Benacta-Roles`
  headers. Roles are declared by the caller. This is enough to demonstrate maker-checker and accountability on a
  laptop; it is not authentication or authorisation.
- The API binds to loopback (`benacta serve`) and has no TLS, no rate limit and no session.
- The embedded PostgreSQL runs without a password on a local port.
- Odoo API key: one key, administrator user, no expiry recorded; a read-only bot user for ingestion is still an
  open item (`docs/progress.md`).

## Sensitive data

- Every dataset in the repository is synthetic; the demonstration never uses client or employer data.
- Reference documents under `private/` are confidential and excluded from the repository; no figure, name or client
  from them reaches seeds, fixtures, screenshots or public documents.
- Audit exports (`.benacta/exports/`) are local runtime artefacts, excluded from the repository.

## Language model boundary (milestone 3)

- The model receives computed facts, evidence and governed documents only; it never reads the oracle, the raw
  database or the Odoo API. Its output is schema-validated, checked for invented numbers and stored as a draft
  (`decision.margin_recommendation`, source `LLM_DRAFT`) that follows the same approval path as a template.
- Governed documents carry source, owner, effective date, authorisation and version; unauthorised documents are
  refused at indexing, and an injection test is part of the evaluation plan.

## Production gaps

Authentication and authorisation against the company directory; per-user Odoo identity for activities; TLS and
network isolation; secret management; key rotation; database roles separating the application from migrations;
signed audit checkpoints or WORM storage; retention policy for exports. These are listed, not started.
