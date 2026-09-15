# Project controlling model

Scope: the project controlling extension of the Lab (status reports, planning, resources, overdues). Decisions:
`docs/adr/0004-operational-analytical-planning-separation.md`. Metric contracts: `semantic/metrics.yml`.

## 1. The synthetic company

BENACTA DEMO, the fictional company of the margin dataset, is extended into an engineering and project delivery
company. The spares and components sales of dataset `demo_v1` become one business unit among three:

| Business unit | Code | Activity |
|---|---|---|
| Process Plants | PLANTS | engineering, procurement and construction of process units |
| Automation & Controls | AUTOMATION | automation and instrumentation engineering |
| Field Services & Spares | SERVICES | service interventions and spare parts (the existing sales dataset) |

Dataset `demo_v2` = `demo_v1` unchanged + projects, people, time, purchasing, billing and plans. All names, people,
customers, contracts and amounts are invented. The anchor date is configurable; by default the reporting cutoff is
2026-08-31 with 12 months of actuals and forecasts to project completion (monthly detail).

## 2. The chain every project must support

```text
contract -> order -> project -> work packages -> assignments and time -> purchases and costs -> milestones
         -> invoices -> receivables -> payments
```

| Link | Odoo 19 native field | Status on the connected instance | BENACTA handling |
|---|---|---|---|
| contract -> order | `sale.order` (confirmed) | native | contract = order of the project's originating line |
| order -> project | `project.project.sale_line_id`, `sale.order.line.project_id` | native (`sale_project`) | contract line via `sale_line_id`; change orders via `project_id` on other order lines |
| change order approval | `sale.order.state` (`sale` vs `draft`/`sent`) | native | confirmed = approved; quotation = pending |
| project -> work packages | `project.task` (`project_id`, `parent_id`, `allocated_hours`) | native | a top-level task is a work package; WBS code in an extension field |
| project -> business unit | `project.tags` | native | tag `BU/<code>`; mapping in BENACTA |
| project -> contract type, phase | none | missing | extension fields `x_benacta_contract_type`, `x_benacta_phase` (Studio) |
| project -> analytic account | `project.project.account_id` | native, unused on existing data | cost attribution key |
| work package -> assignments | `planning.slot` project link needs `project_forecast` | not installed | assignments planned in BENACTA planning |
| resource -> time | `account.analytic.line` with `project_id`, `task_id`, `employee_id` | **`hr_timesheet` not installed** | fixtures use the timesheet shape; NOT_VERIFIED against Odoo |
| resource -> cost rate | `hr.employee.hourly_cost` | native | labour cost = hours x hourly cost |
| resource -> skills | `hr.employee.skill` | native (`hr_skills`) | read for simulation |
| project -> purchases | `purchase.order.line.analytic_distribution` | native | project attribution by analytic account |
| purchase -> work package, cost category | none | missing | extension field `x_benacta_work_package`; cost category from product category |
| purchase -> receipt | `qty_received` | native | received-not-billed for accruals |
| purchase -> vendor bill | `account.move.line.purchase_line_id` | native | actual cost when posted |
| project -> milestones | `project.milestone` (`deadline`, `is_reached`, `reached_date`, `sale_line_id`, `quantity_percentage`) | native | milestone billing amount = percentage x line amount |
| milestone -> invoice | `sale.order.line.qty_delivered_method = milestones` then invoice lines `sale_line_ids` | native | billed amount by project through the sale line bridge |
| invoice -> receivable | `invoice_date_due`, `amount_residual`, `payment_state` | native | overdue at cutoff |
| receivable -> payment | `account.payment`, reconciliation | native | collected amount by payment date |
| budget and forecast | `account.report.budget` is per account only | no project budget workflow | BENACTA `planning` schema |
| declared physical progress, risks, assumptions | none | missing | BENACTA `planning.assumption` |

## 3. Planning model (BENACTA)

Dimensions: `company`, `business_unit`, `project`, `work_package`, `cost_category`, `resource_or_role`, `period`
(month), `currency`, `scenario`, `version`.

Measures: `planned_hours`, `planned_rate`, `planned_cost`, `planned_revenue`, `planned_billing`,
`planned_cash_collection`. A measure left empty is `NULL`, never zero.

| Version type | Content | Periods |
|---|---|---|
| `BUDGET_BASELINE` | initial approved budget at contract signature | full project life |
| `BUDGET_REVISED` | budget after approved change orders | full project life |
| `FORECAST` | estimate to complete at a cutoff | periods strictly after the cutoff |

Scenarios: `BASE`, `FAVOURABLE`, `UNFAVOURABLE`, `PENDING_CO`. Only `BASE` feeds the status report; other scenarios are
shown side by side and never replace it.

Lifecycle: `DRAFT -> SUBMITTED -> APPROVED -> LOCKED`. Maker-checker: the approver differs from the submitter.
Approved and locked versions are immutable in the database. A revision is a new version with `parent_version_id`.

Cost categories: `LABOUR`, `SUBCONTRACT`, `MATERIALS`, `CONTINGENCY`, `OTHER`. Revenue, billing and cash plans use
category `REVENUE`. Labour lines carry hours and rate; `planned_cost` must equal hours x rate when all three are given.

