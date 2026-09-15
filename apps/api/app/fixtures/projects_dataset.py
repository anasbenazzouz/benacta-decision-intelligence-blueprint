"""Engineering and project delivery extension of the BENACTA DEMO company (dataset demo_v2).

`extend_with_projects(demo_v1)` appends, without changing a single demo_v1 record: people, projects, work packages,
milestones, contracts and change orders, timesheets (Odoo `hr_timesheet` record shape), purchase orders and vendor
bills attributed to projects, milestone invoices and payments. It also returns plan files (budgets, forecasts,
scenarios) that go through the same import path as a user CSV.

Nine projects carry the scenarios of docs/project_controlling_model.md with explicit round figures; six background
projects follow a steady profile. Expected results are written by hand in data/golden/projects_oracle_v1.yml, which
this module never reads. Every name, person, customer, contract and amount is invented.
"""

from __future__ import annotations

import copy
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.fixtures.demo_dataset import COMPANY, EUR, UNITS, USD, FixtureDataset, dt, m2o

D = Decimal
CENT = D("0.01")
PAYMENT_TERMS_DAYS = 45
HOURS_PER_DAY = D("7.5")

ROLE_RATES = {"PM": 130, "PC": 95, "BY": 75, "SS": 90, "LE": 120, "SE": 100, "EN": 80, "DS": 65}
ROLE_NAMES = {
    "PM": "Project Manager", "PC": "Project Controller", "BY": "Buyer", "SS": "Site Supervisor",
    "LE": "Lead Engineer", "SE": "Senior Engineer", "EN": "Engineer", "DS": "Designer",
}
SUPPORT_ROLES = {"PM", "PC", "BY", "SS"}
BUSINESS_UNITS = {"PLANTS": "Process Plants", "AUTOMATION": "Automation & Controls", "SERVICES": "Field Services & Spares"}
INTERNAL_PROJECTS = {
    "INT-PROPOSALS": ("Proposals and tenders", "PROPOSAL"),
    "INT-DEVELOPMENT": ("Product and method development", "DEVELOPMENT"),
    "INT-IMPROVEMENT": ("Continuous improvement", "IMPROVEMENT"),
    "INT-NONPROD": ("Training, administration and internal meetings", "NON_PRODUCTIVE"),
    "INT-SUPPORT": ("Support functions: project management, controls, procurement, site", "SUPPORT_FUNCTION"),
}
FIRST_NAMES = [
    "Alix", "Bastien", "Camille", "Dorian", "Elodie", "Fabien", "Gaelle", "Hadrien", "Ines", "Jules",
    "Katia", "Loris", "Maelle", "Noam", "Oriane", "Pierrick", "Quitterie", "Romain", "Salome", "Tristan",
    "Ugo", "Valentine", "Wassim", "Xenia", "Yanis", "Zelie", "Aurele", "Blandine", "Cyprien", "Delphine",
    "Enzo", "Flavie", "Gaspard", "Heloise", "Ilan", "Josephine", "Kylian", "Leonie", "Marius", "Nina",
]
LAST_NAMES = [
    "Arnaud", "Besson", "Carrel", "Delmas", "Estrade", "Faure", "Garnier", "Hervieu", "Icard", "Jourdan",
    "Klein", "Lacombe", "Marchal", "Noiret", "Olivier", "Perrin", "Quesnel", "Rigal", "Sauvage", "Tessier",
    "Urbain", "Vasseur", "Weber", "Xavier", "Yvon", "Zimmer", "Aubry", "Brunel", "Cordier", "Dumont",
    "Etienne", "Fleury", "Gauthier", "Huet", "Imbert", "Joly", "Kieffer", "Laporte", "Masson", "Nicolas",
]
# code: role; E34-E37 and E39-E40 are external contractors
EMPLOYEE_ROLES = ["PM"] * 3 + ["PC"] * 2 + ["BY"] + ["SS"] + ["LE"] * 4 + ["SE"] * 10 + ["EN"] * 16 + ["DS"] * 3
EXTERNAL_CODES = {"E34", "E35", "E36", "E37", "E39", "E40"}
SKILLS = {
    "LE": ["Process design", "Hazard studies"], "SE": ["Process design", "Instrumentation"], "EN": ["Piping", "Electrical design"],
    "DS": ["3D modelling"], "PM": ["Project management"], "PC": ["Cost control"], "BY": ["Procurement"], "SS": ["Site supervision"],
}

WORK_PACKAGES = [("WP20", "Engineering"), ("WP30", "Procurement and materials"), ("WP40", "Subcontracted construction")]
CATEGORY_WORK_PACKAGE = {"LABOUR": "WP20", "MATERIALS": "WP30", "SUBCONTRACT": "WP40", "CONTINGENCY": "WP90"}


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------- scenario definitions
# Dates are (month offset from the cutoff month, day). Amounts in contract currency, excluding taxes.
@dataclass
class Milestone:
    key: str
    name: str
    pct: Decimal
    deadline: tuple[int, int]
    reached: tuple[int, int] | None = None
    invoiced: tuple[int, int] | None = None
    payments: list[tuple[tuple[int, int], Decimal]] = field(default_factory=list)  # tax-inclusive amounts
    line: str = "contract"  # or a change order key
    billing_period_prev: int | None = None  # month offset of planned billing in the previous forecast
    billing_period_curr: int | None = None


@dataclass
class ChangeOrder:
    key: str
    name: str
    amount: Decimal
    state: str  # sale (approved) or sent (pending)
    date: tuple[int, int]


@dataclass
class PurchaseLine:
    category: str
    amount: Decimal
    ordered: tuple[int, int]
    supplier: str = "SUPPLIER-A"


@dataclass
class Bill:
    category: str
    amount: Decimal
    day: int
    po_index: int | None = None
    analytic_project: str | None = None  # attribute the analytic distribution to another project (inconsistency)


@dataclass
class ProjectSpec:
    code: str
    name: str
    bu: str
    customer: str
    contract: Decimal
    start: tuple[int, int]
    end: tuple[int, int]
    budget_hours: dict[str, int]
    budget_costs: dict[str, Decimal]
    prev_hours: dict[str, int]
    prev_costs: dict[str, Decimal]
    month_hours: dict[str, int]
    month_bills: list[Bill]
    purchases: list[PurchaseLine]
    fc_prev_hours: dict[str, int]
    fc_prev_costs: dict[str, Decimal]
    fc_curr_hours: dict[str, int]
    fc_curr_costs: dict[str, Decimal]
    milestones: list[Milestone]
    currency: tuple[int, str] = EUR
    fixed_rate: Decimal | None = None
    vat: Decimal = D("0.20")
    contract_type: str = "LUMP_SUM"
    phase: str = "EXECUTION"
    change_orders: list[ChangeOrder] = field(default_factory=list)
    revised_budget: dict[str, Any] | None = None  # {"hours": {}, "costs": {}, "effective": (m, d)}
    progress_prev: Decimal | None = None
    progress_curr: Decimal | None = None
    notes_curr: str | None = None
    pending_co_scenario: dict[str, Any] | None = None  # {"hours": {role: extra}, "billing_period": m}
    change_order_scope_hours: dict[str, int] = field(default_factory=dict)  # current-month hours on CO work package
    month_extra_employees: dict[str, list[str]] = field(default_factory=dict)  # join the role pool for the cutoff month
    month_absent_employees: dict[str, list[str]] = field(default_factory=dict)  # planned but log no time in the cutoff month
    fc_curr_status: str = "APPROVED"
    first_prev_bill_month: int | None = None


def _h(**kw: int) -> dict[str, int]:
    return dict(kw)


def _c(**kw: int) -> dict[str, Decimal]:
    return {k: D(v) for k, v in kw.items()}


