from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.config import REPO_ROOT
from app.fixtures.demo_dataset import BACKGROUND_CUSTOMERS, SCENARIO_CUSTOMERS, build_demo_dataset
from tests.oracle import case, dec, load_oracle


@pytest.fixture(scope="module")
def dataset():
    return build_demo_dataset()


@pytest.fixture(scope="module")
def oracle():
    return load_oracle()


def _digest(ds) -> str:
    return hashlib.sha256(json.dumps(ds.records, sort_keys=True).encode()).hexdigest()


def test_generation_is_deterministic(dataset):
    assert _digest(dataset) == _digest(build_demo_dataset())


def test_anchor_date_is_configurable_and_moves_the_whole_window():
    shifted = build_demo_dataset(anchor=date(2026, 9, 30))
    assert shifted.window_start == date(2026, 7, 3)
    assert max(o["date_order"][:10] for o in shifted.records["sale.order"]) <= "2026-09-30"
    assert min(o["date_order"][:10] for o in shifted.records["sale.order"]) >= "2026-07-03"


def test_structure_matches_the_oracle(dataset, oracle):
    structure = oracle["structure"]
    orders = dataset.records["sale.order"]
    assert len(orders) == structure["sale_orders"]
    assert Counter(o["state"] for o in orders) == structure["sale_orders_by_state"]
    partners = dataset.records["res.partner"]
    assert sum(1 for p in partners if p["customer_rank"]) == structure["customers"]
    assert sum(1 for p in partners if p["supplier_rank"]) == structure["suppliers"]
    templates = dataset.records["product.template"]
    assert sum(1 for t in templates if t["is_storable"]) == structure["storable_products"]
    assert sum(1 for t in templates if t["type"] == "service") == structure["service_products"]


def test_every_journal_entry_is_balanced(dataset):
    balance = defaultdict(Decimal)
    for line in dataset.records["account.move.line"]:
        balance[line["move_id"][0]] += Decimal(str(line["balance"]))
    assert all(total == 0 for total in balance.values()), {k: v for k, v in balance.items() if v}


def test_everything_happens_inside_the_window(dataset):
    end = dataset.anchor_date.isoformat()
    start = (dataset.window_start - timedelta(days=0)).isoformat()
    for model, field in (("sale.order", "date_order"), ("account.move", "date"), ("stock.move", "date")):
        values = [r[field][:10] for r in dataset.records[model]]
        assert min(values) >= start and max(values) <= end, model


def test_golden_cases_are_isolated(dataset):
    orders_by_customer = Counter(o["partner_id"][1] for o in dataset.records["sale.order"])
    for key in ("G1", "G2", "G3", "G4", "G5", "N13"):
        assert orders_by_customer[SCENARIO_CUSTOMERS[key][0]] == 1
    lines_by_product = Counter(line["product_id"][1] for line in dataset.records["sale.order.line"])
    for code in ("SC1", "SC2", "SC3", "SC4", "SC5"):
        assert sum(n for name, n in lines_by_product.items() if "] " in name and name.startswith(f"[{code}]")) == 1


def test_background_orders_are_compliant_by_construction(dataset):
    caps = {"standard": Decimal(5), "key_account": Decimal(10)}
    freight_customers = {v[0] for v in BACKGROUND_CUSTOMERS.values() if v[2] == "rebill"}
    customer_segment = {v[0]: v[1] for v in BACKGROUND_CUSTOMERS.values()}
    orders = {o["id"]: o for o in dataset.records["sale.order"] if o["name"][6:].isdigit()}
    assert len(orders) == 106
    for line in dataset.records["sale.order.line"]:
        order = orders.get(line["order_id"][0])
        if order is None:
            continue
        assert Decimal(str(line["discount"])) <= caps[customer_segment[order["partner_id"][1]]]
    for order in orders.values():
        products = {
            line["product_id"][1] for line in dataset.records["sale.order.line"] if line["order_id"][0] == order["id"]
        }
        has_freight = any(p.startswith("[FRT]") for p in products)
        assert has_freight == (order["partner_id"][1] in freight_customers)


def test_business_terms_realise_the_oracle_context(dataset, oracle):
    terms = dataset.terms
    policies = {p["policy_id"]: p for p in terms["discount_policies"]}

    disc = case(oracle, "DISC-001")["facts"]
    assert dec(policies[disc["applicable_policy"]]["max_discount_pct"]) == dec(disc["allowed_discount_pct"])

    neg01 = case(oracle, "NEG-01")
    derogation = next(d for d in terms["discount_derogations"] if d["derogation_id"] == neg01["facts"]["derogation"])
    order_date = dataset.find("sale.order", name="BD/SO/NEG-01")[0]["date_order"][:10]
    assert derogation["valid_from"] <= order_date <= derogation["valid_to"]

    neg09 = case(oracle, "NEG-09")["facts"]
    distributor = policies[neg09["only_segment_policy"]]
    assert distributor["valid_to"] == neg09["policy_valid_to"] < neg09["order_date"]

    neg10 = case(oracle, "NEG-10")["facts"]
    a, b = (policies[p] for p in neg10["policies"])
    assert a["priority"] == b["priority"] and [a["max_discount_pct"], b["max_discount_pct"]] == neg10["caps"]

    contracts = {c["contract_id"]: c for c in terms["freight_contracts"]}
    freight = case(oracle, "FREIGHT-001")["facts"]
    assert contracts[freight["contract"]]["terms"] == "rebill"
    assert dec(contracts[freight["contract"]]["amount"]) == dec(freight["contract_amount"])
    assert contracts[case(oracle, "NEG-02")["facts"]["contract"]]["terms"] == "waived"

    price = next(c for c in terms["contract_prices"] if c["contract_id"] == case(oracle, "PRICE-001")["facts"]["contract"])
    assert (price["customer"], price["product"], dec(price["unit_price"])) == ("G4", "P07", dec(case(oracle, "PRICE-001")["facts"]["contract_unit_price"]))
    items = {i["product_tmpl_id"][1]: dec(i["fixed_price"]) for i in dataset.records["product.pricelist.item"]}
    assert items["[P02] Flow Meter P02"] == dec(case(oracle, "PLIST-001")["facts"]["distributor_fixed_price"])
    references = {r["product"]: dec(r["unit_cost"]) for r in terms["cost_references"]}
    assert references["SC3"] == dec(case(oracle, "COST-001")["facts"]["reference_unit_cost"])
    assert references["SC4"] == dec(case(oracle, "NEG-08")["facts"]["reference_unit_cost"])
    cost_sale = dataset.find("sale.order", name="BD/SO/COST-001")[0]["date_order"][:10]
    assert next(r for r in terms["cost_references"] if r["product"] == "SC3")["frozen_on"] < cost_sale


def _code_strings_and_imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            yield node.value
        elif isinstance(node, ast.Import | ast.ImportFrom):
            yield from (alias.name for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                yield node.module


def test_application_code_never_reads_the_oracle():
    """Ground-truth labels must stay out of reach of the engine, rules and tools."""
    for path in (REPO_ROOT / "apps" / "api" / "app").rglob("*.py"):
        for value in _code_strings_and_imports(path):
            assert "oracle" not in value.lower() and "golden" not in value.lower(), f"{path.name}: {value!r}"
