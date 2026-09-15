"""Build dimensions, facts and bridges for one snapshot.

Grains:
- fact_sales_order_line: one ordered line (section and note lines excluded)
- fact_invoice_line: one posted customer invoice or credit note product line, signed
- fact_posted_cogs_line: one posted COGS item on a direct cost account
- fact_stock_move: one stock move with its Odoo valuation
- fact_cost_allocation: one slice of a delivery's quantity attributed to a receipt
- bridge_sale_invoice_line: one link between an order line and an invoice line

Facts are never summed through a bridge unless its allocation weight is known,
which prevents fan-out on many-to-many links.

Dates are UTC calendar dates of the Odoo datetime; company time zones are not
applied in this version.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine

from app.audit.log import append_event

MARTS_TABLES = (
    "fact_margin_period",
    "fact_margin_rule_evaluation",
    "reconciliation_result",
    "data_quality_issue",
    "bridge_sale_invoice_line",
    "fact_cost_allocation",
    "fact_stock_move",
    "fact_posted_cogs_line",
    "fact_invoice_line",
    "fact_sales_order_line",
    "dim_pricelist_item",
    "dim_pricelist",
    "dim_account",
    "dim_product",
    "dim_partner",
    "dim_uom",
    "fx_rate",
    "dim_currency",
    "dim_company",
)
REVENUE_MOVE_TYPES = ("out_invoice", "out_refund")
AMOUNT_TOLERANCE = Decimal("0.01")
# Recorded on every snapshot and reconciliation row. Bump when a transformation changes a computed figure.
TRANSFORMATION_VERSION = "marts.2026.09.2"


def D(value: Any) -> Decimal:
    return Decimal(str(value))


def m2o(value: Any) -> int | None:
    return int(value[0]) if isinstance(value, list) and value else None


def to_date(value: str | bool | None) -> date | None:
    return date.fromisoformat(value[:10]) if value else None


def quantize(value: Decimal, rounding: Decimal) -> Decimal:
    """Round to the currency rounding step (0.01 for EUR and USD)."""
    return value.quantize(rounding, rounding=ROUND_HALF_UP)


@dataclass
class SnapshotData:
    snapshot_id: uuid.UUID
    source_instance: str
    batch_seq: int
    records: dict[str, dict[int, dict[str, Any]]]

    def get(self, model: str, record_id: int | None) -> dict[str, Any] | None:
        return self.records.get(model, {}).get(record_id) if record_id is not None else None


def load_snapshot(conn: Connection, snapshot_id: uuid.UUID) -> SnapshotData:
    batch = conn.execute(
        sa.text("select source_instance, batch_seq, status, models from raw.ingestion_batch where batch_id = :b"),
        {"b": snapshot_id},
    ).first()
    if batch is None or batch.status != "SUCCEEDED":
        raise ValueError(f"snapshot {snapshot_id} is not a succeeded ingestion batch")
    records = {}
    for model in batch.models:
        rows = conn.execute(
            sa.text("select source_id, payload from staging.records_at(:i, :m, :s)"),
            {"i": batch.source_instance, "m": model, "s": batch.batch_seq},
        )
        records[model] = {row.source_id: row.payload for row in rows}
    return SnapshotData(snapshot_id, batch.source_instance, batch.batch_seq, records)


class _Builder:
    def __init__(self, data: SnapshotData):
        self.data = data
        self.s = data.snapshot_id
        self.rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.dates: set[date] = set()
        self.currency_by_id = {cid: c for cid, c in data.records.get("res.currency", {}).items()}

    def issue(self, code: str, model: str, source_id: int, detail: str) -> None:
        self.rows["data_quality_issue"].append(
            {"snapshot_id": self.s, "issue_code": code, "source_model": model, "source_id": source_id, "detail": detail}
        )

    def company_currency(self, company_id: int) -> tuple[str, Decimal]:
        company = self.data.get("res.company", company_id)
        currency = self.currency_by_id.get(m2o(company["currency_id"])) if company else None
        if currency is None:
            return "UNKNOWN", Decimal("0.01")
        return currency["name"], D(currency["rounding"])

    def rate(self, company_id: int, currency_id: int, on: date) -> tuple[Decimal, date] | None:
        candidates = [
            r
            for r in self.data.records.get("res.currency.rate", {}).values()
            if m2o(r["currency_id"]) == currency_id
            and m2o(r.get("company_id")) in (company_id, None)
            and to_date(r["name"]) <= on
        ]
        if not candidates:
            return None
        best = max(candidates, key=lambda r: (r["name"], m2o(r.get("company_id")) is not None))
        return D(best["rate"]), to_date(best["name"])

    # ------------------------------------------------------------------ dimensions
    def dimensions(self) -> None:
        d = self.data
        for cid, company in d.records.get("res.company", {}).items():
            self.rows["dim_company"].append(
                {
                    "snapshot_id": self.s,
                    "company_id": cid,
                    "name": company["name"],
                    "currency_code": self.company_currency(cid)[0],
                }
            )
        for cid, currency in d.records.get("res.currency", {}).items():
            self.rows["dim_currency"].append(
                {
                    "snapshot_id": self.s,
                    "currency_id": cid,
                    "code": currency["name"],
                    "rounding": D(currency["rounding"]),
                    "decimal_places": currency["decimal_places"],
                }
            )
        for rid, rate in d.records.get("res.currency.rate", {}).items():
            self.rows["fx_rate"].append(
                {
                    "snapshot_id": self.s,
                    "company_id": m2o(rate.get("company_id")) or 0,
                    "currency_id": m2o(rate["currency_id"]),
                    "rate_date": to_date(rate["name"]),
                    "rate": D(rate["rate"]),
                    "source_id": rid,
                }
            )
        for uid, uom in d.records.get("uom.uom", {}).items():
            self.rows["dim_uom"].append(
                {"snapshot_id": self.s, "uom_id": uid, "name": uom["name"], "factor": D(uom["factor"])}
            )
        for pid, partner in d.records.get("res.partner", {}).items():
            self.rows["dim_partner"].append(
                {
                    "snapshot_id": self.s,
                    "partner_id": pid,
                    "commercial_partner_id": m2o(partner.get("commercial_partner_id")) or pid,
                    "name": partner["name"],
                    "ref": partner.get("ref") or None,
                    "pricelist_id": m2o(partner.get("property_product_pricelist")),
                    "company_id": m2o(partner.get("company_id")),
                    "is_customer": (partner.get("customer_rank") or 0) > 0,
                    "is_supplier": (partner.get("supplier_rank") or 0) > 0,
                }
            )
        for pid, product in d.records.get("product.product", {}).items():
            template = d.get("product.template", m2o(product["product_tmpl_id"])) or {}
            category = d.get("product.category", m2o(template.get("categ_id"))) or {}
            self.rows["dim_product"].append(
                {
                    "snapshot_id": self.s,
                    "product_id": pid,
                    "template_id": m2o(product["product_tmpl_id"]),
                    "default_code": product.get("default_code") or None,
                    "name": template.get("name", f"product {pid}"),
                    "product_type": template.get("type", "unknown"),
                    "is_storable": template.get("is_storable"),
                    "category_id": m2o(template.get("categ_id")),
                    "cost_method": category.get("property_cost_method"),
                    "valuation": category.get("property_valuation"),
                    "uom_id": m2o(template.get("uom_id")),
                    "list_price": D(template["list_price"]) if template.get("list_price") is not None else None,
                }
            )
        for lid, pricelist in d.records.get("product.pricelist", {}).items():
            self.rows["dim_pricelist"].append(
                {
                    "snapshot_id": self.s,
                    "pricelist_id": lid,
                    "name": pricelist["name"],
                    "currency_code": self.currency_by_id.get(m2o(pricelist.get("currency_id")), {}).get("name", "UNKNOWN"),
                    "company_id": m2o(pricelist.get("company_id")),
                    "active": bool(pricelist.get("active", True)),
                }
            )
        for iid, item in d.records.get("product.pricelist.item", {}).items():
            self.rows["dim_pricelist_item"].append(
                {
                    "snapshot_id": self.s,
                    "item_id": iid,
                    "pricelist_id": m2o(item["pricelist_id"]),
                    "applied_on": item.get("applied_on") or "3_global",
                    "product_template_id": m2o(item.get("product_tmpl_id")),
                    "product_id": m2o(item.get("product_id")),
                    "category_id": m2o(item.get("categ_id")),
                    "min_quantity": D(item.get("min_quantity") or 0),
                    "compute_price": item.get("compute_price") or "fixed",
                    "fixed_price": D(item["fixed_price"]) if item.get("fixed_price") is not None else None,
                    "percent_price": D(item["percent_price"]) if item.get("percent_price") is not None else None,
                    "currency_code": self.currency_by_id.get(m2o(item.get("currency_id")), {}).get("name"),
                    "date_start": to_date(item.get("date_start")),
                    "date_end": to_date(item.get("date_end")),
                }
            )
        for aid, account in d.records.get("account.account", {}).items():
            self.rows["dim_account"].append(
                {
                    "snapshot_id": self.s,
                    "account_id": aid,
                    "code": account["code"],
                    "name": account["name"],
                    "account_type": account["account_type"],
                }
            )

    def product_uom_factor(self, product_id: int | None) -> Decimal | None:
        product = self.data.get("product.product", product_id)
        template = self.data.get("product.template", m2o(product["product_tmpl_id"])) if product else None
        uom = self.data.get("uom.uom", m2o(template.get("uom_id"))) if template else None
        return D(uom["factor"]) if uom else None

    def to_product_uom(self, qty: Decimal, uom_id: int | None, product_id: int | None) -> Decimal | None:
        uom = self.data.get("uom.uom", uom_id)
        product_factor = self.product_uom_factor(product_id)
        if uom is None or product_factor is None:
            return None
        return qty * D(uom["factor"]) / product_factor

    # ------------------------------------------------------------------ facts
    def sales_lines(self) -> None:
        d = self.data
        for lid, line in d.records.get("sale.order.line", {}).items():
            if line.get("display_type"):
                continue
            order = d.get("sale.order", m2o(line["order_id"]))
            if order is None:
                self.issue("ORDER_LINE_WITHOUT_ORDER", "sale.order.line", lid, "order missing from snapshot")
                continue
            company_id = m2o(line.get("company_id")) or m2o(order["company_id"])
            order_date = to_date(order["date_order"])
            self.dates.add(order_date)
            currency_id = m2o(order["currency_id"])
            currency_code = self.currency_by_id.get(currency_id, {}).get("name", "UNKNOWN")
            company_code, company_rounding = self.company_currency(company_id)
            subtotal = D(line["price_subtotal"])
            fx_rate = fx_date = subtotal_company = None
            if currency_code == company_code:
                subtotal_company = subtotal
            else:
                found = self.rate(company_id, currency_id, order_date)
                if found is None:
                    self.issue(
                        "FX_RATE_MISSING", "sale.order.line", lid, f"no {currency_code} rate on or before {order_date}"
                    )
                else:
                    fx_rate, fx_date = found
                    subtotal_company = quantize(subtotal / fx_rate, company_rounding)
            qty = D(line["product_uom_qty"])
            uom_id = m2o(line.get("product_uom_id"))
            qty_product_uom = self.to_product_uom(qty, uom_id, m2o(line.get("product_id")))
            if qty_product_uom is None and line.get("product_id"):
                self.issue("UOM_UNRESOLVED", "sale.order.line", lid, "unit of measure factor unavailable")
            self.rows["fact_sales_order_line"].append(
                {
                    "snapshot_id": self.s,
                    "sale_line_id": lid,
                    "sale_order_id": m2o(line["order_id"]),
                    "order_name": order["name"],
                    "company_id": company_id,
                    "customer_id": m2o(order["partner_id"]),
                    "product_id": m2o(line.get("product_id")),
                    "order_date": order_date,
                    "order_state": order["state"],
                    "currency_code": currency_code,
                    "pricelist_id": m2o(order.get("pricelist_id")),
                    "uom_id": uom_id,
                    "qty_ordered": qty,
                    "qty_ordered_product_uom": qty_product_uom,
                    "price_unit": D(line["price_unit"]),
                    "discount_pct": D(line["discount"]),
                    "subtotal": subtotal,
                    "subtotal_company_ccy": subtotal_company,
                    "fx_rate": fx_rate,
                    "fx_rate_date": fx_date,
                    "qty_delivered": D(line["qty_delivered"]),
                    "qty_invoiced": D(line["qty_invoiced"]),
                }
            )

    def invoice_lines(self) -> None:
        d = self.data
        accounts = d.records.get("account.account", {})
        links_per_sale_line: dict[int, int] = defaultdict(int)
        pending_links: list[tuple[int, list[int]]] = []
        for lid, line in d.records.get("account.move.line", {}).items():
            move = d.get("account.move", m2o(line["move_id"]))
            if move is None or move["state"] != "posted":
                continue
            accounting_date = to_date(line["date"])
            company_id = m2o(line["company_id"])
            if line["display_type"] == "cogs":
                account = accounts.get(m2o(line["account_id"]), {})
                if account.get("account_type") == "expense_direct_cost":
                    self.rows["fact_posted_cogs_line"].append(
                        {
                            "snapshot_id": self.s,
                            "move_line_id": lid,
                            "invoice_id": m2o(line["move_id"]),
                            "company_id": company_id,
                            "product_id": m2o(line.get("product_id")),
                            "account_id": m2o(line["account_id"]),
                            "accounting_date": accounting_date,
                            "balance": D(line["balance"]),
                        }
                    )
                continue
            if line["display_type"] != "product" or move["move_type"] not in REVENUE_MOVE_TYPES:
                continue
            self.dates.add(accounting_date)
            sign = Decimal(-1) if move["move_type"] == "out_refund" else Decimal(1)
            self.rows["fact_invoice_line"].append(
                {
                    "snapshot_id": self.s,
                    "invoice_line_id": lid,
                    "invoice_id": m2o(line["move_id"]),
                    "invoice_name": move["name"],
                    "move_type": move["move_type"],
                    "company_id": company_id,
                    "customer_id": m2o(move.get("partner_id")),
                    "product_id": m2o(line.get("product_id")),
                    "account_id": m2o(line["account_id"]),
                    "invoice_date": to_date(move.get("invoice_date")),
                    "accounting_date": accounting_date,
                    "currency_code": self.currency_by_id.get(m2o(line["currency_id"]), {}).get("name", "UNKNOWN"),
                    "uom_id": m2o(line.get("product_uom_id")),
                    "quantity_signed": sign * D(line["quantity"]),
                    "price_unit": D(line["price_unit"]),
                    "discount_pct": D(line["discount"]),
                    "subtotal_signed": sign * D(line["price_subtotal"]),
                    "revenue_company_ccy": -D(line["balance"]),
                    "reversed_entry_id": m2o(move.get("reversed_entry_id")),
                }
            )
            sale_lines = list(line.get("sale_line_ids") or [])
            if not sale_lines:
                self.issue(
                    "INVOICE_LINE_WITHOUT_SALE_LINE", "account.move.line", lid, f"{move['name']} has no order line link"
                )
            for sale_line in sale_lines:
                links_per_sale_line[sale_line] += 1
            pending_links.append((lid, sale_lines))

        for invoice_line_id, sale_lines in pending_links:
            per_invoice = len(sale_lines)
            for sale_line in sale_lines:
                per_order = links_per_sale_line[sale_line]
                cardinality = {(True, True): "1:1", (True, False): "1:N", (False, True): "N:1"}.get(
                    (per_invoice == 1, per_order == 1), "N:M"
                )
                self.rows["bridge_sale_invoice_line"].append(
                    {
                        "snapshot_id": self.s,
                        "sale_line_id": sale_line,
                        "invoice_line_id": invoice_line_id,
                        "link_cardinality": cardinality,
                        "allocation_weight": Decimal(1) if per_invoice == 1 else None,
                    }
                )

    def stock_moves_and_costs(self) -> None:
        d = self.data
        layers: dict[int, list[dict[str, Any]]] = defaultdict(list)
        outgoing: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for mid, move in sorted(d.records.get("stock.move", {}).items(), key=lambda kv: (kv[1]["date"], kv[0])):
            picking = d.get("stock.picking", m2o(move.get("picking_id")))
            direction = (picking or {}).get("picking_type_code") or "unknown"
            product_id = m2o(move["product_id"])
            qty = self.to_product_uom(D(move["quantity"]), m2o(move.get("uom_id")), product_id)
            if qty is None:
                self.issue("UOM_UNRESOLVED", "stock.move", mid, "unit of measure factor unavailable")
                qty = D(move["quantity"])
            value = D(move["value"]) if move.get("value") is not None else None
            row = {
                "snapshot_id": self.s,
                "move_id": mid,
                "direction": direction,
                "picking_id": m2o(move.get("picking_id")),
                "company_id": m2o(move["company_id"]),
                "product_id": product_id,
                "sale_line_id": m2o(move.get("sale_line_id")),
                "purchase_line_id": m2o(move.get("purchase_line_id")),
                "move_date": datetime.fromisoformat(move["date"]),
                "state": move["state"],
                "qty_product_uom": qty,
                "value_company_ccy": value,
            }
            self.rows["fact_stock_move"].append(row)
            if move["state"] != "done" or qty <= 0:
                continue
            if direction == "incoming" and value is not None and value != 0:
                layers[product_id].append({"move_id": mid, "remaining": qty, "unit_cost": abs(value) / qty})
            elif direction == "outgoing":
                outgoing[product_id].append(row)

        products = {r["product_id"]: r for r in self.rows["dim_product"]}
        for product_id, deliveries in outgoing.items():
            method = (products.get(product_id) or {}).get("cost_method")
            for delivery in deliveries:
                self._allocate(delivery, layers[product_id], method)

    def _allocate(self, delivery: dict[str, Any], layers: list[dict[str, Any]], method: str | None) -> None:
        base = {
            "snapshot_id": self.s,
            "delivery_move_id": delivery["move_id"],
            "company_id": delivery["company_id"],
            "product_id": delivery["product_id"],
            "sale_line_id": delivery["sale_line_id"],
            "method": "FIFO_REPLAY",
        }
        if method != "fifo":
            self.rows["fact_cost_allocation"].append(
                {
                    **base,
                    "receipt_move_id": None,
                    "allocation_no": 1,
                    "quantity": delivery["qty_product_uom"],
                    "unit_cost": None,
                    "amount": None,
                    "status": "UNDETERMINED",
                    "reason": f"cost method {method or 'unknown'} is not attributable to receipts in this version",
                }
            )
            return
        remaining = delivery["qty_product_uom"]
        slices = []
        for layer in layers:
            if remaining <= 0:
                break
            if layer["remaining"] <= 0:
                continue
            take = min(remaining, layer["remaining"])
            layer["remaining"] -= take
            remaining -= take
            slices.append(
                {
                    "receipt_move_id": layer["move_id"],
                    "quantity": take,
                    "unit_cost": layer["unit_cost"],
                    "amount": take * layer["unit_cost"],
                }
            )
        status, reason = "ATTRIBUTED", None
        if remaining > 0:
            status, reason = "UNDETERMINED", f"no valued receipt layer for {remaining} units"
        else:
            replayed = sum(s["amount"] for s in slices)
            recorded = delivery["value_company_ccy"]
            if recorded is None or abs(abs(recorded) - replayed) > AMOUNT_TOLERANCE:
                status, reason = (
                    "UNDETERMINED",
                    f"replayed FIFO cost {replayed} differs from Odoo move value {recorded}",
                )
        for number, piece in enumerate(slices, start=1):
            self.rows["fact_cost_allocation"].append(
                {**base, **piece, "allocation_no": number, "status": status, "reason": reason}
            )
        if remaining > 0:
            self.rows["fact_cost_allocation"].append(
                {
                    **base,
                    "receipt_move_id": None,
                    "allocation_no": len(slices) + 1,
                    "quantity": remaining,
                    "unit_cost": None,
                    "amount": None,
                    "status": "UNDETERMINED",
                    "reason": reason,
                }
            )


def build_marts(engine: Engine, snapshot_id: uuid.UUID, *, actor: str = "service:marts") -> dict[str, int]:
    with engine.begin() as conn:
        data = load_snapshot(conn, snapshot_id)
        builder = _Builder(data)
        builder.dimensions()
        builder.sales_lines()
        builder.invoice_lines()
        builder.stock_moves_and_costs()
        from app.marts.project_build import PROJECT_TABLES, build_project_facts

        build_project_facts(builder)

        # Table and column names below come from MARTS_TABLES and the builder, never from input.
        for table in (*PROJECT_TABLES, *MARTS_TABLES):
            conn.execute(sa.text(f"delete from marts.{table} where snapshot_id = :s"), {"s": snapshot_id})  # noqa: S608
        conn.execute(
            sa.text(
                "insert into marts.snapshot (snapshot_id, source_instance, batch_seq, transformation_version)"
                " values (:s, :i, :q, :v) on conflict (snapshot_id) do update set built_at = now(),"
                " transformation_version = excluded.transformation_version"
            ),
            {"s": snapshot_id, "i": data.source_instance, "q": data.batch_seq, "v": TRANSFORMATION_VERSION},
        )
        if builder.dates:
            first, last = min(builder.dates), max(builder.dates)
            days = [first + timedelta(days=n) for n in range((last - first).days + 1)]
            conn.execute(
                sa.text(
                    "insert into marts.dim_date (date_day, year, quarter, month, iso_week, period)"
                    " values (:d, :y, :q, :m, :w, :p) on conflict (date_day) do nothing"
                ),
                [
                    {
                        "d": day,
                        "y": day.year,
                        "q": (day.month - 1) // 3 + 1,
                        "m": day.month,
                        "w": day.isocalendar()[1],
                        "p": f"{day.year}-{day.month:02d}",
                    }
                    for day in days
                ],
            )
        stats = {}
        for table in (*reversed(MARTS_TABLES), *reversed(PROJECT_TABLES)):
            rows = builder.rows.get(table, [])
            stats[table] = len(rows)
            if rows:
                columns = list(rows[0])
                conn.execute(
                    sa.text(
                        f"insert into marts.{table} ({', '.join(columns)}) values ({', '.join(':' + c for c in columns)})"  # noqa: S608
                    ),
                    rows,
                )
        conn.execute(
            sa.text("update marts.snapshot set stats = cast(:st as jsonb) where snapshot_id = :s"),
            {"st": json.dumps(stats), "s": snapshot_id},
        )
        append_event(
            conn,
            actor=actor,
            action="marts.snapshot_built",
            object_type="snapshot",
            object_id=str(snapshot_id),
            run_id=str(snapshot_id),
            payload={
                "source_instance": data.source_instance,
                "row_counts": stats,
                "transformation_version": TRANSFORMATION_VERSION,
            },
        )
    return stats
