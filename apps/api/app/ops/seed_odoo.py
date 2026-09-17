"""Odoo seed of the trading company (dataset `demo_v1`): plan, dry run and guarded executor.

The plan maps the deterministic demo dataset to Odoo business operations in order, with stable external identifiers
under the `benacta_demo` module so a replay skips what already exists. The dry run reads Odoo and writes nothing:
it reports the write guard, the prerequisites, the instance facts the executor relies on and what it would create.

With `--confirm` and a passing write guard the executor drives Odoo's own workflows (confirm orders, validate
pickings, invoice from the orders, reverse through the credit-note wizard, post) so that valuation, cost of goods
sold and links between documents are Odoo's, not ours. Documents keep their fixture names (`BD/SO/...`, `BD/PO/...`)
and are dated as in the dataset; Odoo stamps validation and posting times itself. Two shared settings change on the
owner's decision, recorded in the report: anglo-saxon accounting on the sandbox company (cost of goods sold posted
with the invoice, which the margin reconciliation needs) and the unit of measure "Dozens" (one scenario).
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from app.config import REPO_ROOT, Settings
from app.connectors.guards import GuardReport, odoo_write_guard
from app.connectors.odoo import OdooJson2Client, OdooReader, OdooWriter
from app.fixtures.demo_dataset import COMPANY, FixtureDataset, build_demo_dataset
from app.margin.reference import REGISTER_PATH
from app.ops.odoo_seed_base import XMLID_MODULE, OdooSeeder, batched, m2o_id, print_report

REQUIRED_MODULES = ("sale_management", "sale_stock", "purchase_stock", "stock_account", "account_accountant")
PLAN_DIR = REPO_ROOT / ".benacta" / "seed_plans"
WRITE_TIMEOUT_SECONDS = 300.0

# Order matters: each step only references objects created by earlier steps.
OPERATIONS: tuple[tuple[str, str], ...] = (
    ("res.company", "use the sandbox company; switch it to anglo-saxon accounting when it is not (cost of goods sold at invoicing)"),
    ("res.currency.rate", "create company-specific USD rates (requires USD active)"),
    ("product.category", "create categories; FIFO and automated valuation on the goods category"),
    ("res.partner", "create customers and suppliers with non-deliverable addresses"),
    ("product.template", "create storable goods and the freight service"),
    ("purchase.order", "create, button_confirm, then validate receipts with the planned quantities"),
    ("sale.order", "create; action_confirm confirmed orders, action_cancel cancelled ones, keep drafts"),
    ("stock.picking", "validate deliveries with delivered quantities (partial where planned)"),
    (
        "account.move",
        "invoice through the sale order, post; reverse via the credit note wizard; post the unlinked invoice",
    ),
)
MAIL_SAFE_CONTEXT = {
    "tracking_disable": True,
    "mail_create_nolog": True,
    "mail_notrack": True,
    "mail_auto_subscribe_no_notify": True,
}


@dataclass
class SeedPlan:
    generated_at: str
    target: str | None
    company: str | None
    guard: list[dict[str, Any]]
    prerequisites: list[dict[str, Any]]
    operations: list[dict[str, Any]]
    already_seeded: dict[str, int]
    risks: list[str] = field(default_factory=list)


@dataclass
class InstanceFacts:
    """What the executor needs from the instance, read once. `missing` lists what blocks a confirmed run."""

    company: int | None = None
    anglo_saxon: bool | None = None
    currency: dict[str, int] = field(default_factory=dict)
    units: int | None = None
    units_category: int | None = None
    dozens: int | None = None
    uom_relative: bool = False  # Odoo 19 units (relative factor to a reference unit) instead of unit categories
    sale_tax: int | None = None
    warehouse: dict[str, Any] | None = None
    category_fields: dict[str, dict[str, Any]] = field(default_factory=dict)
    stock_accounts: dict[str, int] = field(default_factory=dict)
    line_uom_field: dict[str, str] = field(default_factory=dict)
    template_fields: set[str] = field(default_factory=set)
    missing: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _fields(reader: OdooReader, model: str, attributes: list[str]) -> dict[str, dict[str, Any]]:
    try:
        described = reader.fields_get(model, attributes)
    except Exception as error:  # noqa: BLE001 - a model absent from the instance is a fact, not a crash
        return {"__error__": {"error": str(error)}}
    return described if isinstance(described, dict) else {}


def read_facts(reader: OdooReader, settings: Settings) -> InstanceFacts:
    """Read-only inventory of the sandbox company: references, units, tax, warehouse, valuation fields."""
    f = InstanceFacts()
    company_name = settings.odoo_sandbox_company or COMPANY[1]

    def first(model: str, domain: list, fields: list[str], context: dict[str, Any] | None = None) -> dict[str, Any] | None:
        rows = reader.search_read(model, domain, fields, limit=1, context=context)
        return rows[0] if rows else None

    company = first("res.company", [["name", "=", company_name]], ["id", "anglo_saxon_accounting"])
    if company is None:
        f.missing.append(f"company {company_name}")
        return f
    f.company = company["id"]
    f.anglo_saxon = bool(company.get("anglo_saxon_accounting"))
    for code in ("EUR", "USD"):
        row = first("res.currency", [["name", "=", code]], ["id", "name", "active"], context={"active_test": False})
        if row is None or not row.get("active", True):
            f.missing.append(f"currency {code} active")
        else:
            f.currency[code] = row["id"]
    uom_fields = _fields(reader, "uom.uom", ["type"])
    f.uom_relative = "relative_factor" in uom_fields
    units = first("uom.uom", [["name", "in", ["Units", "Unit"]]], ["id"] + ([] if f.uom_relative else ["category_id"]))
    if units is None:
        f.missing.append("unit of measure Units")
    else:
        f.units, f.units_category = units["id"], m2o_id(units.get("category_id"))
    dozens = first("uom.uom", [["name", "=", "Dozens"]], ["id"])
    f.dozens = dozens["id"] if dozens else None
    tax = first("account.tax", [["type_tax_use", "=", "sale"], ["amount", "=", 20.0], ["company_id", "=", f.company]], ["id"])
    f.sale_tax = tax["id"] if tax else None
    if tax is None:
        f.notes.append("no 20 % sale tax on the company: invoices will carry no VAT")
    f.warehouse = first("stock.warehouse", [["company_id", "=", f.company]], ["id", "lot_stock_id", "in_type_id", "out_type_id"])
    if f.warehouse is None:
        f.missing.append("warehouse of the company")
    f.category_fields = {k: v for k, v in _fields(reader, "product.category", ["type", "selection"]).items() if k.startswith("property_")}
    # Odoo 19 keeps the valuation account and journal on the category; older versions also carried input and output accounts.
    account_fields = [name for name in ("property_stock_valuation_account_id", "property_stock_account_input_categ_id",
                                        "property_stock_account_output_categ_id", "property_stock_journal") if name in f.category_fields]
    if "property_stock_valuation_account_id" in account_fields:
        template = first("product.category", [["property_stock_valuation_account_id", "!=", False]], account_fields)
        if template:
            f.stock_accounts = {k: m2o_id(v) for k, v in template.items() if k in account_fields and m2o_id(v)}
        else:
            prefixes = {"property_stock_valuation_account_id": ("37", "35", "3"), "property_stock_account_input_categ_id": ("6037", "603"),
                        "property_stock_account_output_categ_id": ("6037", "603")}
            for name in account_fields:
                for prefix in prefixes.get(name, ()):
                    account = first("account.account", [["code", "=like", f"{prefix}%"]], ["id"])
                    if account:
                        f.stock_accounts[name] = account["id"]
                        break
            journal = first("account.journal", [["type", "=", "general"], ["company_id", "=", f.company]], ["id"])
            if journal and "property_stock_journal" in account_fields:
                f.stock_accounts["property_stock_journal"] = journal["id"]
    for model in ("sale.order.line", "purchase.order.line"):
        described = _fields(reader, model, ["type"])
        f.line_uom_field[model] = "product_uom_id" if "product_uom_id" in described or not described else "product_uom"
    f.template_fields = set(_fields(reader, "product.template", ["type"]))
    return f


def _prerequisites(reader: OdooReader, settings: Settings) -> tuple[list[dict[str, Any]], bool | None]:
    checks: list[dict[str, Any]] = []
    installed = {
        row["name"]
        for row in reader.search_read(
            "ir.module.module", [["name", "in", list(REQUIRED_MODULES)], ["state", "=", "installed"]], ["name"]
        )
    }
    for module in REQUIRED_MODULES:
        checks.append({"check": f"module {module} installed", "ok": module in installed, "decision_needed": False})

    company_exists = None
    if settings.odoo_sandbox_company:
        companies = reader.search_read(
            "res.company", [["name", "=", settings.odoo_sandbox_company]], ["name", "account_peppol_proxy_state"]
        )
        company_exists = bool(companies)
        checks.append(
            {
                "check": f"sandbox company '{settings.odoo_sandbox_company}' exists",
                "ok": company_exists,
                "decision_needed": not company_exists,
            }
        )
        if companies:
            state = companies[0].get("account_peppol_proxy_state")
            checks.append(
                {
                    "check": "sandbox company not registered for e-invoicing",
                    "ok": state in (None, False, "not_registered"),
                    "decision_needed": False,
                    "observed": state,
                }
            )
    else:
        checks.append({"check": "ODOO_SANDBOX_COMPANY configured", "ok": False, "decision_needed": True})

    usd = reader.search_read("res.currency", [["name", "=", "USD"]], ["active"], context={"active_test": False})
    checks.append(
        {
            "check": "USD currency active (global setting)",
            "ok": bool(usd and usd[0]["active"]),
            "decision_needed": not (usd and usd[0]["active"]),
            "note": "activating a currency changes shared configuration; otherwise NEG-07 stays fixture-only",
        }
    )
    dozens = reader.search_read("uom.uom", [["name", "=", "Dozens"]], ["id"])
    checks.append(
        {
            "check": "unit of measure 'Dozens' exists (global setting)",
            "ok": bool(dozens),
            "decision_needed": not dozens,
            "note": "creating a unit changes shared configuration; the executor creates it on the owner's decision (NEG-06)",
        }
    )
    return checks, company_exists


def build_plan(reader: OdooReader, settings: Settings) -> SeedPlan:
    dataset = build_demo_dataset()
    prerequisites, company_exists = _prerequisites(reader, settings)
    guard: GuardReport = odoo_write_guard(settings, sandbox_company_exists=company_exists)

    existing = Counter(
        row["model"] for row in reader.search_read("ir.model.data", [["module", "=", XMLID_MODULE]], ["model"])
    )
    counts = {model: len(rows) for model, rows in dataset.records.items()}
    orders = Counter(o["state"] for o in dataset.records["sale.order"])
    moves = Counter(m["move_type"] for m in dataset.records["account.move"])
    pickings = Counter(p["picking_type_code"] for p in dataset.records["stock.picking"])
    planned = {
        "res.company": 1,
        "res.currency.rate": counts["res.currency.rate"],
        "product.category": counts["product.category"],
        "res.partner": counts["res.partner"],
        "product.template": counts["product.template"],
        "purchase.order": counts["purchase.order"],
        "sale.order": counts["sale.order"],
        "stock.picking": pickings["outgoing"],
        "account.move": counts["account.move"],
    }
    details = {
        "sale.order": dict(orders),
        "account.move": dict(moves),
        "stock.picking": {"receipts": pickings["incoming"], "deliveries": pickings["outgoing"]},
    }
    operations = [
        {
            "step": n,
            "model": model,
            "operation": text,
            "objects": planned[model],
            "already_seeded": existing.get(model, 0),
            "to_create": max(planned[model] - existing.get(model, 0), 0),
            **({"detail": details[model]} if model in details else {}),
        }
        for n, (model, text) in enumerate(OPERATIONS, start=1)
    ]
    return SeedPlan(
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        target=settings.odoo_target,
        company=settings.odoo_sandbox_company or COMPANY[1],
        guard=[{"check": c.name, "passed": c.passed, "detail": c.detail} for c in guard.checks],
        prerequisites=prerequisites,
        operations=operations,
        already_seeded=dict(existing),
        risks=[
            "Stock validation dates: Odoo stamps validation time; the executor writes the dataset dates on pickings and moves afterwards.",
            "Perpetual valuation posts COGS at invoicing with anglo-saxon accounting; the value sign on outgoing moves is verified on the first run.",
            "Invoices created through sale orders link lines through sale_order_line_invoice_rel; the unlinked invoice is created directly.",
            f"Every write uses context {sorted(MAIL_SAFE_CONTEXT)} and partners use .invalid addresses.",
        ],
    )


def write_plan(plan: SeedPlan) -> Path:
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    path = PLAN_DIR / f"seed_plan_{plan.generated_at.replace(':', '').replace('+0000', 'Z')}.json"
    path.write_text(json.dumps(plan.__dict__, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def print_plan(plan: SeedPlan) -> None:
    print(f"Seed plan for {plan.target} / company '{plan.company}' (dry run, nothing written)")
    print("\nWrite guard")
    for check in plan.guard:
        print(f"  [{'x' if check['passed'] else ' '}] {check['check']}: {check['detail']}")
    print("\nPrerequisites")
    for check in plan.prerequisites:
        flag = "ok" if check["ok"] else ("DECISION NEEDED" if check["decision_needed"] else "missing")
        print(
            f"  {flag:15} {check['check']}" + (f" ({check['note']})" if not check["ok"] and check.get("note") else "")
        )
    print("\nOperations")
    for op in plan.operations:
        print(
            f"  {op['step']}. {op['model']:18} create {op['to_create']:4} (seeded {op['already_seeded']}): {op['operation']}"
        )
    print("\nRisks to confirm on the first sandbox run")
    for risk in plan.risks:
        print(f"  - {risk}")


def print_facts(facts: InstanceFacts) -> None:
    print("\nInstance facts")
    print(f"  company id {facts.company}, anglo-saxon accounting {facts.anglo_saxon}, currencies {facts.currency}")
    print(f"  units {facts.units} ({'relative units' if facts.uom_relative else 'unit categories'}), dozens {facts.dozens}, sale tax {facts.sale_tax}")
    print(f"  warehouse {facts.warehouse}")
    print(f"  category valuation fields {sorted(facts.category_fields)}; stock accounts {facts.stock_accounts}")
    for note in facts.notes:
        print(f"  note: {note}")
    for item in facts.missing:
        print(f"  MISSING {item}")


# --------------------------------------------------------------------------- executor
class TradingSeeder(OdooSeeder):
    """Writes the trading company through Odoo's own workflows. Dry run when no writer is given."""

    def __init__(self, reader: OdooReader, writer: OdooWriter | None, company_name: str, facts: InstanceFacts,
                 dataset: FixtureDataset | None = None):
        super().__init__(reader, writer, company_name, dataset or build_demo_dataset())
        self.f = facts
        self.tax = [[6, 0, [facts.sale_tax]]] if facts.sale_tax else [[6, 0, []]]
        self.usd_pricelist: int | None = None
        self.orders_by_name = {o["name"]: o for o in self.ds.records["sale.order"]}

    # ------------------------------------------------------------------ reference and configuration
    def reference(self) -> None:
        self.company = self.f.company or 0
        self.ids["res.company"][1] = self.company
        for fixture_id, code in self.ds.keys["res.currency"].items():
            if code in self.f.currency:
                self.ids["res.currency"][fixture_id] = self.f.currency[code]
        for fixture_id, key in self.ds.keys["uom.uom"].items():
            unit = self.f.units if key == "units" else self.f.dozens
            if unit:
                self.ids["uom.uom"][fixture_id] = unit

    def configuration(self) -> None:
        if self.f.anglo_saxon is False:
            self.report.configuration.append("anglo-saxon accounting on the sandbox company (cost of goods sold posted with the invoice)")
        if self.f.dozens is None:
            self.report.configuration.append("unit of measure Dozens (12 units)")
        if self.dry_run:
            return
        if self.f.anglo_saxon is False:
            self.w.write("res.company", [self.company], {"anglo_saxon_accounting": True})
            self.f.anglo_saxon = True
        if self.f.dozens is None:
            vals: dict[str, Any] = {"name": "Dozens"}
            if self.f.uom_relative:
                vals.update({"relative_factor": 12.0, "relative_uom_id": self.f.units})
            else:
                vals.update({"category_id": self.f.units_category, "uom_type": "bigger", "factor_inv": 12.0})
            [self.f.dozens] = self.w.create("uom.uom", [vals])
            for fixture_id, key in self.ds.keys["uom.uom"].items():
                if key == "dozens":
                    self.ids["uom.uom"][fixture_id] = self.f.dozens

    # ------------------------------------------------------------------ catalogue
    def _valuation(self, row: dict[str, Any]) -> dict[str, Any]:
        goods = row["name"].endswith("Goods")
        vals: dict[str, Any] = {}
        described = self.f.category_fields

        def selection(name: str) -> set[str]:
            return {value for value, _label in (described.get(name, {}).get("selection") or [])}

        if "property_cost_method" in described:
            vals["property_cost_method"] = "fifo" if goods and "fifo" in selection("property_cost_method") else "standard"
        if "property_valuation" in described:
            automated = next((v for v in ("real_time", "automated") if v in selection("property_valuation")), None)
            periodic = next((v for v in ("manual_periodic", "periodic", "manual") if v in selection("property_valuation")), None)
            chosen = automated if goods else periodic
            if chosen:
                vals["property_valuation"] = chosen
        if goods:
            vals.update({name: account for name, account in self.f.stock_accounts.items() if name in described})
        return vals

    def catalogue(self) -> None:
        self.map_by_name("product.category", self.ds.records["product.category"], self._valuation)
        pricelists = self.ds.records["product.pricelist"]
        self.ensure("product.pricelist", pricelists, lambda row: {
            "name": row["name"], "currency_id": self.ref("res.currency", row["currency_id"]), "company_id": self.company},
            adopt=("name", lambda row: row["name"]))
        if any(o["currency_id"][1] == "USD" for o in self.ds.records["sale.order"]):
            name = "product_pricelist__USD"
            step = self.report.step("product.pricelist")
            step.planned += 1
            if name in self.existing:
                self.usd_pricelist = self.existing[name]
                step.existing += 1
            elif self.dry_run:
                step.created += 1
            else:
                [pid] = self.w.create("product.pricelist", [{"name": "BENACTA_DEMO USD", "currency_id": self.f.currency["USD"], "company_id": self.company}])
                self.w.create("ir.model.data", [{"module": XMLID_MODULE, "name": name, "model": "product.pricelist", "res_id": pid, "noupdate": True}])
                self.existing[name] = self.usd_pricelist = pid
                step.created += 1

        variants = {p["product_tmpl_id"][0]: p for p in self.ds.records["product.product"]}
        fields = self.f.template_fields

        def product_vals(row: dict[str, Any]) -> dict[str, Any]:
            variant = variants[row["id"]]
            goods = row["type"] != "service"
            vals = {"name": row["name"], "default_code": variant["default_code"], "type": row["type"],
                    "categ_id": self.ref("product.category", row["categ_id"]), "list_price": row["list_price"],
                    "standard_price": variant["standard_price"], "uom_id": self.f.units, "sale_ok": True, "purchase_ok": goods,
                    "invoice_policy": "delivery" if goods else "order", "company_id": self.company,
                    "taxes_id": self.tax, "supplier_taxes_id": [[6, 0, []]]}
            if "is_storable" in fields or not fields:
                vals["is_storable"] = bool(row["is_storable"])
            if "uom_po_id" in fields:
                vals["uom_po_id"] = self.f.units
            return vals

        self.ensure("product.template", self.ds.records["product.template"], product_vals,
                    adopt=("default_code", lambda row: variants[row["id"]]["default_code"]))
        if not self.dry_run:
            templates = {t["id"]: t["product_variant_id"][0] for t in self.r.search_read(
                "product.template", [["id", "in", list(self.ids["product.template"].values())]], ["product_variant_id"])}
            for product in self.ds.records["product.product"]:
                self.ids["product.product"][product["id"]] = templates[self.ref("product.template", product["product_tmpl_id"])]
        self.ensure("product.pricelist.item", self.ds.records["product.pricelist.item"], lambda row: {
            "pricelist_id": self.ref("product.pricelist", row["pricelist_id"]), "applied_on": "1_product",
            "product_tmpl_id": self.ref("product.template", row["product_tmpl_id"]), "min_quantity": row["min_quantity"],
            "compute_price": "fixed", "fixed_price": row["fixed_price"]})
        self.ensure("res.partner", self.ds.records["res.partner"], lambda row: {
            "name": row["name"], "ref": row["ref"], "is_company": bool(row["is_company"]), "email": row["email"], "company_id": self.company,
            "customer_rank": row["customer_rank"], "supplier_rank": row["supplier_rank"],
            "property_product_pricelist": self.ref("product.pricelist", row["property_product_pricelist"])},
            adopt=("ref", lambda row: row["ref"]))
        rates = self.ds.records["res.currency.rate"]
        present = {(r["name"], m2o_id(r["currency_id"])) for r in self.r.search_read(
            "res.currency.rate", [["company_id", "=", self.company]], ["name", "currency_id"])}
        fresh = [r for r in rates if self.key("res.currency.rate", r["id"]) in self.existing
                 or (r["name"], self.ids["res.currency"].get(m2o_id(r["currency_id"]))) not in present]
        self.ensure("res.currency.rate", fresh, lambda row: {
            "name": row["name"], "rate": row["rate"], "currency_id": self.ref("res.currency", row["currency_id"]), "company_id": self.company})

    # ------------------------------------------------------------------ pickings
    def _validate_picking(self, picking_id: int, quantities: dict[int, float], done_at: str) -> None:
        """Set the quantities per product, validate (a backorder for the rest), then date the transfer as planned."""
        moves = self.r.search_read("stock.move", [["picking_id", "=", picking_id], ["state", "not in", ["done", "cancel"]]],
                                   ["id", "product_id", "product_uom_qty"])
        for move in moves:
            quantity = quantities.get(m2o_id(move["product_id"]), 0.0)
            self.w.write("stock.move", [move["id"]], {"quantity": quantity, "picked": quantity > 0})
        result = self.w.call("stock.picking", "button_validate", ids=[picking_id])
        if isinstance(result, dict) and result.get("res_model") == "stock.backorder.confirmation":
            context = result.get("context") or {}
            [wizard] = self.w.create("stock.backorder.confirmation", [{"pick_ids": [[6, 0, [picking_id]]]}], context=context)
            self.w.call("stock.backorder.confirmation", "process", ids=[wizard], context=context)
        elif isinstance(result, dict) and result.get("res_model"):
            raise RuntimeError(f"picking {picking_id}: unexpected wizard {result['res_model']} on validation")
        self.w.write("stock.picking", [picking_id], {"date_done": done_at})
        done = [m["id"] for m in self.r.search_read("stock.move", [["picking_id", "=", picking_id], ["state", "=", "done"]], ["id"])]
        if done:
            self.w.write("stock.move", done, {"date": done_at})

    # ------------------------------------------------------------------ purchases and receipts
    def purchases(self) -> None:
        orders = self.ds.records["purchase.order"]
        lines_of: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for line in self.ds.records["purchase.order.line"]:
            lines_of[line["order_id"][0]].append(line)
        receipts = {p["origin"]: p for p in self.ds.records["stock.picking"] if p["picking_type_code"] == "incoming"}
        uom_field = self.f.line_uom_field.get("purchase.order.line", "product_uom_id")

        def order_vals(order: dict[str, Any]) -> dict[str, Any]:
            planned = receipts[order["name"]]["date_done"]
            return {"name": order["name"], "partner_ref": order["name"], "partner_id": self.ref("res.partner", order["partner_id"]),
                    "company_id": self.company, "currency_id": self.ref("res.currency", order["currency_id"]), "date_order": order["date_order"],
                    "order_line": [[0, 0, {"product_id": self.ref("product.product", line["product_id"]), "name": line["product_id"][1],
                                           "product_qty": line["product_qty"], uom_field: self.f.units, "price_unit": line["price_unit"],
                                           "date_planned": planned, "tax_ids": [[6, 0, []]]}] for line in lines_of[order["id"]]]}

        self.ensure("purchase.order", orders, order_vals, adopt=("partner_ref", lambda row: row["name"]), batch=20)
        step = self.report.step("stock.picking")
        step.planned += len(receipts)
        if self.dry_run:
            step.created += sum(1 for p in receipts.values() if self.key("stock.picking", p["id"]) not in self.existing)
            step.existing += sum(1 for p in receipts.values() if self.key("stock.picking", p["id"]) in self.existing)
            return
        self._map_lines("purchase.order", "order_line", "purchase.order.line", orders)
        states = {o["id"]: o["state"] for o in self.r.search_read("purchase.order", [["id", "in", list(self.ids["purchase.order"].values())]], ["state"])}
        for order in orders:
            odoo_id = self.ids["purchase.order"][order["id"]]
            if order["state"] == "purchase" and states[odoo_id] in ("draft", "sent"):
                self.w.call("purchase.order", "button_confirm", ids=[odoo_id])
                self.w.write("purchase.order", [odoo_id], {"date_order": order["date_order"], "date_approve": order["date_order"]})
            receipt = receipts[order["name"]]
            if self.key("stock.picking", receipt["id"]) in self.existing:
                step.existing += 1
                continue
            pickings = self.r.search_read("stock.picking", [["purchase_id", "=", odoo_id], ["state", "not in", ["done", "cancel"]]], ["id"], order="id asc")
            if not pickings:
                raise RuntimeError(f"purchase order {order['name']}: no open receipt after confirmation")
            quantities = {self.ref("product.product", line["product_id"]): float(line["qty_received"]) for line in lines_of[order["id"]]}
            self._validate_picking(pickings[0]["id"], quantities, receipt["date_done"])
            self.register_one("stock.picking", receipt, pickings[0]["id"])
            step.created += 1

    # ------------------------------------------------------------------ sales, deliveries
    def sales(self) -> None:
        orders = self.ds.records["sale.order"]
        uom_field = self.f.line_uom_field.get("sale.order.line", "product_uom_id")
        public = next(p for p in self.ds.records["product.pricelist"] if p["name"].endswith("Public"))

        def order_vals(order: dict[str, Any]) -> dict[str, Any]:
            if order["currency_id"][1] == "USD":
                pricelist = self.usd_pricelist
            else:
                pricelist = self.ref("product.pricelist", order["pricelist_id"] or [public["id"], public["name"]])
            lines = [self.fixture["sale.order.line"][i] for i in order["order_line"]]
            return {"name": order["name"], "client_order_ref": order["name"], "partner_id": self.ref("res.partner", order["partner_id"]),
                    "company_id": self.company, "pricelist_id": pricelist, "date_order": order["date_order"],
                    "order_line": [[0, 0, {"product_id": self.ref("product.product", line["product_id"]), "name": line["product_id"][1],
                                           "product_uom_qty": line["product_uom_qty"], uom_field: self.ref("uom.uom", line["product_uom_id"]),
                                           "price_unit": line["price_unit"], "discount": line["discount"], "tax_ids": self.tax}] for line in lines]}

        self.ensure("sale.order", orders, order_vals, adopt=("client_order_ref", lambda row: row["name"]), batch=25)
        deliveries = sorted((p for p in self.ds.records["stock.picking"] if p["picking_type_code"] == "outgoing"), key=lambda p: (p["date_done"], p["id"]))
        step = self.report.step("stock.picking")
        step.planned += len(deliveries)
        if self.dry_run:
            step.created += sum(1 for p in deliveries if self.key("stock.picking", p["id"]) not in self.existing)
            step.existing += sum(1 for p in deliveries if self.key("stock.picking", p["id"]) in self.existing)
            return
        self._map_lines("sale.order", "order_line", "sale.order.line", orders)
        states = {o["id"]: o["state"] for o in self.r.search_read("sale.order", [["id", "in", list(self.ids["sale.order"].values())]], ["state"])}
        for chunk in batched([o for o in orders if o["state"] == "sale" and states[self.ids["sale.order"][o["id"]]] in ("draft", "sent")], 25):
            self.w.call("sale.order", "action_confirm", ids=[self.ids["sale.order"][o["id"]] for o in chunk])
            for order in chunk:
                self.w.write("sale.order", [self.ids["sale.order"][order["id"]]], {"date_order": order["date_order"]})
        cancelled = [self.ids["sale.order"][o["id"]] for o in orders if o["state"] == "cancel" and states[self.ids["sale.order"][o["id"]]] != "cancel"]
        if cancelled:
            self.w.call("sale.order", "action_cancel", ids=cancelled)
        for delivery in deliveries:
            if self.key("stock.picking", delivery["id"]) in self.existing:
                step.existing += 1
                continue
            order = self.orders_by_name[delivery["sale_id"][1]]
            odoo_order = self.ids["sale.order"][order["id"]]
            pickings = self.r.search_read("stock.picking", [["sale_id", "=", odoo_order], ["state", "not in", ["done", "cancel"]]], ["id"], order="id asc")
            if not pickings:
                raise RuntimeError(f"sale order {order['name']}: no open delivery after confirmation")
            quantities = {self.ref("product.product", line["product_id"]): float(line["qty_delivered"])
                          for line in (self.fixture["sale.order.line"][i] for i in order["order_line"]) if line["product_id"][1] != "[FRT] Freight rebilling"}
            self._validate_picking(pickings[0]["id"], quantities, delivery["date_done"])
            self.register_one("stock.picking", delivery, pickings[0]["id"])
            step.created += 1

    # ------------------------------------------------------------------ invoices
    def _align_lines(self, move_id: int, expected: dict[int, float], dates: dict[str, Any]) -> None:
        """Match the draft document's product lines to the dataset: quantities per sale line, extra lines removed."""
        lines = self.r.search_read("account.move.line", [["move_id", "=", move_id], ["display_type", "=", "product"]],
                                   ["id", "sale_line_ids", "quantity"])
        commands: list[list[Any]] = []
        for line in lines:
            sale_lines = [s for s in line["sale_line_ids"] if s in expected]
            if not sale_lines:
                commands.append([2, line["id"], 0])
            elif abs(line["quantity"] - expected[sale_lines[0]]) > 1e-6:
                commands.append([1, line["id"], {"quantity": expected[sale_lines[0]]}])
        self.w.write("account.move", [move_id], {**dates, "invoice_line_ids": commands})

    def invoices(self) -> None:
        moves = sorted(self.ds.records["account.move"], key=lambda m: (m["invoice_date"], m["id"]))
        product_lines: dict[int, dict[int, float]] = defaultdict(dict)  # fixture move -> {fixture sale line: quantity}
        direct_lines: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for line in self.ds.records["account.move.line"]:
            if line["display_type"] != "product":
                continue
            if line.get("sale_line_ids"):
                product_lines[line["move_id"][0]][line["sale_line_ids"][0]] = float(line["quantity"])
            else:
                direct_lines[line["move_id"][0]].append(line)
        step = self.report.step("account.move")
        step.planned += len(moves)
        if self.dry_run:
            step.existing += sum(1 for m in moves if self.key("account.move", m["id"]) in self.existing)
            step.created += sum(1 for m in moves if self.key("account.move", m["id"]) not in self.existing)
            return
        for move in moves:
            name = self.key("account.move", move["id"])
            if name in self.existing:
                self.ids["account.move"][move["id"]] = self.existing[name]
                step.existing += 1
                continue
            dates = {"invoice_date": move["invoice_date"], "date": move["date"], "ref": move["name"]}
            expected = {self.ids["sale.order.line"][s]: q for s, q in product_lines[move["id"]].items()}
            if move["move_type"] == "out_refund":
                reversed_id = self.ids["account.move"][move["reversed_entry_id"][0]]
                [journal] = self.r.search_read("account.move", [["id", "=", reversed_id]], ["journal_id"])
                context = {"active_model": "account.move", "active_ids": [reversed_id], "active_id": reversed_id}
                [wizard] = self.w.create("account.move.reversal", [{"reason": "partial credit note", "date": move["invoice_date"],
                                                                     "journal_id": m2o_id(journal["journal_id"])}], context=context)
                self.w.call("account.move.reversal", "reverse_moves", ids=[wizard], context=context)
                [credit] = self.r.search_read("account.move", [["reversed_entry_id", "=", reversed_id], ["state", "=", "draft"]], ["id"], order="id desc", limit=1)
                move_id = credit["id"]
                self._align_lines(move_id, expected, dates)
            elif move.get("invoice_origin"):
                order = self.orders_by_name[move["invoice_origin"]]
                odoo_order = self.ids["sale.order"][order["id"]]
                before = set(self.r.search_read("sale.order", [["id", "=", odoo_order]], ["invoice_ids"])[0]["invoice_ids"])
                context = {"active_model": "sale.order", "active_ids": [odoo_order], "active_id": odoo_order}
                [wizard] = self.w.create("sale.advance.payment.inv", [{"advance_payment_method": "delivered"}], context=context)
                self.w.call("sale.advance.payment.inv", "create_invoices", ids=[wizard], context=context)
                after = set(self.r.search_read("sale.order", [["id", "=", odoo_order]], ["invoice_ids"])[0]["invoice_ids"])
                new = sorted(after - before)
                if len(new) != 1:
                    raise RuntimeError(f"{move['name']}: {len(new)} invoice(s) created from {order['name']}, one expected")
                move_id = new[0]
                self._align_lines(move_id, expected, dates)
            else:
                [move_id] = self.w.create("account.move", [{
                    "move_type": move["move_type"], "partner_id": self.ref("res.partner", move["partner_id"]), "company_id": self.company,
                    "currency_id": self.ref("res.currency", move["currency_id"]), **dates,
                    "invoice_line_ids": [[0, 0, {"product_id": self.ref("product.product", line["product_id"]), "name": line["product_id"][1],
                                                 "quantity": line["quantity"], "price_unit": line["price_unit"], "discount": line["discount"],
                                                 "tax_ids": self.tax}] for line in direct_lines[move["id"]]]}])
            self.w.call("account.move", "action_post", ids=[move_id])
            self.register_one("account.move", move, move_id)
            step.created += 1
            [posted] = self.r.search_read("account.move", [["id", "=", move_id]], ["amount_untaxed", "state"])
            if posted["state"] != "posted" or abs(posted["amount_untaxed"] - abs(move["amount_untaxed_signed"])) > 0.005:
                self.report.mismatches.append(f"{move['name']}: Odoo {posted['state']} {posted['amount_untaxed']} vs dataset {abs(move['amount_untaxed_signed'])}")

    def run(self) -> None:
        self.reference()
        self.configuration()
        self.catalogue()
        self.purchases()
        self.sales()
        self.invoices()


