"""Price baseline hierarchy: the expected unit price a sale line is compared with.

1. approved customer contract price (`semantic.contract_price`)
2. approved customer price list (the price list assigned to the customer, Odoo `property_product_pricelist`)
3. approved product price list (the product list price)
4. approved comparable historical baseline (median confirmed price of the product over the trailing window)
5. unavailable

The result is expressed in the order currency per order unit of measure, so the comparison with `price_unit`
is direct. Every conversion (currency, unit) is recorded in the baseline reference.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from statistics import median
from typing import Any

from app.margin.rules import HUNDRED, Baseline, LineFacts, money
from app.margin.thresholds import Thresholds
from app.numbers import decimal_text


@dataclass(frozen=True)
class PricelistItem:
    item_id: int
    pricelist_id: int
    applied_on: str
    product_template_id: int | None
    product_id: int | None
    category_id: int | None
    min_quantity: Decimal
    compute_price: str
    fixed_price: Decimal | None
    percent_price: Decimal | None
    currency_code: str | None
    date_start: date | None
    date_end: date | None

    def applies(self, *, product_id: int | None, template_id: int | None, category_id: int | None, on: date, quantity: Decimal) -> bool:
        if self.date_start and on < self.date_start:
            return False
        if self.date_end and on > self.date_end:
            return False
        if quantity < self.min_quantity:
            return False
        return {
            "0_product_variant": self.product_id == product_id,
            "1_product": self.product_template_id == template_id,
            "2_product_category": self.category_id == category_id,
            "3_global": True,
        }.get(self.applied_on, False)

    @property
    def specificity(self) -> int:
        return {"0_product_variant": 4, "1_product": 3, "2_product_category": 2, "3_global": 1}.get(self.applied_on, 0)


def pricelist_unit_price(items: list[PricelistItem], *, list_price: Decimal | None, product_id: int | None, template_id: int | None,
                         category_id: int | None, on: date, quantity: Decimal) -> tuple[Decimal | None, PricelistItem | None, str | None]:
    """Price given by the most specific applicable item; (None, None, reason) when the list gives no usable price."""
    applicable = [i for i in items if i.applies(product_id=product_id, template_id=template_id, category_id=category_id, on=on, quantity=quantity)]
    if not applicable:
        return None, None, "no applicable item"
    item = max(applicable, key=lambda i: (i.specificity, i.min_quantity))
    if item.compute_price == "fixed" and item.fixed_price is not None:
        return item.fixed_price, item, None
    if item.compute_price == "percentage" and item.percent_price is not None and list_price is not None:
        return list_price * (1 - item.percent_price / HUNDRED), item, None
    return None, item, f"compute_price {item.compute_price} not supported"


def dispersion_pct(values: list[Decimal], med: Decimal) -> Decimal | None:
    """Median absolute deviation over the median, in percent; None when the median is zero."""
    if not values or med == 0:
        return None
    mad = Decimal(str(median([abs(v - med) for v in values])))
    return (mad * 100 / abs(med)).quantize(Decimal("0.01"))


def _per_order_unit(unit_price: Decimal, line: LineFacts) -> Decimal:
    """A baseline per product unit becomes a baseline per order unit (a dozen, a pallet)."""
    if line.qty_product_uom is None or line.qty_ordered == 0 or line.qty_product_uom == line.qty_ordered:
        return unit_price
    return unit_price * line.qty_product_uom / line.qty_ordered


def _to_order_currency(amount: Decimal, currency: str, line: LineFacts) -> Decimal | None:
    if currency == line.currency_code:
        return amount
    if currency == line.company_currency and line.fx_rate:
        return amount * line.fx_rate
    return None


def resolve_baseline(
    line: LineFacts,
    *,
    contract: dict[str, Any] | None,
    customer_items: list[PricelistItem],
    customer_pricelist_currency: str | None,
    order_items: list[PricelistItem],
    order_pricelist_currency: str | None,
    template_id: int | None,
    category_id: int | None,
    history_company_ccy: list[Decimal],
    thresholds: Thresholds,
) -> Baseline:
    quantity = line.qty_product_uom if line.qty_product_uom is not None else line.qty_ordered
    order_price, order_item, _ = pricelist_unit_price(order_items, list_price=line.list_price, product_id=line.product_id,
                                                      template_id=template_id, category_id=category_id, on=line.order_date, quantity=quantity)
    order_pricelist_price = None
    if order_price is not None and order_pricelist_currency:
        converted = _to_order_currency(order_price, order_pricelist_currency, line)
        order_pricelist_price = None if converted is None else money(_per_order_unit(converted, line))
    tried: list[str] = []

    if contract is not None:
        price = _to_order_currency(Decimal(contract["unit_price"]), contract["currency"], line)
        if price is not None:
            return Baseline(1, "CONTRACT_PRICE", money(_per_order_unit(price, line)),
                            {"contract_id": contract["contract_id"], "contract_unit_price": decimal_text(contract["unit_price"]),
                             "contract_currency": contract["currency"], "source": contract.get("source")}, order_pricelist_price)
        tried.append(f"contract price in {contract['currency']} not convertible")

    if line.customer_pricelist_id is not None:
        price, item, reason = pricelist_unit_price(customer_items, list_price=line.list_price, product_id=line.product_id,
                                                   template_id=template_id, category_id=category_id, on=line.order_date, quantity=quantity)
        converted = _to_order_currency(price, customer_pricelist_currency or line.currency_code, line) if price is not None else None
        if converted is not None and item is not None:
            return Baseline(2, "CUSTOMER_PRICELIST", money(_per_order_unit(converted, line)),
                            {"pricelist_id": item.pricelist_id, "pricelist_item_id": item.item_id, "applied_on": item.applied_on,
                             "compute_price": item.compute_price}, order_pricelist_price)
        tried.append(f"customer price list: {reason or 'currency not convertible'}")

    if line.list_price is not None and line.list_price > 0:
        converted = _to_order_currency(line.list_price, line.company_currency, line)
        if converted is not None:
            return Baseline(3, "PRODUCT_LIST_PRICE", money(_per_order_unit(converted, line)),
                            {"list_price": decimal_text(line.list_price), "list_price_currency": line.company_currency,
                             "fx_rate": decimal_text(line.fx_rate)}, order_pricelist_price)
        tried.append("list price not convertible to the order currency")
    else:
        tried.append("no list price")

    if len(history_company_ccy) >= thresholds.historical_min_observations:
        med = Decimal(str(median(history_company_ccy)))
        dispersion = dispersion_pct(history_company_ccy, med)
        converted = _to_order_currency(med, line.company_currency, line)
        if dispersion is not None and dispersion > thresholds.historical_max_dispersion_pct:
            tried.append(f"history not comparable: dispersion {dispersion}% above {thresholds.historical_max_dispersion_pct}%")
        elif converted is not None:
            return Baseline(4, "HISTORICAL_COMPARABLE", money(_per_order_unit(converted, line)),
                            {"observations": len(history_company_ccy), "window_months": thresholds.historical_months,
                             "median_company_ccy": str(money(med)), "dispersion_pct": decimal_text(dispersion)}, order_pricelist_price)
    else:
        tried.append(f"history: {len(history_company_ccy)} observation(s), {thresholds.historical_min_observations} required")
    return Baseline(None, "UNAVAILABLE", None, {"tried": tried}, order_pricelist_price)
