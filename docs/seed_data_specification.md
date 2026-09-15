# Seed data specification

Two synthetic profiles, one generator lineage, one ingestion path. Every name, customer, supplier, product,
person and amount is invented. Ground truth lives apart from the records and is versioned under `data/golden/`,
which application code cannot read.

| Profile | Purpose | Window | Volumes | Where |
|---|---|---|---|---|
| `dev` (`demo_v1` + projects = `demo_v2`) | automated tests, local development, the command-line demo | 90 days to 2026-08-31, plus 12 months of project actuals | 24 customers, 5 suppliers, 18 products, 123 orders, 20 projects, 40 people | `app/fixtures/demo_dataset.py`, `app/fixtures/projects_dataset.py` |
| `full` (`demo_full`) | the demonstration company: realistic distributions at pilot scale | 36 months to 2026-08-31 | 505 customers, 100 suppliers, 213 products, about 9 500 orders and 20 900 order lines, about 5 800 purchase orders with 8 900 lines, about 9 700 invoices and 76 500 journal items, about 26 700 stock moves, about 8 200 payments | `app/fixtures/full_profile.py` |

Commands: `benacta seed-fixtures` (dev), `benacta seed-fixtures --profile full`; the views read the profile named
by `BENACTA_FIXTURE_PROFILE` (`dev` or `full`).

## 1. Company

BENACTA DEMO, an industrial supplier of instrumentation, valves, drives, control, safety, spares, consumables,
enclosures and tooling, based in France, selling across Europe with a few customers in the United Kingdom, the
United States and Switzerland. Company currency EUR; French VAT at 20 % on customer invoices; FIFO valuation with
perpetual accounting on goods (posted cost of goods sold), so gross margin reconciles.

The project extension (`demo_v2`) adds three business units, engineering projects, milestones, people, time
entries, purchases and milestone billing; it is documented in `docs/project_controlling_model.md` and kept as an
engine family.

## 2. Distributions of the demonstration profile

| Dimension | Rule |
|---|---|
| Customers | 500 generated names; country weights FR 70 %, DE 8, BE 6, ES 4, IT 4, NL 3, GB 2, US 2, CH 1; segment key account 6 %, distributor 14 %, standard 80 %; size large 5 %, medium 25 %, small 50 %, long tail 20 % |
| Order frequency | large 3 orders a month, medium 1, small 0.25, tail 0.03; times a monthly seasonality (August trough, spring and autumn peaks) and 4 % growth a year; key accounts push volume by 60 % in year three |
| Lines | 1 to 4 lines per order (45 / 30 / 17 / 8 %); the first eight products of each family carry most lines (long tail); spare parts and consumables weigh twice as much in year three (mix shift) |
| Prices | product list price; distributors on a price list at 88 % of list; twenty key accounts hold contract prices at 93 % of list on three products; discounts within the segment cap (0 to 5 % standard, up to 10 % key accounts, none for distributors on top of their list) |
| Currency | orders in the customer's currency; one rate per month per currency with a slow drift |
| Freight | 30 % of customers on a rebill clause (150 to 400 EUR by size), 10 % waived; rebill orders carry the freight line |
| Deliveries and invoicing | delivered 1 to 5 days after the order (10 % late, 8 to 21 days), never beyond the cost quarter of the order; invoiced 1 to 3 days after delivery; 5 % of orders partially delivered with an open backorder; orders near the anchor stay undelivered or uninvoiced |
| Refunds | 2 % of invoiced orders receive a partial credit note 5 to 20 days later, never after the anchor |
| Payments | terms 30, 45 or 60 days; 60 % paid within a few days of due date, 30 % late by 5 to 40 days, 10 % unpaid; due dates and payment states carried on invoices |
| Purchasing | just-in-time replenishment: one purchase order per supplier on the first and on the fifteenth of each month, sized on the deliveries of the half-month it serves, received the same day at the reference cost of the quarter; no safety stock, so every layer is consumed within its half-month |
| Costs | reference unit cost per product per quarter, drifting 1 to 4 % a year by family with supplier noise; frozen the day before the quarter. Deliveries are valued from the receipt layers they consume, in the order the marts replay FIFO, so the recorded move value and the replay agree and background lines never show a cost variance |

