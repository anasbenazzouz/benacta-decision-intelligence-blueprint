# ADR-0004: Odoo operates, BENACTA governs facts and plans, spreadsheets only feed

## Status

Accepted, 2026-09-14.

## Context

The Lab extends from margin leakage to project controlling: status reports, resource monitoring, flash reports,
overdues and a first budget and forecast scope. Project controlling practice shows three recurring failure modes: plans kept in spreadsheets as the only store, the same
version edited after publication, and reports that could not navigate past periods.

The connected Odoo (saas~19.4) provides, natively: sale orders and change orders as quotations, projects with an
analytic account, `project.milestone` linked to a sale order line for milestone billing, tasks, employees with an
hourly cost and skills, purchase order lines with received and billed quantities and an analytic distribution,
invoices with due dates and residuals, and payments. It does not provide, on this instance: timesheets
(`hr_timesheet` not installed), versioned project budgets or forecasts with a workflow, or revenue recognition
policies. It offers `account.report.budget`, a budget per general ledger account and date for accounting reports.

## Decision

| Layer | Owns | Never owns |
|---|---|---|
| Odoo | customers, suppliers, products and services, quotations, orders and change orders, projects and tasks, milestones, logged time, purchase orders and receipts, deliveries, invoices, credit notes, payments, analytic accounts | budgets or forecasts of record, published reports |
| BENACTA data foundation | ingestion, snapshots and history, mappings, quality checks, reconciliation, analytical facts, reproducible calculations | business transactions |
| BENACTA planning (EPM scope) | budget baseline and revisions, forecasts, scenarios, estimate to complete and at completion, assumptions, submission, approval, locking, version history | actuals |
| Spreadsheet input (optional) | a place where people type assumptions | the only copy of an approved budget, a dependency to start |
| BENACTA Command Center | status reports, flash reports, alert queue, investigations, simulations, decisions and action follow-up | calculations that bypass the metric service |

Rules:

1. A plan version exists once, in `planning.plan_version`. Its lifecycle is `DRAFT -> SUBMITTED -> APPROVED -> LOCKED`.
   Lines of an approved or locked version cannot change (database trigger). A revision creates a new version that
   references its parent.
2. Every import, from CSV or a spreadsheet, goes `staging -> validation -> error report -> DRAFT version`. Provenance
   (author, source, timestamp, file hash) is kept. An empty cell stays empty; it never becomes zero.
3. `account.report.budget` is not a second source. If accounting reports need a budget, BENACTA exports a locked
   version to it one way, stamped with the version identifier; edits in Odoo are not read back.
4. Change orders live in Odoo as sale orders or quotations on the project. Approved (confirmed) change orders enter
   revenue at completion; pending ones only enter a `PENDING_CO` scenario.
5. Logged time is expected from Odoo timesheets. Until `hr_timesheet` is installed on the sandbox, synthetic timesheets
   use the same record shape in fixtures and the integration stays `NOT_VERIFIED`.
6. A published status report stores its figures, versions, rules and comments. Later data or plan changes produce a new
   report; they never alter a published one.
7. Revenue recognition is not derived from billing. Until a policy is declared and approved, recognised revenue is shown
   as unavailable.

## Consequences

- Budgets and forecasts are auditable and comparable over time; the flash report and status reports read the same
  locked versions.
- A planning UI and importer are needed in BENACTA; spreadsheets become optional.
- Installing `hr_timesheet` on the sandbox is a prerequisite to verify time-based metrics against Odoo.
- Consolidation, statutory reporting, tax and intercompany eliminations stay out of scope.
