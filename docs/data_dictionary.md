# Data dictionary: analytical foundation, planning and project controlling

Database: BENACTA analytics PostgreSQL (`benacta_analytics`), never the Odoo database. Migrations:
`apps/api/migrations/versions/0001_foundation.py`, `0002_planning_and_reports.py`, `0003_project_marts.py`,
`0004_margin_control.py`. Money and quantities are `numeric`, handled as `Decimal` in code, never as floats.

## Schemas

| Schema | Owns | Written by |
|---|---|---|
| `raw` | Every observed source record version, batches, watermarks | `benacta ingest` |
| `staging` | `staging.records_at(instance, model, batch_seq)`: the consistent state of a model at a snapshot | function, no storage |
| `marts` | Snapshot-scoped dimensions, facts, bridges, data quality, reconciliation | `benacta marts`, `benacta reconcile` |
| `semantic` | Governed commercial terms (segments, discount policies, derogations, freight contracts, contract prices, cost references) with provenance | `benacta load-policies`, `benacta seed-fixtures` |
| `planning` | Budget and forecast versions, lines, assignments, assumptions, imports | `benacta seed-fixtures` (step plans), CSV import |
| `decision` | Exception cases, status reports, investigations, recommendations; later approvals and actions | `benacta exceptions`, `benacta psr --save`, `benacta investigate --save` |
| `audit` | Append-only hash-chained journal | every command |

## raw

| Table | Grain | Notes |
|---|---|---|
| `ingestion_batch` | one extraction run | `batch_seq` orders snapshots; status `RUNNING`, `SUCCEEDED`, `FAILED` |
| `batch_model_state` | one model inside a batch | counts, missing fields, watermark reached |
| `source_record_version` | one distinct content of a source record | key `(source_instance, source_model, source_id, version_no)`; `record_hash` is SHA-256 of canonical JSON; deletions are versions with `is_deletion` |
| `source_record_current` | latest version per source record | maintained in the same transaction as versions |
| `watermark` | one model per source instance | `(write_date, last_id)`; the next run starts at `write_date` minus the overlap window |

Provenance carried by every version: `source_instance`, `company_id`, `source_id`, `source_write_date` (UTC),
`extracted_at`, `record_hash`, `batch_id`.

## marts

Every table is keyed by `snapshot_id` (a succeeded ingestion batch). Rebuilding a snapshot replaces its rows.

| Table | Grain | Key columns | Notes |
|---|---|---|---|
| `dim_company` | company | `company_id` | company currency code |
| `dim_currency` | currency | `currency_id` | rounding step |
| `fx_rate` | dated rate | `company_id` (0 when shared), `currency_id`, `rate_date` | Odoo convention: units of currency per one unit of company currency |
| `dim_uom` | unit of measure | `uom_id` | `factor` relative to the root unit (Odoo 19) |
| `dim_partner` | partner | `partner_id` | views `dim_customer`, `dim_supplier`; `ref` is the business key of policies and contracts; `pricelist_id` the assigned price list |
| `dim_product` | product variant | `product_id` | type, storable flag, costing method and valuation of its category, list price |
| `dim_pricelist` | price list | `pricelist_id` | currency, active flag |
| `dim_pricelist_item` | price rule | `item_id` | applicability (variant, template, category, global), minimum quantity, fixed or percentage price, validity dates |
| `dim_account` | account | `account_id` | `account_type` separates income and direct cost |
| `dim_date` | calendar day | `date_day` | shared across snapshots |
| `fact_sales_order_line` | ordered line (sections and notes excluded) | `sale_line_id` | quantity in order unit and in product unit; company-currency subtotal at the rate valid on the order date; price list applied on the order |
| `fact_invoice_line` | posted customer invoice or credit note product line | `invoice_line_id` | quantity and subtotal signed negative for credit notes; `revenue_company_ccy = -balance` |
| `fact_posted_cogs_line` | posted COGS item on a direct cost account | `move_line_id` | empty when valuation is periodic |
| `fact_stock_move` | stock move | `move_id` | direction from the picking type; Odoo valuation `value` |
| `fact_cost_allocation` | slice of a delivered quantity attributed to a receipt | `delivery_move_id`, `allocation_no` | FIFO replay; `UNDETERMINED` when no valued receipt layer exists, when the replay differs from Odoo's move value, or when the costing method is not FIFO |
| `bridge_sale_invoice_line` | link between order line and invoice line | `sale_line_id`, `invoice_line_id` | from `sale_order_line_invoice_rel`; `allocation_weight` is 1 only when the invoice line belongs to a single order line, otherwise null and never summed |
| `data_quality_issue` | one issue on one source record | `issue_code`, `source_model`, `source_id` | `INVOICE_LINE_WITHOUT_SALE_LINE`, `FX_RATE_MISSING`, `UOM_UNRESOLVED`, `ORDER_LINE_WITHOUT_ORDER` |
| `reconciliation_result` | one check per company and month | `check_id`, `company_id`, `period` | see below; carries `tolerance`, `source_timestamp`, `ingested_at`, `transformation_version`, `detail` |
| `fact_margin_rule_evaluation` | one rule applied to one subject (order line, order, invoice line) | `rule_id`, `subject_type`, `subject_id` | outcome, classification, cause, amounts in company currency, severity, confidence, controllability, materiality, `evidence` JSON with every input, formula and threshold version; every outcome is stored, including compliant ones |
| `fact_margin_period` | gross margin per company and accounting month | `company_id`, `period` | revenue (goods and services), COGS, gross margin and percentage, basis and status from the reconciliation, leakage by type, addressable and recoverable amounts, untraceable revenue, exception counts |

