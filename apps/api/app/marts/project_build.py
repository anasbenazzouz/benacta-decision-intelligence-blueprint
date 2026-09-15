"""Project controlling marts built from one snapshot.

Attribution rules (documented in docs/project_controlling_model.md):
- a project's code is the code of its analytic account;
- purchase lines and vendor bill lines are attributed through the analytic distribution; a vendor bill line that
  bills a purchase line inherits the purchase line's project, and a different analytic project raises
  VENDOR_BILL_PROJECT_MISMATCH;
- customer invoices are attributed through their order lines: the contract line (project.sale_line_id) or a
  change order line (sale.order.line.project_id);
- payments are allocated to reconciled invoices in order, up to each invoice total.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

import yaml

from app.config import REPO_ROOT
from app.marts.build import D, _Builder, m2o, to_date

PROJECT_TABLES = (
    "fact_change_order",
    "fact_customer_payment",
    "fact_receivable",
    "fact_vendor_bill_line",
    "fact_purchase_commitment",
    "fact_timesheet",
    "dim_employee",
    "dim_milestone",
    "dim_work_package",
    "dim_project",
)
MAPPINGS_PATH = REPO_ROOT / "data" / "mappings" / "project_mappings.yml"


def load_mappings() -> dict[str, Any]:
    return yaml.safe_load(MAPPINGS_PATH.read_text(encoding="utf-8"))


def _main_analytic(distribution: Any) -> int | None:
    """The analytic account carrying the largest share; ties resolved by account id."""
    if not distribution:
        return None
    shares = {int(key.split(",")[0]): Decimal(str(value)) for key, value in distribution.items()}
    return max(shares.items(), key=lambda kv: (kv[1], -kv[0]))[0]


def build_project_facts(builder: _Builder) -> None:
    d = builder.data
    if not d.records.get("project.project"):
        return
    mappings = load_mappings()
    s = builder.s

    accounts = d.records.get("account.analytic.account", {})
    tags = d.records.get("project.tags", {})
    projects_by_account: dict[int, int] = {}
    project_code: dict[int, str] = {}
    contract_line_project: dict[int, int] = {}
    for pid, project in d.records["project.project"].items():
        account_id = m2o(project.get("account_id"))
        code = accounts.get(account_id, {}).get("code") or f"PROJECT-{pid}"
        project_code[pid] = code
        if account_id:
            projects_by_account[account_id] = pid
        tag_names = [tags.get(t, {}).get("name", "") for t in project.get("tag_ids") or []]
        bu = next((n[len(mappings["business_unit_tag_prefix"]):] for n in tag_names if n.startswith(mappings["business_unit_tag_prefix"])), None)
        internal = next((n[len(mappings["internal_tag_prefix"]):] for n in tag_names if n.startswith(mappings["internal_tag_prefix"])), None)
        contract_line = m2o(project.get("sale_line_id"))
        if contract_line:
            contract_line_project[contract_line] = pid
        contract_currency = None
        if contract_line:
            line = d.get("sale.order.line", contract_line)
            order = d.get("sale.order", m2o(line["order_id"])) if line else None
            contract_currency = builder.currency_by_id.get(m2o(order["currency_id"]), {}).get("name") if order else None
        fixed_rate = project.get("x_benacta_fixed_rate_per_eur")
        if bu is None and internal is None:
            builder.issue("PROJECT_WITHOUT_BUSINESS_UNIT", "project.project", pid, f"{code} has no BU tag")
        builder.rows["dim_project"].append({
            "snapshot_id": s, "project_id": pid, "project_code": code, "name": project["name"],
            "company_id": m2o(project.get("company_id")) or 0, "business_unit": bu, "is_internal": internal is not None,
            "hour_category": internal or "PROJECT", "customer_id": m2o(project.get("partner_id")),
            "manager_user_id": m2o(project.get("user_id")),
            "manager_name": (d.get("res.users", m2o(project.get("user_id"))) or {}).get("name"),
            "customer_name": (d.get("res.partner", m2o(project.get("partner_id"))) or {}).get("name"),
            "contract_type": project.get("x_benacta_contract_type") or None,
            "phase": project.get("x_benacta_phase") or None, "date_start": to_date(project.get("date_start")),
            "date_end": to_date(project.get("date")), "analytic_account_id": account_id, "contract_sale_line_id": contract_line,
            "contract_currency": contract_currency, "fixed_rate_per_eur": D(fixed_rate) if fixed_rate else None,
        })

    for tid, task in d.records.get("project.task", {}).items():
        # Subtasks roll up to their parent; Odoo private to-dos have no project and are not work packages.
        if task.get("parent_id") or not m2o(task.get("project_id")):
            continue
        builder.rows["dim_work_package"].append({
            "snapshot_id": s, "task_id": tid, "project_id": m2o(task["project_id"]),
            "wbs_code": task.get("x_benacta_wbs_code") or f"TASK-{tid}", "name": task["name"],
            "allocated_hours": D(task["allocated_hours"]) if task.get("allocated_hours") is not None else None,
            "is_change_order_scope": bool(task.get("x_benacta_change_order")),
        })

    for mid, milestone in d.records.get("project.milestone", {}).items():
        line_id = m2o(milestone.get("sale_line_id"))
        line = d.get("sale.order.line", line_id)
        pct = D(milestone["quantity_percentage"]) if milestone.get("quantity_percentage") is not None else None
        amount = (D(line["price_subtotal"]) * pct).quantize(Decimal("0.01")) if line and pct is not None else None
        if line_id is None:
            builder.issue("MILESTONE_WITHOUT_SALE_LINE", "project.milestone", mid, "milestone billing amount unavailable")
        builder.rows["dim_milestone"].append({
            "snapshot_id": s, "milestone_id": mid, "project_id": m2o(milestone["project_id"]),
            "milestone_code": milestone.get("x_benacta_milestone_code") or None, "name": milestone["name"],
            "deadline": to_date(milestone.get("deadline")), "is_reached": bool(milestone.get("is_reached")),
            "reached_date": to_date(milestone.get("reached_date")), "sale_line_id": line_id, "quantity_percentage": pct,
            "billing_amount": amount,
        })

    jobs = d.records.get("hr.job", {})
    departments = d.records.get("hr.department", {})
    calendars = d.records.get("resource.calendar", {})
    for eid, employee in d.records.get("hr.employee", {}).items():
        job = jobs.get(m2o(employee.get("job_id")), {}).get("name")
        calendar = calendars.get(m2o(employee.get("resource_calendar_id")), {})
        builder.rows["dim_employee"].append({
            "snapshot_id": s, "employee_id": eid, "employee_code": employee.get("x_benacta_employee_code") or f"EMP-{eid}",
            "name": employee["name"], "company_id": m2o(employee.get("company_id")) or 0,
            "department": departments.get(m2o(employee.get("department_id")), {}).get("name"),
            "role": mappings["role_by_job"].get(job), "hourly_cost": D(employee["hourly_cost"]) if employee.get("hourly_cost") is not None else None,
            "is_external": bool(employee.get("x_benacta_is_external")),
            "hours_per_day": D(calendar["hours_per_day"]) if calendar.get("hours_per_day") is not None else None,
        })

    for lid, line in d.records.get("account.analytic.line", {}).items():
        project = m2o(line.get("project_id"))
        if project is None:
            continue  # analytic lines that are not timesheets
        if m2o(line.get("employee_id")) is None:
            builder.issue("TIMESHEET_WITHOUT_EMPLOYEE", "account.analytic.line", lid, "timesheet has no employee")
            continue
        builder.rows["fact_timesheet"].append({
            "snapshot_id": s, "line_id": lid, "entry_date": to_date(line["date"]), "company_id": m2o(line.get("company_id")) or 0,
            "employee_id": m2o(line["employee_id"]), "project_id": project, "task_id": m2o(line.get("task_id")),
            "hours": D(line["unit_amount"]), "cost_amount": -D(line["amount"]),
        })

    categories = {cid: c.get("complete_name") or c.get("name") for cid, c in d.records.get("product.category", {}).items()}

    def cost_category(product_id: int | None) -> str:
        product = d.get("product.product", product_id)
        template = d.get("product.template", m2o(product["product_tmpl_id"])) if product else None
        name = categories.get(m2o(template.get("categ_id"))) if template else None
        return mappings["cost_category_by_product_category"].get(name, mappings["default_cost_category"])

    line_project: dict[int, int | None] = {}
    for pid_line, line in d.records.get("purchase.order.line", {}).items():
        analytic = _main_analytic(line.get("analytic_distribution"))
        project = projects_by_account.get(analytic) if analytic else None
        line_project[pid_line] = project
        if project is None:
            continue  # purchases without project attribution are not project commitments
        order = d.get("purchase.order", m2o(line["order_id"]))
        builder.rows["fact_purchase_commitment"].append({
            "snapshot_id": s, "purchase_line_id": pid_line, "purchase_order_id": m2o(line["order_id"]),
            "order_date": to_date(order["date_order"]) if order else None, "company_id": m2o(order["company_id"]) if order else 0,
            "project_id": project, "work_package": line.get("x_benacta_work_package") or None,
            "supplier_id": m2o(order["partner_id"]) if order else None, "cost_category": cost_category(m2o(line["product_id"])),
            "ordered_quantity": D(line["product_qty"]), "received_quantity": D(line.get("qty_received") or 0),
            "price_unit": D(line["price_unit"]), "ordered_amount": D(line.get("price_subtotal") or D(line["product_qty"]) * D(line["price_unit"])),
        })

    receivable_project: dict[int, int | None] = {}
    for mlid, line in d.records.get("account.move.line", {}).items():
        move = d.get("account.move", m2o(line["move_id"]))
        if move is None or move["state"] != "posted" or line.get("display_type") != "product":
            continue
        if move["move_type"] in ("in_invoice", "in_refund"):
            purchase_line = m2o(line.get("purchase_line_id"))
            analytic_project = projects_by_account.get(_main_analytic(line.get("analytic_distribution")))
            project = line_project.get(purchase_line) if purchase_line else analytic_project
            if purchase_line and analytic_project and project and analytic_project != project:
                builder.issue(
                    "VENDOR_BILL_PROJECT_MISMATCH", "account.move.line", mlid,
                    f"{move['name']} bills a purchase line of {project_code[project]} but is analytically attributed to "
                    f"{project_code[analytic_project]}; cost kept on {project_code[project]}",
                )
            if project is None:
                continue
            builder.rows["fact_vendor_bill_line"].append({
                "snapshot_id": s, "move_line_id": mlid, "move_id": move["id"] if "id" in move else m2o(line["move_id"]),
                "bill_name": move["name"], "move_type": move["move_type"], "accounting_date": to_date(line["date"]),
                "company_id": m2o(line["company_id"]), "project_id": project, "analytic_project_id": analytic_project,
                "purchase_line_id": purchase_line, "cost_category": cost_category(m2o(line.get("product_id"))),
                "quantity": D(line["quantity"]), "amount": D(line["balance"]),
            })
        elif move["move_type"] in ("out_invoice", "out_refund"):
            for sale_line in line.get("sale_line_ids") or []:
                project = contract_line_project.get(sale_line)
                if project is None:
                    so_line = d.get("sale.order.line", sale_line)
                    project = m2o(so_line.get("project_id")) if so_line else None
                if project is not None:
                    receivable_project[m2o(line["move_id"])] = project

    lines_by_move: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for line in d.records.get("account.move.line", {}).values():
        if line.get("display_type") in ("product", "tax"):
            lines_by_move[m2o(line["move_id"])].append(line)
    for move_id, move in d.records.get("account.move", {}).items():
        if move["state"] != "posted" or move["move_type"] not in ("out_invoice", "out_refund"):
            continue
        sign = Decimal(-1) if move["move_type"] == "out_refund" else Decimal(1)
        lines = lines_by_move[move_id]
        products = [line for line in lines if line["display_type"] == "product"]
        untaxed_ccy = sum((D(line["price_subtotal"]) for line in products), Decimal(0))
        if move.get("amount_total") is not None:
            total_ccy = D(move["amount_total"])
        else:
            total_ccy = -sum((D(line["amount_currency"]) for line in lines), Decimal(0)) * sign
        company_untaxed = -sum((D(line["balance"]) for line in products), Decimal(0))
        company_total = -sum((D(line["balance"]) for line in lines), Decimal(0))
        builder.rows["fact_receivable"].append({
            "snapshot_id": s, "invoice_id": move_id, "invoice_name": move["name"], "move_type": move["move_type"],
            "company_id": m2o(move["company_id"]), "project_id": receivable_project.get(move_id),
            "customer_id": m2o(move.get("partner_id")), "invoice_date": to_date(move.get("invoice_date") or move["date"]),
            "due_date": to_date(move.get("invoice_date_due")),
            "currency_code": builder.currency_by_id.get(m2o(move["currency_id"]), {}).get("name", "UNKNOWN"),
            "amount_untaxed_ccy": sign * untaxed_ccy, "amount_total_ccy": sign * total_ccy,
            "amount_untaxed_company": company_untaxed, "amount_total_company": company_total,
        })

    totals = {r["invoice_id"]: r["amount_total_ccy"] for r in builder.rows["fact_receivable"]}
    allocated: dict[int, Decimal] = defaultdict(Decimal)
    for pay_id, payment in sorted(d.records.get("account.payment", {}).items(), key=lambda kv: (kv[1]["date"], kv[0])):
        if payment.get("payment_type") != "inbound" or payment.get("state") not in ("paid", "in_process", "posted"):
            continue
        remaining = D(payment["amount"])
        for invoice_id in payment.get("reconciled_invoice_ids") or []:
            if invoice_id not in totals or remaining <= 0:
                continue
            part = min(remaining, totals[invoice_id] - allocated[invoice_id])
            if part <= 0:
                continue
            allocated[invoice_id] += part
            remaining -= part
            builder.rows["fact_customer_payment"].append({
                "snapshot_id": s, "payment_id": pay_id, "invoice_id": invoice_id, "payment_date": to_date(payment["date"]),
                "company_id": m2o(payment.get("company_id")) or 0,
                "currency_code": builder.currency_by_id.get(m2o(payment.get("currency_id")), {}).get("name", "UNKNOWN"),
                "amount_ccy": part,
            })
        if remaining > 0:
            builder.issue("PAYMENT_NOT_FULLY_ALLOCATED", "account.payment", pay_id, f"{remaining} not matched to an invoice")

    for order_id, order in d.records.get("sale.order", {}).items():
        # amount and contract flag per project referenced by the order's lines
        per_project: dict[int, dict[str, Any]] = {}
        for line_id in order.get("order_line") or []:
            line = d.get("sale.order.line", line_id)
            project = (contract_line_project.get(line_id) or m2o(line.get("project_id"))) if line else None
            if project is None:
                continue
            entry = per_project.setdefault(project, {"amount": Decimal(0), "is_contract": False})
            entry["amount"] += D(line["price_subtotal"])
            entry["is_contract"] = entry["is_contract"] or line_id in contract_line_project
        for project, entry in per_project.items():
            builder.rows["fact_change_order"].append({
                "snapshot_id": s, "sale_order_id": order_id, "project_id": project, "order_name": order["name"],
                "state": order["state"], "order_date": to_date(order["date_order"]), "is_contract": entry["is_contract"],
                "currency_code": builder.currency_by_id.get(m2o(order["currency_id"]), {}).get("name", "UNKNOWN"),
                "amount_untaxed_ccy": entry["amount"],
            })