## 3. Injected scenarios (ground truth `data/golden/demo_full_manifest_v1.json`)

Eighty scenario instances, most of them not raised on purpose:

| Family | Instances | Expected outcome |
|---|---|---|
| Unauthorised discount | 12 | confirmed leakage, `DISCOUNT_ABOVE_CAP` |
| Management-approved exception (derogation) | 6 | legitimate exception, never raised |
| Invoiced below contract price | 6 | confirmed leakage, `PRICE_BELOW_CONTRACT` |
| Incorrect price-list application | 5 | confirmed leakage, `PRICELIST_MISMATCH` |
| Freight not recharged | 8 | confirmed leakage, `FREIGHT_NOT_INVOICED` |
| Partial freight recharge | 4 | confirmed leakage, `FREIGHT_PARTIALLY_INVOICED` |
| Freight waived by contract | 5 | legitimate exception, never raised |
| Purchase price variance | 8 | confirmed leakage, `PURCHASE_PRICE_VARIANCE`, not receivable |
| Missing cost | 3 | data-quality issue, `MISSING_COST` |
| Distributor policy gap | 2 | insufficient evidence, `POLICY_EXPIRED` |
| Conflicting customer policies | 1 | insufficient evidence, `POLICY_CONFLICT` |
| Product mapping (unit of measure unresolved) | 3 | data-quality issue, `UNRESOLVED_UNIT_OR_PRODUCT` |
| Credit note after invoice | 10 | compliant, never raised |
| Currency effect | 3 | compliant at the order-date rate, never raised |
| Invoice without order | 4 | data-quality issue, `INVOICE_WITHOUT_ORDER` |
| Margin erosion hidden by volume and mix | period signal | goods gross-margin percentage of year three at least one point below year two |

Each instance records identifier, family, rule, subject, order date, period, expected outcome, class, cause,
amounts, materiality, whether a case is created, root cause, evidence, recommended action.

## 4. Guarantees and how they are tested

| Guarantee | Test |
|---|---|
| Deterministic across processes (no set iteration decides an identifier) | `test_generation_is_deterministic` (dev), `test_full_profile.py::test_generation_is_deterministic` (full, opt-in) |
| Referential integrity: every line has its order and product, every journal item its move, every payment its invoice; every journal entry balances; every sold good has a receipt except the missing-cost scenarios and the freight service | `test_referential_integrity` |
| Realistic distributions: seasonality, growth, currencies, customer concentration, long tails, payment states, refunds, backorders, cost drift | `test_realistic_distributions` |
| Ground truth separate from records and equal to the committed manifest | `test_ground_truth_is_separate_and_versioned` |
| The pipeline reconciles every month, detects every injected scenario as expected, raises nothing else, and shows the year-three deterioration | `test_full_profile_pipeline.py` (opt-in, `BENACTA_FULL_PROFILE=1`); the same checks on the development database after `benacta seed-fixtures --profile full` with `scripts/verify_full_profile.py` |
| Idempotent seed: replaying the pipeline adds no record version and no case | ingestion and engine replay tests |

## 5. Limits

- Purchases are in EUR; supplier currencies and lead-time variance are not modelled.
- Inventory locations, backorder pickings and stock counts are not modelled beyond partial deliveries; purchasing is
  just in time, so no stock is carried between half-months and no timing variance arises between the frozen reference
  of an order and the receipt cost of its delivery.
- Tax configuration is one rate; intra-community and export treatments are not modelled.
- The Odoo seed of the demonstration profile is not written yet; the profile runs on the embedded database.