GOLDEN_PROJECTS: list[ProjectSpec] = [
    ProjectSpec(
        code="PRJ-01", name="Northgate Packaging Line Automation", bu="AUTOMATION", customer="Northgate Foods",
        contract=D(800000), start=(-7, 5), end=(4, 18),
        budget_hours=_h(SE=1000, EN=3750), budget_costs=_c(SUBCONTRACT=150000, MATERIALS=50000),
        prev_hours=_h(SE=500, EN=1625), prev_costs=_c(SUBCONTRACT=65000, MATERIALS=25000),
        month_hours=_h(SE=40, EN=200), month_bills=[Bill("SUBCONTRACT", D(10000), 24)],
        purchases=[PurchaseLine("SUBCONTRACT", D(150000), (-6, 1)), PurchaseLine("MATERIALS", D(50000), (-6, 15), "SUPPLIER-B")],
        fc_prev_hours=_h(SE=500, EN=2125), fc_prev_costs=_c(SUBCONTRACT=85000, MATERIALS=25000),
        fc_curr_hours=_h(SE=460, EN=1925), fc_curr_costs=_c(SUBCONTRACT=75000, MATERIALS=25000),
        milestones=[
            Milestone("MS01", "Advance payment", D("0.10"), (-7, 31), (-7, 20), (-7, 25), [((-5, 10), D(96000))]),
            Milestone("MS02", "Design approval", D("0.30"), (-3, 31), (-3, 25), (-3, 30), [((-1, 10), D(288000))]),
            Milestone("MS03", "Factory acceptance test", D("0.30"), (2, 31)),
            Milestone("MS04", "Commissioning", D("0.30"), (4, 18)),
        ],
        progress_prev=D(45), progress_curr=D(50),
    ),
    ProjectSpec(
        code="PRJ-02", name="Riverside Water Treatment Revamp", bu="PLANTS", customer="Riverside Water Authority",
        contract=D(2000000), start=(-10, 1), end=(7, 31),
        budget_hours=_h(LE=2000, EN=7000), budget_costs=_c(SUBCONTRACT=500000, MATERIALS=250000, CONTINGENCY=50000),
        prev_hours=_h(LE=1000, EN=3500), prev_costs=_c(SUBCONTRACT=200000, MATERIALS=100000),
        month_hours=_h(LE=150, EN=900), month_bills=[Bill("SUBCONTRACT", D(50000), 26, po_index=0)],
        purchases=[
            PurchaseLine("SUBCONTRACT", D(500000), (-9, 1)),
            PurchaseLine("MATERIALS", D(250000), (-8, 1), "SUPPLIER-B"),
            PurchaseLine("SUBCONTRACT", D(40000), (0, 20)),  # price revision accepted in the cutoff month
        ],
        fc_prev_hours=_h(LE=1000, EN=3500), fc_prev_costs=_c(SUBCONTRACT=300000, MATERIALS=150000, CONTINGENCY=50000),
        fc_curr_hours=_h(LE=1050, EN=3850), fc_curr_costs=_c(SUBCONTRACT=290000, MATERIALS=150000, CONTINGENCY=50000),
        milestones=[
            Milestone("MS01", "Advance payment", D("0.10"), (-10, 31), (-10, 5), (-10, 6), [((-9, 20), D(240000))]),
            Milestone("MS02", "Basic engineering", D("0.20"), (-5, 15), (-5, 5), (-5, 10), [((-3, 10), D(300000))]),
            Milestone("MS03", "Detailed engineering approval", D("0.30"), (-1, 15), billing_period_prev=0, billing_period_curr=2),
            Milestone("MS04", "Mechanical completion", D("0.30"), (5, 31)),
            Milestone("MS05", "Final acceptance", D("0.10"), (7, 31)),
        ],
        progress_prev=D(40), progress_curr=D(42),
        notes_curr=(
            "Client comments on the process design package required rework of detailed engineering; "
            "subcontractor price revision of 40000 EUR accepted on the 20th."
        ),
        month_extra_employees={"EN": ["E34", "E35", "E36"]},
    ),
    ProjectSpec(
        code="PRJ-03", name="Harbor Cold Storage Expansion", bu="PLANTS", customer="Harbor Logistics Group",
        contract=D(1500000), start=(-9, 1), end=(6, 26),
        budget_hours=_h(SE=1500, EN=5625), budget_costs=_c(MATERIALS=450000, SUBCONTRACT=150000),
        prev_hours=_h(SE=700, EN=2375), prev_costs=_c(MATERIALS=150000, SUBCONTRACT=40000),
        month_hours=_h(SE=80, EN=400), month_bills=[Bill("SUBCONTRACT", D(10000), 21)],
        purchases=[
            PurchaseLine("MATERIALS", D(150000), (-7, 15), "SUPPLIER-B"),
            PurchaseLine("SUBCONTRACT", D(150000), (-6, 1)),
            PurchaseLine("MATERIALS", D(300000), (0, 10), "SUPPLIER-C"),  # compressors, planned in ETC before being ordered
        ],
        fc_prev_hours=_h(SE=800, EN=3250), fc_prev_costs=_c(MATERIALS=300000, SUBCONTRACT=110000),
        fc_curr_hours=_h(SE=720, EN=2850), fc_curr_costs=_c(MATERIALS=300000, SUBCONTRACT=100000),
        milestones=[
            Milestone("MS01", "Advance payment", D("0.10"), (-9, 15), (-9, 10), (-9, 15), [((-7, 29), D(180000))]),
            Milestone("MS02", "Equipment delivery", D("0.40"), (3, 30)),
            Milestone("MS03", "Handover", D("0.50"), (6, 26)),
        ],
        progress_prev=D(33), progress_curr=D(38),
    ),
    ProjectSpec(
        code="PRJ-04", name="Eastfield Boiler House Retrofit", bu="PLANTS", customer="Eastfield Hospital Trust",
        contract=D(1150000), start=(-9, 3), end=(3, 27),
        budget_hours=_h(SE=1200, EN=4125), budget_costs=_c(SUBCONTRACT=400000, CONTINGENCY=50000),
        prev_hours=_h(SE=500, EN=1875), prev_costs=_c(SUBCONTRACT=150000),
        month_hours=_h(SE=60, EN=300), month_bills=[Bill("SUBCONTRACT", D(100000), 25)],
        purchases=[PurchaseLine("SUBCONTRACT", D(400000), (-8, 1))],
        fc_prev_hours=_h(SE=700, EN=2250), fc_prev_costs=_c(SUBCONTRACT=250000, CONTINGENCY=50000),
        fc_curr_hours=_h(SE=640, EN=1950), fc_curr_costs=_c(SUBCONTRACT=150000, CONTINGENCY=50000),
        milestones=[
            Milestone("MS01", "Advance payment", D("0.10"), (-9, 30), (-9, 20), (-9, 25), [((-7, 9), D(138000))]),
            Milestone("MS02", "Boiler installation", D("0.40"), (-2, 30), (-2, 30), (-1, 3)),
            Milestone("MS03", "Commissioning and handover", D("0.50"), (3, 27)),
        ],
        progress_prev=D(50), progress_curr=D(55),
    ),
    ProjectSpec(
        code="PRJ-05", name="Westbrook Biogas Upgrading Unit", bu="PLANTS", customer="Westbrook Energy Cooperative",
        contract=D(1000000), start=(-9, 2), end=(5, 29),
        budget_hours=_h(SE=1000, EN=3750), budget_costs=_c(SUBCONTRACT=250000, MATERIALS=150000),
        revised_budget={"hours": _h(SE=1000, EN=4000), "costs": _c(SUBCONTRACT=250000, MATERIALS=240000), "effective": (-2, 30)},
        prev_hours=_h(SE=440, EN=1650), prev_costs=_c(SUBCONTRACT=100000, MATERIALS=140000),
        month_hours=_h(SE=60, EN=225), month_bills=[],
        purchases=[
            PurchaseLine("SUBCONTRACT", D(250000), (-8, 1)),
            PurchaseLine("MATERIALS", D(150000), (-7, 10), "SUPPLIER-B"),
            PurchaseLine("MATERIALS", D(90000), (-1, 1), "SUPPLIER-C"),  # scope added by the approved change order
        ],
        fc_prev_hours=_h(SE=560, EN=2350), fc_prev_costs=_c(SUBCONTRACT=150000, MATERIALS=100000),
        fc_curr_hours=_h(SE=500, EN=2125), fc_curr_costs=_c(SUBCONTRACT=150000, MATERIALS=100000),
        change_orders=[ChangeOrder("CO1", "Additional gas analyser package", D(150000), "sale", (-2, 15))],
        milestones=[
            Milestone("MS01", "Advance payment", D("0.10"), (-9, 30), (-9, 15), (-9, 17), [((-8, 30), D(120000))]),
            Milestone("MS02", "Gas analyser package design", D("0.50"), (-1, 31), (-1, 20), (-1, 25), line="CO1"),
            Milestone("MS03", "Mechanical completion", D("0.60"), (3, 31)),
            Milestone("MS04", "Final acceptance", D("0.30"), (5, 29)),
            Milestone("MS05", "Gas analyser commissioning", D("0.50"), (4, 30), line="CO1"),
        ],
        progress_prev=D(46), progress_curr=D(48),
    ),
    ProjectSpec(
        code="PRJ-06", name="Southport Tank Farm Instrumentation", bu="AUTOMATION", customer="Southport Terminals",
        contract=D(600000), start=(-6, 9), end=(4, 18),
        budget_hours=_h(SE=900, EN=3000), budget_costs=_c(MATERIALS=150000),
        prev_hours=_h(SE=360, EN=1700), prev_costs=_c(MATERIALS=90000),
        month_hours=_h(SE=40, EN=250), month_bills=[],
        change_order_scope_hours=_h(EN=200),
        purchases=[PurchaseLine("MATERIALS", D(150000), (-5, 1), "SUPPLIER-B")],
        fc_prev_hours=_h(SE=540, EN=1300), fc_prev_costs=_c(MATERIALS=60000),
        fc_curr_hours=_h(SE=500, EN=1050), fc_curr_costs=_c(MATERIALS=60000),
        change_orders=[ChangeOrder("CO1", "Additional tank level loops", D(80000), "sent", (0, 5))],
        pending_co_scenario={"hours": _h(EN=550), "billing_period": 2},
        milestones=[
            Milestone("MS01", "Instrument index approval", D("0.20"), (-6, 28), (-6, 20), (-6, 25), [((-4, 10), D(144000))]),
            Milestone("MS02", "Loop checks", D("0.40"), (2, 30)),
            Milestone("MS03", "Site acceptance", D("0.40"), (4, 18)),
        ],
        progress_prev=D(52), progress_curr=D(56),
    ),
    ProjectSpec(
        code="PRJ-07", name="Lakeshore Compressor Station Controls", bu="AUTOMATION", customer="Lakeshore Pipeline Company",
        contract=D(1100000), currency=USD, fixed_rate=D("1.10"), vat=D(0), start=(-5, 9), end=(6, 26),
        budget_hours=_h(SE=1300, EN=4625), budget_costs=_c(SUBCONTRACT=200000, MATERIALS=50000),
        prev_hours=_h(SE=360, EN=1150), prev_costs=_c(),
        month_hours=_h(SE=40, EN=225), month_bills=[],
        purchases=[],
        fc_prev_hours=_h(SE=940, EN=3475), fc_prev_costs=_c(SUBCONTRACT=200000, MATERIALS=50000),
        fc_curr_hours=_h(SE=900, EN=3250), fc_curr_costs=_c(SUBCONTRACT=200000, MATERIALS=50000),
        milestones=[
            Milestone("MS01", "Advance payment", D("0.10"), (-5, 15), (-5, 9), (-5, 10), [((-4, 24), D(110000))]),
            Milestone("MS02", "Control system design review", D("0.40"), (2, 30)),
            Milestone("MS03", "Station commissioning", D("0.50"), (6, 26)),
        ],
        progress_prev=D(18), progress_curr=D(21),
    ),
    ProjectSpec(
        code="PRJ-08", name="Hillcrest Chemical Dosing Skids", bu="SERVICES", customer="Hillcrest Chemicals",
        contract=D(400000), start=(-4, 6), end=(3, 27),
        budget_hours=_h(SE=500, EN=1875), budget_costs=_c(MATERIALS=100000),
        prev_hours=_h(SE=180, EN=650), prev_costs=_c(MATERIALS=50000),
        month_hours=_h(SE=20, EN=100), month_bills=[],
        month_absent_employees={"SE": ["E18"]},
        purchases=[PurchaseLine("MATERIALS", D(100000), (-3, 1), "SUPPLIER-B")],
        fc_prev_hours=_h(SE=320, EN=1225), fc_prev_costs=_c(MATERIALS=50000),
        fc_curr_hours=_h(SE=300, EN=1125), fc_curr_costs=_c(MATERIALS=50000),
        milestones=[
            Milestone("MS01", "Skid design approval", D("0.20"), (-4, 30), (-4, 20), (-4, 22), [((-2, 5), D(96000))]),
            Milestone("MS02", "Skid delivery", D("0.50"), (1, 30)),
            Milestone("MS03", "Start-up", D("0.30"), (3, 27)),
        ],
        progress_prev=D(30), progress_curr=None, fc_curr_status="DRAFT",
    ),
    ProjectSpec(
        code="PRJ-09", name="Ironbridge Conveyor Upgrade", bu="AUTOMATION", customer="Ironbridge Quarries",
        contract=D(500000), start=(-5, 2), end=(2, 30),
        budget_hours=_h(SE=700, EN=2250), budget_costs=_c(SUBCONTRACT=150000),
        prev_hours=_h(SE=380, EN=1150), prev_costs=_c(SUBCONTRACT=30000),
        month_hours=_h(SE=40, EN=200), first_prev_bill_month=-1,
        month_bills=[Bill("SUBCONTRACT", D(30000), 12, po_index=0, analytic_project="PRJ-01")],
        purchases=[PurchaseLine("SUBCONTRACT", D(150000), (-4, 1))],
        fc_prev_hours=_h(SE=320, EN=1100), fc_prev_costs=_c(SUBCONTRACT=120000),
        fc_curr_hours=_h(SE=280, EN=900), fc_curr_costs=_c(SUBCONTRACT=90000),
        milestones=[
            Milestone("MS01", "Advance payment", D("0.10"), (-5, 15), (-5, 5), (-5, 6), [((-4, 20), D(60000))]),
            Milestone("MS02", "Conveyor installation", D("0.90"), (2, 30)),
        ],
        progress_prev=D(38), progress_curr=D(44),
    ),
]

