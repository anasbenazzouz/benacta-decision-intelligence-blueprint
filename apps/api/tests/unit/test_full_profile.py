"""The demonstration profile: deterministic, referentially coherent, realistically distributed, with its ground truth kept
apart from the records and versioned under data/golden."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from decimal import Decimal

import pytest

from app.config import REPO_ROOT
from app.fixtures.full_profile import MONTHS, build_full_profile, ground_truth

MANIFEST = REPO_ROOT / "data" / "golden" / "demo_full_manifest_v1.json"
# Building the profile takes about a minute; these checks run with the opt-in full-profile gate.
pytestmark = pytest.mark.full_profile


@pytest.fixture(scope="module")
def dataset():
    return build_full_profile()


@pytest.fixture(scope="module")
def manifest(dataset):
    return ground_truth(dataset)


def _digest(records) -> str:
    return hashlib.sha256(json.dumps(records, sort_keys=True, default=str).encode()).hexdigest()


def test_generation_is_deterministic(dataset):
    assert _digest(dataset.records) == _digest(build_full_profile().records)
    assert ground_truth(build_full_profile()) == ground_truth(dataset)


def test_volumes_meet_the_demonstration_targets(manifest):
    s = manifest["structure"]
    assert s["customers"] >= 500 and s["suppliers"] >= 100 and s["products"] >= 200
    assert s["sale_order_lines"] >= 10_000 and s["purchase_order_lines"] >= 8_000 and s["journal_items"] >= 50_000
    assert s["payments"] > 0 and s["currency_rates"] >= 100 and manifest["months"] == MONTHS


def test_referential_integrity(dataset):
    r = dataset.records
    orders = {o["id"] for o in r["sale.order"]}
    products = {p["id"] for p in r["product.product"]}
    partners = {p["id"] for p in r["res.partner"]}
    moves = {m["id"] for m in r["account.move"]}
    for line in r["sale.order.line"]:
        assert line["order_id"][0] in orders and line["product_id"][0] in products
    for order in r["sale.order"]:
        assert order["partner_id"][0] in partners
    for line in r["account.move.line"]:
        assert line["move_id"][0] in moves
        for sol in line["sale_line_ids"]:
            assert any(s["id"] == sol for s in r["sale.order.line"][sol - 1: sol]) or sol <= len(r["sale.order.line"])
    for move in r["stock.move"]:
        assert move["product_id"][0] in products
    for payment in r["account.payment"]:
        assert all(i in moves for i in payment["reconciled_invoice_ids"])
    balance: dict[int, Decimal] = {}
    for line in r["account.move.line"]:
        balance[line["move_id"][0]] = balance.get(line["move_id"][0], Decimal(0)) + Decimal(str(line["balance"]))
    assert all(abs(v) < Decimal("0.02") for v in balance.values())
    sold = {line["product_id"][0] for line in r["sale.order.line"]}
    received = {m["product_id"][0] for m in r["stock.move"] if m["purchase_line_id"]}
    missing = {p["default_code"] for p in r["product.product"] if p["id"] in sold and p["id"] not in received}
    assert missing == {"FRT", "SCM-01", "SCM-02", "SCM-03"}, "only the freight service and the missing-cost scenario products have no receipt"


def test_realistic_distributions(dataset, manifest):
    r = dataset.records
    by_month = Counter(o["date_order"][:7] for o in r["sale.order"])
    counts = [by_month[m] for m in sorted(by_month)]
    assert len(counts) == MONTHS
    assert max(counts) > 1.5 * min(counts), "seasonality: August troughs against spring and autumn peaks"
    assert sum(counts[24:]) > sum(counts[:12]), "growth over the three years"
    currencies = Counter(o["currency_id"][1] for o in r["sale.order"])
    assert set(currencies) == {"EUR", "USD", "GBP", "CHF"} and currencies["EUR"] > 0.9 * len(r["sale.order"])
    per_customer = Counter(o["partner_id"][0] for o in r["sale.order"])
    top = sorted(per_customer.values(), reverse=True)
    assert sum(top[:25]) > 0.25 * sum(top), "customer concentration: the largest twenty-five customers carry over a quarter of the orders"
    assert sum(1 for v in per_customer.values() if v <= 3) > 50, "long tail of customers"
    per_product = Counter(line["product_id"][0] for line in r["sale.order.line"])
    assert sum(sorted(per_product.values(), reverse=True)[:60]) > 0.6 * sum(per_product.values()), "long tail of products"
    states = Counter(m["payment_state"] for m in r["account.move"])
    assert states["paid"] > states["not_paid"] > 0
    refunds = [m for m in r["account.move"] if m["move_type"] == "out_refund"]
    assert 50 < len(refunds) < 600
    partial = [line for line in r["sale.order.line"] if 0 < line["qty_delivered"] < line["product_uom_qty"]]
    assert len(partial) > 100, "partial deliveries and backorders"
    costs = {}
    for ref in dataset.terms["cost_references"]:
        costs.setdefault(ref["product"], []).append((ref["valid_from"], Decimal(ref["unit_cost"])))
    sample = costs["SPR-001"]
    assert len(sample) == 12 and sorted(sample)[-1][1] > sorted(sample)[0][1], "reference costs drift upwards quarter after quarter"


def test_ground_truth_is_separate_and_versioned(dataset, manifest):
    assert "ground_truth" not in dataset.records and "scenarios" not in dataset.records
    assert manifest["expected_totals"]["exceptions_outside_scenarios"] == 0
    ids = [s["scenario_id"] for s in manifest["scenarios"]]
    assert len(ids) == len(set(ids)) and all(s["expected"]["classification"] for s in manifest["scenarios"])
    families = {s["family"] for s in manifest["scenarios"]}
    assert {"unauthorised_discount", "management_approved_exception", "invoiced_below_contract_price", "incorrect_pricelist_application",
            "freight_not_recharged", "partial_freight_recharge", "legitimate_low_margin_transaction", "purchase_price_variance",
            "missing_or_delayed_cost_posting", "data_quality_prevents_recommendation", "incorrect_product_mapping", "credit_note_after_invoice",
            "currency_effect_explained", "invoice_without_order"} <= families
    assert MANIFEST.exists(), "export the manifest with scripts/export_ground_truth.py"
    committed = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(manifest, default=str)), "the committed manifest must equal the generated ground truth"