### Project marts (migration `0003_project_marts`)

Built by `app/marts/project_build.py` from the same snapshot. Classification rules come from
`data/mappings/project_mappings.yml` (business unit and internal tags, cost category by product category, role by job).

| Table | Grain | Key columns | Notes |
|---|---|---|---|
| `dim_project` | project | `project_id` | `project_code` is the analytic account code; business unit from the `BU/` tag; internal projects carry an `INTERNAL/` hour category; contract sale line, contract currency and fixed project rate |
| `dim_work_package` | top-level task of a project | `task_id` | WBS code; change order scope flag; subtasks and private to-dos without a project are excluded |
| `dim_milestone` | milestone | `milestone_id` | deadline, reached date, billing amount = linked sale line subtotal × quantity percentage; null when no sale line |
| `dim_employee` | employee | `employee_id` | employee code, role from the job, hourly cost, external flag, department, hours per day |
| `fact_timesheet` | time entry | `line_id` | hours and cost from `account.analytic.line` with a project (`hr_timesheet` shape); cost stored positive (Odoo amount is negative) |
| `fact_purchase_commitment` | purchase order line with a project analytic | `purchase_line_id` | ordered amount, cost category, work package; open commitment is computed at a cutoff, never stored |
| `fact_vendor_bill_line` | posted vendor bill or refund product line | `move_line_id` | project inherited from the purchase line; a different analytic project raises `VENDOR_BILL_PROJECT_MISMATCH` |
| `fact_receivable` | posted customer invoice or credit note | `invoice_id` | project from the contract or change order lines; untaxed, total, residual and due date |
| `fact_customer_payment` | inbound payment allocated to an invoice | `payment_id`, `invoice_id` | payments in date order, split across their reconciled invoices up to each invoice total |
| `fact_change_order` | sale order linked to a project, per project | `sale_order_id`, `project_id` | `is_contract` separates the contract from change orders; confirmed change order = approved, draft or sent = pending |

## semantic (migration `0004_margin_control`)

Governed commercial terms keyed by business references (`customer_ref` = partner `ref`, `product_code` = product
internal reference), never by Odoo ids, so the rules read the same terms whatever the system of record. Each row
carries `owner`, `source`, `valid_from`, `valid_to` and the `load_id` of its provenance.

