# Financial reconciliation specification

The pilot is not credible unless the numbers tie. Every snapshot of the analytical foundation is reconciled
against its source before any margin figure is shown, and every closed period can be reported with its totals,
tolerance, timestamps and transformation version (`benacta reconciliation-report --period YYYY-MM`,
`GET /api/v1/reconciliation?period=`).

## 1. Checks (`app/marts/reconcile.py`)

| Check | Source total | Analytical total | Independence | Statuses |
|---|---|---|---|---|
| `REVENUE_POSTED` | server aggregate of posted customer invoice and credit note product lines (`account.move.line.balance`, negated), per company and month | `sum(marts.fact_invoice_line.revenue_company_ccy)` | `SERVER_AGGREGATE` on Odoo (`formatted_read_group`), `FIXTURE_CONTROL_TOTAL` on fixtures | `RECONCILED`, `UNRECONCILED`, `UNAVAILABLE` |
| `COGS_POSTED` | server aggregate of posted COGS items on expense accounts (`expense_direct_cost`, or `expense` where the chart has no direct cost type, as Odoo 19 with the French chart) | `sum(marts.fact_posted_cogs_line.balance)` | as above; `NONE` when goods were invoiced without any posted COGS | `RECONCILED`, `UNRECONCILED`, `UNAVAILABLE` |
| `INVOICE_HEADER_LINES` | `amount_untaxed_signed` of every posted revenue invoice header in the snapshot | sum of that invoice's product lines in the marts | `SOURCE_HEADER` (the source's own header, consistent with its lines by construction) | `RECONCILED`, `UNRECONCILED` with the mismatched invoices listed, `UNAVAILABLE` |

Tolerance: 0.01 in company currency on every check. Revenue and cost are compared at the same grain (company,
accounting month); customer, product, order and invoice totals are regroupings of the same reconciled lines, and
the invoice check ties every header to its lines.

## 2. Report fields per row

| Field | Meaning |
|---|---|
| `source_total`, `analytical_total`, `difference`, `tolerance` | the comparison |
| `status`, `explanation`, `detail` | the outcome and, for the invoice check, the mismatched documents |
| `independence` | how independent the control total is from our own extraction |
| `source_timestamp` | newest `write_date` of the accounting records behind the snapshot |
| `ingestion_timestamp` | when the ingestion batch finished |
| `transformation_version` | `marts.build.TRANSFORMATION_VERSION` stamped on the snapshot |

Period status: `RECONCILED` when every check of the period reconciled (COGS may be `UNAVAILABLE`, which flags the
margin basis), `BLOCKED` otherwise. A blocked period keeps its figures visible with the `UNRECONCILED` status; the
overview shows them as blocked and never fabricates precision.

## 3. Margin basis

| Basis | Condition | Consequence |
|---|---|---|
| `RECONCILED_COGS` | `COGS_POSTED` reconciled for the period | gross margin is a closing figure |
| `MANAGEMENT_PROXY` | a difference remains on the COGS check | gross margin shown with status `UNRECONCILED` |
| `UNAVAILABLE` | goods invoiced without posted COGS | gross margin unavailable for the period |

Cost baseline for line-level analysis: the frozen reference cost valid on the order date (`semantic.cost_reference`)
compared with the FIFO replay of receipts attributed to the delivery (`marts.fact_cost_allocation`); a replay that
differs from the Odoo move value, or a missing receipt layer, is `UNDETERMINED`, never zero.

## 4. Evidence on the connected Odoo (read-only runs)

- Revenue reconciles against server aggregates for every month of the connected instance (`VERIFIED_ODOO_READ`).
- No COGS is posted on that instance: margin on its data is a management proxy and cost rules abstain.
- None of its posted invoice lines links to an order line: price, discount and freight rules report untraceable
  revenue there. Order-level exceptions are demonstrated on the seeded dataset until the sandbox company is written.
