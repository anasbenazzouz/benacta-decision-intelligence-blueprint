"""Deterministic margin rules. Pure functions over typed facts: no database, no model, no randomness.

Each rule returns one `RuleResult` whose outcome vocabulary matches the hand-written oracle
(`VIOLATION, COMPLIANT, NOT_DUE, EXCLUDED, UNDETERMINED, UNKNOWN, CONFLICT, NO_SALE_LINK`) and whose
classification is one of the six decision classes a Finance team acts on, plus `COMPLIANT` and
`NOT_APPLICABLE` for evaluations that raise nothing. Amounts in the result are in company currency; the
order-currency figures and every input the rule read are kept in `evidence`.

Rule versions are part of the result. Changing a formula means a new version, never a silent edit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.margin.thresholds import Thresholds
from app.numbers import decimal_text

CENT = Decimal("0.01")
HUNDRED = Decimal(100)

RULES: dict[str, dict[str, Any]] = {
    "DISCOUNT_CAP": {
        "version": 1,
        "name": "Discount above the approved policy",
        "grain": "sale order line",
        "exposure_type": "discount",
        "component": "billing_leakage",
        "formula": "adverse_exposure = qty_ordered x price_unit x (discount_pct - allowed_discount_pct) / 100, "
                   "when discount_pct > allowed_discount_pct and no valid derogation covers the discount",
        "controllability": "CONTROLLABLE",
    },
    "PRICE_BELOW_BASELINE": {
        "version": 1,
        "name": "Unit price below the approved baseline",
        "grain": "sale order line",
        "exposure_type": "price",
        "component": "billing_leakage",
        "formula": "adverse_exposure = qty_ordered x (baseline_unit_price - price_unit), when price_unit < baseline_unit_price "
                   "x (1 - price_tolerance_pct / 100); baseline from the hierarchy contract price > customer price list > "
                   "product list price > historical comparable",
        "controllability": "CONTROLLABLE",
    },
    "FREIGHT_REBILL": {
        "version": 1,
        "name": "Contractual freight not recharged",
        "grain": "sale order",
        "exposure_type": "freight",
        "component": "billing_leakage",
        "formula": "adverse_exposure = contract_amount - freight_invoiced, once every goods line is fully delivered and "
                   "invoiced under a rebill clause; NOT_DUE before the trigger; waived clauses are compliant",
        "controllability": "CONTROLLABLE",
    },
    "COST_REFERENCE_VARIANCE": {
        "version": 1,
        "name": "Realised cost above the frozen reference cost",
        "grain": "sale order line",
        "exposure_type": "cost",
        "component": "cost_variance",
        "formula": "adverse_exposure = sum(attributed receipt cost of the delivered units) - reference_unit_cost x delivered_units, "
                   "when both the absolute and the relative tolerance are exceeded; UNDETERMINED without full attribution",
        "controllability": "PARTIALLY_CONTROLLABLE",
    },
    "INVOICE_WITHOUT_SALE_LINK": {
        "version": 1,
        "name": "Posted revenue not traceable to an order line",
        "grain": "invoice line",
        "exposure_type": None,
        "component": None,
        "formula": "potential_exposure = revenue of the invoice line; no leakage is computed because no order, policy "
                   "or baseline can be matched",
        "controllability": "NOT_APPLICABLE",
    },
}


# --------------------------------------------------------------------------- typed facts
@dataclass(frozen=True)
class InvoiceRef:
    invoice_id: int
    invoice_name: str
    move_type: str
    period: str
    subtotal_signed: Decimal
    revenue_company_ccy: Decimal
    allocation_weight: Decimal | None


@dataclass(frozen=True)
class LineFacts:
    sale_line_id: int
    sale_order_id: int
    order_name: str
    order_state: str
    order_date: date
    company_id: int
    customer_id: int | None
    customer_ref: str | None
    product_id: int | None
    product_code: str | None
    product_name: str | None
    product_type: str
    is_storable: bool | None
    is_freight: bool
    currency_code: str
    company_currency: str
    fx_rate: Decimal | None
    qty_ordered: Decimal
    qty_product_uom: Decimal | None
    price_unit: Decimal
    discount_pct: Decimal
    subtotal: Decimal
    qty_delivered: Decimal
    qty_invoiced: Decimal
    invoices: tuple[InvoiceRef, ...] = ()
    pricelist_id: int | None = None
    customer_pricelist_id: int | None = None
    list_price: Decimal | None = None
    period_reconciled: bool = True

    @property
    def invoice_links_unresolved(self) -> bool:
        return any(i.allocation_weight is None for i in self.invoices)

    @property
    def invoiced_subtotal(self) -> Decimal | None:
        if self.invoice_links_unresolved:
            return None
        return sum((i.subtotal_signed * i.allocation_weight for i in self.invoices), Decimal(0))

    @property
    def period(self) -> str:
        invoiced = [i for i in self.invoices if i.move_type == "out_invoice"]
        if invoiced:
            return min(i.period for i in invoiced)
        return f"{self.order_date.year}-{self.order_date.month:02d}"

    @property
    def exposure_stage(self) -> str:
        if self.qty_invoiced <= 0:
            return "ORDERED"
        return "INVOICED" if self.qty_invoiced >= self.qty_ordered else "PARTIALLY_INVOICED"


@dataclass(frozen=True)
class Allocation:
    delivery_move_id: int
    receipt_move_id: int | None
    quantity: Decimal
    unit_cost: Decimal | None
    amount: Decimal | None
    status: str
    reason: str | None


@dataclass(frozen=True)
class CostFacts:
    allocations: tuple[Allocation, ...]
    delivered_units: Decimal
    reference: dict[str, Any] | None


@dataclass(frozen=True)
class Baseline:
    level: int | None
    basis: str
    unit_price: Decimal | None
    reference: dict[str, Any] = field(default_factory=dict)
    order_pricelist_price: Decimal | None = None


@dataclass(frozen=True)
class OrderFacts:
    sale_order_id: int
    order_name: str
    order_state: str
    order_date: date
    company_id: int
    customer_id: int | None
    customer_ref: str | None
    currency_code: str
    fx_rate: Decimal | None
    goods_lines: tuple[LineFacts, ...]
    freight_lines: tuple[LineFacts, ...]
    freight_invoiced: Decimal
    freight_invoice_refs: tuple[dict[str, Any], ...] = ()
    period_reconciled: bool = True

    @property
    def goods_delivered_all(self) -> bool:
        return bool(self.goods_lines) and all(line.qty_delivered >= line.qty_ordered for line in self.goods_lines)

    @property
    def goods_invoiced_all(self) -> bool:
        return bool(self.goods_lines) and all(line.qty_invoiced >= line.qty_ordered for line in self.goods_lines)

    @property
    def period(self) -> str:
        return min((line.period for line in self.goods_lines), default=f"{self.order_date.year}-{self.order_date.month:02d}")


@dataclass(frozen=True)
class UnlinkedInvoiceLine:
    invoice_line_id: int
    invoice_id: int
    invoice_name: str
    move_type: str
    company_id: int
    customer_id: int | None
    product_id: int | None
    product_code: str | None
    period: str
    accounting_date: date
    revenue_company_ccy: Decimal
    period_reconciled: bool = True


@dataclass
class RuleResult:
    rule_id: str
    rule_version: int
    outcome: str
    classification: str
    cause: str
    exposure_type: str | None
    component: str | None
    expected_amount: Decimal | None
    actual_amount: Decimal | None
    adverse_exposure: Decimal | None
    potential_exposure: Decimal | None
    exposure_stage: str | None
    severity: str
    confidence: str
    controllability: str
    material: bool
    requires_human_review: bool
    evidence: dict[str, Any]
    formula: str
    reason: str

    @property
    def creates_case(self) -> bool:
        return self.classification in {"CONFIRMED_LEAKAGE", "PROBABLE_LEAKAGE", "DATA_QUALITY_ISSUE", "INSUFFICIENT_EVIDENCE"} and (
            self.material or self.requires_human_review
        )


# --------------------------------------------------------------------------- helpers
def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def to_company(amount: Decimal | None, fx_rate: Decimal | None) -> Decimal | None:
    """Order currency to company currency. `fx_rate` is units of order currency per company unit (Odoo convention)."""
    if amount is None:
        return None
    return money(amount / fx_rate) if fx_rate else money(amount)


def _fmt(value: Decimal | None) -> str | None:
    return None if value is None else str(money(value))


def _num(value: Decimal | None) -> str | None:
    """Percentages, quantities, weights and rates: no forced decimals (money keeps two through `_fmt`)."""
    return decimal_text(value, min_decimals=0)


def _result(rule_id: str, outcome: str, classification: str, cause: str, *, thresholds: Thresholds, evidence: dict[str, Any],
            reason: str, expected: Decimal | None = None, actual: Decimal | None = None, adverse: Decimal | None = None,
            potential: Decimal | None = None, stage: str | None = None, confidence: str = "HIGH",
            requires_review: bool = False, controllability: str | None = None) -> RuleResult:
    spec = RULES[rule_id]
    raises = classification in {"CONFIRMED_LEAKAGE", "PROBABLE_LEAKAGE", "DATA_QUALITY_ISSUE", "INSUFFICIENT_EVIDENCE"}
    # Severity and materiality follow the adverse exposure; when none can be computed, the potential exposure (an upper bound).
    basis = adverse if adverse else potential
    return RuleResult(
        rule_id=rule_id,
        rule_version=spec["version"],
        outcome=outcome,
        classification=classification,
        cause=cause,
        exposure_type=spec["exposure_type"],
        component=spec["component"],
        expected_amount=None if expected is None else money(expected),
        actual_amount=None if actual is None else money(actual),
        adverse_exposure=None if adverse is None else money(adverse),
        potential_exposure=None if potential is None else money(potential),
        exposure_stage=stage,
        severity=thresholds.severity(basis) if raises else "NONE",
        confidence=confidence,
        controllability=controllability or (spec["controllability"] if raises else "NOT_APPLICABLE"),
        material=thresholds.is_material(basis) if raises else False,
        requires_human_review=requires_review,
        evidence={**evidence, "thresholds": thresholds.stamp},
        formula=spec["formula"],
        reason=reason,
    )


def _violation_class(confidence: str) -> str:
    return "CONFIRMED_LEAKAGE" if confidence == "HIGH" else "PROBABLE_LEAKAGE"


def _line_confidence(line: LineFacts, *extra_downgrades: bool) -> str:
    if line.invoice_links_unresolved or not line.period_reconciled or any(extra_downgrades):
        return "MEDIUM"
    return "HIGH"


def _line_evidence(line: LineFacts) -> dict[str, Any]:
    return {
        "sale_line_id": line.sale_line_id,
        "order": line.order_name,
        "order_state": line.order_state,
        "order_date": str(line.order_date),
        "customer_ref": line.customer_ref,
        "product_code": line.product_code,
        "currency": line.currency_code,
        "fx_rate": _num(line.fx_rate),
        "qty_ordered": _num(line.qty_ordered),
        "qty_delivered": _num(line.qty_delivered),
        "qty_invoiced": _num(line.qty_invoiced),
        "price_unit": _num(line.price_unit),
        "discount_pct": _num(line.discount_pct),
        "subtotal": _num(line.subtotal),
        "invoiced_subtotal": _fmt(line.invoiced_subtotal),
        "invoices": [
            {"invoice_id": i.invoice_id, "name": i.invoice_name, "type": i.move_type, "period": i.period,
             "subtotal_signed": _num(i.subtotal_signed), "allocation_weight": _num(i.allocation_weight)}
            for i in line.invoices
        ],
        "invoice_links_unresolved": line.invoice_links_unresolved,
        "period_revenue_reconciled": line.period_reconciled,
    }


def _excluded(rule_id: str, line: LineFacts, thresholds: Thresholds) -> RuleResult | None:
    if line.order_state == "sale":
        return None
    cause = "ORDER_CANCELLED" if line.order_state == "cancel" else "ORDER_NOT_CONFIRMED"
    return _result(rule_id, "EXCLUDED", "NOT_APPLICABLE", cause, thresholds=thresholds, evidence=_line_evidence(line),
                   reason=f"order state {line.order_state}: no commitment to evaluate")


# --------------------------------------------------------------------------- DISCOUNT_CAP
def evaluate_discount_cap(line: LineFacts, *, segment: str | None, applicable: list[dict[str, Any]],
                          expired: list[dict[str, Any]], derogation: dict[str, Any] | None, thresholds: Thresholds) -> RuleResult:
    rule = "DISCOUNT_CAP"
    if (excluded := _excluded(rule, line, thresholds)) is not None:
        return excluded
    evidence = {**_line_evidence(line), "segment": segment,
                "policies_considered": [_policy_ref(p) for p in applicable + expired],
                "derogation": _derogation_ref(derogation)}
    gross = line.qty_ordered * line.price_unit
    whole_discount = to_company(gross * line.discount_pct / HUNDRED, line.fx_rate)
    if line.discount_pct <= 0:
        return _result(rule, "COMPLIANT", "COMPLIANT", "NO_DISCOUNT", thresholds=thresholds, evidence=evidence, reason="no discount on the line")
    if not applicable:
        cause = "POLICY_EXPIRED" if expired else "NO_POLICY"
        return _result(rule, "UNKNOWN", "INSUFFICIENT_EVIDENCE", cause, thresholds=thresholds, evidence=evidence,
                       reason="no discount policy valid on the order date covers this customer or segment",
                       potential=whole_discount, stage=line.exposure_stage, confidence="LOW", requires_review=True)
    top = max(p["priority"] for p in applicable)
    caps = sorted({p["max_discount_pct"] for p in applicable if p["priority"] == top})
    if len(caps) > 1:
        return _result(rule, "CONFLICT", "INSUFFICIENT_EVIDENCE", "POLICY_CONFLICT", thresholds=thresholds,
                       evidence={**evidence, "conflicting_caps": [_num(c) for c in caps]},
                       reason="two policies of the same priority give different caps", potential=whole_discount,
                       stage=line.exposure_stage, confidence="LOW", requires_review=True)
    cap = caps[0]
    evidence["allowed_discount_pct"] = _num(cap)
    evidence["applied_policy"] = next(_policy_ref(p) for p in applicable if p["priority"] == top and p["max_discount_pct"] == cap)
    if line.discount_pct <= cap:
        return _result(rule, "COMPLIANT", "COMPLIANT", "WITHIN_POLICY", thresholds=thresholds, evidence=evidence,
                       reason=f"discount {_num(line.discount_pct)}% within the {_num(cap)}% cap")
    if derogation is not None and derogation["max_discount_pct"] >= line.discount_pct:
        return _result(rule, "COMPLIANT", "LEGITIMATE_EXCEPTION", "APPROVED_DEROGATION", thresholds=thresholds, evidence=evidence,
                       reason=f"discount {_num(line.discount_pct)}% covered by derogation {derogation['derogation_id']}")
    expected = gross * (1 - cap / HUNDRED)
    actual = gross * (1 - line.discount_pct / HUNDRED)
    confidence = _line_confidence(line)
    return _result(rule, "VIOLATION", _violation_class(confidence), "DISCOUNT_ABOVE_CAP", thresholds=thresholds, evidence=evidence,
                   reason=f"discount {_num(line.discount_pct)}% exceeds the {_num(cap)}% cap without a valid derogation",
                   expected=to_company(expected, line.fx_rate), actual=to_company(actual, line.fx_rate),
                   adverse=to_company(expected - actual, line.fx_rate), stage=line.exposure_stage, confidence=confidence)


def _policy_ref(policy: dict[str, Any] | None) -> dict[str, Any] | None:
    if policy is None:
        return None
    return {"policy_id": policy["policy_id"], "version": policy["version"], "max_discount_pct": _num(policy["max_discount_pct"]),
            "priority": policy["priority"], "valid_from": str(policy["valid_from"]),
            "valid_to": None if policy["valid_to"] is None else str(policy["valid_to"]), "source": policy.get("source")}


def _derogation_ref(derogation: dict[str, Any] | None) -> dict[str, Any] | None:
    if derogation is None:
        return None
    return {"derogation_id": derogation["derogation_id"], "max_discount_pct": _num(derogation["max_discount_pct"]),
            "approved_by_role": derogation["approved_by_role"], "approved_on": str(derogation["approved_on"]),
            "valid_from": str(derogation["valid_from"]), "valid_to": None if derogation["valid_to"] is None else str(derogation["valid_to"]),
            "evidence_ref": derogation.get("evidence_ref")}


# --------------------------------------------------------------------------- PRICE_BELOW_BASELINE
def evaluate_price_baseline(line: LineFacts, baseline: Baseline, *, thresholds: Thresholds) -> RuleResult:
    rule = "PRICE_BELOW_BASELINE"
    if (excluded := _excluded(rule, line, thresholds)) is not None:
        return excluded
    evidence = {**_line_evidence(line), "baseline": {"level": baseline.level, "basis": baseline.basis, "unit_price": _fmt(baseline.unit_price),
                                                     **baseline.reference},
                "order_pricelist_id": line.pricelist_id, "customer_pricelist_id": line.customer_pricelist_id}
    if line.is_freight:
        return _result(rule, "COMPLIANT", "NOT_APPLICABLE", "FREIGHT_LINE", thresholds=thresholds, evidence=evidence,
                       reason="freight lines are evaluated by FREIGHT_REBILL")
    if baseline.unit_price is None:
        return _result(rule, "UNKNOWN", "INSUFFICIENT_EVIDENCE", "NO_PRICE_BASELINE", thresholds=thresholds, evidence=evidence,
                       reason="no defensible price baseline (no contract price, price list or comparable history)",
                       confidence="LOW", stage=line.exposure_stage)
    floor = baseline.unit_price * (1 - thresholds.price_tolerance_pct / HUNDRED)
    if line.price_unit >= floor:
        return _result(rule, "COMPLIANT", "COMPLIANT", "AT_OR_ABOVE_BASELINE", thresholds=thresholds, evidence=evidence,
                       reason=f"unit price {_num(line.price_unit)} at or above baseline {money(baseline.unit_price)} (level {baseline.level})")
    expected = line.qty_ordered * baseline.unit_price
    actual = line.qty_ordered * line.price_unit
    mismatch = (line.pricelist_id is not None and line.customer_pricelist_id is not None and line.pricelist_id != line.customer_pricelist_id
                and baseline.order_pricelist_price is not None and abs(baseline.order_pricelist_price - line.price_unit) <= CENT)
    cause = "PRICELIST_MISMATCH" if mismatch else {1: "PRICE_BELOW_CONTRACT", 2: "PRICE_BELOW_CUSTOMER_PRICELIST",
                                                   3: "PRICE_BELOW_LIST_PRICE", 4: "PRICE_BELOW_HISTORICAL"}[baseline.level]
    confidence = _line_confidence(line, baseline.level == 4)
    return _result(rule, "VIOLATION", _violation_class(confidence), cause, thresholds=thresholds,
                   evidence={**evidence, "order_pricelist_price": _fmt(baseline.order_pricelist_price)},
                   reason=f"unit price {_num(line.price_unit)} below baseline {money(baseline.unit_price)} ({baseline.basis})",
                   expected=to_company(expected, line.fx_rate), actual=to_company(actual, line.fx_rate),
                   adverse=to_company(expected - actual, line.fx_rate), stage=line.exposure_stage, confidence=confidence)


# --------------------------------------------------------------------------- FREIGHT_REBILL
def evaluate_freight(order: OrderFacts, contract: dict[str, Any] | None, *, thresholds: Thresholds) -> RuleResult:
    rule = "FREIGHT_REBILL"
    evidence: dict[str, Any] = {
        "order": order.order_name, "order_state": order.order_state, "order_date": str(order.order_date), "customer_ref": order.customer_ref,
        "contract": None if contract is None else {"contract_id": contract["contract_id"], "terms": contract["terms"],
                                                   "amount": _num(contract["amount"]), "currency": contract["currency"],
                                                   "trigger": contract.get("trigger"), "source": contract.get("source")},
        "goods_lines": [{"sale_line_id": ln.sale_line_id, "product_code": ln.product_code, "qty_ordered": _num(ln.qty_ordered),
                         "qty_delivered": _num(ln.qty_delivered), "qty_invoiced": _num(ln.qty_invoiced)} for ln in order.goods_lines],
        "freight_lines_on_order": [{"sale_line_id": ln.sale_line_id, "subtotal": _num(ln.subtotal), "qty_invoiced": _num(ln.qty_invoiced)}
                                   for ln in order.freight_lines],
        "freight_invoiced": str(money(order.freight_invoiced)),
        "freight_invoice_lines": list(order.freight_invoice_refs),
        "period_revenue_reconciled": order.period_reconciled,
    }
    if order.order_state != "sale":
        cause = "ORDER_CANCELLED" if order.order_state == "cancel" else "ORDER_NOT_CONFIRMED"
        return _result(rule, "EXCLUDED", "NOT_APPLICABLE", cause, thresholds=thresholds, evidence=evidence,
                       reason=f"order state {order.order_state}")
    if contract is None:
        return _result(rule, "COMPLIANT", "NOT_APPLICABLE", "NO_FREIGHT_CONTRACT", thresholds=thresholds, evidence=evidence,
                       reason="no freight clause for this customer on the order date")
    if contract["terms"] != "rebill":
        return _result(rule, "COMPLIANT", "LEGITIMATE_EXCEPTION", "CONTRACT_WAIVER", thresholds=thresholds, evidence=evidence,
                       reason=f"freight {contract['terms']} by contract {contract['contract_id']}")
    if not order.goods_delivered_all or not order.goods_invoiced_all:
        return _result(rule, "NOT_DUE", "EXPLAINED_VARIANCE", "FREIGHT_NOT_YET_DUE", thresholds=thresholds, evidence=evidence,
                       reason="freight becomes due after full delivery and invoicing of the goods")
    amount = Decimal(contract["amount"])
    fx = order.fx_rate if contract["currency"] != order.currency_code else None
    invoiced = order.freight_invoiced
    if invoiced >= amount - CENT:
        return _result(rule, "COMPLIANT", "COMPLIANT", "FREIGHT_INVOICED", thresholds=thresholds, evidence=evidence,
                       reason="contractual freight invoiced in full")
    cause = "FREIGHT_NOT_INVOICED" if invoiced <= 0 else "FREIGHT_PARTIALLY_INVOICED"
    confidence = "HIGH" if order.period_reconciled else "MEDIUM"
    return _result(rule, "VIOLATION", _violation_class(confidence), cause, thresholds=thresholds, evidence=evidence,
                   reason=f"freight due {_num(amount)} {contract['currency']}, invoiced {money(invoiced)}",
                   expected=to_company(amount, fx), actual=to_company(invoiced, fx), adverse=to_company(amount - invoiced, fx),
                   stage="INVOICED", confidence=confidence)


# --------------------------------------------------------------------------- COST_REFERENCE_VARIANCE
def evaluate_cost_variance(line: LineFacts, cost: CostFacts, *, thresholds: Thresholds) -> RuleResult:
    rule = "COST_REFERENCE_VARIANCE"
    if (excluded := _excluded(rule, line, thresholds)) is not None:
        return excluded
    evidence = {**_line_evidence(line), "delivered_units": _num(cost.delivered_units),
                "allocations": [{"delivery_move_id": a.delivery_move_id, "receipt_move_id": a.receipt_move_id, "quantity": _num(a.quantity),
                                 "unit_cost": _fmt(a.unit_cost), "amount": _fmt(a.amount), "status": a.status, "reason": a.reason}
                                for a in cost.allocations],
                "cost_reference": None if cost.reference is None else {
                    "reference_id": cost.reference["reference_id"], "unit_cost": _num(cost.reference["unit_cost"]),
                    "frozen_on": str(cost.reference["frozen_on"]), "valid_from": str(cost.reference["valid_from"]),
                    "valid_to": None if cost.reference["valid_to"] is None else str(cost.reference["valid_to"]),
                    "source": cost.reference.get("source")}}
    if line.is_freight or line.product_type == "service" or not line.is_storable:
        return _result(rule, "COMPLIANT", "NOT_APPLICABLE", "NOT_A_STORABLE_GOOD", thresholds=thresholds, evidence=evidence,
                       reason="no inventory cost to attribute")
    if cost.delivered_units <= 0:
        return _result(rule, "NOT_DUE", "EXPLAINED_VARIANCE", "NOT_DELIVERED", thresholds=thresholds, evidence=evidence,
                       reason="nothing delivered yet, no realised cost")
    if not cost.allocations or any(a.status != "ATTRIBUTED" for a in cost.allocations):
        reasons = sorted({a.reason for a in cost.allocations if a.reason}) or ["no cost allocation for the delivered units"]
        return _result(rule, "UNDETERMINED", "DATA_QUALITY_ISSUE", "MISSING_COST", thresholds=thresholds,
                       evidence={**evidence, "attribution_reasons": reasons},
                       reason="realised cost cannot be attributed to receipts: " + "; ".join(reasons),
                       confidence="LOW", requires_review=True, stage=line.exposure_stage)
    realised = sum((a.amount for a in cost.allocations), Decimal(0))
    if cost.reference is None:
        return _result(rule, "UNKNOWN", "INSUFFICIENT_EVIDENCE", "NO_COST_REFERENCE", thresholds=thresholds, evidence=evidence,
                       reason="no frozen reference cost valid on the order date", confidence="LOW", actual=realised,
                       stage=line.exposure_stage)
    expected = Decimal(cost.reference["unit_cost"]) * cost.delivered_units
    variance = realised - expected
    evidence["realised_cost"] = str(money(realised))
    evidence["reference_cost"] = str(money(expected))
    adverse = variance > thresholds.cost_tolerance_abs and (expected == 0 or variance / expected * HUNDRED > thresholds.cost_tolerance_pct)
    if not adverse:
        cause = "FAVOURABLE_VARIANCE" if variance < 0 else "AT_REFERENCE_COST"
        return _result(rule, "COMPLIANT", "COMPLIANT", cause, thresholds=thresholds, evidence=evidence,
                       reason=f"realised cost {money(realised)} against reference {money(expected)}", expected=expected, actual=realised)
    confidence = "HIGH" if line.period_reconciled else "MEDIUM"
    return _result(rule, "VIOLATION", _violation_class(confidence), "PURCHASE_PRICE_VARIANCE", thresholds=thresholds,
                   evidence={**evidence, "customer_receivable": False},
                   reason=f"realised cost {money(realised)} exceeds reference {money(expected)} by {money(variance)}",
                   expected=expected, actual=realised, adverse=variance, stage=line.exposure_stage, confidence=confidence)


# --------------------------------------------------------------------------- INVOICE_WITHOUT_SALE_LINK
def evaluate_unlinked_invoice_line(line: UnlinkedInvoiceLine, *, thresholds: Thresholds) -> RuleResult:
    evidence = {"invoice_line_id": line.invoice_line_id, "invoice": line.invoice_name, "type": line.move_type, "period": line.period,
                "accounting_date": str(line.accounting_date), "product_code": line.product_code,
                "revenue_company_ccy": str(money(line.revenue_company_ccy)), "sale_line_links": 0,
                "period_revenue_reconciled": line.period_reconciled, "counted_in_net_revenue": True}
    return _result("INVOICE_WITHOUT_SALE_LINK", "NO_SALE_LINK", "DATA_QUALITY_ISSUE", "INVOICE_WITHOUT_ORDER", thresholds=thresholds,
                   evidence=evidence, reason="posted revenue with no order line behind it: price, discount and freight cannot be verified",
                   adverse=Decimal(0), potential=abs(line.revenue_company_ccy), stage="INVOICED", confidence="LOW", requires_review=True)
