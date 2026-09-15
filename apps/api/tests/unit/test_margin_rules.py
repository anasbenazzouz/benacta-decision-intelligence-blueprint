"""Pure rule tests: every outcome and class of each rule on hand-built facts, without a database."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.margin import rules
from app.margin.baseline import PricelistItem, pricelist_unit_price, resolve_baseline
from app.margin.rules import Allocation, Baseline, CostFacts, InvoiceRef, LineFacts, OrderFacts, UnlinkedInvoiceLine
from app.margin.thresholds import Thresholds, load_thresholds

D = Decimal
ON = date(2026, 7, 3)


@pytest.fixture(scope="module")
def thresholds() -> Thresholds:
    return load_thresholds()


def line(**overrides) -> LineFacts:
    base = dict(
        sale_line_id=1, sale_order_id=1, order_name="SO/1", order_state="sale", order_date=ON, company_id=1, customer_id=10,
        customer_ref="C01", product_id=100, product_code="P01", product_name="Pressure Sensor", product_type="consu", is_storable=True,
        is_freight=False, currency_code="EUR", company_currency="EUR", fx_rate=None, qty_ordered=D(100), qty_product_uom=D(100),
        price_unit=D(100), discount_pct=D(0), subtotal=D(10000), qty_delivered=D(100), qty_invoiced=D(100),
        invoices=(InvoiceRef(5, "INV/5", "out_invoice", "2026-07", D(10000), D(10000), D(1)),), pricelist_id=1, customer_pricelist_id=1,
        list_price=D(100), period_reconciled=True,
    )
    base.update(overrides)
    if "subtotal" not in overrides:
        base["subtotal"] = base["qty_ordered"] * base["price_unit"] * (1 - base["discount_pct"] / 100)
    return LineFacts(**base)


def policy(cap: str, *, segment="standard", customer=None, priority=10, valid_to=None) -> dict:
    return {"policy_id": f"POL-{segment or customer}-{cap}", "version": 1, "scope_segment": segment, "scope_customer_ref": customer,
            "max_discount_pct": D(cap), "priority": priority, "valid_from": date(2026, 1, 1), "valid_to": valid_to, "source": "test"}


# --------------------------------------------------------------------------- DISCOUNT_CAP
class TestDiscountCap:
    def test_violation_is_confirmed_leakage_with_the_oracle_arithmetic(self, thresholds):
        result = rules.evaluate_discount_cap(line(discount_pct=D(15)), segment="standard", applicable=[policy("5")], expired=[],
                                             derogation=None, thresholds=thresholds)
        assert (result.outcome, result.classification, result.cause) == ("VIOLATION", "CONFIRMED_LEAKAGE", "DISCOUNT_ABOVE_CAP")
        assert (result.expected_amount, result.actual_amount, result.adverse_exposure) == (D("9500.00"), D("8500.00"), D("1000.00"))
        assert (result.severity, result.material, result.controllability, result.exposure_stage) == ("HIGH", True, "CONTROLLABLE", "INVOICED")
        assert result.evidence["allowed_discount_pct"] == "5" and result.evidence["applied_policy"]["policy_id"] == "POL-standard-5"
        assert result.creates_case

    def test_discount_at_the_cap_is_compliant(self, thresholds):
        result = rules.evaluate_discount_cap(line(discount_pct=D(5)), segment="standard", applicable=[policy("5")], expired=[],
                                             derogation=None, thresholds=thresholds)
        assert (result.outcome, result.classification, result.creates_case) == ("COMPLIANT", "COMPLIANT", False)

    def test_valid_derogation_is_a_legitimate_exception_not_a_case(self, thresholds):
        derogation = {"derogation_id": "DEROG-1", "max_discount_pct": D(15), "approved_by_role": "finance_approver", "approved_on": ON,
                      "valid_from": ON, "valid_to": None, "evidence_ref": "mail"}
        result = rules.evaluate_discount_cap(line(discount_pct=D(15)), segment="standard", applicable=[policy("5")], expired=[],
                                             derogation=derogation, thresholds=thresholds)
        assert (result.outcome, result.classification, result.cause) == ("COMPLIANT", "LEGITIMATE_EXCEPTION", "APPROVED_DEROGATION")
        assert not result.creates_case and result.evidence["derogation"]["derogation_id"] == "DEROG-1"

    def test_derogation_below_the_discount_does_not_cover_it(self, thresholds):
        derogation = {"derogation_id": "DEROG-1", "max_discount_pct": D(10), "approved_by_role": "finance_approver", "approved_on": ON,
                      "valid_from": ON, "valid_to": None, "evidence_ref": None}
        result = rules.evaluate_discount_cap(line(discount_pct=D(15)), segment="standard", applicable=[policy("5")], expired=[],
                                             derogation=derogation, thresholds=thresholds)
        assert result.outcome == "VIOLATION"

    def test_expired_policy_is_insufficient_evidence_with_an_upper_bound(self, thresholds):
        result = rules.evaluate_discount_cap(line(qty_ordered=D(6), qty_product_uom=D(6), price_unit=D(340), discount_pct=D(12)),
                                             segment="distributor", applicable=[], expired=[policy("12", segment="distributor", valid_to=date(2026, 6, 2))],
                                             derogation=None, thresholds=thresholds)
        assert (result.outcome, result.classification, result.cause) == ("UNKNOWN", "INSUFFICIENT_EVIDENCE", "POLICY_EXPIRED")
        assert result.adverse_exposure is None and result.potential_exposure == D("244.80")
        assert result.requires_human_review and result.confidence == "LOW" and result.creates_case

    def test_conflicting_policies_of_the_same_priority(self, thresholds):
        result = rules.evaluate_discount_cap(line(discount_pct=D(8)), segment="distributor",
                                             applicable=[policy("5", segment=None, customer="N10", priority=30), policy("10", segment=None, customer="N10", priority=30)],
                                             expired=[], derogation=None, thresholds=thresholds)
        assert (result.outcome, result.classification, result.cause) == ("CONFLICT", "INSUFFICIENT_EVIDENCE", "POLICY_CONFLICT")
        assert result.evidence["conflicting_caps"] == ["5", "10"]

    def test_customer_policy_outranks_segment_policy(self, thresholds):
        result = rules.evaluate_discount_cap(line(discount_pct=D(8)), segment="standard",
                                             applicable=[policy("5"), policy("10", segment=None, customer="C01", priority=30)],
                                             expired=[], derogation=None, thresholds=thresholds)
        assert result.outcome == "COMPLIANT" and result.evidence["allowed_discount_pct"] == "10"

    def test_cancelled_and_draft_orders_are_excluded(self, thresholds):
        for state, cause in (("cancel", "ORDER_CANCELLED"), ("draft", "ORDER_NOT_CONFIRMED")):
            result = rules.evaluate_discount_cap(line(order_state=state, discount_pct=D(20)), segment="standard", applicable=[policy("5")],
                                                 expired=[], derogation=None, thresholds=thresholds)
            assert (result.outcome, result.classification, result.cause) == ("EXCLUDED", "NOT_APPLICABLE", cause)

    def test_foreign_currency_exposure_is_converted_to_company_currency(self, thresholds):
        usd = line(currency_code="USD", fx_rate=D("1.10"), qty_ordered=D(4), qty_product_uom=D(4), price_unit=D(430), discount_pct=D(15))
        result = rules.evaluate_discount_cap(usd, segment="standard", applicable=[policy("5")], expired=[], derogation=None, thresholds=thresholds)
        assert result.adverse_exposure == (D(4) * D(430) * D("0.10") / D("1.10")).quantize(D("0.01"))

    def test_unresolved_invoice_links_downgrade_confidence_to_probable(self, thresholds):
        fuzzy = line(discount_pct=D(15), invoices=(InvoiceRef(5, "INV/5", "out_invoice", "2026-07", D(8500), D(8500), None),))
        result = rules.evaluate_discount_cap(fuzzy, segment="standard", applicable=[policy("5")], expired=[], derogation=None, thresholds=thresholds)
        assert (result.classification, result.confidence) == ("PROBABLE_LEAKAGE", "MEDIUM")


# --------------------------------------------------------------------------- PRICE_BELOW_BASELINE
class TestPriceBaseline:
    def test_price_below_contract_is_confirmed_leakage(self, thresholds):
        baseline = Baseline(1, "CONTRACT_PRICE", D(500), {"contract_id": "CTR-1"})
        result = rules.evaluate_price_baseline(line(qty_ordered=D(20), qty_product_uom=D(20), price_unit=D(470)), baseline, thresholds=thresholds)
        assert (result.outcome, result.classification, result.cause, result.adverse_exposure) == ("VIOLATION", "CONFIRMED_LEAKAGE", "PRICE_BELOW_CONTRACT", D("600.00"))

    def test_price_within_tolerance_is_compliant(self, thresholds):
        result = rules.evaluate_price_baseline(line(price_unit=D("99.60")), Baseline(3, "PRODUCT_LIST_PRICE", D(100)), thresholds=thresholds)
        assert result.outcome == "COMPLIANT"

    def test_pricelist_mismatch_is_the_cause_when_the_order_list_explains_the_price(self, thresholds):
        baseline = Baseline(3, "PRODUCT_LIST_PRICE", D(340), {}, order_pricelist_price=D(300))
        result = rules.evaluate_price_baseline(line(price_unit=D(300), pricelist_id=2, customer_pricelist_id=1, qty_ordered=D(10), qty_product_uom=D(10)),
                                               baseline, thresholds=thresholds)
        assert (result.cause, result.adverse_exposure) == ("PRICELIST_MISMATCH", D("400.00"))

    def test_historical_baseline_is_only_probable(self, thresholds):
        result = rules.evaluate_price_baseline(line(price_unit=D(80)), Baseline(4, "HISTORICAL_COMPARABLE", D(100)), thresholds=thresholds)
        assert (result.classification, result.confidence, result.cause) == ("PROBABLE_LEAKAGE", "MEDIUM", "PRICE_BELOW_HISTORICAL")

    def test_no_baseline_is_insufficient_evidence_without_a_case(self, thresholds):
        result = rules.evaluate_price_baseline(line(), Baseline(None, "UNAVAILABLE", None, {"tried": ["no list price"]}), thresholds=thresholds)
        assert (result.outcome, result.classification, result.creates_case) == ("UNKNOWN", "INSUFFICIENT_EVIDENCE", False)

    def test_baseline_hierarchy_levels(self, thresholds):
        base = line(price_unit=D(470), qty_ordered=D(20), qty_product_uom=D(20))
        contract = {"contract_id": "CTR-1", "unit_price": D(500), "currency": "EUR", "min_quantity": D(0)}
        item = PricelistItem(7, 1, "1_product", 50, None, None, D(0), "fixed", D(450), None, "EUR", None, None)
        assert resolve_baseline(base, contract=contract, customer_items=[item], customer_pricelist_currency="EUR", order_items=[],
                                order_pricelist_currency=None, template_id=50, category_id=3, history_company_ccy=[], thresholds=thresholds).level == 1
        level2 = resolve_baseline(base, contract=None, customer_items=[item], customer_pricelist_currency="EUR", order_items=[],
                                  order_pricelist_currency=None, template_id=50, category_id=3, history_company_ccy=[], thresholds=thresholds)
        assert (level2.level, level2.unit_price) == (2, D("450.00"))
        level3 = resolve_baseline(base, contract=None, customer_items=[], customer_pricelist_currency=None, order_items=[],
                                  order_pricelist_currency=None, template_id=50, category_id=3, history_company_ccy=[], thresholds=thresholds)
        assert (level3.level, level3.unit_price) == (3, D("100.00"))
        no_list = line(list_price=None)
        level4 = resolve_baseline(no_list, contract=None, customer_items=[], customer_pricelist_currency=None, order_items=[],
                                  order_pricelist_currency=None, template_id=50, category_id=3, history_company_ccy=[D(90), D(100), D(110)], thresholds=thresholds)
        assert (level4.level, level4.unit_price) == (4, D("100.00"))
        none = resolve_baseline(no_list, contract=None, customer_items=[], customer_pricelist_currency=None, order_items=[],
                                order_pricelist_currency=None, template_id=50, category_id=3, history_company_ccy=[D(90)], thresholds=thresholds)
        assert none.level is None and none.basis == "UNAVAILABLE" and none.reference["tried"]
        lump_sums = resolve_baseline(no_list, contract=None, customer_items=[], customer_pricelist_currency=None, order_items=[],
                                     order_pricelist_currency=None, template_id=50, category_id=3,
                                     history_company_ccy=[D(98500), D(400000), D(1200000)], thresholds=thresholds)
        assert lump_sums.level is None and any("not comparable" in t for t in lump_sums.reference["tried"]), (
            "lump-sum contract amounts are not a comparable price history"
        )

    def test_baseline_respects_unit_of_measure_and_currency(self, thresholds):
        dozens = line(qty_ordered=D(5), qty_product_uom=D(60), price_unit=D(480), list_price=D(40))
        assert resolve_baseline(dozens, contract=None, customer_items=[], customer_pricelist_currency=None, order_items=[], order_pricelist_currency=None,
                                template_id=1, category_id=1, history_company_ccy=[], thresholds=thresholds).unit_price == D("480.00")
        usd = line(currency_code="USD", fx_rate=D("1.10"), price_unit=D(430), list_price=D(390), qty_ordered=D(4), qty_product_uom=D(4))
        assert resolve_baseline(usd, contract=None, customer_items=[], customer_pricelist_currency=None, order_items=[], order_pricelist_currency=None,
                                template_id=1, category_id=1, history_company_ccy=[], thresholds=thresholds).unit_price == D("429.00")

    def test_pricelist_item_specificity_and_validity(self):
        items = [
            PricelistItem(1, 1, "3_global", None, None, None, D(0), "percentage", None, D(10), "EUR", None, None),
            PricelistItem(2, 1, "1_product", 50, None, None, D(0), "fixed", D(300), None, "EUR", None, date(2026, 6, 30)),
            PricelistItem(3, 1, "1_product", 50, None, None, D(10), "fixed", D(280), None, "EUR", None, None),
        ]
        price, item, _ = pricelist_unit_price(items, list_price=D(340), product_id=100, template_id=50, category_id=3, on=ON, quantity=D(5))
        assert (price, item.item_id) == (D("306.0"), 1), "expired product item skipped, global percentage applies"
        price, item, _ = pricelist_unit_price(items, list_price=D(340), product_id=100, template_id=50, category_id=3, on=ON, quantity=D(10))
        assert (price, item.item_id) == (D(280), 3)


# --------------------------------------------------------------------------- FREIGHT_REBILL
def order(**overrides) -> OrderFacts:
    goods = line(qty_ordered=D(10), qty_product_uom=D(10), price_unit=D(200))
    base = dict(sale_order_id=1, order_name="SO/1", order_state="sale", order_date=ON, company_id=1, customer_id=10, customer_ref="G2",
                currency_code="EUR", fx_rate=None, goods_lines=(goods,), freight_lines=(), freight_invoiced=D(0))
    base.update(overrides)
    return OrderFacts(**base)


REBILL = {"contract_id": "CTR-FREIGHT-G2", "terms": "rebill", "amount": D(250), "currency": "EUR", "trigger": "full_delivery", "source": "contract"}


class TestFreight:
    def test_missing_freight_after_full_delivery_and_invoicing(self, thresholds):
        result = rules.evaluate_freight(order(), REBILL, thresholds=thresholds)
        assert (result.outcome, result.classification, result.cause, result.adverse_exposure) == ("VIOLATION", "CONFIRMED_LEAKAGE", "FREIGHT_NOT_INVOICED", D("250.00"))
        assert (result.expected_amount, result.actual_amount, result.severity) == (D("250.00"), D("0.00"), "MEDIUM")

    def test_partial_freight_recharge(self, thresholds):
        result = rules.evaluate_freight(order(freight_invoiced=D(100)), REBILL, thresholds=thresholds)
        assert (result.cause, result.adverse_exposure) == ("FREIGHT_PARTIALLY_INVOICED", D("150.00"))

    def test_partial_delivery_is_not_due(self, thresholds):
        partial = line(qty_ordered=D(100), qty_product_uom=D(100), qty_delivered=D(60), qty_invoiced=D(60))
        result = rules.evaluate_freight(order(goods_lines=(partial,)), REBILL, thresholds=thresholds)
        assert (result.outcome, result.classification, result.cause) == ("NOT_DUE", "EXPLAINED_VARIANCE", "FREIGHT_NOT_YET_DUE")

    def test_waiver_is_legitimate_and_no_contract_is_not_applicable(self, thresholds):
        waived = rules.evaluate_freight(order(), {**REBILL, "terms": "waived", "amount": D(0)}, thresholds=thresholds)
        assert (waived.outcome, waived.classification, waived.cause) == ("COMPLIANT", "LEGITIMATE_EXCEPTION", "CONTRACT_WAIVER")
        none = rules.evaluate_freight(order(), None, thresholds=thresholds)
        assert (none.outcome, none.classification) == ("COMPLIANT", "NOT_APPLICABLE")

    def test_freight_invoiced_in_full_is_compliant(self, thresholds):
        assert rules.evaluate_freight(order(freight_invoiced=D(250)), REBILL, thresholds=thresholds).outcome == "COMPLIANT"


# --------------------------------------------------------------------------- COST_REFERENCE_VARIANCE
REFERENCE = {"reference_id": "REF-COST-Q3", "unit_cost": D(60), "frozen_on": date(2026, 6, 2), "valid_from": date(2026, 6, 2), "valid_to": None, "source": "freeze"}


def cost(unit_cost: str | None, qty: str = "100", status="ATTRIBUTED", reference=REFERENCE) -> CostFacts:
    amount = None if unit_cost is None else D(unit_cost) * D(qty)
    return CostFacts((Allocation(1, 2 if unit_cost else None, D(qty), None if unit_cost is None else D(unit_cost), amount, status,
                                 None if status == "ATTRIBUTED" else "no valued receipt layer"),), D(qty), reference)


class TestCostVariance:
    def test_purchase_price_variance_is_confirmed_leakage_not_receivable(self, thresholds):
        result = rules.evaluate_cost_variance(line(price_unit=D(120)), cost("68"), thresholds=thresholds)
        assert (result.outcome, result.cause, result.adverse_exposure) == ("VIOLATION", "PURCHASE_PRICE_VARIANCE", D("800.00"))
        assert (result.expected_amount, result.actual_amount, result.controllability) == (D("6000.00"), D("6800.00"), "PARTIALLY_CONTROLLABLE")
        assert result.evidence["customer_receivable"] is False

    def test_missing_cost_is_a_data_quality_issue_not_zero(self, thresholds):
        result = rules.evaluate_cost_variance(line(), cost(None, "10", status="UNDETERMINED"), thresholds=thresholds)
        assert (result.outcome, result.classification, result.cause, result.adverse_exposure) == ("UNDETERMINED", "DATA_QUALITY_ISSUE", "MISSING_COST", None)
        assert result.requires_human_review and result.creates_case

    def test_favourable_and_within_tolerance_variances_are_compliant(self, thresholds):
        assert rules.evaluate_cost_variance(line(), cost("55"), thresholds=thresholds).cause == "FAVOURABLE_VARIANCE"
        assert rules.evaluate_cost_variance(line(), cost("60.005"), thresholds=thresholds).outcome == "COMPLIANT"

    def test_no_reference_is_insufficient_evidence_without_a_case(self, thresholds):
        result = rules.evaluate_cost_variance(line(), cost("68", reference=None), thresholds=thresholds)
        assert (result.outcome, result.classification, result.creates_case) == ("UNKNOWN", "INSUFFICIENT_EVIDENCE", False)

    def test_services_and_undelivered_lines_raise_nothing(self, thresholds):
        assert rules.evaluate_cost_variance(line(product_type="service", is_storable=False), cost("68"), thresholds=thresholds).classification == "NOT_APPLICABLE"
        undelivered = rules.evaluate_cost_variance(line(qty_delivered=D(0)), CostFacts((), D(0), REFERENCE), thresholds=thresholds)
        assert (undelivered.outcome, undelivered.cause) == ("NOT_DUE", "NOT_DELIVERED")


# --------------------------------------------------------------------------- INVOICE_WITHOUT_SALE_LINK
def test_unlinked_invoice_line_is_a_data_quality_case_sized_by_its_revenue(thresholds):
    result = rules.evaluate_unlinked_invoice_line(
        UnlinkedInvoiceLine(9, 8, "INV/NEG-11", "out_invoice", 1, 12, 110, "P10", "2026-08", date(2026, 8, 10), D(650)), thresholds=thresholds)
    assert (result.outcome, result.classification, result.cause) == ("NO_SALE_LINK", "DATA_QUALITY_ISSUE", "INVOICE_WITHOUT_ORDER")
    assert (result.adverse_exposure, result.potential_exposure, result.severity, result.material) == (D("0.00"), D("650.00"), "MEDIUM", True)


def test_every_rule_declares_version_and_formula():
    for rule_id, spec in rules.RULES.items():
        assert spec["version"] >= 1 and spec["formula"] and spec["name"], rule_id