# code, name, business unit, customer, start offset, duration months, SE h/month, EN h/month, DS h/month,
# subcontract total, materials total
BACKGROUND_PROJECTS = [
    ("PRJ-10", "Millbrook Dairy Utilities Upgrade", "PLANTS", "Millbrook Dairy", -11, 18, 30, 60, 20, 240000, 120000),
    ("PRJ-11", "Crestline Bottling Line Controls", "AUTOMATION", "Crestline Beverages", -8, 14, 20, 50, 10, 60000, 40000),
    ("PRJ-12", "Stonegate Pump Station Refurbishment", "SERVICES", "Stonegate District Council", -6, 10, 15, 40, 0, 80000, 60000),
    ("PRJ-13", "Fairhaven Steam Network Extension", "PLANTS", "Fairhaven Paper Mill", -10, 20, 25, 70, 20, 300000, 150000),
    ("PRJ-14", "Oakridge Compressed Air Optimisation", "SERVICES", "Oakridge Glass", -3, 8, 10, 30, 0, 30000, 50000),
    ("PRJ-15", "Kingsport Warehouse Automation", "AUTOMATION", "Kingsport Distribution", -7, 16, 25, 60, 15, 120000, 90000),
]


# --------------------------------------------------------------------------- calendar helpers
def month_start(anchor: date, offset: int) -> date:
    index = anchor.year * 12 + anchor.month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)


def month_end(anchor: date, offset: int) -> date:
    return month_start(anchor, offset + 1) - timedelta(days=1)


def on(anchor: date, when: tuple[int, int]) -> date:
    offset, day = when
    return min(month_start(anchor, offset) + timedelta(days=day - 1), month_end(anchor, offset))


def month_offset(anchor: date, when: date) -> int:
    return (when.year * 12 + when.month) - (anchor.year * 12 + anchor.month)


def working_days(first: date) -> int:
    last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    return sum(1 for n in range((last - first).days + 1) if (first + timedelta(days=n)).weekday() < 5)