| Table | Grain | Notes |
|---|---|---|
| `reference_load` | one load of terms for an instance and company | source kind `FIXTURE_TERMS` or `POLICY_REGISTER`, file reference, content hash, actor, row counts |
| `customer_segment` | customer and validity | segment used by segment-scoped policies |
| `discount_policy` | policy version | scope by segment or customer, cap, priority, validity |
| `discount_derogation` | one approved derogation | order reference, cap, approving role, validity, evidence reference |
| `freight_contract` | one clause per customer | `rebill`, `waived` or `included`, amount, currency, trigger |
| `contract_price` | contract and product | unit price, currency, minimum quantity, validity |
| `cost_reference` | reference and product | frozen unit cost, freeze date, validity |

## planning (migration `0002_planning_and_reports`)

Owned by BENACTA (ADR-0004). Odoo has no equivalent for versioned project plans.

| Table | Grain | Notes |
|---|---|---|
| `plan_version` | one budget or forecast version of a project and scenario | types `BUDGET_BASELINE`, `BUDGET_REVISED`, `FORECAST`; scenarios `BASE`, `FAVOURABLE`, `UNFAVOURABLE`, `PENDING_CO`; status moves forward only `DRAFT` → `SUBMITTED` → `APPROVED` → `LOCKED`; approver differs from submitter; a forecast needs a cutoff date; budgets store their effective date there |
| `plan_line` | work package × cost category × resource or role × month | hours, rate, cost, revenue, billing, cash collection; null means not provided, never zero; triggers refuse any change to lines of an `APPROVED` or `LOCKED` version |
| `assignment` | planned hours of one person on one work package and month | input of the Resources Monitoring view (sprint E) |
| `assumption` | one stated assumption of a version, per work package | numeric or text value, author, evidence reference, recording time; frozen with its version; the investigation cites it as a statement, not as a verified fact |
| `import_batch` | one CSV, spreadsheet, UI or seed submission | file hash, row count, error count, control totals, status `VALIDATED` or `REJECTED`, resulting version |
| `import_error` | one issue on one row | row number, field, code, message; a rejected import creates no version |

## decision

| Table | Grain | Notes |
|---|---|---|
| `exception_case` | the stable identity of one exception (rule and subject) across snapshots | `case_ref` (`MC-000001`), first and last snapshot, latest classification, cause, severity and exposures; status `NEW` until milestone 2 adds the workflow; `NO_LONGER_RAISED` with `resolved_note` when the newest snapshot stops raising it; never deleted |
| `project_status_report` | one revision of a project status report per period | content JSON and its hash, plan versions and snapshot used; `DRAFT` or `PUBLISHED`; a published revision is immutable (trigger); publisher differs from preparer; a correction is a new revision |
| `investigation` | one investigation run | question, mode `DETERMINISTIC_NO_LLM` or `LLM`, status `COMPLETED`, `ABSTAINED` or `FAILED`, full report |
| `recommendation` | one proposed action of an investigation | `action_key` and version; created `PENDING_REVIEW`, never executed without approval |

## Reconciliation statuses

| Status | Meaning |
|---|---|
| `RECONCILED` | marts total equals the control total within 0.01 |
| `PARTIAL` | reserved for decompositions with an explained residual |
| `UNRECONCILED` | a difference remains; the explanation lists the possible causes |
| `UNAVAILABLE` | no control total can be computed, or goods were invoiced without any posted COGS |

`independence` states how independent the control total is: `SERVER_AGGREGATE` (Odoo `formatted_read_group`
computed by the server), `FIXTURE_CONTROL_TOTAL` (the fixture source itself, not independent evidence),
`SOURCE_HEADER` (the source's own invoice headers against their lines) or `NONE`. Specification and report:
`docs/reconciliation_specification.md`.

Margin basis: `RECONCILED_COGS` only when every COGS check reconciled; otherwise `MANAGEMENT_PROXY`.

## Known limits

- Dates are UTC calendar dates of Odoo datetimes; company time zones are not applied yet.
- The Odoo API has no cross-call snapshot: a batch is consistent per record and the overlap window catches
  changes committed during extraction.
- Computed, non-stored Odoo fields (`stock.move.is_valued`, `remaining_value`) are read at extraction time and
  are not a stable history.
