# Margin Control: KPI and rule catalogue

Every figure the Command Center shows is computed by one of the functions listed here. Rules and thresholds are
versioned; every evaluation stores the rule version, the formula, the threshold set and every input it read
(`marts.fact_margin_rule_evaluation.evidence`). No language model touches any of them.

Metric contracts with owner, grain, null handling and tests: `semantic/metrics.yml` (`domain: margin`).
Thresholds: `data/policies/margin_thresholds.yml`. Governed terms: `data/policies/margin_policy_register.example.yml`.

## 1. KPIs (`app/margin/kpis.py`, `app/margin/engine.py`)

| KPI | Formula | Grain | Availability |
|---|---|---|---|
| Revenue | sum of posted customer invoice and credit note product lines, company currency (`-balance`) | company, period; customer, product, order on demand | always, with the period reconciliation status |
| Revenue goods / services | the same split by product type | company, period | always |
| COGS | sum of posted COGS journal items on direct cost accounts | company, period | `UNAVAILABLE` when goods were invoiced without any posted COGS |
| Gross margin | revenue minus COGS | company, period | `UNAVAILABLE` when COGS is unavailable |
| Gross margin percentage | gross margin over revenue, ratio of sums | company, period | null when revenue is zero |
| Goods gross margin percentage | (goods revenue minus COGS) over goods revenue; the deterioration signal reads this one | company, period | as above |
| Margin basis | `RECONCILED_COGS` when the COGS check reconciled, `MANAGEMENT_PROXY` when a difference remains, `UNAVAILABLE` otherwise | period | |
| Deteriorating | goods gross margin percentage fell by at least `gm_pct_deterioration_points` against the previous period | period | needs two periods |
| Discount, price, freight, cost leakage | sum of adverse exposures of confirmed and probable leakage by exposure type | period | |
| Total addressable leakage | leakage whose driver is at least partially controllable | period | |
| Recoverable from customer | leakage of the billing component (price, discount, freight); cost variances are never receivable | period | |
| Untraceable revenue | posted revenue with no order line behind it (potential exposure of `INVOICE_WITHOUT_SALE_LINK`) | period | |
| Margin at policy (illustrative) | gross margin plus every confirmed and probable leakage | period | labelled illustrative |
| Approved recovery, realised recovery, acceptance rate, time to decision, time to action | milestone 2 | | `NOT_MEASURED` today |

Line-level margin is never displayed unless revenue (bridge weight 1) and cost (`ATTRIBUTED` allocations) exist at
the same grain; otherwise the case shows the parts that exist and the reason the rest is unavailable.

## 2. Price baseline hierarchy (`app/margin/baseline.py`)

| Level | Basis | Source | Cause when the price is below it |
|---|---|---|---|
| 1 | `CONTRACT_PRICE` | `semantic.contract_price` valid on the order date, minimum quantity respected | `PRICE_BELOW_CONTRACT` |
| 2 | `CUSTOMER_PRICELIST` | most specific applicable item of the price list assigned to the customer | `PRICE_BELOW_CUSTOMER_PRICELIST` |
| 3 | `PRODUCT_LIST_PRICE` | product list price in company currency | `PRICE_BELOW_LIST_PRICE` |
| 4 | `HISTORICAL_COMPARABLE` | median confirmed price of the product over the trailing window, at least `min_observations`, dispersion (MAD over median) at most `max_dispersion_pct` | `PRICE_BELOW_HISTORICAL` (probable at most) |
| 5 | `UNAVAILABLE` | none of the above | `NO_PRICE_BASELINE`, insufficient evidence, no case |

The baseline is converted to the order currency at the rate valid on the order date and to the order unit of
measure. When the order applied a price list that is not the customer's and that list explains the price, the cause
is `PRICELIST_MISMATCH`.

## 3. Rules (`app/margin/rules.py`)