def fridays(first: date) -> list[date]:
    last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    days = [first + timedelta(days=n) for n in range((last - first).days + 1)]
    result = [d for d in days if d.weekday() == 4]
    return result or [last]


def spread(total: int | Decimal, parts: int) -> list:
    """Split `total` into `parts` integer amounts; the remainder goes to the last part."""
    if parts <= 0:
        return []
    kind = type(total)
    base = int(total) // parts
    values = [base] * parts
    values[-1] += int(total) - base * parts
    return [kind(v) for v in values]


# --------------------------------------------------------------------------- generator
@dataclass
class PlanFile:
    """One version to import, then transitions and attachments applied by the seed."""

    project_code: str
    version_type: str
    scenario: str
    label: str
    cutoff_date: date | None
    target_status: str
    rows: list[dict[str, Any]]
    assumptions: list[dict[str, Any]] = field(default_factory=list)
    assignments: list[dict[str, Any]] = field(default_factory=list)


class _ProjectsBuilder:
    def __init__(self, base: FixtureDataset):
        if (base.anchor_date + timedelta(days=1)).day != 1:
            raise ValueError("the project extension needs an anchor date on the last day of a month")
        self.ds = copy.deepcopy(base)
        self.anchor = base.anchor_date
        self.records = self.ds.records
        self.keys = self.ds.keys
        self.counters = {model: max((r["id"] for r in rows), default=0) for model, rows in self.records.items()}
        self.plans: list[PlanFile] = []
        self.ids: dict[str, int] = {}
        self.pools: dict[tuple[str, str], list[str]] = {}

    # ---- record helpers
    def add(self, model: str, key: str, **values: Any) -> int:
        self.counters[model] = self.counters.get(model, 0) + 1
        record_id = self.counters[model]
        self.records.setdefault(model, []).append({"id": record_id, **values})
        self.keys.setdefault(model, {})[record_id] = key
        self.ids[f"{model}:{key}"] = record_id
        return record_id

    def ref(self, model: str, key: str) -> int:
        return self.ids[f"{model}:{key}"]

    def get(self, model: str, record_id: int) -> dict[str, Any]:
        return next(r for r in self.records[model] if r["id"] == record_id)

    def stamp(self, when: date) -> str:
        return dt(when, 10)

    # ---- reference data
    def reference(self) -> None:
        start = self.stamp(month_start(self.anchor, -12))
        self.add("res.currency.rate", "USD_proj_1", name=str(month_start(self.anchor, -6)), rate=1.08,
                 currency_id=m2o(USD), company_id=m2o(COMPANY), write_date=start)
        self.add("res.currency.rate", "USD_proj_2", name=str(month_start(self.anchor, -5)), rate=1.12,
                 currency_id=m2o(USD), company_id=m2o(COMPANY), write_date=start)
        for code, name, account_type in (("604000", "Project purchases and subcontracting", "expense_direct_cost"),
                                         ("704000", "Engineering services", "income"),
                                         ("401100", "Suppliers", "liability_payable"),
                                         ("445660", "VAT deductible", "asset_current")):
            self.add("account.account", f"account_{code}", code=code, name=name, account_type=account_type, write_date=start)
        for key, name in (("categ_subcontract", "BENACTA_DEMO Subcontracting"), ("categ_project_materials", "BENACTA_DEMO Project materials"),
                          ("categ_contract", "BENACTA_DEMO Engineering contracts")):
            self.add("product.category", key, name=name, complete_name=name, property_cost_method="standard",
                     property_valuation="periodic", write_date=start)
        for key, name, categ in (("SUBCON", "Subcontracted works", "categ_subcontract"), ("PMAT", "Project materials", "categ_project_materials"),
                                 ("CONTRACT", "Engineering and delivery contract", "categ_contract"),
                                 ("CHANGE", "Contract change order", "categ_contract")):
            categ_id = self.ref("product.category", categ)
            template = self.add("product.template", f"template_{key}", name=name, type="service", is_storable=False,
                                categ_id=[categ_id, self.get("product.category", categ_id)["name"]], list_price=0.0,
                                uom_id=m2o(UNITS), company_id=m2o(COMPANY), seller_ids=[], write_date=start)
            self.add("product.product", f"product_{key}", product_tmpl_id=[template, name], default_code=key,
                     standard_price=0.0, write_date=start)

        plan = self.add("account.analytic.plan", "plan_projects", name="Projects", write_date=start)
        for code in BUSINESS_UNITS:
            self.add("project.tags", f"tag_BU_{code}", name=f"BU/{code}", write_date=start)
        for category in sorted({c for _n, c in INTERNAL_PROJECTS.values()}):
            self.add("project.tags", f"tag_INTERNAL_{category}", name=f"INTERNAL/{category}", write_date=start)
        self.plan_id = plan
        self.calendar = self.add("resource.calendar", "calendar_standard", name="Standard 37.5 hours per week",
                                 hours_per_day=float(HOURS_PER_DAY), write_date=start)

        departments = {"PM": "Project Management Office", "PC": "Project Management Office", "BY": "Procurement",
                       "SS": "Construction", "LE": "Engineering", "SE": "Engineering", "EN": "Engineering", "DS": "Design"}
        for name in sorted(set(departments.values())):
            self.add("hr.department", f"department_{name}", name=name, write_date=start)
        for role, name in ROLE_NAMES.items():
            self.add("hr.job", f"job_{role}", name=name, write_date=start)
        skill_type = self.add("hr.skill.type", "skill_type_technical", name="Technical", write_date=start)
        for skill in sorted({s for values in SKILLS.values() for s in values}):
            self.add("hr.skill", f"skill_{skill}", name=skill, skill_type_id=[skill_type, "Technical"], write_date=start)

        self.employees: dict[str, dict[str, Any]] = {}
        for index, role in enumerate(EMPLOYEE_ROLES, start=1):
            code = f"E{index:02d}"
            name = f"{FIRST_NAMES[index - 1]} {LAST_NAMES[index - 1]}"
            user = self.add("res.users", f"user_{code}", name=name, write_date=start)
            department = self.ref("hr.department", f"department_{departments[role]}")
            job = self.ref("hr.job", f"job_{role}")
            employee = self.add(
                "hr.employee", f"employee_{code}", name=name, job_id=[job, ROLE_NAMES[role]],
                department_id=[department, departments[role]], hourly_cost=float(ROLE_RATES[role]), company_id=m2o(COMPANY),
                user_id=[user, name], resource_calendar_id=[self.calendar, "Standard 37.5 hours per week"],
                x_benacta_employee_code=code, x_benacta_is_external=code in EXTERNAL_CODES, write_date=start,
            )
            for skill in SKILLS[role]:
                self.add("hr.employee.skill", f"employee_skill_{code}_{skill}", employee_id=[employee, name],
                         skill_id=[self.ref("hr.skill", f"skill_{skill}"), skill], skill_type_id=[skill_type, "Technical"],
                         write_date=start)
            self.employees[code] = {"id": employee, "name": name, "role": role, "user": user}
        self.by_role: dict[str, list[str]] = defaultdict(list)
        for code, employee in self.employees.items():
            if code not in EXTERNAL_CODES:
                self.by_role[employee["role"]].append(code)

        suppliers = {"SUPPLIER-A": "Delta Site Works", "SUPPLIER-B": "Meridian Process Supplies", "SUPPLIER-C": "Aurelian Machinery"}
        self.partners: dict[str, int] = {}
        for key, name in suppliers.items():
            self.partners[key] = self.add("res.partner", f"partner_{key}", name=name, company_id=m2o(COMPANY), is_company=True,
                                          customer_rank=0, supplier_rank=1, commercial_partner_id=False,
                                          email=f"{key.lower()}@benacta-demo.invalid", write_date=start)
        for partner in self.records["res.partner"][-len(suppliers):]:
            partner["commercial_partner_id"] = [partner["id"], partner["name"]]

    def customer(self, name: str) -> int:
        key = "customer_" + name.replace(" ", "_")
        if f"res.partner:{key}" in self.ids:
            return self.ids[f"res.partner:{key}"]
        partner = self.add("res.partner", key, name=name, company_id=m2o(COMPANY), is_company=True, customer_rank=1,
                           supplier_rank=0, commercial_partner_id=False, email=f"{key.lower()}@benacta-demo.invalid",
                           write_date=self.stamp(month_start(self.anchor, -12)))
        self.get("res.partner", partner)["commercial_partner_id"] = [partner, name]
        return partner

    # ---- internal projects and time
    def internal_projects(self) -> None:
        start = self.stamp(month_start(self.anchor, -12))
        for code, (name, category) in INTERNAL_PROJECTS.items():
            account = self.add("account.analytic.account", f"analytic_{code}", name=name, code=code, plan_id=[self.plan_id, "Projects"],
                               partner_id=False, company_id=m2o(COMPANY), write_date=start)
            tag = self.ref("project.tags", f"tag_INTERNAL_{category}")
            self.add("project.project", f"project_{code}", name=name, partner_id=False, user_id=False,
                     date_start=str(month_start(self.anchor, -12)), date=False, account_id=[account, name], allow_milestones=False,
                     tag_ids=[tag], company_id=m2o(COMPANY), sale_line_id=False, x_benacta_contract_type=False,
                     x_benacta_phase=False, x_benacta_fixed_rate_per_eur=False, write_date=start)
        # Odoo creates private to-dos without a project (seen on the live company); they are not work packages.
        self.add("project.task", "task_private_todo", name="Personal to-do", project_id=False, parent_id=False, milestone_id=False,
                 allocated_hours=0.0, x_benacta_wbs_code=False, x_benacta_change_order=False, write_date=start)

        for offset in range(-11, 1):
            first = month_start(self.anchor, offset)
            for code, employee in self.employees.items():
                if code in EXTERNAL_CODES:
                    continue
                if employee["role"] in SUPPORT_ROLES:
                    self.timesheets(code, "INT-SUPPORT", None, first, 120, "Support function time")
                    self.timesheets(code, "INT-NONPROD", None, first, 6, "Training and administration")
                else:
                    self.timesheets(code, "INT-PROPOSALS", None, first, 8, "Proposal support")
                    self.timesheets(code, "INT-DEVELOPMENT", None, first, 4, "Method development")
                    self.timesheets(code, "INT-NONPROD", None, first, 6, "Training and administration")

    def timesheets(self, employee_code: str, project_code: str, task_id: int | None, first: date, hours: int, label: str) -> None:
        if hours <= 0:
            return
        employee = self.employees[employee_code]
        project = self.ref("project.project", f"project_{project_code}")
        account = self.ref("account.analytic.account", f"analytic_{project_code}")
        weeks = fridays(first)
        for week, week_hours in zip(weeks, spread(hours, len(weeks)), strict=True):
            if week_hours == 0:
                continue
            self.add(
                "account.analytic.line", f"timesheet_{self.counters.get('account.analytic.line', 0) + 1:06d}",
                date=str(week), name=label, account_id=[account, project_code], project_id=[project, project_code],
                task_id=[task_id, ""] if task_id else False, employee_id=[employee["id"], employee["name"]],
                unit_amount=float(week_hours), amount=float(-D(week_hours) * ROLE_RATES[employee["role"]]),
                product_uom_id=False, company_id=m2o(COMPANY), write_date=self.stamp(week),
            )

    # ---- delivery projects
    def pool(self, project_code: str, role: str) -> list[str]:
        key = (project_code, role)
        if key not in self.pools:
            members = self.by_role[role]
            index = int(project_code.split("-")[1])
            size = min(1 if role == "LE" else 2 if role in {"SE", "DS"} else 3, len(members))
            self.pools[key] = [members[(index * 2 + n) % len(members)] for n in range(size)]
        return self.pools[key]

    def distribute(self, project_code: str, role: str, first: date, hours: int, task_id: int, label: str,
                   employees: list[str] | None = None) -> None:
        members = employees or self.pool(project_code, role)
        per_member = spread(hours, len(members))
        # Put the remainder first so the most loaded member is the first of the pool.
        per_member.reverse()
        for code, member_hours in zip(members, per_member, strict=True):
            self.timesheets(code, project_code, task_id, first, member_hours, label)

    def project(self, spec: ProjectSpec) -> None:
        a = self.anchor
        start_date, end_date = on(a, spec.start), on(a, spec.end)
        start_offset = spec.start[0]
        created = self.stamp(start_date - timedelta(days=20))
        customer = self.customer(spec.customer)
        pm_code = f"E0{int(spec.code.split('-')[1]) % 3 + 1}"
        pm = self.employees[pm_code]

        account = self.add("account.analytic.account", f"analytic_{spec.code}", name=spec.name, code=spec.code,
                           plan_id=[self.plan_id, "Projects"], partner_id=[customer, spec.customer], company_id=m2o(COMPANY),
                           write_date=created)
        contract_date = start_date - timedelta(days=10)
        so_id = self.add("sale.order", f"so_{spec.code}_CONTRACT", name=f"BD/SO/{spec.code}", partner_id=[customer, spec.customer],
                         company_id=m2o(COMPANY), currency_id=m2o(spec.currency), pricelist_id=False, date_order=dt(contract_date),
                         state="sale", order_line=[], invoice_ids=[], picking_ids=[], write_date=self.stamp(contract_date))
        contract_line = self.add(
            "sale.order.line", f"sol_{spec.code}_CONTRACT", order_id=[so_id, f"BD/SO/{spec.code}"],
            product_id=[self.ref("product.product", "product_CONTRACT"), "[CONTRACT] Engineering and delivery contract"],
            company_id=m2o(COMPANY), currency_id=m2o(spec.currency), display_type=False, product_uom_qty=1.0,
            product_uom_id=m2o(UNITS), price_unit=float(spec.contract), discount=0.0, price_subtotal=float(spec.contract),
            qty_delivered=0.0, qty_invoiced=0.0, invoice_lines=[], move_ids=[], tax_ids=[], project_id=False,
            qty_delivered_method="milestones", write_date=self.stamp(contract_date),
        )
        self.get("sale.order", so_id)["order_line"] = [contract_line]
        project_id = self.add(
            "project.project", f"project_{spec.code}", name=spec.name, partner_id=[customer, spec.customer],
            user_id=[pm["user"], pm["name"]], date_start=str(start_date), date=str(end_date), account_id=[account, spec.name],
            allow_milestones=True, tag_ids=[self.ref("project.tags", f"tag_BU_{spec.bu}")], company_id=m2o(COMPANY),
            sale_line_id=[contract_line, spec.name], x_benacta_contract_type=spec.contract_type, x_benacta_phase=spec.phase,
            x_benacta_fixed_rate_per_eur=float(spec.fixed_rate) if spec.fixed_rate else False, write_date=created,
        )
        tasks = {}
        for wbs, name in WORK_PACKAGES:
            tasks[wbs] = self.add("project.task", f"task_{spec.code}_{wbs}", name=f"{wbs} {name}", project_id=[project_id, spec.name],
                                  parent_id=False, milestone_id=False, allocated_hours=0.0, x_benacta_wbs_code=wbs,
                                  x_benacta_change_order=False, write_date=created)

        lines = {"contract": (contract_line, spec.contract)}
        for co in spec.change_orders:
            co_date = on(a, co.date)
            co_so = self.add("sale.order", f"so_{spec.code}_{co.key}", name=f"BD/SO/{spec.code}/{co.key}",
                             partner_id=[customer, spec.customer], company_id=m2o(COMPANY), currency_id=m2o(spec.currency),
                             pricelist_id=False, date_order=dt(co_date), state=co.state, order_line=[], invoice_ids=[],
                             picking_ids=[], write_date=self.stamp(co_date))
            co_line = self.add(
                "sale.order.line", f"sol_{spec.code}_{co.key}", order_id=[co_so, f"BD/SO/{spec.code}/{co.key}"],
                product_id=[self.ref("product.product", "product_CHANGE"), "[CHANGE] Contract change order"],
                company_id=m2o(COMPANY), currency_id=m2o(spec.currency), display_type=False, product_uom_qty=1.0,
                product_uom_id=m2o(UNITS), price_unit=float(co.amount), discount=0.0, price_subtotal=float(co.amount),
                qty_delivered=0.0, qty_invoiced=0.0, invoice_lines=[], move_ids=[], tax_ids=[], project_id=[project_id, spec.name],
                qty_delivered_method="milestones", write_date=self.stamp(co_date),
            )
            self.get("sale.order", co_so)["order_line"] = [co_line]
            lines[co.key] = (co_line, co.amount)
            if co.state != "sale":
                tasks[f"CO-{co.key}"] = self.add(
                    "project.task", f"task_{spec.code}_CO_{co.key}", name=f"{co.key} {co.name}", project_id=[project_id, spec.name],
                    parent_id=False, milestone_id=False, allocated_hours=0.0, x_benacta_wbs_code=f"CO-{co.key}",
                    x_benacta_change_order=True, write_date=self.stamp(co_date),
                )

        # time: previous months spread evenly, then the cutoff month
        months_before = list(range(start_offset, 0))
        for role, total in spec.prev_hours.items():
            for offset, hours in zip(months_before, spread(total, len(months_before)), strict=True):
                self.distribute(spec.code, role, month_start(a, offset), hours, tasks["WP20"], "Engineering")
        for role, hours in spec.month_hours.items():
            scope = spec.change_order_scope_hours.get(role, 0)
            co_task = next((t for k, t in tasks.items() if k.startswith("CO-")), None)
            pool = self.pool(spec.code, role)
            employees = [e for e in pool if e not in spec.month_absent_employees.get(role, [])]
            employees += spec.month_extra_employees.get(role, [])
            self.distribute(spec.code, role, month_start(a, 0), hours - scope, tasks["WP20"], "Engineering", employees)
            if scope:
                self.distribute(spec.code, role, month_start(a, 0), scope, co_task, "Change order scope", employees)

        # purchasing and vendor bills
        po_lines: list[tuple[int, PurchaseLine]] = []
        for number, purchase in enumerate(spec.purchases, start=1):
            order_date = on(a, purchase.ordered)
            po_name = f"BD/PO/{spec.code}/{number:02d}"
            po_id = self.add("purchase.order", f"po_{spec.code}_{number:02d}", name=po_name,
                             partner_id=[self.partners[purchase.supplier], purchase.supplier], company_id=m2o(COMPANY),
                             currency_id=m2o(EUR), date_order=dt(order_date), state="purchase", write_date=self.stamp(order_date))
            product = "product_SUBCON" if purchase.category == "SUBCONTRACT" else "product_PMAT"
            line_id = self.add(
                "purchase.order.line", f"pol_{spec.code}_{number:02d}", order_id=[po_id, po_name],
                product_id=[self.ref("product.product", product), product[8:]], product_qty=1.0, uom_id=m2o(UNITS),
                price_unit=float(purchase.amount), price_subtotal=float(purchase.amount), qty_received=0.0, qty_invoiced=0.0,
                move_ids=[], analytic_distribution={str(account): 100.0},
                x_benacta_work_package=CATEGORY_WORK_PACKAGE[purchase.category], date_planned=dt(order_date + timedelta(days=30)),
                write_date=self.stamp(order_date),
            )
            po_lines.append((line_id, purchase))

        billed: dict[int, Decimal] = defaultdict(Decimal)
        first_bill = spec.first_prev_bill_month if spec.first_prev_bill_month is not None else start_offset + 1
        bill_months = list(range(first_bill, 0))
        for category, total in spec.prev_costs.items():
            for offset, amount in zip(bill_months, spread(total, len(bill_months)), strict=True):
                self.allocate_bills(spec, po_lines, billed, category, amount, on(a, (offset, 25)), account)
        for bill in spec.month_bills:
            target = on(a, (0, bill.day))
            analytic = self.ref("account.analytic.account", f"analytic_{bill.analytic_project}") if bill.analytic_project else account
            if bill.po_index is not None:
                line_id, purchase = [p for p in po_lines if p[1].category == bill.category][bill.po_index]
                self.vendor_bill(spec, line_id, purchase, bill.amount, target, analytic)
                billed[line_id] += bill.amount
            else:
                self.allocate_bills(spec, po_lines, billed, bill.category, bill.amount, target, analytic)
        for line_id, purchase in po_lines:
            line = self.get("purchase.order.line", line_id)
            line["qty_invoiced"] = float(billed[line_id] / purchase.amount)
            line["qty_received"] = line["qty_invoiced"]

        # milestones, invoices, payments
        for ms in spec.milestones:
            line_id, line_amount = lines[ms.line]
            reached = on(a, ms.reached) if ms.reached else None
            milestone = self.add(
                "project.milestone", f"milestone_{spec.code}_{ms.key}", name=ms.name, project_id=[project_id, spec.name],
                deadline=str(on(a, ms.deadline)), is_reached=reached is not None, reached_date=str(reached) if reached else False,
                sale_line_id=[line_id, ms.line], quantity_percentage=float(ms.pct), x_benacta_milestone_code=ms.key,
                write_date=self.stamp(reached or month_start(a, -12)),
            )
            if ms.invoiced:
                self.customer_invoice(spec, customer, line_id, milestone, ms, line_amount, on(a, ms.invoiced))

        self.plan_files(spec, lines)

    def allocate_bills(self, spec, po_lines, billed, category, amount, when, analytic) -> None:
        remaining = amount
        for line_id, purchase in po_lines:
            if purchase.category != category or remaining <= 0:
                continue
            capacity = purchase.amount - billed[line_id]
            part = min(capacity, remaining)
            if part > 0:
                self.vendor_bill(spec, line_id, purchase, part, when, analytic)
                billed[line_id] += part
                remaining -= part
        if remaining > 0:
            raise ValueError(f"{spec.code}: {category} bills exceed ordered amounts by {remaining}")

    def vendor_bill(self, spec, line_id, purchase, amount, when, analytic) -> None:
        name = f"BD/BILL/{self.counters.get('account.move', 0) + 1:05d}"
        move = self.add("account.move", f"move_{name}", name=name, move_type="in_invoice", state="posted", company_id=m2o(COMPANY),
                        partner_id=[self.partners[purchase.supplier], purchase.supplier], currency_id=m2o(EUR),
                        invoice_date=str(when), date=str(when), invoice_origin=False, reversed_entry_id=False,
                        amount_untaxed_signed=float(-amount), payment_state="not_paid",
                        invoice_date_due=str(when + timedelta(days=PAYMENT_TERMS_DAYS)), amount_untaxed=float(amount),
                        amount_total=float(money(amount * D("1.2"))), amount_residual=float(money(amount * D("1.2"))),
                        write_date=self.stamp(when))
        product = "product_SUBCON" if purchase.category == "SUBCONTRACT" else "product_PMAT"
        tax = money(amount * D("0.2"))
        common = dict(move_id=[move, name], company_id=m2o(COMPANY), parent_state="posted", currency_id=m2o(EUR), date=str(when),
                      sale_line_ids=[], write_date=self.stamp(when))
        self.add("account.move.line", f"aml_{self.counters.get('account.move.line', 0) + 1:05d}", **common,
                 account_id=[self.ref("account.account", "account_604000"), "604000"], display_type="product",
                 product_id=[self.ref("product.product", product), product[8:]], quantity=float(amount / purchase.amount),
                 product_uom_id=m2o(UNITS), price_unit=float(purchase.amount), discount=0.0, price_subtotal=float(amount),
                 balance=float(amount), amount_currency=float(amount), purchase_line_id=[line_id, ""],
                 analytic_distribution={str(analytic): 100.0})
        self.add("account.move.line", f"aml_{self.counters.get('account.move.line', 0) + 1:05d}", **common,
                 account_id=[self.ref("account.account", "account_445660"), "445660"], display_type="tax", product_id=False,
                 quantity=0.0, product_uom_id=False, price_unit=0.0, discount=0.0, price_subtotal=0.0, balance=float(tax),
                 amount_currency=float(tax), purchase_line_id=False, analytic_distribution=False)
        self.add("account.move.line", f"aml_{self.counters.get('account.move.line', 0) + 1:05d}", **common,
                 account_id=[self.ref("account.account", "account_401100"), "401100"], display_type="payment_term", product_id=False,
                 quantity=0.0, product_uom_id=False, price_unit=0.0, discount=0.0, price_subtotal=0.0,
                 balance=float(-(amount + tax)), amount_currency=float(-(amount + tax)), purchase_line_id=False, analytic_distribution=False)

    def rate_on(self, when: date) -> Decimal:
        rates = [r for r in self.records["res.currency.rate"] if r["currency_id"][0] == USD[0] and r["name"] <= str(when)]
        return D(str(max(rates, key=lambda r: r["name"])["rate"]))

    def customer_invoice(self, spec, customer, line_id, milestone, ms, line_amount, when) -> None:
        amount = money(line_amount * ms.pct)
        tax = money(amount * spec.vat)
        rate = D(1) if spec.currency == EUR else self.rate_on(when)
        name = f"BD/INV/{spec.code}/{ms.key}"
        total = amount + tax
        paid = sum((p for _w, p in ms.payments), D(0))
        move = self.add("account.move", f"move_{name}", name=name, move_type="out_invoice", state="posted", company_id=m2o(COMPANY),
                        partner_id=[customer, spec.customer], currency_id=m2o(spec.currency), invoice_date=str(when), date=str(when),
                        invoice_origin=f"BD/SO/{spec.code}", reversed_entry_id=False,
                        amount_untaxed_signed=float(money(amount / rate)), payment_state="paid" if paid >= total else ("partial" if paid else "not_paid"),
                        invoice_date_due=str(when + timedelta(days=PAYMENT_TERMS_DAYS)), amount_untaxed=float(amount),
                        amount_total=float(total), amount_residual=float(total - paid), write_date=self.stamp(when))
        common = dict(move_id=[move, name], company_id=m2o(COMPANY), parent_state="posted", currency_id=m2o(spec.currency),
                      date=str(when), write_date=self.stamp(when), purchase_line_id=False, analytic_distribution=False)
        aml = self.add("account.move.line", f"aml_{self.counters.get('account.move.line', 0) + 1:05d}", **common,
                       account_id=[self.ref("account.account", "account_704000"), "704000"], display_type="product",
                       product_id=[self.ref("product.product", "product_CONTRACT"), "CONTRACT"], quantity=float(ms.pct),
                       product_uom_id=m2o(UNITS), price_unit=float(line_amount), discount=0.0, price_subtotal=float(amount),
                       balance=float(-money(amount / rate)), amount_currency=float(-amount), sale_line_ids=[line_id])
        self.get("sale.order.line", line_id)["invoice_lines"].append(aml)
        if tax:
            self.add("account.move.line", f"aml_{self.counters.get('account.move.line', 0) + 1:05d}", **common,
                     account_id=[4, "445710 VAT collected"], display_type="tax", product_id=False, quantity=0.0, product_uom_id=False,
                     price_unit=0.0, discount=0.0, price_subtotal=0.0, balance=float(-money(tax / rate)), amount_currency=float(-tax),
                     sale_line_ids=[])
        self.add("account.move.line", f"aml_{self.counters.get('account.move.line', 0) + 1:05d}", **common,
                 account_id=[1, "411100 Customers"], display_type="payment_term", product_id=False, quantity=0.0, product_uom_id=False,
                 price_unit=0.0, discount=0.0, price_subtotal=0.0,
                 balance=float(money(amount / rate) + money(tax / rate)), amount_currency=float(total), sale_line_ids=[])
        for number, (paid_on, paid_amount) in enumerate(ms.payments, start=1):
            pay_date = on(self.anchor, paid_on)
            self.add("account.payment", f"payment_{spec.code}_{ms.key}_{number}", name=f"BD/PAY/{spec.code}/{ms.key}/{number}",
                     date=str(pay_date), amount=float(paid_amount), currency_id=m2o(spec.currency), partner_id=[customer, spec.customer],
                     payment_type="inbound", state="paid", reconciled_invoice_ids=[move], company_id=m2o(COMPANY),
                     write_date=self.stamp(pay_date))

    # ---- planning files
    def plan_files(self, spec: ProjectSpec, lines: dict[str, tuple[int, Decimal]]) -> None:
        a = self.anchor
        start_offset, end_offset = spec.start[0], spec.end[0]
        life = list(range(start_offset, end_offset + 1))
        currency = "EUR"

        def cost_rows(hours: dict[str, int], costs: dict[str, Decimal], months: list[int]) -> list[dict[str, Any]]:
            rows = []
            for role, total in sorted(hours.items()):
                for offset, value in zip(months, spread(total, len(months)), strict=True):
                    if value:
                        rows.append({"work_package": "WP20", "cost_category": "LABOUR", "resource_or_role": role,
                                     "period": month_start(a, offset), "planned_hours": D(value),
                                     "planned_rate": D(ROLE_RATES[role]), "planned_cost": D(value * ROLE_RATES[role])})
            for category, total in sorted(costs.items()):
                for offset, value in zip(months, spread(total, len(months)), strict=True):
                    if value:
                        rows.append({"work_package": CATEGORY_WORK_PACKAGE[category], "cost_category": category,
                                     "resource_or_role": "", "period": month_start(a, offset), "planned_cost": D(value)})
            return rows

        def billing_rows(cutoff_offset: int | None, which: str) -> list[dict[str, Any]]:
            rows = []
            for ms in spec.milestones:
                if cutoff_offset is not None and ms.invoiced and on(a, ms.invoiced) <= month_end(a, cutoff_offset):
                    continue
                period = ms.deadline[0]
                override = ms.billing_period_prev if which == "prev" else ms.billing_period_curr if which == "curr" else None
                if override is not None:
                    period = override
                if cutoff_offset is not None:
                    period = max(period, cutoff_offset + 1)
                _line, line_amount = lines[ms.line]
                amount = money(line_amount * ms.pct)
                if spec.fixed_rate:
                    amount = money(amount / spec.fixed_rate)
                cash_date = month_start(a, period) + timedelta(days=14 + PAYMENT_TERMS_DAYS)
                rows.append({"work_package": ms.key, "cost_category": "REVENUE", "resource_or_role": "", "period": month_start(a, period),
                             "planned_billing": amount})
                rows.append({"work_package": ms.key, "cost_category": "REVENUE", "resource_or_role": "",
                             "period": date(cash_date.year, cash_date.month, 1), "planned_cash_collection": money(amount * (1 + spec.vat))})
            merged: dict[tuple, dict[str, Any]] = {}
            for row in rows:
                key = (row["work_package"], row["period"])
                merged.setdefault(key, {**row}).update({k: v for k, v in row.items() if k.startswith("planned_")})
            return list(merged.values())

        def rows_with_header(rows, version_type, scenario, label, cutoff):
            header = {"project_code": spec.code, "version_type": version_type, "scenario": scenario, "label": label,
                      "cutoff_date": str(cutoff) if cutoff else "", "currency": currency, "business_unit": spec.bu}
            out = []
            for row in rows:
                full = {**header, **{m: "" for m in ("planned_hours", "planned_rate", "planned_cost", "planned_revenue",
                                                     "planned_billing", "planned_cash_collection")}}
                for key, value in row.items():
                    full[key] = value.isoformat()[:7] if isinstance(value, date) else (str(value) if isinstance(value, Decimal) else value)
                out.append(full)
            return out

        effective_baseline = on(a, spec.start) - timedelta(days=10)
        baseline = cost_rows(spec.budget_hours, spec.budget_costs, life) + billing_rows(None, "budget")
        self.plans.append(PlanFile(spec.code, "BUDGET_BASELINE", "BASE", "BUDGET-BASELINE", effective_baseline, "LOCKED",
                                   rows_with_header(baseline, "BUDGET_BASELINE", "BASE", "BUDGET-BASELINE", effective_baseline)))
        if spec.revised_budget:
            effective = on(a, spec.revised_budget["effective"])
            revised = cost_rows(spec.revised_budget["hours"], spec.revised_budget["costs"], life) + billing_rows(None, "budget")
            self.plans.append(PlanFile(spec.code, "BUDGET_REVISED", "BASE", "BUDGET-REVISED-1", effective, "LOCKED",
                                       rows_with_header(revised, "BUDGET_REVISED", "BASE", "BUDGET-REVISED-1", effective)))

        # FC-06 derived: same completion estimate as FC-07 minus the actuals of the month before the previous cutoff
        july_hours = {role: spread(total, len(range(start_offset, 0)))[-1] for role, total in spec.prev_hours.items()}
        first_bill = spec.first_prev_bill_month if spec.first_prev_bill_month is not None else start_offset + 1
        july_costs = {cat: spread(total, len(range(first_bill, 0)))[-1] for cat, total in spec.prev_costs.items()}
        fc06_hours = {role: spec.fc_prev_hours.get(role, 0) + july_hours.get(role, 0) for role in sorted(set(spec.fc_prev_hours) | set(july_hours))}
        fc06_costs = {cat: spec.fc_prev_costs.get(cat, D(0)) + july_costs.get(cat, D(0)) for cat in sorted(set(spec.fc_prev_costs) | set(july_costs))}
        for label, cutoff_offset, hours, costs, status, which in (
            ("FC-{:%Y-%m}", -2, fc06_hours, fc06_costs, "LOCKED", "prev"),
            ("FC-{:%Y-%m}", -1, spec.fc_prev_hours, spec.fc_prev_costs, "LOCKED", "prev"),
            ("FC-{:%Y-%m}", 0, spec.fc_curr_hours, spec.fc_curr_costs, spec.fc_curr_status, "curr"),
        ):
            cutoff = month_end(a, cutoff_offset)
            name = label.format(cutoff)
            months = list(range(cutoff_offset + 1, end_offset + 1))
            rows = cost_rows(hours, costs, months) + billing_rows(cutoff_offset, which)
            assumptions = []
            progress = spec.progress_prev if cutoff_offset < 0 else spec.progress_curr
            if progress is not None:
                assumptions.append({"key": "physical_progress_pct", "value_numeric": progress, "evidence_ref": f"milestones:{spec.code}"})
            if cutoff_offset == 0 and spec.notes_curr:
                assumptions.append({"key": "forecast_change_note", "value_text": spec.notes_curr, "evidence_ref": f"forecast:{spec.code}:{name}"})
            assignments = []
            if cutoff_offset == 0:
                for role, total in hours.items():
                    for offset, value in zip(months, spread(total, len(months)), strict=True):
                        members = self.pool(spec.code, role)
                        per_member = spread(value, len(members))
                        per_member.reverse()
                        for code, member_hours in zip(members, per_member, strict=True):
                            if member_hours:
                                assignments.append({"work_package": "WP20", "employee_code": code, "role": role,
                                                    "period": month_start(a, offset), "planned_hours": D(member_hours)})
            if cutoff_offset == -1:
                # the previous forecast planned the cutoff month; used by the timesheet completeness check
                for role, total in hours.items():
                    value = spread(total, len(months))[0] if months else 0
                    members = self.pool(spec.code, role)
                    for code, member_hours in zip(members, reversed(spread(value, len(members))), strict=True):
                        if member_hours:
                            assignments.append({"work_package": "WP20", "employee_code": code, "role": role,
                                                "period": month_start(a, 0), "planned_hours": D(member_hours)})
            self.plans.append(PlanFile(spec.code, "FORECAST", "BASE", name, cutoff, status,
                                       rows_with_header(rows, "FORECAST", "BASE", name, cutoff), assumptions, assignments))

        if spec.pending_co_scenario:
            cutoff = month_end(a, 0)
            name = f"FC-{cutoff:%Y-%m}"
            hours = dict(spec.fc_curr_hours)
            for role, extra in spec.pending_co_scenario["hours"].items():
                hours[role] = hours.get(role, 0) + extra
            months = list(range(1, end_offset + 1))
            rows = cost_rows(hours, spec.fc_curr_costs, months) + billing_rows(0, "curr")
            for co in spec.change_orders:
                if co.state != "sale":
                    rows.append({"work_package": f"CO-{co.key}", "cost_category": "REVENUE", "resource_or_role": "",
                                 "period": month_start(a, spec.pending_co_scenario["billing_period"]), "planned_billing": co.amount})
            self.plans.append(PlanFile(spec.code, "FORECAST", "PENDING_CO", name, cutoff, "APPROVED",
                                       rows_with_header(rows, "FORECAST", "PENDING_CO", name, cutoff)))

    # ---- background projects
    def background(self) -> None:
        for code, name, bu, customer, start_offset, duration, se, en, ds, subcontract, materials in BACKGROUND_PROJECTS:
            end_offset = start_offset + duration - 1
            hours_month = {role: value for role, value in (("SE", se), ("EN", en), ("DS", ds)) if value}
            elapsed_prev = -start_offset  # months before the cutoff month
            total_months = duration
            budget_hours = {role: value * total_months for role, value in hours_month.items()}
            labour = sum(D(h * ROLE_RATES[r]) for r, h in budget_hours.items())
            budget_costs = {"SUBCONTRACT": D(subcontract), "MATERIALS": D(materials)}
            budget_total = labour + D(subcontract) + D(materials)
            contract = D(int(budget_total / D("0.8") / 1000) * 1000)
            bill_months_prev = elapsed_prev - 1  # bills start the month after project start
            per_month = {cat: amount // total_months for cat, amount in budget_costs.items()}
            prev_costs = {cat: per_month[cat] * bill_months_prev for cat in budget_costs}
            month_costs = {cat: per_month[cat] for cat in budget_costs}
            prev_hours = {role: value * elapsed_prev for role, value in hours_month.items()}
            remaining_months = end_offset
            fc_prev_hours = {role: budget_hours[role] - prev_hours[role] for role in hours_month}
            fc_curr_hours = {role: budget_hours[role] - prev_hours[role] - hours_month[role] for role in hours_month}
            fc_prev_costs = {cat: budget_costs[cat] - prev_costs[cat] for cat in budget_costs}
            fc_curr_costs = {cat: budget_costs[cat] - prev_costs[cat] - month_costs[cat] for cat in budget_costs}
            advance = (start_offset, 20)
            mid_offset = start_offset + duration // 2
            mid_reached = mid_offset < 0
            milestones = [
                Milestone("MS01", "Advance payment", D("0.10"), (start_offset, 28), (start_offset, 15), (start_offset, 16),
                          [((min(start_offset + 2, 0), 1), money(contract * D("0.10") * D("1.2")))]),
                Milestone("MS02", "Mid-project milestone", D("0.40"), (mid_offset if mid_reached else max(mid_offset, 1), 28),
                          (mid_offset, 25) if mid_reached else None, (mid_offset, 28) if mid_reached else None,
                          [((min(mid_offset + 2, 0), 12), money(contract * D("0.40") * D("1.2")))] if mid_offset + 2 <= 0 else []),
                Milestone("MS03", "Completion", D("0.50"), (end_offset, 28)),
            ]
            del advance, remaining_months
            spec = ProjectSpec(
                code=code, name=name, bu=bu, customer=customer, contract=contract, start=(start_offset, 1), end=(end_offset, 28),
                budget_hours=budget_hours, budget_costs=budget_costs, prev_hours=prev_hours, prev_costs=prev_costs,
                month_hours=hours_month,
                month_bills=[Bill(cat, amount, 25) for cat, amount in month_costs.items() if amount],
                purchases=[PurchaseLine("SUBCONTRACT", D(subcontract), (start_offset, 10)),
                           PurchaseLine("MATERIALS", D(materials), (start_offset, 12), "SUPPLIER-B")],
                fc_prev_hours=fc_prev_hours, fc_prev_costs=fc_prev_costs, fc_curr_hours=fc_curr_hours, fc_curr_costs=fc_curr_costs,
                milestones=milestones,
                progress_prev=D(round(100 * (elapsed_prev) / duration)), progress_curr=D(round(100 * (elapsed_prev + 1) / duration)),
            )
            self.project(spec)

    def build(self) -> FixtureDataset:
        self.reference()
        self.internal_projects()
        for spec in GOLDEN_PROJECTS:
            self.project(spec)
        self.background()
        self.ds.dataset_id = "demo_v2"
        self.ds.source_instance = "fixture_demo_v2"
        self.ds.plans = self.plans
        self.ds.pools = dict(self.pools)
        return self.ds


def extend_with_projects(base: FixtureDataset) -> FixtureDataset:
    return _ProjectsBuilder(base).build()