## 4. Canonical conventions

All project amounts are in company currency (EUR) excluding taxes, except receivables and cash, which are
tax-inclusive because they are what the customer pays.

**Actual cost to cutoff** = labour (timesheet hours x hourly cost, dated on or before the cutoff)
+ posted vendor bill lines attributed to the project (accounting date on or before the cutoff)
+ posted vendor credit notes (negative). Cost is recognised when the vendor bill is posted, not when paid.

**Open commitments at cutoff** = for each purchase order line attributed to the project and confirmed on or before
the cutoff: ordered amount - posted billed amount on or before the cutoff. Payment status is irrelevant: paying a bill
changes the liability and the cash, not the cost. A billed amount above the ordered amount is a data quality issue and
the line's commitment is zero, never negative. Received-not-billed amounts are reported separately for accrual review;
they remain inside open commitments.

**Estimate to complete (ETC)** = sum of `planned_cost` of the `BASE` forecast version for periods after the cutoff.
**Convention: ETC includes open commitments.** A forecast whose ETC for a cost category is below that category's open
commitments raises the data quality flag `ETC_BELOW_OPEN_COMMITMENTS`, and the figures are shown, not corrected.

**Estimate at completion (EAC)** = actual cost to cutoff + ETC. Open commitments are never added again. The
reconciliation detail is `EAC = actual cost + open commitments + uncommitted ETC`, where
`uncommitted ETC = ETC - open commitments`.

**Approved budget** = total `planned_cost` of the latest `BUDGET_REVISED` version in status APPROVED or LOCKED approved
on or before the cutoff, otherwise of the locked `BUDGET_BASELINE`.

**Cost variance at completion** = EAC - approved budget. Positive is unfavourable.

**Forecast revenue at completion (FRAC)**, basis `CONTRACT_APPROVED` = untaxed amount of the contract order + untaxed
amounts of change orders confirmed on or before the cutoff. Foreign currency contracts are converted at the fixed project
rate recorded at contract signature. Pending change orders appear only in the `PENDING_CO` scenario.

**Forecast margin at completion** = FRAC - EAC; **percentage** = margin / FRAC, null when FRAC is zero.

**Billed amount** = untaxed amount of posted customer invoices minus credit notes linked to the project's order lines,
dated on or before the cutoff. **Remaining to bill** = FRAC - billed amount.

**Collected amount** = payments dated on or before the cutoff reconciled with the project's invoices (tax-inclusive).
**Overdue amount** = for invoices dated on or before the cutoff, tax-inclusive amount minus collected amount where the
due date is before the cutoff. Ageing buckets: 1-30, 31-90, 91-180, 181-365, above 365 days past due.

**Physical progress** is declared per work package with weights by the project manager, with an evidence reference. It
is never computed from costs. **Cost consumption ratio** = actual cost / EAC, shown next to it and compared in a
consistency check, never substituted.

**Recognised revenue**: unavailable until an approved revenue recognition policy exists.

**Milestone delay**: a milestone with a deadline before the cutoff and not reached is late by `cutoff - deadline`
days. Its billing amount (percentage x contract line amount) moves to the period in which the current forecast plans it;
the change in planned billing and planned cash between the previous and current forecasts is the billing and cash
impact.

## 5. Status report (PSR)

One PSR per project and reporting period, built from one snapshot, one cutoff and the versions in force. Sections:
identity, contract and revenue, costs and forecast, execution, treasury, commentary. Each figure carries its metric
contract identifier and version identifiers. Status `DRAFT` until approved by a different person than the preparer;
then `PUBLISHED` and immutable. A later change produces a new PSR revision for the same period.

Commentary separates computed facts, supported hypotheses, unresolved questions, evidence references, recommendations,
owner and validation. A draft produced without a language model is labelled "sans LLM".

## 6. Deterministic scenarios in `demo_v2`

| Scenario | Project | What it proves |
|---|---|---|
| Healthy | PRJ-01 | no exception, EAC equals budget |
| Hours overrun and margin erosion | PRJ-02 | golden MARGIN-EROSION-001 decomposition |
| Late milestone | PRJ-02 | billing and cash shift between forecasts |
| Partially paid overdue invoice | PRJ-02 | overdue equals residual only |
| Commitment already in ETC | PRJ-03 | EAC not inflated by open commitments |
| Vendor bill already in actual cost | PRJ-04 | bill moves from commitment to actual once |
| Approved change order | PRJ-05 | revenue at completion and revised budget move together |
| Pending change order | PRJ-06 | only the PENDING_CO scenario changes |
| Foreign currency contract | PRJ-07 | fixed project rate for revenue, EUR costs |
| Missing forecast and missing time | PRJ-08 | UNKNOWN, never zero |
| Reconciliation inconsistency | PRJ-09 | vendor bill attributed to a different project than its purchase line |
| Locked version edit | PRJ-01 | database refuses the change |

Expected values for these scenarios are written by hand in `data/golden/projects_oracle_v1.yml`.