def write_policy_register(dataset: FixtureDataset, settings: Settings, path: Path = REGISTER_PATH) -> Path:
    """The governed terms of the seeded company as the policy register of the connected instance."""
    document = {
        "register_version": 1,
        "source_instance": settings.odoo_source_instance,
        "company_id": 1,
        "owner": "Sales finance controller (synthetic)",
        "source": f"fixture {dataset.dataset_id} terms, seeded into {settings.odoo_target}",
        **dataset.terms,
    }
    path.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def dry_run(settings: Settings) -> int:
    with OdooJson2Client.from_settings(settings) as client:
        plan = build_plan(OdooReader(client), settings)
    print_plan(plan)
    path = write_plan(plan)
    print(f"\nPlan written to {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}")
    return 0


def seed(settings: Settings, *, confirm: bool = False) -> int:
    """Dry run by default; with `confirm`, write through the guarded writer. Never writes when the guard blocks."""
    company = settings.odoo_sandbox_company or COMPANY[1]
    with OdooJson2Client.from_settings(settings, max_retries=0) as client:
        reader = OdooReader(client)
        _checks, company_exists = _prerequisites(reader, settings)
        guard = odoo_write_guard(settings, sandbox_company_exists=company_exists)
        facts = read_facts(reader, settings)
        if not confirm:
            seeder = TradingSeeder(reader, None, company, facts)
            seeder.run()
            print(f"Trading company seed for {settings.odoo_target} / {company} (dry run, nothing written)")
            print_report(seeder.report, dry_run=True)
            print_facts(facts)
            print("\nWrite guard")
            for check in guard.checks:
                print(f"  [{'x' if check.passed else ' '}] {check.name}: {check.detail}")
            print("\nRun again with --confirm to write.")
            return 0
        if not guard.allowed:
            print("Seed refused by the write guard. Nothing was written.")
            for check in guard.checks:
                print(f"  [{'x' if check.passed else ' '}] {check.name}: {check.detail}")
            return 2
        if facts.missing:
            print("Seed refused: the instance lacks " + "; ".join(facts.missing) + ". Nothing was written.")
            return 4
        client._http.timeout = WRITE_TIMEOUT_SECONDS  # noqa: SLF001 confirmations and postings take longer than reads
        seeder = TradingSeeder(reader, OdooWriter(client, guard), company, facts)
        seeder.run()
    print(f"Trading company seed for {settings.odoo_target} / {company}")
    print_report(seeder.report, dry_run=False)
    register = write_policy_register(seeder.ds, settings)
    print(f"policy register written to {register.relative_to(REPO_ROOT) if register.is_relative_to(REPO_ROOT) else register}")
    return 1 if seeder.report.mismatches else 0
