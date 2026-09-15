"""The analytical foundation must realise every fact stated by the hand-written oracle.

Exposure amounts are asserted from S4 onward, when the exception engine exists.
Here the oracle checks the governed facts those rules will read.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa

from app.audit.log import verify_chain
from app.fixtures.demo_dataset import build_demo_dataset
from app.ingestion.runner import FOUNDATION_MODELS, ingest
from app.ingestion.sources import FixtureSource
from app.marts.build import build_marts
from app.marts.reconcile import margin_basis, reconcile
from app.ops.discover_odoo import load_spec
from tests.oracle import case, dec, load_oracle


@pytest.fixture(scope="module")
def oracle():
    return load_oracle()


@pytest.fixture(scope="module")
def built(engine):
    dataset = build_demo_dataset()
    source = FixtureSource(dataset, source_instance=f"fixture_oracle_{uuid.uuid4().hex[:8]}")
    batch = ingest(engine, source, load_spec(), models=FOUNDATION_MODELS)
    stats = build_marts(engine, batch.batch_id)
    results = reconcile(engine, source, batch.batch_id)
    return {"snapshot": batch.batch_id, "stats": stats, "reconciliation": results, "source": source, "engine": engine}


def q(built, sql: str, **params):
    with built["engine"].connect() as c:
        return c.execute(sa.text(sql), {"s": built["snapshot"], **params}).mappings().all()


def one(built, sql: str, **params):
    rows = q(built, sql, **params)
    assert len(rows) == 1, rows
    return rows[0]


def sale_line(built, order: str, product: str):
    return one(
        built,
        "select f.* from marts.fact_sales_order_line f join marts.dim_product p"
        " on p.snapshot_id = f.snapshot_id and p.product_id = f.product_id"
        " where f.snapshot_id = :s and f.order_name = :o and p.default_code = :p",
        o=order,
        p=product,
    )


def invoiced_subtotal(built, sale_line_id: int, move_type: str | None = None) -> Decimal:
    rows = q(
        built,
        "select coalesce(sum(i.subtotal_signed * b.allocation_weight), 0) as total from marts.bridge_sale_invoice_line b"
        " join marts.fact_invoice_line i on i.snapshot_id = b.snapshot_id and i.invoice_line_id = b.invoice_line_id"
        " where b.snapshot_id = :s and b.sale_line_id = :l and (cast(:t as text) is null or i.move_type = :t)",
        l=sale_line_id,
        t=move_type,
    )
    return rows[0]["total"]


def allocations(built, sale_line_id: int):
    return q(
        built, "select * from marts.fact_cost_allocation where snapshot_id = :s and sale_line_id = :l", l=sale_line_id
    )


def test_structure(built, oracle):
    structure = oracle["structure"]
    orders = q(
        built,
        "select order_state, count(distinct sale_order_id) as n from marts.fact_sales_order_line"
        " where snapshot_id = :s group by order_state",
    )
    assert {r["order_state"]: r["n"] for r in orders} == structure["sale_orders_by_state"]
    assert (
        one(built, "select count(*) as n from marts.dim_customer where snapshot_id = :s")["n"] == structure["customers"]
    )
    assert (
        one(built, "select count(*) as n from marts.dim_supplier where snapshot_id = :s")["n"] == structure["suppliers"]
    )
    assert (
        one(built, "select count(*) as n from marts.dim_product where snapshot_id = :s and is_storable")["n"]
        == structure["storable_products"]
    )
    unlinked = q(
        built,
        "select distinct i.invoice_name from marts.data_quality_issue d join marts.fact_invoice_line i"
        " on i.snapshot_id = d.snapshot_id and i.invoice_line_id = d.source_id"
        " where d.snapshot_id = :s and d.issue_code = 'INVOICE_LINE_WITHOUT_SALE_LINE'",
    )
    assert len(unlinked) == structure["invoices_without_sale_order"]


def test_disc_001_facts(built, oracle):
    facts = case(oracle, "DISC-001")["facts"]
    line = sale_line(built, "BD/SO/DISC-001", "SC1")
    assert str(line["order_date"]) == facts["order_date"]
    assert line["qty_ordered"] == dec(facts["quantity"])
    assert line["price_unit"] == dec(facts["price_unit"])
    assert line["discount_pct"] == dec(facts["discount_pct"])
    assert line["subtotal"] == dec(facts["line_subtotal"])
    assert line["qty_delivered"] == dec(facts["qty_delivered"])
    assert line["qty_invoiced"] == dec(facts["qty_invoiced"])
    assert invoiced_subtotal(built, line["sale_line_id"]) == dec(facts["invoiced_subtotal"])


def test_freight_001_facts(built, oracle):
    facts = case(oracle, "FREIGHT-001")["facts"]
    goods = sale_line(built, "BD/SO/FREIGHT-001", "SC2")
    assert goods["qty_ordered"] == dec(facts["goods_quantity"])
    assert goods["qty_delivered"] == dec(facts["goods_delivered"])
    assert goods["qty_invoiced"] == dec(facts["goods_invoiced"])
    freight_on_order = q(
        built,
        "select 1 from marts.fact_sales_order_line f join marts.dim_product p on p.snapshot_id ="
        " f.snapshot_id and p.product_id = f.product_id where f.snapshot_id = :s and f.order_name ="
        " 'BD/SO/FREIGHT-001' and p.default_code = 'FRT'",
    )
    assert len(freight_on_order) == facts["freight_lines_on_order"]
    invoice_ids = q(
        built,
        "select distinct i.invoice_id from marts.bridge_sale_invoice_line b join marts.fact_invoice_line i"
        " on i.snapshot_id = b.snapshot_id and i.invoice_line_id = b.invoice_line_id"
        " where b.snapshot_id = :s and b.sale_line_id = :l",
        l=goods["sale_line_id"],
    )
    freight_on_invoices = q(
        built,
        "select 1 from marts.fact_invoice_line i join marts.dim_product p on p.snapshot_id ="
        " i.snapshot_id and p.product_id = i.product_id where i.snapshot_id = :s and"
        " i.invoice_id = any(:ids) and p.default_code = 'FRT'",
        ids=[r["invoice_id"] for r in invoice_ids],
    )
    assert len(freight_on_invoices) == facts["freight_lines_on_invoices"]


def test_cost_001_facts(built, oracle):
    facts = case(oracle, "COST-001")["facts"]
    line = sale_line(built, "BD/SO/COST-001", "SC3")
    assert line["qty_ordered"] == dec(facts["quantity_sold"])
    assert line["qty_delivered"] == dec(facts["quantity_delivered"])
    slices = allocations(built, line["sale_line_id"])
    assert {s["status"] for s in slices} == {"ATTRIBUTED"}
    assert all(s["receipt_move_id"] is not None for s in slices), "cost must trace back to a receipt"
    assert sum(s["amount"] for s in slices) == dec(facts["delivery_move_value"])
    assert {s["unit_cost"] for s in slices} == {dec(facts["receipt_unit_cost"])}
    move_value = one(
        built,
        "select value_company_ccy from marts.fact_stock_move where snapshot_id = :s and sale_line_id = :l",
        l=line["sale_line_id"],
    )["value_company_ccy"]
    assert move_value == dec(facts["delivery_move_value"])
    assert invoiced_subtotal(built, line["sale_line_id"]) == dec(facts["invoiced_revenue"])
    cogs = one(
        built,
        "select sum(c.balance) as total from marts.fact_posted_cogs_line c join marts.dim_product p"
        " on p.snapshot_id = c.snapshot_id and p.product_id = c.product_id"
        " where c.snapshot_id = :s and p.default_code = 'SC3'",
    )["total"]
    assert cogs == dec(facts["posted_cogs"])


def test_neg_03_partial_delivery_and_invoicing(built, oracle):
    facts = case(oracle, "NEG-03")["facts"]
    line = sale_line(built, "BD/SO/NEG-03", "P01")
    assert (line["qty_ordered"], line["qty_delivered"], line["qty_invoiced"]) == (
        dec(facts["quantity"]),
        dec(facts["qty_delivered"]),
        dec(facts["qty_invoiced"]),
    )
    assert invoiced_subtotal(built, line["sale_line_id"]) == dec(facts["invoiced_subtotal"])


def test_neg_04_credit_note_is_signed_and_linked(built, oracle):
    facts = case(oracle, "NEG-04")["facts"]
    line = sale_line(built, "BD/SO/NEG-04", "P04")
    assert invoiced_subtotal(built, line["sale_line_id"], "out_invoice") == dec(facts["invoiced_subtotal"])
    assert invoiced_subtotal(built, line["sale_line_id"], "out_refund") == -dec(facts["refunded_subtotal"])
    assert invoiced_subtotal(built, line["sale_line_id"]) == dec(facts["net_revenue"])
    refund = one(
        built,
        "select i.quantity_signed, i.reversed_entry_id from marts.fact_invoice_line i join"
        " marts.bridge_sale_invoice_line b on b.snapshot_id = i.snapshot_id and b.invoice_line_id ="
        " i.invoice_line_id where i.snapshot_id = :s and b.sale_line_id = :l and i.move_type = 'out_refund'",
        l=line["sale_line_id"],
    )
    assert refund["quantity_signed"] == -dec(facts["refunded_quantity"])
    assert refund["reversed_entry_id"] is not None
    links = q(
        built,
        "select link_cardinality from marts.bridge_sale_invoice_line where snapshot_id = :s and sale_line_id = :l",
        l=line["sale_line_id"],
    )
    assert {r["link_cardinality"] for r in links} == {"1:N"}


def test_neg_05_cancelled_order_has_no_revenue(built, oracle):
    facts = case(oracle, "NEG-05")["facts"]
    line = sale_line(built, "BD/SO/NEG-05", "P08")
    assert line["order_state"] == facts["state"]
    assert invoiced_subtotal(built, line["sale_line_id"]) == Decimal(0)
    assert not q(
        built,
        "select 1 from marts.fact_stock_move where snapshot_id = :s and sale_line_id = :l",
        l=line["sale_line_id"],
    )


def test_neg_06_unit_of_measure_is_converted(built, oracle):
    facts = case(oracle, "NEG-06")["facts"]
    line = sale_line(built, "BD/SO/NEG-06", "P05")
    assert line["qty_ordered"] == dec(facts["quantity"])
    assert line["qty_ordered_product_uom"] == dec(facts["quantity_in_units"])
    assert line["subtotal"] == dec(facts["line_subtotal"])
    delivered = one(
        built,
        "select qty_product_uom from marts.fact_stock_move where snapshot_id = :s and sale_line_id = :l",
        l=line["sale_line_id"],
    )
    assert delivered["qty_product_uom"] == dec(facts["delivered_units"])
    assert line["price_unit"] * line["qty_ordered"] / line["qty_ordered_product_uom"] == dec(
        facts["list_price_per_unit"]
    )


def test_neg_07_foreign_currency_uses_the_dated_rate(built, oracle):
    facts = case(oracle, "NEG-07")["facts"]
    line = sale_line(built, "BD/SO/NEG-07", "P06")
    assert line["currency_code"] == facts["currency"]
    assert line["subtotal"] == dec(facts["line_subtotal_usd"])
    assert str(line["fx_rate_date"]) == facts["rate_date"]
    assert line["fx_rate"] == dec(facts["rate_usd_per_eur"])
    invoice = one(
        built,
        "select i.revenue_company_ccy, i.invoice_date from marts.fact_invoice_line i join"
        " marts.bridge_sale_invoice_line b on b.snapshot_id = i.snapshot_id and b.invoice_line_id ="
        " i.invoice_line_id where i.snapshot_id = :s and b.sale_line_id = :l",
        l=line["sale_line_id"],
    )
    assert invoice["revenue_company_ccy"] == dec(facts["revenue_eur"])
    assert str(invoice["invoice_date"]) == facts["invoice_date"]


def test_neg_08_missing_cost_is_undetermined_not_zero(built, oracle):
    facts = case(oracle, "NEG-08")["facts"]
    line = sale_line(built, "BD/SO/NEG-08", "SC4")
    slices = allocations(built, line["sale_line_id"])
    assert [s["status"] for s in slices] == ["UNDETERMINED"]
    assert slices[0]["amount"] is None and slices[0]["receipt_move_id"] is None
    assert slices[0]["quantity"] == dec(facts["quantity_delivered"])
    cogs = q(
        built,
        "select 1 from marts.fact_posted_cogs_line c join marts.dim_product p on p.snapshot_id = c.snapshot_id"
        " and p.product_id = c.product_id where c.snapshot_id = :s and p.default_code = 'SC4'",
    )
    assert len(cogs) == facts["posted_cogs_lines"]


def test_neg_12_same_line_carries_price_and_cost_facts(built, oracle):
    facts = case(oracle, "NEG-12")["facts"]
    line = sale_line(built, "BD/SO/NEG-12", "SC5")
    assert line["subtotal"] == dec(facts["line_subtotal"])
    assert line["discount_pct"] == dec(facts["discount_pct"])
    slices = allocations(built, line["sale_line_id"])
    assert sum(s["amount"] for s in slices) == dec(facts["delivery_move_value"])


def test_only_the_missing_cost_case_is_undetermined(built):
    undetermined = q(
        built,
        "select distinct p.default_code from marts.fact_cost_allocation a join marts.dim_product p"
        " on p.snapshot_id = a.snapshot_id and p.product_id = a.product_id"
        " where a.snapshot_id = :s and a.status = 'UNDETERMINED'",
    )
    assert [r["default_code"] for r in undetermined] == ["SC4"]
    issues = q(
        built, "select issue_code, count(*) as n from marts.data_quality_issue where snapshot_id = :s group by 1"
    )
    assert {r["issue_code"]: r["n"] for r in issues} == {"INVOICE_LINE_WITHOUT_SALE_LINE": 1}


def test_bridge_prevents_fan_out(built):
    totals = one(
        built,
        "select (select sum(revenue_company_ccy) from marts.fact_invoice_line where snapshot_id = :s) as facts,"
        " (select sum(i.revenue_company_ccy) from marts.fact_invoice_line i where i.snapshot_id = :s and exists"
        "   (select 1 from marts.bridge_sale_invoice_line b where b.snapshot_id = i.snapshot_id and b.invoice_line_id = i.invoice_line_id))"
        "  + (select coalesce(sum(i.revenue_company_ccy), 0) from marts.fact_invoice_line i where i.snapshot_id = :s and not exists"
        "   (select 1 from marts.bridge_sale_invoice_line b where b.snapshot_id = i.snapshot_id and b.invoice_line_id = i.invoice_line_id))"
        "  as partitioned,"
        " (select count(*) from marts.bridge_sale_invoice_line where snapshot_id = :s and allocation_weight is null) as unresolved",
    )
    assert totals["facts"] == totals["partitioned"]
    assert totals["unresolved"] == 0


def test_reconciliation_statuses_are_explicit(built):
    results = built["reconciliation"]
    assert results, "every month with activity is reconciled"
    assert {r.status for r in results} == {"RECONCILED"}
    assert {r.independence for r in results} == {"FIXTURE_CONTROL_TOTAL"}
    assert margin_basis(built["engine"], built["snapshot"]) == "RECONCILED_COGS"


def test_reconciliation_detects_a_divergent_source(built):
    source = built["source"]
    line = next(r for r in source.dataset.records["account.move.line"] if r["display_type"] == "product")
    original = line["balance"]
    line["balance"] = original - 100.0
    try:
        results = reconcile(built["engine"], source, built["snapshot"])
        broken = [r for r in results if r.check_id == "REVENUE_POSTED" and r.status == "UNRECONCILED"]
        assert len(broken) == 1 and broken[0].actual - broken[0].expected == Decimal("-100.00")
    finally:
        line["balance"] = original
        reconcile(built["engine"], source, built["snapshot"])


def test_rebuild_is_idempotent_and_audited(built):
    again = build_marts(built["engine"], built["snapshot"])
    assert again == built["stats"]
    reconcile(built["engine"], built["source"], built["snapshot"])
    with built["engine"].connect() as c:
        assert verify_chain(c).valid