| Rule | Version | Grain | Outcome and class | Exposure |
|---|---|---|---|---|
| `DISCOUNT_CAP` | 1 | sale order line | `VIOLATION` (confirmed or probable leakage) when the discount exceeds the cap of the applicable policy without a valid derogation; `COMPLIANT` within the cap; `LEGITIMATE_EXCEPTION` with a derogation; `UNKNOWN` (`POLICY_EXPIRED`, `NO_POLICY`) and `CONFLICT` (`POLICY_CONFLICT`) are insufficient evidence for human review; `EXCLUDED` on cancelled or unconfirmed orders | discount, billing leakage: `qty x price_unit x (discount - cap) / 100` |
| `PRICE_BELOW_BASELINE` | 1 | sale order line | `VIOLATION` when `price_unit < baseline x (1 - price_tolerance_pct)`; freight lines not applicable | price, billing leakage: `qty x (baseline - price_unit)` |
| `FREIGHT_REBILL` | 1 | sale order | `VIOLATION` (`FREIGHT_NOT_INVOICED`, `FREIGHT_PARTIALLY_INVOICED`) once goods are fully delivered and invoiced under a rebill clause; `NOT_DUE` before (explained variance); `LEGITIMATE_EXCEPTION` for waived or included clauses; not applicable without a clause | freight, billing leakage: `contract amount - freight invoiced` |
| `COST_REFERENCE_VARIANCE` | 1 | sale order line | `VIOLATION` (`PURCHASE_PRICE_VARIANCE`) when the attributed receipt cost exceeds the frozen reference beyond both tolerances; `UNDETERMINED` (`MISSING_COST`, data quality) without full attribution; `UNKNOWN` (`NO_COST_REFERENCE`) without a reference; not applicable to services | cost, cost variance: `realised - reference x delivered units`; never receivable |
| `INVOICE_WITHOUT_SALE_LINK` | 1 | invoice line | `NO_SALE_LINK`, data quality, human review | potential exposure = the line's revenue |

Policy resolution: customer-scoped policies outrank segment policies by priority; two policies of the top priority
with different caps are a conflict; validity is checked on the order date.

## 4. Classification, severity, confidence, controllability

| Field | Values | Rule |
|---|---|---|
| Classification | `CONFIRMED_LEAKAGE`, `PROBABLE_LEAKAGE`, `EXPLAINED_VARIANCE`, `LEGITIMATE_EXCEPTION`, `DATA_QUALITY_ISSUE`, `INSUFFICIENT_EVIDENCE`, `COMPLIANT`, `NOT_APPLICABLE` | a violation is confirmed with `HIGH` confidence, probable otherwise |
| Confidence | `HIGH`, `MEDIUM`, `LOW` | `HIGH` when the period revenue reconciled and every invoice link has a known weight; `MEDIUM` with unresolved links, an unreconciled period or a historical baseline; `LOW` for unknown, conflict, undetermined and unlinked outcomes |
| Severity | `HIGH`, `MEDIUM`, `LOW`, `NONE` | on the adverse exposure, or on the potential exposure (an upper bound) when none can be computed; tiers in the thresholds file |
| Material | boolean | adverse or potential exposure at or above `materiality_min_exposure` |
| Controllability | `CONTROLLABLE` (discount, price, freight), `PARTIALLY_CONTROLLABLE` (purchase cost), `NOT_CONTROLLABLE`, `NOT_APPLICABLE` | per rule; currency effects are explained variances, not leakage |
| Exposure stage | `ORDERED`, `PARTIALLY_INVOICED`, `INVOICED` | where the leakage sits: an ordered line can still be corrected before invoicing |

A case (`decision.exception_case`) is created for confirmed and probable leakage, data-quality issues and
insufficient evidence, when the exception is material or flagged for human review. Compliant, legitimate and
explained evaluations are stored but never become cases; they are the false positives the engine did not raise.
A case the newest snapshot no longer raises is closed as `NO_LONGER_RAISED` with the reason recorded (the new
classification and cause, the rule version and the threshold set, or the subject's absence), never deleted.

## 5. Suggested follow-up

Each cause maps to one deterministic "Suggested follow-up" (`app/margin/service.py`), a proposal for a human,
never a decision. Milestone 2 turns it into an approvable recommendation; milestone 3 lets the investigation draft
a richer one from the same evidence.

## 6. Known limits

- Thresholds are demonstration settings for the synthetic company, not financial standards.
- Level 4 of the baseline is only ever probable; lump-sum or configured items get no historical baseline.
- Freight recharge is checked at order level; multi-order consolidated shipments are not modelled.
- Cost variance requires a frozen reference and FIFO attribution to receipts; average or standard costing is
  reported as undetermined until the costing method is supported.
- Currency effects are not yet isolated as a separate explained variance line; foreign-currency lines are compared
  at the order-date rate and pass or fail like any other line.
