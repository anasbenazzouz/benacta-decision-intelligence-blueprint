"""Demonstration profile `demo_full`: a synthetic industrial company over three fiscal years, shaped like Odoo 19.

Built on the same generator as `demo_v1` (records in Odoo shapes, same ingestion, same marts, same rules), scaled
and made realistic: hundreds of customers with sizes, segments, countries and currencies; a hundred suppliers;
two hundred products in ten families with their own margin profiles; seasonality, growth and a year-three mix
shift; quarterly reference-cost freezes with drift; price lists and contract prices; partial deliveries and
backorders; refunds; payment terms and late payments; a pipeline of open orders at the anchor.

Most transactions are compliant by construction. A controlled minority carries injected scenarios. Their ground
truth (identifier, family, subject, expected rule outcome, class, cause, amount, evidence, recommended action)
is returned next to the records as `dataset.ground_truth`, never inside them: the engine reads business data and
governed terms only. `scripts/export_ground_truth.py` writes the manifest under `data/golden/` for review, and a
test checks the committed manifest still equals the generated one.

Every name, customer, supplier, product and amount is invented. Deterministic across processes: no set iteration
decides an identifier.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.fixtures.demo_dataset import (
    ACCOUNTS,
    CENT,
    COMPANY,
    EUR,
    UNITS,
    USD,
    VAT,
    FixtureDataset,
    _Builder,
    _DemoGenerator,
    _Line,
    _Order,
    dt,
    m2o,
    money,
)

PROFILE_ID = "demo_full"
FULL_SEED = 20260831
MONTHS = 36
GBP = (3, "GBP")
CHF = (4, "CHF")
CURRENCIES = {"EUR": EUR, "USD": USD, "GBP": GBP, "CHF": CHF}
# Units of currency per EUR, one rate per month with a slow drift (Odoo convention).
BASE_RATES = {"USD": Decimal("1.08"), "GBP": Decimal("0.86"), "CHF": Decimal("0.96")}
MATERIALITY = Decimal(200)

# code prefix: (family name, cost ratio, price band, weight in year 1-2, weight in year 3, unit cost drift per year)
FAMILIES = {
    "SEN": ("Sensors and instrumentation", Decimal("0.55"), (60, 420), 5, 5, Decimal("0.02")),
    "FLW": ("Flow and level measurement", Decimal("0.56"), (120, 900), 4, 4, Decimal("0.02")),
    "VLV": ("Valves and actuators", Decimal("0.54"), (90, 700), 4, 4, Decimal("0.03")),
    "DRV": ("Drives and motors", Decimal("0.58"), (200, 1500), 3, 3, Decimal("0.03")),
    "CTL": ("Control and automation", Decimal("0.60"), (150, 1200), 3, 3, Decimal("0.01")),
    "SAF": ("Safety components", Decimal("0.57"), (100, 800), 2, 2, Decimal("0.02")),
    "SPR": ("Spare parts", Decimal("0.63"), (20, 250), 4, 8, Decimal("0.04")),
    "CON": ("Consumables and filters", Decimal("0.66"), (10, 120), 3, 7, Decimal("0.04")),
    "ENC": ("Enclosures and cabinets", Decimal("0.59"), (150, 900), 2, 2, Decimal("0.02")),
    "TLG": ("Tooling and calibration", Decimal("0.52"), (80, 600), 2, 2, Decimal("0.01")),
}
PRODUCT_WORDS = ["Pressure", "Temperature", "Flow", "Level", "Proximity", "Vibration", "Gas", "Optical", "Servo", "Gear", "Linear",
                 "Rotary", "Ball", "Butterfly", "Solenoid", "Check", "Relay", "Module", "Panel", "Drive", "Curtain", "Guard", "Seal",
                 "Bearing", "Coupling", "Filter", "Cartridge", "Gland", "Cabinet", "Rack", "Gauge", "Probe", "Bench", "Kit", "Unit"]
CUSTOMER_A = ["Alcor", "Brevan", "Castell", "Dorval", "Estrel", "Fontaine", "Garnier", "Halden", "Ivry", "Jura", "Keraval", "Lumen", "Morvan",
              "Nerac", "Orsay", "Pelican", "Quimper", "Rocroi", "Sarlat", "Tessier", "Ubaye", "Vannes", "Wissant", "Yssingeaux", "Zuydcoote",
              "Auray", "Bergerac", "Cahors", "Dinan", "Embrun", "Figeac", "Gisors", "Honfleur", "Issoire", "Josselin", "Kaysersberg", "Lannion",
              "Millau", "Nyons", "Oloron", "Pontivy", "Quillan", "Riom", "Saumur", "Tulle", "Uzes", "Vitre", "Wasselonne", "Yvetot", "Zonza",
              "Rennes", "Nantes", "Colmar", "Arles", "Belfort", "Chartres", "Dax", "Epinal", "Foix", "Gap"]
CUSTOMER_B = ["Process Systems", "Energy", "Pharma Plants", "Packaging", "Water Services", "Agro", "Metalworks", "Logistics", "Food Lines",
              "Precision", "Chemicals", "Glassworks", "Paper", "Textiles", "Hydraulics", "Marine Yards", "Thermal", "Mining", "Cement",
              "Distribution", "Trade Partners", "Trading", "Automation", "Plastics", "Composites", "Foundry", "Cranes", "Rail Works", "Aero Parts"]
SUPPLIER_A = ["Nordline", "Atelier", "Rhone", "Kessler", "Meridian", "Baltic", "Ardennes", "Sud", "Alpine", "Loire", "Vosges", "Delta", "Iberia",
              "Hansa", "Tyrol", "Ligure", "Adour", "Moselle", "Escaut", "Garonne"]
SUPPLIER_B = ["Components", "Vasseur", "Industrial Supply", "Automation", "Thermal Parts", "Mechanics", "Electric", "Fluid Systems", "Precision",
              "Fasteners", "Castings", "Controls", "Filtration", "Enclosures", "Instruments"]
COUNTRIES = [("FR", "France", 75, "EUR", 70), ("DE", "Germany", 57, "EUR", 8), ("BE", "Belgium", 20, "EUR", 6), ("ES", "Spain", 68, "EUR", 4),
             ("IT", "Italy", 109, "EUR", 4), ("NL", "Netherlands", 165, "EUR", 3), ("GB", "United Kingdom", 231, "GBP", 2),
             ("US", "United States", 233, "USD", 2), ("CH", "Switzerland", 43, "CHF", 1)]
SEASON = [Decimal(x) for x in ("0.95", "0.90", "1.10", "1.00", "1.00", "1.15", "0.85", "0.60", "1.10", "1.05", "1.15", "0.80")]
GROWTH_PER_YEAR = Decimal("0.04")
SEGMENT_CAPS = {"standard": Decimal(5), "key_account": Decimal(10), "distributor": Decimal(12)}
SIZE_RATE = {"large": Decimal("3.0"), "medium": Decimal("1.0"), "small": Decimal("0.25"), "tail": Decimal("0.03")}
PAYMENT_TERMS = (30, 45, 60)


@dataclass
class Customer:
    key: str
    name: str
    segment: str
    size: str
    country: tuple[str, str, int, str]
    freight: str | None
    freight_amount: Decimal
    terms: int
    pricelist: str  # public or distributor


@dataclass
class Product:
    code: str
    name: str
    family: str
    list_price: Decimal
    base_cost: Decimal
    supplier: str
    scenario: bool = False
    receipt_cost: Decimal | None = None  # scenario products: one receipt at this unit cost (None: no receipt)
    receipt_qty: int = 0


class _FullGenerator(_DemoGenerator):
    """Overrides reference data, order planning, receipts and terms; reuses the document machinery of the base."""

    def __init__(self, anchor: date, seed: int):
        super().__init__(anchor, seed)
        window_start = date(anchor.year, anchor.month, 1)
        for _ in range(MONTHS - 1):
            window_start = (window_start - timedelta(days=1)).replace(day=1)
        self.b = _Builder(anchor, window_start, f"fixture_{PROFILE_ID}")
        self.customers: dict[str, Customer] = {}
        self.products: dict[str, Product] = {}
        self.suppliers: dict[str, str] = {}
        self.quarter_cost: dict[tuple[str, int], Decimal] = {}  # (product, quarter index) -> reference unit cost
        self.scenarios: list[dict[str, Any]] = []
        self.payments: list[dict[str, Any]] = []
        self.pricelist_ids: dict[str, int] = {}
        self.currency_ids: dict[str, int] = {}
        self.layers: dict[str, list[list[Decimal]]] = defaultdict(list)  # product -> [[remaining qty, unit cost], ...] in receipt order
        self.delivery_cost: dict[tuple[str, str], Decimal | None] = {}  # (order key, product) -> FIFO unit cost of its delivery

    # ------------------------------------------------------------------ calendar helpers
    def month_of(self, offset: int) -> date:
        d = self.b.window_start
        for _ in range(offset):
            d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        return d

    def day_in_month(self, offset: int, day: int) -> date:
        first = self.month_of(offset)
        last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        return first.replace(day=min(day, last.day))

    def quarter(self, offset: int) -> int:
        return offset // 3

    def offset_of(self, day: date) -> int:
        return (day.year - self.b.window_start.year) * 12 + day.month - self.b.window_start.month

    # ------------------------------------------------------------------ reference data
    def reference_data(self) -> None:
        b, rng = self.b, self.rng
        start = dt(b.day(0), 0)
        b.add("res.company", "company", name="BENACTA DEMO", currency_id=m2o(EUR), country_id=[75, "France"], parent_id=False, write_date=start)
        for code in CURRENCIES:
            self.currency_ids[code] = b.add("res.currency", code, name=code, decimal_places=2, rounding=0.01, active=True, write_date=start)
        for offset in range(-1, MONTHS):
            day = self.month_of(max(offset, 0)) if offset >= 0 else b.window_start - timedelta(days=15)
            for code, base in BASE_RATES.items():
                drift = Decimal(1) + Decimal(offset + 1) * Decimal("0.0015") + Decimal(rng.randint(-8, 8)) / Decimal(1000)
                b.add("res.currency.rate", f"rate_{code}_{offset}", name=str(day), rate=float(money(base * drift)), currency_id=m2o(CURRENCIES[code]),
                      company_id=m2o(COMPANY), write_date=start)
        b.add("uom.uom", "units", name="Units", factor=1.0, relative_factor=1.0, relative_uom_id=False, write_date=start)
        b.add("uom.uom", "dozens", name="Dozens", factor=12.0, relative_factor=12.0, relative_uom_id=m2o(UNITS), write_date=start)
        for code, name, account_type in ((v[1], v[2], v[3]) for v in ACCOUNTS.values()):
            b.add("account.account", f"account_{code}", code=code, name=name, account_type=account_type, write_date=start)
        goods = b.add("product.category", "categ_goods", name="BENACTA_DEMO Goods", complete_name="BENACTA_DEMO Goods", property_cost_method="fifo",
                      property_valuation="real_time", write_date=start)
        services = b.add("product.category", "categ_services", name="BENACTA_DEMO Services", complete_name="BENACTA_DEMO Services",
                         property_cost_method="standard", property_valuation="periodic", write_date=start)
        self.pricelist_ids["public"] = b.add("product.pricelist", "pricelist_public", name="BENACTA_DEMO Public", currency_id=m2o(EUR),
                                             company_id=m2o(COMPANY), active=True, item_ids=[], write_date=start)
        self.pricelist_ids["distributor"] = b.add("product.pricelist", "pricelist_distributor", name="BENACTA_DEMO Distributor", currency_id=m2o(EUR),
                                                  company_id=m2o(COMPANY), active=True, item_ids=[], write_date=start)
        self.public_pricelist = self.pricelist_ids["public"]
        self.pricelists = {"public": self.pricelist_ids["public"], "distributor": self.pricelist_ids["distributor"]}

        # suppliers
        names = [f"{a} {c}" for a in SUPPLIER_A for c in SUPPLIER_B]
        rng.shuffle(names)
        for i in range(100):
            key = f"S{i + 1:03d}"
            self.suppliers[key] = names[i]
            self.partner_ids[key] = b.add("res.partner", f"partner_{key}", name=names[i], ref=key, company_id=m2o(COMPANY), is_company=True,
                                          customer_rank=0, supplier_rank=1, commercial_partner_id=False, property_product_pricelist=False,
                                          email=f"{key.lower()}@benacta-demo.invalid", write_date=start)
        # products: 20 per family, long tail by weight
        family_codes = list(FAMILIES)
        supplier_keys = list(self.suppliers)
        for fi, family in enumerate(family_codes):
            name, ratio, (low, high), *_ = FAMILIES[family]
            for n in range(20):
                code = f"{family}-{n + 1:03d}"
                price = Decimal(rng.randint(low, high))
                cost = money(price * ratio * (Decimal(1) + Decimal(rng.randint(-8, 8)) / Decimal(100)))
                supplier = supplier_keys[(fi * 10 + n // 2) % 100]
                pname = f"{rng.choice(PRODUCT_WORDS)} {rng.choice(PRODUCT_WORDS)} {n + 1:02d}"
                self.products[code] = Product(code, pname, family, price, cost, supplier)
        # scenario products: one receipt each, sold once (cost scenarios), plus mapping and missing cost
        for i in range(8):
            code = f"SCP-{i + 1:02d}"
            price, cost = Decimal(rng.randint(150, 400)), None
            base = money(price * Decimal("0.56"))
            self.products[code] = Product(code, f"Scenario Plate {i + 1:02d}", "FLW", price, base, "S001", True, money(base * Decimal("1.12")), 120)
        for i in range(3):
            code = f"SCM-{i + 1:02d}"
            price = Decimal(rng.randint(80, 200))
            self.products[code] = Product(code, f"Scenario Coupling {i + 1:02d}", "SPR", price, money(price * Decimal("0.6")), "S002", True, None, 0)
        for code, product in self.products.items():
            template = b.add("product.template", f"template_{code}", name=f"{product.name} {code}", type="consu", is_storable=True,
                             categ_id=[goods, "BENACTA_DEMO Goods"], list_price=float(product.list_price), uom_id=m2o(UNITS), company_id=m2o(COMPANY),
                             seller_ids=[], write_date=start)
            self.product_ids[code] = b.add("product.product", f"product_{code}", product_tmpl_id=[template, f"{product.name} {code}"], default_code=code,
                                           standard_price=float(product.base_cost), write_date=start)
            self.product_names[code] = f"[{code}] {product.name} {code}"
            self.list_price[code] = product.list_price
            self.ref_cost[code] = product.base_cost
            self.receipt_cost[code] = product.receipt_cost if product.scenario else None
            if not product.scenario and code.startswith(("SEN", "FLW", "VLV", "DRV", "CTL", "SAF", "SPR", "CON", "ENC", "TLG")):
                b.add("product.pricelist.item", f"item_distributor_{code}", pricelist_id=[self.pricelist_ids["distributor"], "BENACTA_DEMO Distributor"],
                      applied_on="1_product", product_tmpl_id=[template, f"{product.name} {code}"], product_id=False, categ_id=False, min_quantity=0.0,
                      compute_price="fixed", fixed_price=float(money(product.list_price * Decimal("0.88"))), percent_price=0.0, currency_id=m2o(EUR),
                      date_start=False, date_end=False, write_date=start)
        # a product whose unit of measure is not resolvable (mapping scenario)
        broken = b.add("product.template", "template_MAP-01", name="Unmapped Gauge MAP-01", type="consu", is_storable=True,
                       categ_id=[goods, "BENACTA_DEMO Goods"], list_price=95.0, uom_id=False, company_id=m2o(COMPANY), seller_ids=[], write_date=start)
        self.product_ids["MAP-01"] = b.add("product.product", "product_MAP-01", product_tmpl_id=[broken, "Unmapped Gauge MAP-01"], default_code="MAP-01",
                                           standard_price=50.0, write_date=start)
        self.product_names["MAP-01"] = "[MAP-01] Unmapped Gauge MAP-01"
        self.list_price["MAP-01"] = Decimal(95)
        self.ref_cost["MAP-01"] = Decimal(50)
        self.receipt_cost["MAP-01"] = Decimal(50)
        frt_template = b.add("product.template", "template_FRT", name="Freight rebilling", type="service", is_storable=False,
                             categ_id=[services, "BENACTA_DEMO Services"], list_price=250.0, uom_id=m2o(UNITS), company_id=m2o(COMPANY), seller_ids=[],
                             write_date=start)
        self.product_ids["FRT"] = b.add("product.product", "product_FRT", product_tmpl_id=[frt_template, "Freight rebilling"], default_code="FRT",
                                        standard_price=0.0, write_date=start)
        self.product_names["FRT"] = "[FRT] Freight rebilling"
        self.list_price["FRT"] = Decimal(250)

        # customers
        cnames = [f"{a} {c}" for a in CUSTOMER_A for c in CUSTOMER_B]
        rng.shuffle(cnames)
        weights = [c[4] for c in COUNTRIES]
        for i in range(500):
            key = f"C{i + 1:03d}"
            country = rng.choices(COUNTRIES, weights=weights)[0]
            roll = rng.random()
            segment = "key_account" if roll < 0.06 else ("distributor" if roll < 0.20 else "standard")
            roll = rng.random()
            size = "large" if roll < 0.05 else ("medium" if roll < 0.30 else ("small" if roll < 0.80 else "tail"))
            roll = rng.random()
            freight = "rebill" if roll < 0.30 else ("waived" if roll < 0.40 else None)
            amount = Decimal({"large": 400, "medium": 250, "small": 180, "tail": 150}[size]) if freight == "rebill" else Decimal(0)
            self.customers[key] = Customer(key, cnames[i], segment, size, country[:4], freight, amount, rng.choice(PAYMENT_TERMS),
                                           "distributor" if segment == "distributor" else "public")
            pricelist = self.pricelist_ids[self.customers[key].pricelist]
            self.partner_ids[key] = b.add("res.partner", f"partner_{key}", name=cnames[i], ref=key, company_id=m2o(COMPANY), is_company=True,
                                          customer_rank=1, supplier_rank=0, commercial_partner_id=False,
                                          property_product_pricelist=[pricelist, "BENACTA_DEMO " + self.customers[key].pricelist.capitalize()],
                                          country_id=[country[2], country[1]], email=f"{key.lower()}@benacta-demo.invalid", write_date=start)
        # scenario customers with their own traits
        for key, name, segment, freight in (("G01", "Gravelines Hydraulics", "standard", None), ("G02", "Seyne Marine Yards", "standard", "rebill"),
                                            ("G03", "Bolbec Thermal", "standard", None), ("N01", "Morlaix Distribution", "distributor", None),
                                            ("N02", "Aubagne Trade Partners", "distributor", None)):
            self.customers[key] = Customer(key, name, segment, "medium", ("FR", "France", 75, "EUR"), freight, Decimal(250), 30,
                                           "distributor" if segment == "distributor" else "public")
            pricelist = self.pricelist_ids[self.customers[key].pricelist]
            self.partner_ids[key] = b.add("res.partner", f"partner_{key}", name=name, ref=key, company_id=m2o(COMPANY), is_company=True, customer_rank=1,
                                          supplier_rank=0, commercial_partner_id=False,
                                          property_product_pricelist=[pricelist, "BENACTA_DEMO " + self.customers[key].pricelist.capitalize()],
                                          country_id=[75, "France"], email=f"{key.lower()}@benacta-demo.invalid", write_date=start)
        for partner in b.records["res.partner"]:
            partner["commercial_partner_id"] = [partner["id"], partner["name"]]
        # quarterly reference costs with drift and supplier noise
        for code, product in self.products.items():
            drift = FAMILIES[product.family][5]
            for q in range(MONTHS // 3):
                factor = (Decimal(1) + drift) ** Decimal(q) if q else Decimal(1)
                self.quarter_cost[(code, q)] = money(product.base_cost * Decimal(str(round(float(factor) ** (1 / 4), 6)))) if False else money(
                    product.base_cost * (Decimal(1) + drift * Decimal(q) / Decimal(4)) * (Decimal(1) + Decimal(rng.randint(-10, 10)) / Decimal(1000)))
        self.quarter_cost[("MAP-01", 0)] = Decimal(50)

    def customer_name(self, key: str) -> str:
        return self.customers[key].name

    # ------------------------------------------------------------------ price helpers
    def unit_price(self, customer: Customer, code: str, day: date | None = None) -> Decimal:
        """Price in the customer's currency: EUR terms converted at the rate valid on the order date."""
        product = self.products.get(code)
        if product is None:
            price = self.list_price[code]
        elif (customer.key, code) in self.contract_prices:
            price = self.contract_prices[(customer.key, code)]
        elif customer.pricelist == "distributor" and not product.scenario:
            price = money(product.list_price * Decimal("0.88"))
        else:
            price = product.list_price
        return self.in_currency(price, customer, day)

    def in_currency(self, amount: Decimal, customer: Customer, day: date | None) -> Decimal:
        if customer.country[3] == "EUR" or day is None:
            return amount
        return money(amount * self._rate(CURRENCIES[customer.country[3]], day))

    def _pick_products(self, offset: int, n: int) -> list[str]:
        year = offset // 12
        codes, weights = [], []
        for code, product in self.products.items():
            if product.scenario:
                continue
            fam = FAMILIES[product.family]
            weight = fam[4] if year >= 2 else fam[3]
            weight *= 3 if int(code[-3:]) <= 8 else 1  # long tail: the first eight products of a family carry most lines
            codes.append(code)
            weights.append(weight)
        return self.rng.choices(codes, weights=weights, k=n)

    # ------------------------------------------------------------------ order plan
    def background_orders(self) -> list[_Order]:
        rng = self.rng
        self.contract_prices: dict[tuple[str, str], Decimal] = {}
        key_accounts = [c for c in self.customers.values() if c.segment == "key_account" and c.key.startswith("C") and c.country[3] == "EUR"][:20]
        for customer in key_accounts:
            for code in self._pick_products(0, 3):
                self.contract_prices[(customer.key, code)] = money(self.products[code].list_price * Decimal("0.93"))
        self.gap_start, self.gap_end = self.day_in_month(31, 3), self.day_in_month(31, 20)  # distributor policy gap, month 32
        orders: list[_Order] = []
        n = 0
        for offset in range(MONTHS):
            year = offset // 12
            season = SEASON[self.month_of(offset).month - 1] * (Decimal(1) + GROWTH_PER_YEAR * year)
            for customer in self.customers.values():
                if not customer.key.startswith("C"):
                    continue
                expected = SIZE_RATE[customer.size] * season
                if customer.size == "large" and year == 2 and customer.segment == "key_account":
                    expected *= Decimal("1.6")  # a volume push in year three, at contract prices, on a low-margin mix
                count = int(expected) + (1 if rng.random() < float(expected - int(expected)) else 0)
                for _ in range(count):
                    day = self.day_in_month(offset, rng.randint(1, 28))
                    if customer.segment == "distributor" and self.gap_start <= day <= self.gap_end:
                        continue
                    n += 1
                    cap = SEGMENT_CAPS[customer.segment]
                    lines = []
                    for code in dict.fromkeys(self._pick_products(offset, rng.choices([1, 2, 3, 4], weights=[45, 30, 17, 8])[0])):
                        price = self.products[code].list_price
                        qty = Decimal(rng.randint(1, 10) if price > 300 else rng.randint(2, 40))
                        discount = Decimal(rng.choice([0, 0, 0, 2, 3, int(cap)])) if customer.segment != "distributor" else Decimal(0)
                        lines.append(_Line(code, qty, self.unit_price(customer, code, day), discount))
                    order = _Order(f"FD/SO/{n:05d}", customer.key, self.offset_days(day), lines,
                                   currency=CURRENCIES[customer.country[3]], freight_line=customer.freight == "rebill",
                                   freight_price=self.in_currency(customer.freight_amount, customer, day) if customer.freight == "rebill" else None,
                                   pricelist=customer.pricelist if customer.pricelist != "public" else None)
                    self._schedule(order, day, customer)
                    orders.append(order)
        return orders

    def offset_days(self, day: date) -> int:
        return (day - self.b.window_start).days

    def _schedule(self, order: _Order, day: date, customer: Customer) -> None:
        rng = self.rng
        remaining = (self.anchor - day).days
        deliver = rng.choice([1, 2, 2, 3, 4, 5]) if rng.random() < 0.9 else rng.randint(8, 21)
        invoice = rng.choice([1, 1, 2, 3])
        # Deliveries stay within the order's cost quarter: the receipt cost the delivery consumes is the frozen reference of the order.
        quarter_end = self.month_of(3 * (self.offset_of(day) // 3) + 3) - timedelta(days=1)
        deliver = min(deliver, (quarter_end - day).days)
        if deliver > remaining:
            order.deliver_after, order.invoice_after = None, None
        elif deliver + invoice > remaining:
            order.deliver_after, order.invoice_after = deliver, None
        else:
            order.deliver_after, order.invoice_after = deliver, invoice
            if rng.random() < 0.02 and order.lines[0].qty > 2:
                days = rng.randint(5, 20)
                if deliver + invoice + days <= remaining:  # no document after the anchor
                    order.refund = (days, Decimal(1))
        if order.deliver_after is not None and rng.random() < 0.05 and order.lines[0].qty >= 4:
            first = order.lines[0]
            first.delivered = (first.qty * Decimal(6) / Decimal(10)).quantize(Decimal(1))  # partial delivery, backorder open

    def _freight(self, key: str, day: date) -> dict[str, Any]:
        """Order arguments for the contractual freight line of a rebill customer; nothing for the others."""
        customer = self.customers[key]
        if customer.freight != "rebill":
            return {}
        return {"freight_line": True, "freight_price": self.in_currency(customer.freight_amount, customer, day)}

    def scenario_orders(self) -> list[_Order]:
        """Injected scenarios, spread over the three years. Each records its ground truth."""
        rng = self.rng
        orders: list[_Order] = []
        c = self.customers

        def add(order: _Order, scenario: dict[str, Any]) -> None:
            orders.append(order)
            self.scenarios.append(scenario)

        # 1. unauthorised discounts (12) on standard and key-account customers
        standard = [k for k, v in c.items() if v.segment == "standard" and k.startswith("C") and v.country[3] == "EUR"]
        for i in range(12):
            key = standard[i * 7 % len(standard)]
            code = self._pick_products(3, 1)[0]
            qty, price, discount = Decimal(rng.randint(20, 60)), self.products[code].list_price, Decimal(rng.choice([12, 15, 18, 20]))
            day = self.day_in_month(MONTHS - 1 if i == 0 else rng.randint(0, 34), rng.randint(2, 20))  # one in the anchor month
            order = _Order(f"FD/SO/DISC-{i + 1:03d}", key, self.offset_days(day), [_Line(code, qty, price, discount)], **self._freight(key, day))
            exposure = money(qty * price * (discount - Decimal(5)) / Decimal(100))
            add(order, self._truth(f"FULL-DISC-{i + 1:03d}", "unauthorised_discount", "DISCOUNT_CAP", order.key, code, "VIOLATION", "CONFIRMED_LEAKAGE",
                                   "DISCOUNT_ABOVE_CAP", exposure, "discount", "CONTROLLABLE",
                                   f"discount {discount}% above the 5% standard cap, no derogation", ["order line", "invoice line", "policy POL-DISC-STANDARD"],
                                   "Obtain a derogation or issue a complementary invoice", day))
        # 2. approved derogations (6): legitimate, never raised
        self.derogations: list[dict[str, Any]] = []
        for i in range(6):
            key = standard[(i * 11 + 3) % len(standard)]
            code = self._pick_products(3, 1)[0]
            qty, price, discount = Decimal(rng.randint(10, 40)), self.products[code].list_price, Decimal(15)
            day = self.day_in_month(rng.randint(0, 34), rng.randint(2, 20))
            order = _Order(f"FD/SO/DEROG-{i + 1:03d}", key, self.offset_days(day), [_Line(code, qty, price, discount)], **self._freight(key, day))
            self.derogations.append({"derogation_id": f"DEROG-FULL-{i + 1:03d}", "order": order.key, "max_discount_pct": "15", "approved_by_role": "finance_approver",
                                     "approved_on": str(day - timedelta(days=1)), "valid_from": str(day - timedelta(days=1)), "valid_to": str(day + timedelta(days=30))})
            add(order, self._truth(f"FULL-DEROG-{i + 1:03d}", "management_approved_exception", "DISCOUNT_CAP", order.key, code, "COMPLIANT",
                                   "LEGITIMATE_EXCEPTION", "APPROVED_DEROGATION", None, "discount", "NOT_APPLICABLE",
                                   "discount covered by a dated derogation of a finance approver", ["derogation register"], "None: not raised", day))
        # 3. price below contract (6)
        contracted = list(self.contract_prices)[:6]
        for i, (key, code) in enumerate(contracted):
            contract = self.contract_prices[(key, code)]
            qty, price = Decimal(rng.randint(10, 30)), money(contract * Decimal("0.94"))
            day = self.day_in_month(MONTHS - 1 if i == 0 else rng.randint(2, 34), rng.randint(2, 20))
            order = _Order(f"FD/SO/PRICE-{i + 1:03d}", key, self.offset_days(day), [_Line(code, qty, price, Decimal(0))], **self._freight(key, day))
            add(order, self._truth(f"FULL-PRICE-{i + 1:03d}", "invoiced_below_contract_price", "PRICE_BELOW_BASELINE", order.key, code, "VIOLATION",
                                   "CONFIRMED_LEAKAGE", "PRICE_BELOW_CONTRACT", money(qty * (contract - price)), "price", "CONTROLLABLE",
                                   f"unit price {price} below contract price {contract}", ["order line", "contract price register"],
                                   "Invoice the difference or record the amendment", day))
        # 4. wrong price list applied (5): standard customers priced on the distributor list
        for i in range(5):
            key = standard[(i * 13 + 5) % len(standard)]
            code = self._pick_products(3, 1)[0]
            qty, listed = Decimal(rng.randint(10, 30)), self.products[code].list_price
            price = money(listed * Decimal("0.88"))
            day = self.day_in_month(MONTHS - 1 if i == 0 else rng.randint(0, 34), rng.randint(2, 20))
            order = _Order(f"FD/SO/PLIST-{i + 1:03d}", key, self.offset_days(day), [_Line(code, qty, price, Decimal(0))], pricelist="distributor",
                           **self._freight(key, day))
            add(order, self._truth(f"FULL-PLIST-{i + 1:03d}", "incorrect_pricelist_application", "PRICE_BELOW_BASELINE", order.key, code, "VIOLATION",
                                   "CONFIRMED_LEAKAGE", "PRICELIST_MISMATCH", money(qty * (listed - price)), "price", "CONTROLLABLE",
                                   "order applied the distributor price list to a standard customer", ["order price list", "customer price list", "list price"],
                                   "Re-price the order on the customer's price list", day))
        # 5. freight not invoiced (8) and partially invoiced (4) for rebill customers; waived (5) never raised
        rebill = [k for k, v in c.items() if v.freight == "rebill" and k.startswith("C") and v.country[3] == "EUR"]
        waived = [k for k, v in c.items() if v.freight == "waived" and k.startswith("C") and v.country[3] == "EUR"]
        for i in range(8):
            key = rebill[i * 5 % len(rebill)]
            code = self._pick_products(3, 1)[0]
            qty = Decimal(rng.randint(5, 20))
            day = self.day_in_month(MONTHS - 1 if i == 0 else rng.randint(0, 33), rng.randint(2, 15))
            order = _Order(f"FD/SO/FRT-{i + 1:03d}", key, self.offset_days(day), [_Line(code, qty, self.unit_price(c[key], code), Decimal(0))])
            add(order, self._truth(f"FULL-FRT-{i + 1:03d}", "freight_not_recharged", "FREIGHT_REBILL", order.key, None, "VIOLATION", "CONFIRMED_LEAKAGE",
                                   "FREIGHT_NOT_INVOICED", c[key].freight_amount, "freight", "CONTROLLABLE", "goods delivered and invoiced, no freight line",
                                   ["delivery", "invoices", "freight contract clause"], "Issue the contractual freight invoice", day))
        for i in range(4):
            key = rebill[(i * 7 + 2) % len(rebill)]
            code = self._pick_products(3, 1)[0]
            qty, partial = Decimal(rng.randint(5, 20)), money(c[key].freight_amount * Decimal("0.4"))
            day = self.day_in_month(rng.randint(0, 33), rng.randint(2, 15))
            order = _Order(f"FD/SO/FRTP-{i + 1:03d}", key, self.offset_days(day), [_Line(code, qty, self.unit_price(c[key], code), Decimal(0))],
                           freight_line=True, freight_price=partial)
            exposure = c[key].freight_amount - partial
            add(order, self._truth(f"FULL-FRTP-{i + 1:03d}", "partial_freight_recharge", "FREIGHT_REBILL", order.key, None, "VIOLATION", "CONFIRMED_LEAKAGE",
                                   "FREIGHT_PARTIALLY_INVOICED", exposure, "freight", "CONTROLLABLE", f"freight invoiced {partial} of {c[key].freight_amount}",
                                   ["freight line", "freight contract clause"], "Invoice the remaining freight", day))
        for i in range(5):
            key = waived[i % len(waived)]
            code = self._pick_products(3, 1)[0]
            day = self.day_in_month(rng.randint(0, 33), rng.randint(2, 15))
            order = _Order(f"FD/SO/WAIV-{i + 1:03d}", key, self.offset_days(day), [_Line(code, Decimal(rng.randint(5, 20)), self.unit_price(c[key], code), Decimal(0))])
            add(order, self._truth(f"FULL-WAIV-{i + 1:03d}", "legitimate_low_margin_transaction", "FREIGHT_REBILL", order.key, None, "COMPLIANT",
                                   "LEGITIMATE_EXCEPTION", "CONTRACT_WAIVER", None, "freight", "NOT_APPLICABLE", "freight waived by contract",
                                   ["freight contract clause"], "None: not raised", day))
        # 6. purchase price variance (8) on scenario products with one receipt at +12 %
        for i in range(8):
            code = f"SCP-{i + 1:02d}"
            product = self.products[code]
            key = standard[(i * 17 + 9) % len(standard)]
            qty = Decimal(rng.randint(40, 100))
            day = self.day_in_month(rng.randint(1, 34), rng.randint(2, 20))
            order = _Order(f"FD/SO/COST-{i + 1:03d}", key, self.offset_days(day), [_Line(code, qty, product.list_price, Decimal(0))], **self._freight(key, day))
            reference = self.quarter_cost[(code, self.quarter(self.offset_of(day)))]
            variance = money(qty * (product.receipt_cost - reference))
            add(order, self._truth(f"FULL-COST-{i + 1:03d}", "purchase_price_variance", "COST_REFERENCE_VARIANCE", order.key, code, "VIOLATION",
                                   "CONFIRMED_LEAKAGE", "PURCHASE_PRICE_VARIANCE", variance, "cost", "PARTIALLY_CONTROLLABLE",
                                   f"receipt at {product.receipt_cost} against reference {reference}", ["receipt", "delivery move", "cost allocation", "cost reference"],
                                   "Review the supplier price with procurement", day))
        # 7. missing cost (3): scenario products without any receipt
        for i in range(3):
            code = f"SCM-{i + 1:02d}"
            key = standard[(i * 19 + 4) % len(standard)]
            day = self.day_in_month(rng.randint(1, 34), rng.randint(2, 20))
            order = _Order(f"FD/SO/MISS-{i + 1:03d}", key, self.offset_days(day), [_Line(code, Decimal(rng.randint(5, 15)), self.products[code].list_price, Decimal(0))],
                           **self._freight(key, day))
            add(order, self._truth(f"FULL-MISS-{i + 1:03d}", "missing_or_delayed_cost_posting", "COST_REFERENCE_VARIANCE", order.key, code, "UNDETERMINED",
                                   "DATA_QUALITY_ISSUE", "MISSING_COST", None, "cost", "PARTIALLY_CONTROLLABLE", "delivered without any valued receipt",
                                   ["delivery move", "cost allocation UNDETERMINED"], "Post or attribute the receipt cost", day))
        # 8. distributor policy gap (2) and conflicting customer policies (1)
        for i in range(2):
            key = "N01"
            code = self._pick_products(31, 1)[0]
            day = self.gap_start + timedelta(days=3 + i * 5)
            qty, price = Decimal(rng.randint(10, 30)), self.unit_price(c[key], code)
            order = _Order(f"FD/SO/GAP-{i + 1:03d}", key, self.offset_days(day), [_Line(code, qty, price, Decimal(8))], pricelist="distributor")
            add(order, self._truth(f"FULL-GAP-{i + 1:03d}", "data_quality_prevents_recommendation", "DISCOUNT_CAP", order.key, code, "UNKNOWN",
                                   "INSUFFICIENT_EVIDENCE", "POLICY_EXPIRED", None, "discount", "CONTROLLABLE", "no distributor policy valid in the renewal gap",
                                   ["policy register"], "Renew the policy, then reassess", day, potential=money(qty * price * Decimal(8) / Decimal(100))))
        code = self._pick_products(20, 1)[0]
        day = self.day_in_month(20, 12)
        qty, price = Decimal(20), self.unit_price(c["N02"], code)
        order = _Order("FD/SO/CONF-001", "N02", self.offset_days(day), [_Line(code, qty, price, Decimal(13))], pricelist="distributor")
        add(order, self._truth("FULL-CONF-001", "data_quality_prevents_recommendation", "DISCOUNT_CAP", order.key, code, "CONFLICT", "INSUFFICIENT_EVIDENCE",
                               "POLICY_CONFLICT", None, "discount", "CONTROLLABLE", "two customer policies of the same priority with different caps",
                               ["policy register"], "Resolve the conflicting policies", day, potential=money(qty * price * Decimal(13) / Decimal(100))))
        # 9. mapping issue (3): a product whose unit of measure cannot be resolved
        for i in range(3):
            key = standard[(i * 23 + 7) % len(standard)]
            day = self.day_in_month(rng.randint(0, 34), rng.randint(2, 20))
            qty = Decimal(rng.randint(3, 12))
            order = _Order(f"FD/SO/MAP-{i + 1:03d}", key, self.offset_days(day), [_Line("MAP-01", qty, Decimal(95), Decimal(0))], **self._freight(key, day))
            add(order, self._truth(f"FULL-MAP-{i + 1:03d}", "incorrect_product_mapping", "PRODUCT_MAPPING", order.key, "MAP-01", "UNDETERMINED",
                                   "DATA_QUALITY_ISSUE", "UNRESOLVED_UNIT_OR_PRODUCT", None, None, "NOT_APPLICABLE", "product without a resolvable unit of measure",
                                   ["order line", "product master"], "Correct the product master", day, potential=money(qty * Decimal(95))))
        # 10. credit notes after invoice (10): compliant refunds
        for i in range(10):
            key = standard[(i * 29 + 1) % len(standard)]
            code = self._pick_products(3, 1)[0]
            day = self.day_in_month(rng.randint(0, 32), rng.randint(2, 15))
            order = _Order(f"FD/SO/CN-{i + 1:03d}", key, self.offset_days(day), [_Line(code, Decimal(rng.randint(6, 20)), self.unit_price(c[key], code), Decimal(5))],
                           invoice_after=2, refund=(rng.randint(5, 25), Decimal(2)), **self._freight(key, day))
            add(order, self._truth(f"FULL-CN-{i + 1:03d}", "credit_note_after_invoice", "DISCOUNT_CAP", order.key, code, "COMPLIANT", "COMPLIANT",
                                   "WITHIN_POLICY", None, "discount", "NOT_APPLICABLE", "partial credit note reverses part of the invoice; discount at the cap",
                                   ["invoice", "credit note"], "None: not raised", day))
        # 11. foreign currency (3): compliant at the order-date rate
        foreign = [k for k, v in c.items() if v.country[3] != "EUR" and k.startswith("C")][:3]
        for i, key in enumerate(foreign):
            code = self._pick_products(3, 1)[0]
            day = self.day_in_month(rng.randint(0, 34), rng.randint(2, 20))
            order = _Order(f"FD/SO/FX-{i + 1:03d}", key, self.offset_days(day), [_Line(code, Decimal(rng.randint(5, 20)), self.unit_price(c[key], code, day), Decimal(2))],
                           currency=CURRENCIES[c[key].country[3]], **self._freight(key, day))
            add(order, self._truth(f"FULL-FX-{i + 1:03d}", "currency_effect_explained", "PRICE_BELOW_BASELINE", order.key, code, "COMPLIANT", "COMPLIANT",
                                   "AT_OR_ABOVE_BASELINE", None, "price", "NOT_APPLICABLE", "foreign-currency line compared at the order-date rate",
                                   ["order line", "currency rate"], "None: not raised", day))
        for order in orders:
            self._schedule_scenario(order)
        return orders

    def _schedule_scenario(self, order: _Order) -> None:
        day = self.b.day(order.day)
        remaining = (self.anchor - day).days
        if order.refund is None:
            order.deliver_after, order.invoice_after = (2, 1) if remaining >= 3 else (None, None)
        else:
            order.deliver_after = 2 if remaining >= 3 else None

    def _truth(self, scenario_id: str, family: str, rule: str, order: str, product: str | None, status: str, classification: str, cause: str,
               amount: Decimal | None, exposure_type: str | None, controllability: str, root_cause: str, evidence: list[str], action: str,
               day: date, *, potential: Decimal | None = None) -> dict[str, Any]:
        material = (amount or potential or Decimal(0)) >= MATERIALITY
        creates_case = classification in ("CONFIRMED_LEAKAGE", "PROBABLE_LEAKAGE", "DATA_QUALITY_ISSUE", "INSUFFICIENT_EVIDENCE") and (
            material or classification in ("DATA_QUALITY_ISSUE", "INSUFFICIENT_EVIDENCE"))
        severity = "NONE" if amount is None and potential is None else ("HIGH" if (amount or potential) >= 750 else "MEDIUM" if (amount or potential) >= 250 else "LOW")
        return {
            "scenario_id": scenario_id, "family": family, "rule": rule, "subject": {"type": "sale_order" if product is None else "sale_order_line", "order": order,
                                                                                    "product": product},
            "order_date": str(day), "period": f"{day.year}-{day.month:02d}",
            "expected": {"status": status, "classification": classification, "cause": cause, "adverse_exposure": None if amount is None else str(amount),
                         "potential_exposure": None if potential is None else str(potential), "exposure_type": exposure_type, "controllability": controllability,
                         "severity": severity if classification not in ("COMPLIANT", "LEGITIMATE_EXCEPTION", "NOT_APPLICABLE", "EXPLAINED_VARIANCE") else "NONE",
                         "material": material, "case_created": creates_case},
            "root_cause": root_cause, "evidence": evidence, "recommended_action": action, "status": "INJECTED",
        }

    # ------------------------------------------------------------------ receipts: two waves a month, sized on the deliveries they serve
    @staticmethod
    def _units(line: _Line) -> Decimal:
        """Units the delivery move will carry, as the base generator computes them."""
        if line.qty_units is not None:
            return line.qty_units
        return line.delivered if line.delivered is not None else line.qty

    def _deliveries(self, orders: list[_Order]) -> list[tuple[date, int, int, str, str, Decimal]]:
        """Every delivery move the sales will create, in the order the marts replay them: by date, then creation order."""
        out = []
        for seq, order in enumerate(orders):
            if order.state != "sale" or order.deliver_after is None:
                continue
            day = self.b.day(order.day + order.deliver_after)
            for position, line in enumerate(order.lines):
                if line.product != "FRT":
                    out.append((day, seq, position, order.key, line.product, self._units(line)))
        return sorted(out)

    def receipts(self, orders: list[_Order]) -> None:
        """Purchasing follows a just-in-time replenishment policy: a receipt on the first and on the fifteenth of each month, each
        sized on the deliveries of the half-month it serves. Stock never goes negative, every layer is consumed within its
        half-month and a delivery is valued at the cost of the receipts it consumes, as Odoo's FIFO valuation does. Scenario
        products get their single receipt (or none) in the first wave."""
        b = self.b
        deliveries = self._deliveries(orders)
        demand: dict[tuple[str, int, int], Decimal] = defaultdict(Decimal)
        for day, _seq, _position, _key, code, units in deliveries:
            if code == "MAP-01" or (code in self.products and not self.products[code].scenario):
                demand[(code, self.offset_of(day), 0 if day.day < 15 else 1)] += units
        stocked = [(code, product.supplier) for code, product in self.products.items() if not product.scenario] + [("MAP-01", "S002")]
        index = 0
        for offset in range(MONTHS):
            q = self.quarter(offset)
            for half, receipt_day in ((0, self.month_of(offset)), (1, self.day_in_month(offset, 15))):
                per_supplier: dict[str, list[tuple[str, Decimal, Decimal]]] = defaultdict(list)
                for code, supplier in stocked:
                    need = demand.get((code, offset, half), Decimal(0))
                    if need > 0:
                        per_supplier[supplier].append((code, need, self.quarter_cost.get((code, q), self.quarter_cost[(code, 0)])))
                if offset == 0 and half == 0:
                    for code, product in self.products.items():
                        if product.scenario and product.receipt_cost is not None:
                            per_supplier[product.supplier].append((code, Decimal(product.receipt_qty), product.receipt_cost))
                order_day = receipt_day - timedelta(days=1)
                for supplier in sorted(per_supplier):
                    index += 1
                    po_name = f"FD/PO/{index:05d}"
                    partner = [self.partner_ids[supplier], self.suppliers[supplier]]
                    po_id = b.add("purchase.order", f"po_{index:05d}", name=po_name, partner_id=partner, company_id=m2o(COMPANY), currency_id=m2o(EUR),
                                  date_order=dt(order_day), state="purchase", write_date=dt(receipt_day, 10))
                    picking = b.add("stock.picking", f"receipt_{index:05d}", name=f"FD/IN/{index:05d}", origin=po_name, sale_id=False, partner_id=partner,
                                    company_id=m2o(COMPANY), picking_type_code="incoming", state="done", date_done=dt(receipt_day, 10), write_date=dt(receipt_day, 10))
                    for code, qty, cost in per_supplier[supplier]:
                        pol = b.add("purchase.order.line", f"pol_{index:05d}_{code}", order_id=[po_id, po_name],
                                    product_id=[self.product_ids[code], self.product_names[code]], product_qty=float(qty), uom_id=m2o(UNITS),
                                    price_unit=float(cost), qty_received=float(qty), qty_invoiced=0.0, move_ids=[], write_date=dt(receipt_day, 10))
                        move = self._move(picking, code, qty, money(qty * cost), cost, receipt_day, 10, purchase_line=pol)
                        b.records["purchase.order.line"][-1]["move_ids"] = [move]
                        self.layers[code].append([qty, cost])
        # Value every delivery from the layers it consumes, in the replay order, before any sale is written.
        for _day, _seq, _position, key, code, units in deliveries:
            self.delivery_cost[(key, code)] = self._fifo_cost(code, units)

    def _fifo_cost(self, code: str, units: Decimal) -> Decimal | None:
        """Unit cost of `units` taken from the oldest remaining layers; None when the layers cannot cover them (no valued receipt)."""
        remaining, total = units, Decimal(0)
        for layer in self.layers.get(code, []):
            if remaining <= 0:
                break
            take = min(remaining, layer[0])
            layer[0] -= take
            total += take * layer[1]
            remaining -= take
        return None if remaining > 0 or units <= 0 else total / units

    # ------------------------------------------------------------------ sales with realistic cost, payments and due dates
    def sale(self, order: _Order) -> None:
        # The delivery move carries the FIFO cost planned in `receipts`; the reference cost is the frozen cost of the order's quarter.
        before = len(self.b.records["account.move"])
        q = self.quarter(self.offset_of(self.b.day(order.day)))
        for line in order.lines:
            code = line.product
            if code == "FRT":
                continue
            self.ref_cost[code] = self.quarter_cost.get((code, q), self.ref_cost.get(code))
            self.receipt_cost[code] = self.delivery_cost.get((order.key, code))
        super().sale(order)
        customer = self.customers[order.customer]
        for move in self.b.records["account.move"][before:]:
            self._settle(move, customer)

    def _settle(self, move: dict[str, Any], customer: Customer) -> None:
        rng = self.rng
        invoice_day = date.fromisoformat(move["invoice_date"])
        due = invoice_day + timedelta(days=customer.terms)
        move["invoice_date_due"] = str(due)
        total = abs(Decimal(str(move["amount_untaxed_signed"]))) * (1 + VAT)
        roll = rng.random()
        delay = rng.randint(-2, 3) if roll < 0.6 else (rng.randint(5, 40) if roll < 0.9 else None)
        paid_on = None if delay is None else due + timedelta(days=delay)
        if move["move_type"] == "out_refund" or paid_on is None or paid_on > self.anchor:
            move["payment_state"] = "not_paid"
            move["amount_residual"] = float(money(total)) if move["move_type"] == "out_invoice" else 0.0
            return
        move["payment_state"], move["amount_residual"] = "paid", 0.0
        currency = move["currency_id"]
        pid = self.b.add("account.payment", f"payment_{move['name']}", name=f"FD/PAY/{len(self.b.records['account.payment']) + 1:05d}", date=str(paid_on),
                         amount=float(money(total)), currency_id=currency, partner_id=move["partner_id"], payment_type="inbound", state="paid",
                         reconciled_invoice_ids=[move["id"]], company_id=m2o(COMPANY), write_date=dt(paid_on, 14))
        self.payments.append(pid)

    # ------------------------------------------------------------------ terms
    def terms(self) -> dict[str, Any]:
        day = self.b.day
        segments = {k: v.segment for k, v in self.customers.items()}
        policies = [
            {"policy_id": "POL-DISC-STANDARD", "version": 1, "scope": {"segment": "standard"}, "max_discount_pct": "5", "priority": 10, "valid_from": str(day(-400)), "valid_to": None},
            {"policy_id": "POL-DISC-KEY-ACCOUNT", "version": 1, "scope": {"segment": "key_account"}, "max_discount_pct": "10", "priority": 10, "valid_from": str(day(-400)), "valid_to": None},
            {"policy_id": "POL-DISC-DISTRIBUTOR", "version": 1, "scope": {"segment": "distributor"}, "max_discount_pct": "12", "priority": 10, "valid_from": str(day(-400)),
             "valid_to": str(self.gap_start - timedelta(days=1))},
            {"policy_id": "POL-DISC-DISTRIBUTOR", "version": 2, "scope": {"segment": "distributor"}, "max_discount_pct": "12", "priority": 10,
             "valid_from": str(self.gap_end + timedelta(days=1)), "valid_to": None},
            {"policy_id": "POL-DISC-N02-A", "version": 1, "scope": {"customer": "N02"}, "max_discount_pct": "10", "priority": 30, "valid_from": str(day(-100)), "valid_to": None},
            {"policy_id": "POL-DISC-N02-B", "version": 1, "scope": {"customer": "N02"}, "max_discount_pct": "15", "priority": 30, "valid_from": str(day(-60)), "valid_to": None},
        ]
        freight = [
            {"contract_id": f"CTR-FREIGHT-{k}", "customer": k, "terms": v.freight, "amount": str(v.freight_amount) if v.freight == "rebill" else "0", "currency": "EUR",
             "trigger": "full_delivery" if v.freight == "rebill" else None, "valid_from": str(day(-400)), "valid_to": None}
            for k, v in sorted(self.customers.items()) if v.freight
        ]
        prices = [
            {"contract_id": f"CTR-PRICE-{k}", "customer": k, "product": code, "unit_price": str(price), "currency": "EUR", "min_quantity": "0",
             "valid_from": str(day(-400)), "valid_to": None}
            for (k, code), price in sorted(self.contract_prices.items())
        ]
        costs = []
        for (code, q), cost in sorted(self.quarter_cost.items()):
            first = self.month_of(q * 3)
            last = self.month_of(q * 3 + 3) - timedelta(days=1) if q * 3 + 3 < MONTHS else self.anchor + timedelta(days=90)
            costs.append({"reference_id": f"REF-COST-{first.year}Q{(first.month - 1) // 3 + 1}", "product": code, "unit_cost": str(cost),
                          "frozen_on": str(first - timedelta(days=1)), "valid_from": str(first), "valid_to": str(last)})
        return {"customer_segments": segments, "discount_policies": policies, "discount_derogations": self.derogations, "freight_contracts": freight,
                "contract_prices": prices, "cost_references": costs}

    # ------------------------------------------------------------------ assembly
    def build(self) -> FixtureDataset:
        self.reference_data()
        background = self.background_orders()
        scenarios = self.scenario_orders()
        orders = sorted(background + scenarios, key=lambda o: (o.day, o.key))
        self.receipts(orders)
        for order in orders:
            self.sale(order)
        # invoices without an order (4)
        for i in range(4):
            key = f"C{(i * 37 + 11) % 500 + 1:03d}"
            code = self._pick_products(10, 1)[0]
            day = self.day_in_month(self.rng.randint(0, 34), self.rng.randint(2, 20))
            qty = Decimal(self.rng.randint(4, 12))
            name = f"FD/INV/NOORD-{i + 1:03d}"
            self.invoice(None, None, [self.partner_ids[key], self.customers[key].name], [(None, _Line(code, qty, self.products[code].list_price, Decimal(0)), qty)],
                         day, "out_invoice", name=name)
            self.scenarios.append({"scenario_id": f"FULL-NOORD-{i + 1:03d}", "family": "invoice_without_order", "rule": "INVOICE_WITHOUT_SALE_LINK",
                                   "subject": {"type": "invoice_line", "invoice": name, "product": code}, "order_date": str(day), "period": f"{day.year}-{day.month:02d}",
                                   "expected": {"status": "NO_SALE_LINK", "classification": "DATA_QUALITY_ISSUE", "cause": "INVOICE_WITHOUT_ORDER", "adverse_exposure": "0.00",
                                                "potential_exposure": str(money(qty * self.products[code].list_price)), "exposure_type": None, "controllability": "NOT_APPLICABLE",
                                                "severity": "HIGH" if qty * self.products[code].list_price >= 750 else "MEDIUM" if qty * self.products[code].list_price >= 250 else "LOW",
                                                "material": qty * self.products[code].list_price >= MATERIALITY, "case_created": True},
                                   "root_cause": "invoice entered without an order behind it", "evidence": ["invoice line without order link"],
                                   "recommended_action": "Link the invoice to its order or document the exception", "status": "INJECTED"})
        dataset = FixtureDataset(dataset_id=PROFILE_ID, source_instance=self.b.source_instance, anchor_date=self.anchor, window_start=self.b.window_start,
                                 seed=self.seed, records=dict(self.b.records), keys=dict(self.b.keys), terms=self.terms())
        dataset.ground_truth = self.manifest(dataset)  # type: ignore[attr-defined]
        return dataset

    def manifest(self, dataset: FixtureDataset) -> dict[str, Any]:
        records = dataset.records
        raised = [s for s in self.scenarios if s["expected"]["case_created"]]
        by_type: dict[str, Decimal] = defaultdict(Decimal)
        for s in self.scenarios:
            if s["expected"]["classification"] == "CONFIRMED_LEAKAGE":
                by_type[s["expected"]["exposure_type"]] += Decimal(s["expected"]["adverse_exposure"])
        return {
            "profile": PROFILE_ID, "manifest_version": 1, "seed": self.seed, "anchor_date": str(self.anchor), "window_start": str(self.b.window_start),
            "months": MONTHS,
            "structure": {
                "customers": sum(1 for p in records["res.partner"] if p["customer_rank"]),
                "suppliers": sum(1 for p in records["res.partner"] if p["supplier_rank"]),
                "products": len(records["product.product"]),
                "sale_orders": len(records["sale.order"]),
                "sale_order_lines": len(records["sale.order.line"]),
                "purchase_orders": len(records["purchase.order"]),
                "purchase_order_lines": len(records["purchase.order.line"]),
                "invoices": len(records["account.move"]),
                "journal_items": len(records["account.move.line"]),
                "stock_moves": len(records["stock.move"]),
                "payments": len(records.get("account.payment", [])),
                "currency_rates": len(records["res.currency.rate"]),
                "pricelist_items": len(records["product.pricelist.item"]),
            },
            "scenarios": sorted(self.scenarios, key=lambda s: s["scenario_id"]),
            "expected_totals": {
                "injected_scenarios": len(self.scenarios),
                "cases_from_scenarios": len(raised),
                "confirmed_leakage_exceptions": sum(1 for s in self.scenarios if s["expected"]["classification"] == "CONFIRMED_LEAKAGE"),
                "leakage_by_type": {k: str(v) for k, v in sorted(by_type.items())},
                "exceptions_outside_scenarios": 0,
            },
            "period_signal": {
                "description": "year-three mix shift and volume push on low-margin families: goods gross margin percentage of the last "
                               "twelve months below the previous twelve by at least one point",
                "min_drop_points": "1.0",
            },
        }


def build_full_profile(anchor: date = date(2026, 8, 31), seed: int = FULL_SEED) -> FixtureDataset:
    if (anchor + timedelta(days=1)).day != 1:
        raise ValueError("the demonstration profile needs an anchor on the last day of a month")
    return _FullGenerator(anchor, seed).build()


def ground_truth(dataset: FixtureDataset) -> dict[str, Any]:
    return dataset.ground_truth  # type: ignore[attr-defined]


__all__ = ["CENT", "PROFILE_ID", "build_full_profile", "ground_truth"]
