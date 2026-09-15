# API contracts: Margin Control (`/api/v1`)

The API serves the same service functions as the command line, so one snapshot gives the same figures on every
surface (`test_api_returns_the_same_figures_as_the_service`). Amounts are decimal strings in company currency
(EUR) excluding taxes; dates are ISO 8601; identifiers are UUIDs or case references (`MC-000001`).

Every read route accepts `snapshot` (UUID) to pin a snapshot; without it the latest succeeded ingestion of the
configured source instance is used. Identity for write routes: headers `X-Benacta-Actor` (user identifier) and
`X-Benacta-Roles` (comma-separated: `analyst`, `project_controller`, `finance_approver`, `admin`). This is the
pilot identity, not an authentication system; see `docs/security_notes.md`.

## Read routes

| Route | Returns |
|---|---|
| `GET /api/v1/health` | liveness |
| `GET /api/v1/ready` | readiness from configuration (connection presence, never secrets) |
| `GET /api/v1/margin/overview?period=YYYY-MM` | `kpis` (revenue, goods and services split, COGS, gross margin and percentage, goods gross margin and percentage, previous period, delta in points, `deteriorating`, leakage by type, recoverable, addressable, untraceable revenue, approved and realised recovery, acceptance rate, decisions taken, cycle times), `waterfall`, `periods`, `drivers` (causes, customers, products, orders), `thresholds`, `margin_basis`, `status` |
| `GET /api/v1/margin/exceptions?period=&classification=&include_resolved=&limit=` | ranked queue: case reference, subject, rule, cause, classification, exposures, stage, severity, confidence, controllability, materiality, owner, status, age in days, recommendation status and title, suggested follow-up |
| `GET /api/v1/margin/exceptions/{case_ref}` | `case`, `rule` (version, formula), `evaluation`, `evidence` (every input the rule read), `drill_down` (order lines, invoice lines, deliveries, cost allocations, receipts, posted COGS), `related_evaluations_same_subject`, `period_reconciliation`, `lineage` (raw source record versions), `suggested_follow_up`, `recommendation`, `decisions`, `actions`, `impact`, `investigation` (null until milestone 3) |
| `GET /api/v1/margin/exceptions/{case_ref}/audit` | the case, its evaluations across snapshots (rule and threshold versions), every recommendation version, decisions, actions, impact, lineage and the hash-chained audit events of the case |
| `GET /api/v1/margin/impact` | impact register: estimated against realised recovery per approved case, realisation status, evidence, variance |
| `GET /api/v1/margin/rules` | rule catalogue with versions and formulas |
| `GET /api/v1/reconciliation?period=YYYY-MM` | closed-period reconciliation report: checks, totals, tolerance, timestamps, transformation version, period status |

## Write routes

### `POST /api/v1/margin/exceptions/{case_ref}/decisions` (201)

Body:

```json
{"decision_type": "APPROVE", "expected_version": 2, "reason": null, "comment": "recover through a complementary invoice",
 "assigned_to": null, "defer_until": null}
```

`decision_type`: `APPROVE`, `REJECT`, `REQUEST_EVIDENCE`, `ASSIGN`, `DEFER`, `COMMENT`, `REOPEN`, `CLOSE`.
Rules: a reason is required for `REJECT`, `DEFER`, `REQUEST_EVIDENCE`, `REOPEN`; `ASSIGN` needs `assigned_to`;
`DEFER` needs `defer_until`; `APPROVE`, `REJECT` and `CLOSE` need the `finance_approver` (or `admin`) role;
`expected_version` must equal the case version the decision was taken on.

Responses: `201` with `decision_id`, `status_before`, `status_after`, `version`; `401` no actor header; `403` role
missing; `404` unknown case; `409` stale version; `422` illegal transition or missing field.

State machine (`app/margin/decisions.py`):

```text
NEW ──ASSIGN──▶ OPEN ──REQUEST_EVIDENCE──▶ EVIDENCE_REQUESTED ──DEFER──▶ DEFERRED
 │                │                              │                          │
 └────────────────┴────────── APPROVE ───────────┴──────────────────────────┘──▶ APPROVED ──(action executed)──▶ ACTIONED ──CLOSE──▶ CLOSED
 └────────────────┴────────── REJECT ────────────┴──────────────────────────┘──▶ REJECTED ──CLOSE──▶ CLOSED
REJECTED | DEFERRED | EVIDENCE_REQUESTED | CLOSED | NO_LONGER_RAISED ──REOPEN (reason)──▶ OPEN
COMMENT keeps the status. Every decision is append-only and bumps the case version.
```

### `POST /api/v1/margin/exceptions/{case_ref}/actions`

Body `{"confirm": false}` returns the planned review activity (target model and id, external identifier, request)
without recording anything. `{"confirm": true}` executes it:

| Result | Meaning |
|---|---|
| `PLANNED` / `FIXTURE_MODE` | fixture mode has no target system; the request is recorded, nothing is executed, the case stays `APPROVED` |
| `REFUSED` / `NOT_APPROVED` | only an `APPROVED` case can be actioned |
| `REFUSED` / `DUPLICATE` | an executed action already exists for the external identifier (checked before any call) |
| `REFUSED` / `GUARD_BLOCKED` | `odoo_write_guard` failed; the report is recorded; no write was attempted |
| `REFUSED` / `DUPLICATE_IN_TARGET` | Odoo already holds the external identifier |
| `FAILED` / `<error type>` | the write raised; recorded, case unchanged |
| `EXECUTED` / `REVIEW_ACTIVITY_CREATED` | `mail.activity` created on the document, external identifier registered, case `ACTIONED` |

What the action writes: one `mail.activity` (to-do) on the sale order or the invoice, with a summary naming the
case and the recommendation, a note with the rule, amounts and reason, a deadline, tracking and mail disabled.
Nothing else is written: no price, invoice, journal entry or contractual condition changes.

## Command line equivalents

`margin-overview`, `margin-exceptions`, `margin-case`, `margin-decide`, `margin-act`, `margin-impact`,
`margin-audit`, `reconciliation-report` (`uv run --project apps/api benacta <command> --help`).
