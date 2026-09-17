# Anomaly ground-truth catalogue

Ground truth lives in hand-written oracles that application code cannot read (`data/golden/oracle_v1.yml`, enforced
by `test_application_code_never_reads_the_oracle`). The engine detects from business data and governed terms only;
tests compare its output with the oracle. Every scenario carries a rule, an expected outcome and class, a cause,
the affected references, the expected amounts, the evidence the case must show, the suggested action, severity and
controllability.

## Status of the 18 requested scenarios

| # | Scenario | Dataset case | Rule | Expected class | Status |
|---|---|---|---|---|---|
| 1 | Unauthorised discount above the threshold | DISC-001 (1 000 EUR), NEG-12 (500 EUR) | `DISCOUNT_CAP` | confirmed leakage | TESTED_LOCAL |
| 2 | Customer invoiced below the contractual price | PRICE-001 (600 EUR) | `PRICE_BELOW_BASELINE` level 1 | confirmed leakage | TESTED_LOCAL |
| 3 | Incorrect price-list application | PLIST-001 (400 EUR) | `PRICE_BELOW_BASELINE`, cause `PRICELIST_MISMATCH` | confirmed leakage | TESTED_LOCAL |
| 4 | Freight incurred but not recharged | FREIGHT-001 (250 EUR) | `FREIGHT_REBILL` | confirmed leakage | TESTED_LOCAL |
| 5 | Partial freight recharge | FREIGHT-002 (150 EUR, below materiality: counted, not queued) | `FREIGHT_REBILL`, cause `FREIGHT_PARTIALLY_INVOICED` | confirmed leakage | TESTED_LOCAL |
| 6 | Standard-cost drift after supplier price increases | COST-001 (800 EUR) | `COST_REFERENCE_VARIANCE` | confirmed leakage | TESTED_LOCAL |
| 7 | Purchase-price variance on product margin | NEG-12 (400 EUR) | `COST_REFERENCE_VARIANCE` | confirmed leakage | TESTED_LOCAL |
| 8 | Margin erosion hidden by volume | demonstration profile: key accounts push volume by 60 % in year three on a low-margin mix | period KPI: goods margin percentage falling while revenue grows | deterioration signal | TESTED_LOCAL (opt-in full-profile gate) |
| 9 | Credit note issued after the initial invoice | NEG-04 | `DISCOUNT_CAP` at the cap, signed refund in revenue | compliant | TESTED_LOCAL |
| 10 | Product or customer mix deterioration | demonstration profile: spare parts and consumables weigh twice as much in year three | goods gross-margin percentage of year three at least one point below year two | deterioration signal (a mix line in the bridge is still planned) | TESTED_LOCAL (opt-in) |
| 11 | Currency effect that explains a variance | NEG-07 | `PRICE_BELOW_BASELINE` at the order-date rate | compliant | TESTED_LOCAL; a separate currency line in the bridge is planned |
| 12 | Incorrect product or customer mapping | FULL-MAP-001 to 003 (product without a resolvable unit of measure) | `PRODUCT_MAPPING` | data-quality issue (`UNRESOLVED_UNIT_OR_PRODUCT`) | TESTED_LOCAL (opt-in) |
| 13 | Missing or delayed cost posting | NEG-08 | `COST_REFERENCE_VARIANCE` | data-quality issue (`MISSING_COST`) | TESTED_LOCAL |
| 14 | Invoice and delivery timing mismatch | NEG-03 | `FREIGHT_REBILL` not due on partial delivery | explained variance | TESTED_LOCAL |
| 15 | Project costs posted to the wrong analytic account | PRJ-06 vendor bill (project controlling dataset) | `VENDOR_BILL_PROJECT_MISMATCH` data-quality flag | data-quality issue | TESTED_LOCAL in the project marts; not a margin case yet |
| 16 | Legitimate low-margin transaction that must not be flagged | NEG-02 (waived freight), background low-cap lines | `FREIGHT_REBILL`, `DISCOUNT_CAP` | legitimate exception, compliant | TESTED_LOCAL |
| 17 | Exceptional transaction approved by management | NEG-01 (derogation DEROG-2026-014) | `DISCOUNT_CAP` | legitimate exception | TESTED_LOCAL |
| 18 | Data-quality issue that prevents a reliable recommendation | NEG-09 (expired policy), NEG-10 (conflicting policies), NEG-11 (invoice without order) | `DISCOUNT_CAP`, `INVOICE_WITHOUT_SALE_LINK` | insufficient evidence, data-quality issue | TESTED_LOCAL |

Negative controls also cover: cancelled orders (NEG-05, excluded), units of measure (NEG-06), and two anomalies on
one line counted once per component (NEG-12).

## Totals the engine must reproduce on `demo_v1`

| Total | Amount (EUR) |
|---|---|
| Discount leakage | 1 500.00 |
| Price leakage | 1 000.00 |
| Freight leakage | 400.00 |
| Billing leakage | 2 900.00 |
| Cost variance | 1 200.00 |
| Combined exposure | 4 100.00 |
| Confirmed leakage exceptions | 8 (7 material cases) |
| Exceptions on background orders | 0 |
| Cases requiring human review | 4 |
| Legitimate exceptions, never raised | 2 |

## Where each scenario keeps its ground truth

- Dataset generator: `apps/api/app/fixtures/demo_dataset.py` (records only; no expected outcome).
- Oracle: `data/golden/oracle_v1.yml` (expected rule, outcome, class, cause, amounts, evidence facts).
- Tests: `apps/api/tests/integration/test_margin_engine_oracle.py` (engine against the oracle),
  `apps/api/tests/unit/test_margin_rules.py` (every outcome of every rule on hand-built facts).

The demonstration profile carries eighty scenario instances across fourteen families in its own manifest
(`data/golden/demo_full_manifest_v1.json`, exported by `scripts/export_ground_truth.py`, checked equal to the generated
ground truth by `tests/unit/test_full_profile.py`); the pipeline test `tests/integration/test_full_profile_pipeline.py`
verifies every instance and the absence of any other exception. Specification: `docs/seed_data_specification.md`.
