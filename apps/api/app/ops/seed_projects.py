"""Write the project controlling part of dataset demo_v2 into the configured Odoo company (ADR-0005).

Dry run by default: reads Odoo and prints what would be created. With `--confirm` every write goes through
`OdooWriter` (full guard, attested backup). Each created record receives the external identifier
`benacta_demo.<model>__<fixture key>`, so a replay creates nothing twice; documents also carry their fixture name
(`client_order_ref`, `partner_ref`, `ref`, `memo`) so a record created just before an interruption is adopted
instead of duplicated. Existing records of the company are never modified.

Lump-sum sale and purchase lines are carried as value units (quantity = amount, unit price 1): Odoo rounds
quantities to two decimals and milestone or partial billing fractions would otherwise lose cents. Project marts
read amounts only.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.config import Settings
from app.connectors.guards import odoo_write_guard
from app.connectors.odoo import OdooJson2Client, OdooReader, OdooWriter
from app.fixtures.demo_dataset import DEFAULT_ANCHOR, FixtureDataset, build_demo_dataset
from app.fixtures.projects_dataset import extend_with_projects

XMLID_MODULE = "benacta_demo"
BATCH = 200
TIMESHEET_BATCH = 500
SALE_TAX = ("20% S", "sale")
PURCHASE_TAX = ("20% S", "purchase")
ACCOUNT_BY_CATEGORY = {"BENACTA_DEMO Subcontracting": "604000", "BENACTA_DEMO Project materials": "604000",
                       "BENACTA_DEMO Engineering contracts": "704000"}
CALENDAR_ATTENDANCE = [(day, start, end, period) for day in "01234"
                       for start, end, period in ((8.5, 12.0, "morning"), (13.0, 17.0, "afternoon"))]


def xmlid_name(model: str, key: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", f"{model.replace('.', '_')}__{key}")


def m2o_id(value: Any) -> int | None:
    return value[0] if isinstance(value, list | tuple) and value else None


def batched(items: list[Any], size: int) -> Iterable[list[Any]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


@dataclass
class Step:
    model: str
    planned: int = 0
    existing: int = 0
    adopted: int = 0
    created: int = 0


@dataclass
class SeedReport:
    steps: dict[str, Step] = field(default_factory=dict)
    mismatches: list[str] = field(default_factory=list)

    def step(self, model: str) -> Step:
        return self.steps.setdefault(model, Step(model))


class ProjectSeeder:
    def __init__(self, reader: OdooReader, writer: OdooWriter | None, company_name: str, anchor: date = DEFAULT_ANCHOR):
        self.r, self.w = reader, writer
        self.base = build_demo_dataset(anchor=anchor)
        self.ds: FixtureDataset = extend_with_projects(build_demo_dataset(anchor=anchor))
        self.company_name = company_name
        self.ids: dict[str, dict[int, int]] = defaultdict(dict)
        self.report = SeedReport()
        self.fixture = {m: {row["id"]: row for row in rows} for m, rows in self.ds.records.items()}
        self.existing = {row["name"]: row["res_id"] for row in reader.iter_search_read(
            "ir.model.data", [["module", "=", XMLID_MODULE]], ["name", "res_id"])}

    # ------------------------------------------------------------------ helpers
    @property
    def dry_run(self) -> bool:
        return self.w is None

    def added(self, model: str) -> list[dict[str, Any]]:
        return self.ds.records.get(model, [])[len(self.base.records.get(model, [])):]

    def key(self, model: str, fixture_id: int) -> str:
        return xmlid_name(model, self.ds.keys[model][fixture_id])

    def ref(self, model: str, value: Any) -> int | bool:
        fixture_id = m2o_id(value) if not isinstance(value, int) else value
        if fixture_id is None:
            return False
        return self.ids[model][fixture_id]

    def _register(self, model: str, rows: list[dict[str, Any]], odoo_ids: list[int]) -> None:
        names = [self.key(model, row["id"]) for row in rows]
        self.w.create("ir.model.data", [{"module": XMLID_MODULE, "name": n, "model": model, "res_id": i, "noupdate": True}
                                        for n, i in zip(names, odoo_ids, strict=True)])
        for row, name, odoo_id in zip(rows, names, odoo_ids, strict=True):
            self.existing[name] = odoo_id
            self.ids[model][row["id"]] = odoo_id

    def ensure(
        self,
        model: str,
        rows: list[dict[str, Any]],
        vals: Callable[[dict[str, Any]], dict[str, Any]],
        *,
        adopt: tuple[str, Callable[[dict[str, Any]], Any]] | None = None,
        batch: int = BATCH,
    ) -> list[int]:
        """Map rows already in Odoo, adopt unregistered twins by a unique reference, create the rest."""
        step = self.report.step(model)
        step.planned += len(rows)
        todo = []
        for row in rows:
            name = self.key(model, row["id"])
            if name in self.existing:
                self.ids[model][row["id"]] = self.existing[name]
                step.existing += 1
            else:
                todo.append(row)
        if adopt and todo:
            field_name, value_of = adopt
            wanted = {value_of(row): row for row in todo}
            found = self.r.search_read(model, [[field_name, "in", list(wanted)]], [field_name])
            twins = [(wanted[rec[field_name]], rec["id"]) for rec in found if rec[field_name] in wanted]
            if twins and not self.dry_run:
                self._register(model, [t[0] for t in twins], [t[1] for t in twins])
            step.adopted += len(twins)
            adopted = {id(t[0]) for t in twins}
            todo = [row for row in todo if id(row) not in adopted]
        if self.dry_run:
            step.created += len(todo)
            return []
        created: list[int] = []
        for chunk in batched(todo, batch):
            odoo_ids = self.w.create(model, [vals(row) for row in chunk])
            self._register(model, chunk, odoo_ids)
            created.extend(odoo_ids)
        step.created += len(created)
        return created

    def map_by_name(self, model: str, rows: list[dict[str, Any]], extra: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
                    domain: list | None = None) -> None:
        """Reference data: reuse a record with the same name, create the missing ones."""
        names = {row["name"] for row in rows}
        found = {rec["name"]: rec["id"] for rec in self.r.search_read(model, [["name", "in", list(names)], *(domain or [])], ["name"])}
        missing = []
        for row in rows:
            if row["name"] in found and self.key(model, row["id"]) not in self.existing:
                self.ids[model][row["id"]] = found[row["name"]]
                self.report.step(model).planned += 1
                self.report.step(model).existing += 1
            else:
                missing.append(row)
        self.ensure(model, missing, lambda row: {"name": row["name"], **(extra(row) if extra else {})})

    def lookup_one(self, model: str, domain: list, what: str, context: dict[str, Any] | None = None) -> int:
        rows = self.r.search_read(model, domain, ["id"], limit=1, context=context)
        if not rows:
            raise RuntimeError(f"{what} not found in Odoo ({model} {domain})")
        return rows[0]["id"]

    # ------------------------------------------------------------------ steps
    def reference(self) -> None:
        self.company = self.lookup_one("res.company", [["name", "=", self.company_name]], "company")
        for fixture_id, code in self.ds.keys["res.currency"].items():
            self.ids["res.currency"][fixture_id] = self.lookup_one(
                "res.currency", [["name", "=", code]], f"currency {code}", context={"active_test": False})
        self.ids["res.company"][1] = self.company
        self.ids["uom.uom"][1] = self.lookup_one("uom.uom", [["name", "=", "Units"]], "unit Units")
        self.ids["account.analytic.plan"][1] = self.lookup_one("account.analytic.plan", [["parent_id", "=", False]], "project analytic plan")
        self.sale_tax = self.lookup_one("account.tax", [["name", "=", SALE_TAX[0]], ["type_tax_use", "=", SALE_TAX[1]]], "sale tax")
        self.purchase_tax = self.lookup_one("account.tax", [["name", "=", PURCHASE_TAX[0]], ["type_tax_use", "=", PURCHASE_TAX[1]]], "purchase tax")
        self.bank_journal = self.lookup_one("account.journal", [["type", "=", "bank"], ["company_id", "=", self.company]], "bank journal")
        self.accounts = {a["code"]: a["id"] for a in self.r.search_read(
            "account.account", [["code", "in", sorted(set(ACCOUNT_BY_CATEGORY.values()))]], ["code"])}

    def organisation(self) -> None:
        self.map_by_name("project.tags", self.added("project.tags"))
        self.ensure("resource.calendar", self.added("resource.calendar"), lambda row: {
            "name": row["name"], "hours_per_day": row["hours_per_day"], "company_id": self.company,
            "attendance_ids": [[5, 0, 0]] + [[0, 0, {"name": f"day {d} {p}", "dayofweek": d, "hour_from": f, "hour_to": t, "day_period": p}]
                                             for d, f, t, p in CALENDAR_ATTENDANCE]},
            adopt=("name", lambda row: row["name"]))
        self.map_by_name("hr.department", self.added("hr.department"), lambda _row: {"company_id": self.company})
        self.map_by_name("hr.job", self.added("hr.job"), lambda _row: {"company_id": self.company})
        self.map_by_name("hr.skill.type", self.added("hr.skill.type"), lambda _row: {
            "skill_level_ids": [[0, 0, {"name": "Confirmed", "level_progress": 50, "default_level": True}]]})
        skill_rows = self.added("hr.skill")
        self.map_by_name("hr.skill", skill_rows, lambda row: {"skill_type_id": self.ref("hr.skill.type", row["skill_type_id"])})
        self.levels: dict[int, int] = {}
        if not self.dry_run:
            type_ids = sorted(set(self.ids["hr.skill.type"].values()))
            for level in self.r.search_read("hr.skill.level", [["skill_type_id", "in", type_ids]], ["skill_type_id", "level_progress"],
                                            order="level_progress desc"):
                self.levels.setdefault(level["skill_type_id"][0], level["id"])

    def catalogue(self) -> None:
        self.map_by_name("product.category", self.added("product.category"), lambda row: {
            "property_account_expense_categ_id": self.accounts.get(ACCOUNT_BY_CATEGORY.get(row["name"], "")) or False,
            "property_account_income_categ_id": self.accounts.get(ACCOUNT_BY_CATEGORY.get(row["name"], "")) or False})
        codes = {p["product_tmpl_id"][0]: p["default_code"] for p in self.added("product.product")}

        def product_vals(row: dict[str, Any]) -> dict[str, Any]:
            code = codes[row["id"]]
            milestone = code in ("CONTRACT", "CHANGE")
            return {"name": row["name"], "default_code": code, "type": "service", "categ_id": self.ref("product.category", row["categ_id"]),
                    "list_price": 0.0, "sale_ok": milestone, "purchase_ok": not milestone, "company_id": self.company,
                    "invoice_policy": "delivery" if milestone else "order", "service_type": "milestones" if milestone else "manual",
                    "service_tracking": "no", "purchase_method": "purchase", "taxes_id": [[6, 0, []]], "supplier_taxes_id": [[6, 0, []]]}

        self.ensure("product.template", self.added("product.template"), product_vals, adopt=("default_code", lambda row: codes[row["id"]]))
        if not self.dry_run:
            variants = {t["id"]: t["product_variant_id"][0] for t in self.r.search_read(
                "product.template", [["id", "in", list(self.ids["product.template"].values())]], ["product_variant_id"])}
            for product in self.added("product.product"):
                self.ids["product.product"][product["id"]] = variants[self.ref("product.template", product["product_tmpl_id"])]

        self.ensure("res.partner", self.added("res.partner"), lambda row: {
            "name": row["name"], "is_company": row["is_company"], "email": row["email"], "company_id": self.company,
            "customer_rank": row["customer_rank"], "supplier_rank": row["supplier_rank"]}, adopt=("email", lambda row: row["email"]))

        rates = self.ds.records["res.currency.rate"]
        present = {(r["name"], r["currency_id"][0]) for r in self.r.search_read(
            "res.currency.rate", [["company_id", "=", self.company]], ["name", "currency_id"])}
        fresh = [r for r in rates if (r["name"], self.ref("res.currency", r["currency_id"])) not in present
                 or self.key("res.currency.rate", r["id"]) in self.existing]
        self.ensure("res.currency.rate", fresh, lambda row: {
            "name": row["name"], "rate": row["rate"], "currency_id": self.ref("res.currency", row["currency_id"]), "company_id": self.company})

        if any(o["currency_id"][1] == "USD" for o in self.added("sale.order")):
            name = "product_pricelist__USD"
            if name in self.existing:
                self.usd_pricelist = self.existing[name]
            elif self.dry_run:
                self.usd_pricelist = 0
                self.report.step("product.pricelist").created += 1
            else:
                [pid] = self.w.create("product.pricelist", [{"name": "BENACTA_DEMO USD", "currency_id": self.ref("res.currency", [2]), "company_id": self.company}])
                self.w.create("ir.model.data", [{"module": XMLID_MODULE, "name": name, "model": "product.pricelist", "res_id": pid, "noupdate": True}])
                self.usd_pricelist = pid

    def people(self) -> None:
        self.ensure("hr.employee", self.ds.records["hr.employee"], lambda row: {
            "name": row["name"], "job_id": self.ref("hr.job", row["job_id"]), "department_id": self.ref("hr.department", row["department_id"]),
            "hourly_cost": row["hourly_cost"], "company_id": self.company, "resource_calendar_id": self.ref("resource.calendar", row["resource_calendar_id"]),
            "x_benacta_employee_code": row["x_benacta_employee_code"], "x_benacta_is_external": row["x_benacta_is_external"]},
            adopt=("x_benacta_employee_code", lambda row: row["x_benacta_employee_code"]))
        self.ensure("hr.employee.skill", self.ds.records["hr.employee.skill"], lambda row: {
            "employee_id": self.ref("hr.employee", row["employee_id"]), "skill_id": self.ref("hr.skill", row["skill_id"]),
            "skill_type_id": self.ref("hr.skill.type", row["skill_type_id"]),
            "skill_level_id": self.levels[self.ref("hr.skill.type", row["skill_type_id"])]})

    def contracts(self) -> None:
        self.ensure("account.analytic.account", self.ds.records["account.analytic.account"], lambda row: {
            "name": row["name"], "code": row["code"], "plan_id": self.ref("account.analytic.plan", row["plan_id"]),
            "partner_id": self.ref("res.partner", row["partner_id"]), "company_id": self.company},
            adopt=("code", lambda row: row["code"]))
        orders = self.added("sale.order")

        def order_vals(order: dict[str, Any]) -> dict[str, Any]:
            lines = [self.fixture["sale.order.line"][lid] for lid in order["order_line"]]
            return {"partner_id": self.ref("res.partner", order["partner_id"]), "company_id": self.company,
                    "client_order_ref": order["name"], "date_order": order["date_order"],
                    **({"pricelist_id": self.usd_pricelist} if order["currency_id"][1] == "USD" else {}),
                    "order_line": [[0, 0, {"product_id": self.ref("product.product", line["product_id"]), "name": line["product_id"][1],
                                           "product_uom_qty": line["price_subtotal"], "price_unit": 1.0, "discount": 0.0, "tax_ids": [[6, 0, []]]}]
                                   for line in lines]}

        self.ensure("sale.order", orders, order_vals, adopt=("client_order_ref", lambda row: row["name"]), batch=50)
        if self.dry_run:
            return
        self._map_lines("sale.order", "order_line", "sale.order.line", orders)
        drafts = {o["id"]: o["state"] for o in self.r.search_read("sale.order", [["id", "in", [self.ids["sale.order"][o["id"]] for o in orders]]], ["state"])}
        to_confirm = [o for o in orders if o["state"] == "sale" and drafts[self.ids["sale.order"][o["id"]]] in ("draft", "sent")]
        if to_confirm:
            self.w.call("sale.order", "action_confirm", ids=[self.ids["sale.order"][o["id"]] for o in to_confirm])
            for order in to_confirm:
                self.w.write("sale.order", [self.ids["sale.order"][order["id"]]], {"date_order": order["date_order"]})

    def _map_lines(self, parent_model: str, o2m: str, line_model: str, parents: list[dict[str, Any]]) -> None:
        odoo = {p["id"]: p[o2m] for p in self.r.search_read(parent_model, [["id", "in", [self.ids[parent_model][p["id"]] for p in parents]]], [o2m])}
        rows, ids = [], []
        for parent in parents:
            fixture_lines = parent[o2m] if parent_model == "sale.order" else [
                line["id"] for line in self.ds.records[line_model] if line["order_id"][0] == parent["id"]]
            created = sorted(odoo[self.ids[parent_model][parent["id"]]])
            if len(created) != len(fixture_lines):
                raise RuntimeError(f"{parent_model} {parent['name']}: {len(created)} lines in Odoo, {len(fixture_lines)} expected")
            for fixture_id, odoo_id in zip(fixture_lines, created, strict=True):
                if self.key(line_model, fixture_id) in self.existing:
                    self.ids[line_model][fixture_id] = self.existing[self.key(line_model, fixture_id)]
                else:
                    rows.append(self.fixture[line_model][fixture_id])
                    ids.append(odoo_id)
        if rows:
            self._register(line_model, rows, ids)

    def projects(self) -> None:
        self.ensure("project.project", self.ds.records["project.project"], lambda row: {
            "name": row["name"], "partner_id": self.ref("res.partner", row["partner_id"]), "date_start": row["date_start"],
            "date": row["date"] or False, "account_id": self.ref("account.analytic.account", row["account_id"]),
            "allow_milestones": row["allow_milestones"], "allow_timesheets": True, "allow_billable": bool(row["sale_line_id"]),
            "tag_ids": [[6, 0, [self.ids["project.tags"][t] for t in row["tag_ids"]]]], "company_id": self.company,
            "sale_line_id": self.ref("sale.order.line", row["sale_line_id"]),
            "x_benacta_contract_type": row["x_benacta_contract_type"] or False, "x_benacta_phase": row["x_benacta_phase"] or False,
            "x_benacta_fixed_rate_per_eur": row["x_benacta_fixed_rate_per_eur"] or 0.0},
            adopt=("name", lambda row: row["name"]))
        if not self.dry_run:
            linked = [line for line in self.added("sale.order.line") if line.get("project_id")]
            current = {line["id"]: line["project_id"] for line in self.r.search_read(
                "sale.order.line", [["id", "in", [self.ids["sale.order.line"][line["id"]] for line in linked]]], ["project_id"])}
            for line in linked:
                odoo_id = self.ids["sale.order.line"][line["id"]]
                if not current.get(odoo_id):
                    self.w.write("sale.order.line", [odoo_id], {"project_id": self.ref("project.project", line["project_id"])})
        tasks = [t for t in self.ds.records["project.task"] if t["project_id"]]
        self.ensure("project.task", tasks, lambda row: {
            "name": row["name"], "project_id": self.ref("project.project", row["project_id"]), "allocated_hours": row["allocated_hours"],
            "x_benacta_wbs_code": row["x_benacta_wbs_code"] or False, "x_benacta_change_order": row["x_benacta_change_order"]})
        milestones = self.ds.records["project.milestone"]
        created = self.ensure("project.milestone", milestones, lambda row: {
            "name": row["name"], "project_id": self.ref("project.project", row["project_id"]), "deadline": row["deadline"],
            "is_reached": row["is_reached"], "sale_line_id": self.ref("sale.order.line", row["sale_line_id"]),
            "quantity_percentage": row["quantity_percentage"], "x_benacta_milestone_code": row["x_benacta_milestone_code"]})
        if created:
            by_date: dict[str, list[int]] = defaultdict(list)
            for row in milestones:
                if row["is_reached"] and self.ids["project.milestone"][row["id"]] in created:
                    by_date[row["reached_date"]].append(self.ids["project.milestone"][row["id"]])
            for reached, ids in by_date.items():
                self.w.write("project.milestone", ids, {"reached_date": reached})

    def purchases(self) -> None:
        orders = self.added("purchase.order")
        lines_of = defaultdict(list)
        for line in self.added("purchase.order.line"):
            lines_of[line["order_id"][0]].append(line)

        def distribution(value: dict[str, float] | None) -> dict[str, float] | bool:
            return {str(self.ids["account.analytic.account"][int(k)]): v for k, v in value.items()} if value else False

        self.distribution = distribution
        self.ensure("purchase.order", orders, lambda order: {
            "partner_id": self.ref("res.partner", order["partner_id"]), "company_id": self.company, "partner_ref": order["name"],
            "currency_id": self.ref("res.currency", order["currency_id"]), "date_order": order["date_order"],
            "order_line": [[0, 0, {"product_id": self.ref("product.product", line["product_id"]), "name": line["product_id"][1],
                                   "product_qty": line["price_subtotal"], "price_unit": 1.0, "date_planned": line["date_planned"],
                                   "analytic_distribution": distribution(line.get("analytic_distribution")),
                                   "x_benacta_work_package": line.get("x_benacta_work_package") or False, "tax_ids": [[6, 0, []]]}]
                           for line in lines_of[order["id"]]]},
            adopt=("partner_ref", lambda row: row["name"]), batch=50)
        if self.dry_run:
            return
        self._map_lines("purchase.order", "order_line", "purchase.order.line", orders)
        states = {o["id"]: o["state"] for o in self.r.search_read("purchase.order", [["id", "in", list(self.ids["purchase.order"].values())]], ["state"])}
        to_confirm = [o for o in orders if o["state"] == "purchase" and states[self.ids["purchase.order"][o["id"]]] in ("draft", "sent")]
        if to_confirm:
            self.w.call("purchase.order", "button_confirm", ids=[self.ids["purchase.order"][o["id"]] for o in to_confirm])
            for order in to_confirm:
                self.w.write("purchase.order", [self.ids["purchase.order"][order["id"]]], {"date_order": order["date_order"], "date_approve": order["date_order"]})

    def time(self) -> None:
        self.ensure("account.analytic.line", self.ds.records["account.analytic.line"], lambda row: {
            "date": row["date"], "name": row["name"], "project_id": self.ref("project.project", row["project_id"]),
            "task_id": self.ref("project.task", row["task_id"]), "employee_id": self.ref("hr.employee", row["employee_id"]),
            "unit_amount": row["unit_amount"], "company_id": self.company}, batch=TIMESHEET_BATCH)

    def invoices(self) -> None:
        lines_of: dict[int, list[dict[str, Any]]] = defaultdict(list)
        taxed: set[int] = set()
        for line in self.ds.records["account.move.line"]:
            if line["display_type"] == "product":
                lines_of[line["move_id"][0]].append(line)
            elif line["display_type"] == "tax":
                taxed.add(line["move_id"][0])
        moves = self.added("account.move")

        def move_vals(move: dict[str, Any]) -> dict[str, Any]:
            sale = move["move_type"] == "out_invoice"
            tax = ([self.sale_tax] if sale else [self.purchase_tax]) if move["id"] in taxed else []
            return {"move_type": move["move_type"], "partner_id": self.ref("res.partner", move["partner_id"]), "company_id": self.company,
                    "currency_id": self.ref("res.currency", move["currency_id"]), "invoice_date": move["invoice_date"], "date": move["date"],
                    "invoice_payment_term_id": False, "invoice_date_due": move["invoice_date_due"], "ref": move["name"],
                    "invoice_line_ids": [[0, 0, {
                        "product_id": self.ref("product.product", line["product_id"]), "name": line["product_id"][1],
                        "quantity": line["price_subtotal"], "price_unit": 1.0, "tax_ids": [[6, 0, tax]],
                        **({"sale_line_ids": [[6, 0, [self.ids["sale.order.line"][s] for s in line["sale_line_ids"]]]]} if line.get("sale_line_ids") else {}),
                        **({"purchase_line_id": self.ref("purchase.order.line", line["purchase_line_id"])} if line.get("purchase_line_id") else {}),
                        **({"analytic_distribution": self.distribution(line["analytic_distribution"])} if line.get("analytic_distribution") else {}),
                    }] for line in lines_of[move["id"]]]}

        self.ensure("account.move", moves, move_vals, adopt=("ref", lambda row: row["name"]), batch=50)
        if self.dry_run:
            return
        odoo = {m["id"]: m for m in self.r.search_read("account.move", [["id", "in", [self.ids["account.move"][m["id"]] for m in moves]]],
                                                        ["state", "amount_total", "amount_untaxed", "invoice_date_due"])}
        drafts = [self.ids["account.move"][m["id"]] for m in moves if odoo[self.ids["account.move"][m["id"]]]["state"] == "draft"]
        for chunk in batched(drafts, 50):
            self.w.call("account.move", "action_post", ids=chunk)
        for move in moves:
            got = odoo[self.ids["account.move"][move["id"]]]
            for key in ("amount_total", "amount_untaxed", "invoice_date_due"):
                if str(got[key]) != str(move[key]) and not (isinstance(move[key], float) and abs(got[key] - move[key]) < 0.005):
                    self.report.mismatches.append(f"{move['name']} {key}: Odoo {got[key]} vs dataset {move[key]}")

    def payments(self) -> None:
        payments = self.ds.records["account.payment"]
        step = self.report.step("account.payment")
        step.planned = len(payments)
        memo = {p["memo"]: p["id"] for p in self.r.search_read("account.payment", [["memo", "in", [p["name"] for p in payments]]], ["memo"])}
        for payment in payments:
            name = self.key("account.payment", payment["id"])
            if name in self.existing:
                step.existing += 1
                continue
            if payment["name"] in memo:
                step.adopted += 1
                if not self.dry_run:
                    self._register("account.payment", [payment], [memo[payment["name"]]])
                continue
            step.created += 1
            if self.dry_run:
                continue
            invoices = [self.ids["account.move"][i] for i in payment["reconciled_invoice_ids"]]
            context = {"active_model": "account.move", "active_ids": invoices}
            [wizard] = self.w.create("account.payment.register", [{
                "payment_date": payment["date"], "amount": payment["amount"], "journal_id": self.bank_journal,
                "communication": payment["name"], "payment_difference_handling": "open", "group_payment": True}], context=context)
            self.w.call("account.payment.register", "action_create_payments", ids=[wizard], context=context)
            [created] = self.r.search_read("account.payment", [["memo", "=", payment["name"]]], ["id"], limit=1)
            self._register("account.payment", [payment], [created["id"]])

    def run(self) -> SeedReport:
        self.reference()
        self.organisation()
        self.catalogue()
        self.people()
        self.contracts()
        self.projects()
        self.purchases()
        self.time()
        self.invoices()
        self.payments()
        return self.report


def print_report(report: SeedReport, *, dry_run: bool) -> None:
    print(f"{'model':28} {'planned':>8} {'present':>8} {'adopted':>8} {'to create' if dry_run else 'created':>9}")
    for step in report.steps.values():
        print(f"{step.model:28} {step.planned:8} {step.existing:8} {step.adopted:8} {step.created:9}")
    for mismatch in report.mismatches:
        print(f"  MISMATCH {mismatch}")


def run(settings: Settings, *, confirm: bool) -> int:
    with OdooJson2Client.from_settings(settings, max_retries=0) as client:
        reader = OdooReader(client)
        exists = bool(settings.odoo_sandbox_company) and bool(reader.search_count("res.company", [["name", "=", settings.odoo_sandbox_company]]))
        guard = odoo_write_guard(settings, sandbox_company_exists=exists)
        if not confirm:
            report = ProjectSeeder(reader, None, settings.odoo_sandbox_company or "").run()
            print(f"Project company seed for {settings.odoo_target} / {settings.odoo_sandbox_company} (dry run, nothing written)")
            print_report(report, dry_run=True)
            print("\nWrite guard:")
            for check in guard.checks:
                print(f"  [{'x' if check.passed else ' '}] {check.name}: {check.detail}")
            return 0
        if not guard.allowed:
            print("Refused by the write guard. Nothing was written.")
            for check in guard.checks:
                print(f"  [{'x' if check.passed else ' '}] {check.name}: {check.detail}")
            return 2
        client._http.timeout = 300.0  # noqa: SLF001 large batches and posting take longer than reads
        seeder = ProjectSeeder(reader, OdooWriter(client, guard), settings.odoo_sandbox_company)
        report = seeder.run()
        print(f"Project company seed for {settings.odoo_target} / {settings.odoo_sandbox_company}")
        print_report(report, dry_run=False)
        return 1 if report.mismatches else 0
