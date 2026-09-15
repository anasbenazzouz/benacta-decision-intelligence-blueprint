"""Deterministic BENACTA DEMO dataset shaped like Odoo 19 API records.

One fictional company over 90 days: 21 customers, 5 suppliers, 12 catalogue
products, 5 scenario products, 120 sale orders. Background orders are
compliant by construction. Scenario orders carry the three golden cases and
the negative controls. Expected outcomes are NOT produced here: they live in
the hand-written oracle `data/golden/oracle_v1.yml`, which never imports this
module.

Records use Odoo shapes (many2one as `[id, name]`, `False` for empty values,
floats for amounts, UTC `YYYY-MM-DD HH:MM:SS` datetimes) so ingestion runs the
same code for fixtures and for the connected instance.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

DATASET_ID = "demo_v1"
DEFAULT_ANCHOR = date(2026, 8, 31)
DEFAULT_SEED = 20260831
WINDOW_DAYS = 90
CENT = Decimal("0.01")
VAT = Decimal("0.20")

COMPANY = (1, "BENACTA DEMO")
EUR = (1, "EUR")
USD = (2, "USD")
UNITS = (1, "Units")
DOZENS = (2, "Dozens")

ACCOUNTS = {
    "receivable": (1, "411100", "Customers", "asset_receivable"),
    "sales_goods": (2, "707000", "Sales of goods", "income"),
    "sales_services": (3, "706000", "Services rebilled", "income"),
    "vat_collected": (4, "445710", "VAT collected", "liability_current"),
    "cogs": (5, "603000", "Cost of goods sold", "expense_direct_cost"),
    "stock_valuation": (6, "355000", "Stock valuation", "asset_current"),
}

# code: (name, list price, reference unit cost, supplier key)
CATALOGUE = {
    "P01": ("Pressure Sensor", "120", "66", "S01"),
    "P02": ("Flow Meter", "340", "190", "S01"),
    "P03": ("Valve Actuator", "210", "115", "S02"),
    "P04": ("Control Relay", "85", "44", "S02"),
    "P05": ("Cable Gland Kit", "40", "21", "S03"),
    "P06": ("PLC Module", "390", "228", "S03"),
    "P07": ("HMI Panel", "520", "300", "S04"),
    "P08": ("Servo Drive", "460", "262", "S04"),
    "P09": ("Gear Motor", "280", "158", "S01"),
    "P10": ("Proximity Switch", "65", "34", "S02"),
    "P11": ("Filter Cartridge", "55", "29", "S03"),
    "P12": ("Safety Light Curtain", "610", "350", "S04"),
}
# code: (name, list price, reference unit cost, receipt unit cost or None, receipt qty, supplier key)
SCENARIO_PRODUCTS = {
    "SC1": ("Pump Seal Kit", "100", "55", "55", 100, "S01"),
    "SC2": ("Enclosure Cabinet", "200", "110", "110", 10, "S02"),
    "SC3": ("Heat Exchanger Plate", "120", "60", "68", 100, "S05"),
    "SC4": ("Coupling Set", "90", "48", None, 0, "S03"),
    "SC5": ("Bearing Unit", "100", "60", "68", 50, "S05"),
}
FREIGHT_PRODUCT = ("FRT", "Freight rebilling", "250")
SUPPLIERS = {
    "S01": "Nordline Components",
    "S02": "Atelier Vasseur",
    "S03": "Rhone Industrial Supply",
    "S04": "Kessler Automation",
    "S05": "Meridian Thermal Parts",
}
BACKGROUND_CUSTOMERS = {
    "C01": ("Alcor Process Systems", "key_account", "rebill"),
    "C02": ("Brevan Energy", "key_account", None),
    "C03": ("Castell Pharma Plants", "key_account", None),
    "C04": ("Dorval Packaging", "standard", None),
    "C05": ("Estrel Water Services", "standard", "rebill"),
    "C06": ("Fontaine Agro", "standard", None),
    "C07": ("Garnier Metalworks", "standard", None),
    "C08": ("Halden Logistics", "standard", "rebill"),
    "C09": ("Ivry Food Lines", "standard", None),
    "C10": ("Jura Precision", "standard", None),
    "C11": ("Keraval Chemicals", "standard", None),
    "C12": ("Lumen Glassworks", "standard", None),
    "C13": ("Morvan Paper", "standard", None),
    "C14": ("Nerac Textiles", "standard", None),
}
SCENARIO_CUSTOMERS = {
    "G1": ("Orsay Hydraulics", "standard", None),
    "G2": ("Pelican Marine Yards", "standard", "rebill"),
    "G3": ("Quimper Thermal", "standard", None),
    "N02": ("Rocroi Mining", "standard", "waived"),
    "N03": ("Sarlat Cement", "standard", "rebill"),
    "N09": ("Tessier Distribution", "distributor", None),
    "N10": ("Ubaye Trade Partners", "distributor", None),
}
FREIGHT_AMOUNT = Decimal("250")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def m2o(ref: tuple[int, str] | None) -> Any:
    return [ref[0], ref[1]] if ref else False


def dt(day: date, hour: int = 9) -> str:
    return datetime.combine(day, time(hour, 0)).strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class FixtureDataset:
    dataset_id: str
    source_instance: str
    anchor_date: date
    window_start: date
    seed: int
    records: dict[str, list[dict[str, Any]]]
    keys: dict[str, dict[int, str]]
    terms: dict[str, Any]
    plans: list[Any] = field(default_factory=list)  # plan files added by the project extension
    pools: dict[tuple[str, str], list[str]] = field(default_factory=dict)

    def by_key(self, model: str, key: str) -> dict[str, Any]:
        wanted = {v: k for k, v in self.keys[model].items()}[key]
        return next(r for r in self.records[model] if r["id"] == wanted)

    def find(self, model: str, **criteria: Any) -> list[dict[str, Any]]:
        return [r for r in self.records[model] if all(r.get(k) == v for k, v in criteria.items())]


@dataclass
class _Line:
    product: str
    qty: Decimal
    price_unit: Decimal
    discount: Decimal
    uom: tuple[int, str] = UNITS
    qty_units: Decimal | None = None  # quantity in product units when uom differs
    delivered: Decimal | None = None  # defaults to qty
    invoiced: Decimal | None = None  # defaults to delivered


@dataclass
class _Order:
    key: str
    customer: str
    day: int
    lines: list[_Line]
    state: str = "sale"
    currency: tuple[int, str] = EUR
    deliver_after: int | None = 2
    invoice_after: int | None = 1
    refund: tuple[int, Decimal] | None = None  # (days after invoice, refunded quantity on the first line)
    freight_line: bool = False


@dataclass
class _Builder:
    anchor: date
    window_start: date
    source_instance: str
    records: dict[str, list[dict[str, Any]]] = field(default_factory=lambda: defaultdict(list))
    keys: dict[str, dict[int, str]] = field(default_factory=lambda: defaultdict(dict))
    counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def add(self, model: str, key: str, **values: Any) -> int:
        self.counters[model] += 1
        record_id = self.counters[model]
        self.records[model].append({"id": record_id, **values})
        self.keys[model][record_id] = key
        return record_id

    def day(self, offset: int) -> date:
        return self.window_start + timedelta(days=offset)


class _DemoGenerator:
    def __init__(self, anchor: date, seed: int):
        self.rng = random.Random(seed)  # noqa: S311 - reproducible synthetic data, not security
        self.anchor = anchor
        self.seed = seed
        window_start = anchor - timedelta(days=WINDOW_DAYS - 1)
        self.b = _Builder(anchor, window_start, f"fixture_{DATASET_ID}")
        self.partner_ids: dict[str, int] = {}
        self.product_ids: dict[str, int] = {}
        self.product_names: dict[str, str] = {}
        self.account_ids = {k: v[0] for k, v in ACCOUNTS.items()}
        self.ref_cost: dict[str, Decimal] = {}
        self.receipt_cost: dict[str, Decimal | None] = {}
        self.list_price: dict[str, Decimal] = {}

    # ------------------------------------------------------------------ reference data
    def reference_data(self) -> None:
        b = self.b
        start = dt(b.day(0), 0)
        b.add(
            "res.company",
            "company",
            name=COMPANY[1],
            currency_id=m2o(EUR),
            country_id=[75, "France"],
            parent_id=False,
            write_date=start,
        )
        b.add("res.currency", "EUR", name="EUR", decimal_places=2, rounding=0.01, active=True, write_date=start)
        b.add("res.currency", "USD", name="USD", decimal_places=2, rounding=0.01, active=True, write_date=start)
        b.add(
            "res.currency.rate",
            "USD_1",
            name=str(b.day(-30)),
            rate=1.08,
            currency_id=m2o(USD),
            company_id=m2o(COMPANY),
            write_date=start,
        )
        b.add(
            "res.currency.rate",
            "USD_2",
            name=str(b.day(58)),
            rate=1.10,
            currency_id=m2o(USD),
            company_id=m2o(COMPANY),
            write_date=dt(b.day(58), 0),
        )
        b.add(
            "uom.uom", "units", name="Units", factor=1.0, relative_factor=1.0, relative_uom_id=False, write_date=start
        )
        b.add(
            "uom.uom",
            "dozens",
            name="Dozens",
            factor=12.0,
            relative_factor=12.0,
            relative_uom_id=m2o(UNITS),
            write_date=start,
        )
        for code, name, account_type in ((v[1], v[2], v[3]) for v in ACCOUNTS.values()):
            b.add(
                "account.account", f"account_{code}", code=code, name=name, account_type=account_type, write_date=start
            )
        goods = b.add(
            "product.category",
            "categ_goods",
            name="BENACTA_DEMO Goods",
            complete_name="BENACTA_DEMO Goods",
            property_cost_method="fifo",
            property_valuation="real_time",
            write_date=start,
        )
        services = b.add(
            "product.category",
            "categ_services",
            name="BENACTA_DEMO Services",
            complete_name="BENACTA_DEMO Services",
            property_cost_method="standard",
            property_valuation="periodic",
            write_date=start,
        )

        # One public price list; customer-specific lists are attached to partners by scenarios.
        self.public_pricelist = b.add(
            "product.pricelist",
            "pricelist_public",
            name="BENACTA_DEMO Public",
            currency_id=m2o(EUR),
            company_id=m2o(COMPANY),
            active=True,
            item_ids=[],
            write_date=start,
        )
        for key, name in SUPPLIERS.items():
            self.partner_ids[key] = b.add(
                "res.partner",
                f"partner_{key}",
                name=name,
                ref=key,
                company_id=m2o(COMPANY),
                is_company=True,
                customer_rank=0,
                supplier_rank=1,
                commercial_partner_id=False,
                property_product_pricelist=False,
                email=f"{key.lower()}@benacta-demo.invalid",
                write_date=start,
            )
        for key, (name, _segment, _freight) in {**BACKGROUND_CUSTOMERS, **SCENARIO_CUSTOMERS}.items():
            self.partner_ids[key] = b.add(
                "res.partner",
                f"partner_{key}",
                name=name,
                ref=key,
                company_id=m2o(COMPANY),
                is_company=True,
                customer_rank=1,
                supplier_rank=0,
                commercial_partner_id=False,
                property_product_pricelist=[self.public_pricelist, "BENACTA_DEMO Public"],
                email=f"{key.lower()}@benacta-demo.invalid",
                write_date=start,
            )
        for partner in b.records["res.partner"]:
            partner["commercial_partner_id"] = [partner["id"], partner["name"]]

        products = [(code, n, p, c, c, "S") for code, (n, p, c, _s) in CATALOGUE.items()]
        products += [(code, n, p, c, r, "SC") for code, (n, p, c, r, _q, _s) in SCENARIO_PRODUCTS.items()]
        for code, name, price, ref_cost, receipt_cost, _kind in products:
            template = b.add(
                "product.template",
                f"template_{code}",
                name=f"{name} {code}",
                type="consu",
                is_storable=True,
                categ_id=[goods, "BENACTA_DEMO Goods"],
                list_price=float(price),
                uom_id=m2o(UNITS),
                company_id=m2o(COMPANY),
                seller_ids=[],
                write_date=start,
            )
            self.product_ids[code] = b.add(
                "product.product",
                f"product_{code}",
                product_tmpl_id=[template, f"{name} {code}"],
                default_code=code,
                standard_price=float(ref_cost),
                write_date=start,
            )
            self.product_names[code] = f"[{code}] {name} {code}"
            self.list_price[code] = Decimal(price)
            self.ref_cost[code] = Decimal(ref_cost)
            self.receipt_cost[code] = Decimal(receipt_cost) if receipt_cost else None
        code, name, price = FREIGHT_PRODUCT
        template = b.add(
            "product.template",
            "template_FRT",
            name=name,
            type="service",
            is_storable=False,
            categ_id=[services, "BENACTA_DEMO Services"],
            list_price=float(price),
            uom_id=m2o(UNITS),
            company_id=m2o(COMPANY),
            seller_ids=[],
            write_date=start,
        )
        self.product_ids[code] = b.add(
            "product.product",
            "product_FRT",
            product_tmpl_id=[template, name],
            default_code=code,
            standard_price=0.0,
            write_date=start,
        )
        self.product_names[code] = f"[{code}] {name}"
        self.list_price[code] = Decimal(price)

    # ------------------------------------------------------------------ sales plan
    def background_orders(self) -> list[_Order]:
        orders: list[_Order] = []
        customers = list(BACKGROUND_CUSTOMERS)
        products = list(CATALOGUE)
        draft_slots = {25, 51, 77, 103}
        for n in range(1, 107):
            customer = self.rng.choice(customers)
            segment, freight = BACKGROUND_CUSTOMERS[customer][1:]
            caps = [0, 2, 5, 8, 10] if segment == "key_account" else [0, 2, 3, 5]
            lines = [
                _Line(code, Decimal(self.rng.randint(1, 20)), self.list_price[code], Decimal(self.rng.choice(caps)))
                for code in self.rng.sample(products, self.rng.randint(1, 3))
            ]
            day = 3 + (n * 86) // 106  # spread over days 3 to 89; the last orders are not yet delivered or invoiced
            order = _Order(f"BD/SO/{n:04d}", customer, day, lines, freight_line=freight == "rebill")
            if n in draft_slots:
                order.state, order.deliver_after, order.invoice_after = "draft", None, None
            elif day + 2 > WINDOW_DAYS - 1:
                order.deliver_after = None
            elif day + 3 > WINDOW_DAYS - 1:
                order.invoice_after = None
            orders.append(order)
        return orders

    def scenario_orders(self) -> list[_Order]:
        P = self.list_price
        return [
            _Order("BD/SO/DISC-001", "G1", 30, [_Line("SC1", Decimal(100), Decimal(100), Decimal(15))]),
            _Order("BD/SO/FREIGHT-001", "G2", 35, [_Line("SC2", Decimal(10), Decimal(200), Decimal(0))]),
            _Order("BD/SO/COST-001", "G3", 40, [_Line("SC3", Decimal(100), Decimal(120), Decimal(0))]),
            _Order("BD/SO/NEG-01", "C04", 45, [_Line("P03", Decimal(20), P["P03"], Decimal(15))]),
            _Order("BD/SO/NEG-02", "N02", 46, [_Line("P09", Decimal(5), P["P09"], Decimal(0))]),
            _Order(
                "BD/SO/NEG-03", "N03", 50, [_Line("P01", Decimal(100), P["P01"], Decimal(0), delivered=Decimal(60))]
            ),
            _Order(
                "BD/SO/NEG-04",
                "C06",
                52,
                [_Line("P04", Decimal(10), P["P04"], Decimal(5))],
                invoice_after=3,
                refund=(5, Decimal(2)),
            ),
            _Order(
                "BD/SO/NEG-05",
                "C07",
                55,
                [_Line("P08", Decimal(3), P["P08"], Decimal(20))],
                state="cancel",
                deliver_after=None,
                invoice_after=None,
            ),
            _Order(
                "BD/SO/NEG-06",
                "C09",
                57,
                [_Line("P05", Decimal(5), P["P05"] * 12, Decimal(5), uom=DOZENS, qty_units=Decimal(60))],
            ),
            _Order("BD/SO/NEG-07", "C10", 60, [_Line("P06", Decimal(4), Decimal(430), Decimal(5))], currency=USD),
            _Order("BD/SO/NEG-08", "C11", 62, [_Line("SC4", Decimal(10), P["SC4"], Decimal(0))]),
            _Order("BD/SO/NEG-09", "N09", 65, [_Line("P02", Decimal(6), P["P02"], Decimal(12))]),
            _Order("BD/SO/NEG-10", "N10", 66, [_Line("P07", Decimal(2), P["P07"], Decimal(8))]),
            _Order("BD/SO/NEG-12", "C12", 70, [_Line("SC5", Decimal(50), Decimal(100), Decimal(15))]),
        ]

    # ------------------------------------------------------------------ purchasing
    def receipts(self, orders: list[_Order]) -> None:
        b = self.b
        demand: dict[str, Decimal] = defaultdict(Decimal)
        for order in orders:
            if order.state != "sale":
                continue
            for line in order.lines:
                if line.product in CATALOGUE:
                    demand[line.product] += line.qty_units or line.qty
        per_supplier: dict[str, list[tuple[str, Decimal, Decimal]]] = defaultdict(list)
        for code, (_n, _p, _c, supplier) in CATALOGUE.items():
            per_supplier[supplier].append((code, demand[code] + 20, self.ref_cost[code]))
        for code, (_n, _p, _c, cost, qty, supplier) in SCENARIO_PRODUCTS.items():
            if cost is not None and qty:
                per_supplier[supplier].append((code, Decimal(qty), Decimal(cost)))

        for index, supplier in enumerate(sorted(per_supplier), start=1):
            order_day, receipt_day = b.day(0), b.day(2)
            po_name = f"BD/PO/{index:04d}"
            partner = [self.partner_ids[supplier], SUPPLIERS[supplier]]
            po_id = b.add(
                "purchase.order",
                f"po_{index:04d}",
                name=po_name,
                partner_id=partner,
                company_id=m2o(COMPANY),
                currency_id=m2o(EUR),
                date_order=dt(order_day),
                state="purchase",
                write_date=dt(receipt_day, 10),
            )
            picking = b.add(
                "stock.picking",
                f"receipt_{index:04d}",
                name=f"BD/IN/{index:04d}",
                origin=po_name,
                sale_id=False,
                partner_id=partner,
                company_id=m2o(COMPANY),
                picking_type_code="incoming",
                state="done",
                date_done=dt(receipt_day, 10),
                write_date=dt(receipt_day, 10),
            )
            for code, qty, cost in per_supplier[supplier]:
                pol = b.add(
                    "purchase.order.line",
                    f"pol_{index:04d}_{code}",
                    order_id=[po_id, po_name],
                    product_id=[self.product_ids[code], self.product_names[code]],
                    product_qty=float(qty),
                    uom_id=m2o(UNITS),
                    price_unit=float(cost),
                    qty_received=float(qty),
                    qty_invoiced=0.0,
                    move_ids=[],
                    write_date=dt(receipt_day, 10),
                )
                move = self._move(picking, code, qty, money(qty * cost), cost, receipt_day, 10, purchase_line=pol)
                b.records["purchase.order.line"][-1]["move_ids"] = [move]

    def _move(
        self,
        picking: int,
        code: str,
        qty: Decimal,
        value: Decimal,
        unit: Decimal,
        day: date,
        hour: int,
        *,
        purchase_line: int | None = None,
        sale_line: int | None = None,
    ) -> int:
        b = self.b
        incoming = purchase_line is not None
        return b.add(
            "stock.move",
            f"move_{'in' if incoming else 'out'}_{b.counters['stock.move'] + 1:05d}",
            picking_id=[picking, ""],
            sale_line_id=[sale_line, ""] if sale_line else False,
            purchase_line_id=[purchase_line, ""] if purchase_line else False,
            product_id=[self.product_ids[code], self.product_names[code]],
            company_id=m2o(COMPANY),
            state="done",
            date=dt(day, hour),
            product_uom_qty=float(qty),
            quantity=float(qty),
            uom_id=m2o(UNITS),
            price_unit=float(unit),
            account_move_id=False,
            location_id=[4, "Partners/Vendors"] if incoming else [8, "WH/Stock"],
            location_dest_id=[8, "WH/Stock"] if incoming else [5, "Partners/Customers"],
            value=float(value),
            write_date=dt(day, hour),
        )

    # ------------------------------------------------------------------ sales documents
    def sale(self, order: _Order) -> None:
        b = self.b
        order_day = b.day(order.day)
        customer_name = ({**BACKGROUND_CUSTOMERS, **SCENARIO_CUSTOMERS})[order.customer][0]
        partner = [self.partner_ids[order.customer], customer_name]
        so_id = b.add(
            "sale.order",
            f"so_{order.key}",
            name=order.key,
            partner_id=partner,
            company_id=m2o(COMPANY),
            currency_id=m2o(order.currency),
            pricelist_id=[self.public_pricelist, "BENACTA_DEMO Public"] if order.currency == EUR else False,
            date_order=dt(order_day),
            state=order.state,
            order_line=[],
            invoice_ids=[],
            picking_ids=[],
            write_date=dt(order_day),
        )
        so = b.records["sale.order"][-1]
        lines = list(order.lines)
        if order.freight_line:
            lines.append(_Line("FRT", Decimal(1), FREIGHT_AMOUNT, Decimal(0)))

        delivered_day = b.day(order.day + order.deliver_after) if order.deliver_after is not None else None
        invoice_day = (
            delivered_day + timedelta(days=order.invoice_after)
            if delivered_day is not None and order.invoice_after is not None
            else None
        )
        sol_records = []
        for line in lines:
            delivered = (
                Decimal(0) if delivered_day is None else (line.delivered if line.delivered is not None else line.qty)
            )
            invoiced = (
                Decimal(0) if invoice_day is None else (line.invoiced if line.invoiced is not None else delivered)
            )
            subtotal = money(line.qty * line.price_unit * (1 - line.discount / 100))
            sol = b.add(
                "sale.order.line",
                f"sol_{order.key}_{line.product}",
                order_id=[so_id, order.key],
                product_id=[self.product_ids[line.product], self.product_names[line.product]],
                company_id=m2o(COMPANY),
                currency_id=m2o(order.currency),
                display_type=False,
                product_uom_qty=float(line.qty),
                product_uom_id=m2o(line.uom),
                price_unit=float(line.price_unit),
                discount=float(line.discount),
                price_subtotal=float(subtotal),
                qty_delivered=float(delivered),
                qty_invoiced=float(invoiced),
                invoice_lines=[],
                move_ids=[],
                tax_ids=[],
                write_date=dt(order_day),
            )
            sol_records.append((sol, line, delivered))
        so["order_line"] = [s for s, _l, _d in sol_records]

        if delivered_day is not None:
            picking = b.add(
                "stock.picking",
                f"delivery_{order.key}",
                name=f"BD/OUT/{order.key[6:]}",
                origin=order.key,
                sale_id=[so_id, order.key],
                partner_id=partner,
                company_id=m2o(COMPANY),
                picking_type_code="outgoing",
                state="done",
                date_done=dt(delivered_day, 15),
                write_date=dt(delivered_day, 15),
            )
            so["picking_ids"] = [picking]
            so["write_date"] = dt(delivered_day, 15)
            for sol, line, delivered in sol_records:
                if line.product == "FRT":
                    continue
                units = line.qty_units if line.qty_units is not None else delivered
                cost = self.receipt_cost.get(line.product, self.ref_cost.get(line.product))
                value = money(units * cost) if cost is not None else Decimal(0)
                unit = cost if cost is not None else Decimal(0)
                move = self._move(picking, line.product, units, value, unit, delivered_day, 15, sale_line=sol)
                self._sol(sol)["move_ids"] = [move]
                self._sol(sol)["write_date"] = dt(delivered_day, 15)

        if invoice_day is not None:
            invoice = self.invoice(order, so_id, partner, sol_records, invoice_day, "out_invoice")
            so["invoice_ids"] = [invoice]
            so["write_date"] = dt(invoice_day, 11)
            if order.refund:
                days_after, refunded = order.refund
                first = sol_records[0]
                refund = self.invoice(
                    order,
                    so_id,
                    partner,
                    [(first[0], first[1], refunded)],
                    invoice_day + timedelta(days=days_after),
                    "out_refund",
                    reversed_entry=invoice,
                )
                so["invoice_ids"].append(refund)
                self._sol(first[0])["qty_invoiced"] = float(first[2] - refunded)
                so["write_date"] = dt(invoice_day + timedelta(days=days_after), 11)

    def _sol(self, sol_id: int) -> dict[str, Any]:
        return next(r for r in self.b.records["sale.order.line"] if r["id"] == sol_id)

    def _rate(self, currency: tuple[int, str], day: date) -> Decimal:
        if currency == EUR:
            return Decimal(1)
        rates = [
            r
            for r in self.b.records["res.currency.rate"]
            if r["currency_id"][0] == currency[0] and r["name"] <= str(day)
        ]
        return Decimal(str(max(rates, key=lambda r: r["name"])["rate"]))

    def invoice(
        self,
        order: _Order | None,
        so_id: int | None,
        partner: list,
        lines: list[tuple[int | None, _Line, Decimal]],
        day: date,
        move_type: str,
        *,
        reversed_entry: int | None = None,
        name: str | None = None,
    ) -> int:
        b = self.b
        currency = order.currency if order else EUR
        rate = self._rate(currency, day)
        sign = Decimal(-1) if move_type == "out_invoice" else Decimal(1)  # revenue is a credit
        prefix = "BD/INV" if move_type == "out_invoice" else "BD/RINV"
        move_name = name or f"{prefix}/{b.counters['account.move'] + 1:04d}"
        move_id = b.add(
            "account.move",
            f"move_{move_name}",
            name=move_name,
            move_type=move_type,
            state="posted",
            company_id=m2o(COMPANY),
            partner_id=partner,
            currency_id=m2o(currency),
            invoice_date=str(day),
            date=str(day),
            invoice_origin=order.key if order else False,
            reversed_entry_id=[reversed_entry, ""] if reversed_entry else False,
            amount_untaxed_signed=0.0,
            payment_state="not_paid",
            write_date=dt(day, 11),
        )
        move = b.records["account.move"][-1]
        untaxed = Decimal(0)
        untaxed_company = Decimal(0)
        for sol, line, qty in lines:
            if qty == 0:
                continue
            subtotal = money(qty * line.price_unit * (1 - line.discount / 100))
            company_amount = money(subtotal / rate)
            untaxed += subtotal
            untaxed_company += company_amount
            account = "sales_services" if line.product == "FRT" else "sales_goods"
            aml = self._aml(
                move_id,
                move_name,
                day,
                currency,
                "product",
                account,
                line.product,
                qty,
                line.uom,
                line.price_unit,
                line.discount,
                subtotal,
                sign * company_amount,
                sign * subtotal,
                [sol] if sol else [],
            )
            if sol:
                self._sol(sol)["invoice_lines"].append(aml)
                self._sol(sol)["write_date"] = dt(day, 11)
            cost = self.receipt_cost.get(line.product) if line.product not in CATALOGUE else self.ref_cost[line.product]
            if line.product != "FRT" and cost:
                units = line.qty_units if line.qty_units is not None else qty
                cogs = money(units * cost)
                direction = Decimal(1) if move_type == "out_invoice" else Decimal(-1)
                self._aml(
                    move_id,
                    move_name,
                    day,
                    EUR,
                    "cogs",
                    "cogs",
                    line.product,
                    units,
                    UNITS,
                    cost,
                    Decimal(0),
                    Decimal(0),
                    direction * cogs,
                    direction * cogs,
                    [],
                )
                self._aml(
                    move_id,
                    move_name,
                    day,
                    EUR,
                    "cogs",
                    "stock_valuation",
                    line.product,
                    units,
                    UNITS,
                    cost,
                    Decimal(0),
                    Decimal(0),
                    -direction * cogs,
                    -direction * cogs,
                    [],
                )
        tax = money(untaxed_company * VAT)
        self._aml(
            move_id,
            move_name,
            day,
            currency,
            "tax",
            "vat_collected",
            None,
            Decimal(0),
            None,
            Decimal(0),
            Decimal(0),
            Decimal(0),
            sign * tax,
            sign * money(untaxed * VAT),
            [],
        )
        self._aml(
            move_id,
            move_name,
            day,
            currency,
            "payment_term",
            "receivable",
            None,
            Decimal(0),
            None,
            Decimal(0),
            Decimal(0),
            Decimal(0),
            -sign * (untaxed_company + tax),
            -sign * money(untaxed * (1 + VAT)),
            [],
        )
        move["amount_untaxed_signed"] = float(-sign * untaxed_company)
        return move_id

    def _aml(
        self,
        move_id: int,
        move_name: str,
        day: date,
        currency: tuple[int, str],
        display_type: str,
        account: str,
        product: str | None,
        qty: Decimal,
        uom: tuple[int, str] | None,
        price_unit: Decimal,
        discount: Decimal,
        subtotal: Decimal,
        balance: Decimal,
        amount_currency: Decimal,
        sale_lines: list[int],
    ) -> int:
        code, name = ACCOUNTS[account][1], ACCOUNTS[account][2]
        return self.b.add(
            "account.move.line",
            f"aml_{self.b.counters['account.move.line'] + 1:05d}",
            move_id=[move_id, move_name],
            company_id=m2o(COMPANY),
            account_id=[self.account_ids[account], f"{code} {name}"],
            display_type=display_type,
            parent_state="posted",
            product_id=[self.product_ids[product], self.product_names[product]] if product else False,
            quantity=float(qty),
            product_uom_id=m2o(uom),
            price_unit=float(price_unit),
            discount=float(discount),
            price_subtotal=float(subtotal),
            balance=float(balance),
            amount_currency=float(amount_currency),
            currency_id=m2o(currency),
            date=str(day),
            sale_line_ids=sale_lines,
            write_date=dt(day, 11),
        )

    # ------------------------------------------------------------------ assembly
    def build(self) -> FixtureDataset:
        self.reference_data()
        background = self.background_orders()
        scenarios = self.scenario_orders()
        orders = sorted(background + scenarios, key=lambda o: (o.day, o.key))
        self.receipts(orders)
        for order in orders:
            self.sale(order)
        # NEG-11: a posted customer invoice with no sale order behind it.
        c12 = [self.partner_ids["C12"], BACKGROUND_CUSTOMERS["C12"][0]]
        self.invoice(
            None,
            None,
            c12,
            [(None, _Line("P10", Decimal(10), self.list_price["P10"], Decimal(0)), Decimal(10))],
            self.b.day(68),
            "out_invoice",
            name="BD/INV/NEG-11",
        )
        return FixtureDataset(
            dataset_id=DATASET_ID,
            source_instance=self.b.source_instance,
            anchor_date=self.anchor,
            window_start=self.b.window_start,
            seed=self.seed,
            records=dict(self.b.records),
            keys=dict(self.b.keys),
            terms=self.terms(),
        )

    def terms(self) -> dict[str, Any]:
        """Business context the rules will read in later sprints. Dates are absolute, derived from the anchor."""
        day = self.b.day
        segments = {k: v[1] for k, v in {**BACKGROUND_CUSTOMERS, **SCENARIO_CUSTOMERS}.items()}
        freight = {k: v[2] for k, v in {**BACKGROUND_CUSTOMERS, **SCENARIO_CUSTOMERS}.items() if v[2]}
        return {
            "customer_segments": segments,
            "discount_policies": [
                {
                    "policy_id": "POL-DISC-STANDARD",
                    "version": 1,
                    "scope": {"segment": "standard"},
                    "max_discount_pct": "5",
                    "priority": 10,
                    "valid_from": str(day(-200)),
                    "valid_to": None,
                },
                {
                    "policy_id": "POL-DISC-KEY-ACCOUNT",
                    "version": 1,
                    "scope": {"segment": "key_account"},
                    "max_discount_pct": "10",
                    "priority": 10,
                    "valid_from": str(day(-200)),
                    "valid_to": None,
                },
                {
                    "policy_id": "POL-DISC-DISTRIBUTOR",
                    "version": 1,
                    "scope": {"segment": "distributor"},
                    "max_discount_pct": "12",
                    "priority": 10,
                    "valid_from": str(day(-400)),
                    "valid_to": str(day(-1)),
                },
                {
                    "policy_id": "POL-DISC-UBAYE-A",
                    "version": 1,
                    "scope": {"customer": "N10"},
                    "max_discount_pct": "5",
                    "priority": 30,
                    "valid_from": str(day(-100)),
                    "valid_to": None,
                },
                {
                    "policy_id": "POL-DISC-UBAYE-B",
                    "version": 1,
                    "scope": {"customer": "N10"},
                    "max_discount_pct": "10",
                    "priority": 30,
                    "valid_from": str(day(-60)),
                    "valid_to": None,
                },
            ],
            "discount_derogations": [
                {
                    "derogation_id": "DEROG-2026-014",
                    "order": "BD/SO/NEG-01",
                    "max_discount_pct": "15",
                    "approved_by_role": "finance_approver",
                    "approved_on": str(day(44)),
                    "valid_from": str(day(44)),
                    "valid_to": str(day(60)),
                },
            ],
            "freight_contracts": [
                {
                    "contract_id": f"CTR-FREIGHT-{customer}",
                    "customer": customer,
                    "terms": terms,
                    "amount": str(FREIGHT_AMOUNT) if terms == "rebill" else "0",
                    "currency": "EUR",
                    "trigger": "full_delivery" if terms == "rebill" else None,
                    "valid_from": str(day(-200)),
                    "valid_to": None,
                }
                for customer, terms in sorted(freight.items())
            ],
            "cost_references": [
                {
                    "reference_id": "REF-COST-Q3",
                    "product": code,
                    "unit_cost": str(cost),
                    "frozen_on": str(day(-1)),
                    "valid_from": str(day(-1)),
                    "valid_to": str(day(WINDOW_DAYS + 30)),
                }
                for code, cost in sorted(self.ref_cost.items())
            ],
        }


def build_demo_dataset(anchor: date = DEFAULT_ANCHOR, seed: int = DEFAULT_SEED) -> FixtureDataset:
    return _DemoGenerator(anchor, seed).build()
