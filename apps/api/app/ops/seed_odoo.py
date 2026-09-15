"""Odoo seed planning. The dry run reads Odoo and writes nothing.

The plan maps the deterministic demo dataset to Odoo business operations in
order, with stable external identifiers under the `benacta_demo` module so a
replay skips what already exists. It also lists the prerequisites that would
change shared configuration and therefore need an explicit decision.

`seed_odoo` evaluates the write guard first. The executor ships only once a
sandbox company and an attested backup exist, so it can be verified on a real
run instead of being delivered untested.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import REPO_ROOT, Settings
from app.connectors.guards import GuardReport, odoo_write_guard
from app.connectors.odoo import OdooJson2Client, OdooReader
from app.fixtures.demo_dataset import COMPANY, build_demo_dataset

XMLID_MODULE = "benacta_demo"
REQUIRED_MODULES = ("sale_management", "sale_stock", "purchase_stock", "stock_account", "account_accountant")
PLAN_DIR = REPO_ROOT / ".benacta" / "seed_plans"

# Order matters: each step only references objects created by earlier steps.
OPERATIONS: tuple[tuple[str, str], ...] = (
    ("res.company", "create the fictional company, then load the French chart of accounts for it"),
    ("res.currency.rate", "create company-specific USD rates (requires USD active)"),
    ("product.category", "create categories; set FIFO and perpetual valuation for the sandbox company only"),
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
    dozens = reader.search_read("uom.uom", [["name", "=", "Dozens"]], ["factor"])
    checks.append(
        {
            "check": "unit of measure 'Dozens' exists (global setting)",
            "ok": bool(dozens),
            "decision_needed": not dozens,
            "note": "creating a unit changes shared configuration; otherwise NEG-06 stays fixture-only",
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
            "Stock validation dates: Odoo stamps validation time; historical dating of deliveries must be confirmed on the sandbox.",
            "Perpetual valuation posts COGS at invoicing on Odoo 19; the value sign on outgoing moves is verified on the first run.",
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


def dry_run(settings: Settings) -> int:
    with OdooJson2Client.from_settings(settings) as client:
        plan = build_plan(OdooReader(client), settings)
    print_plan(plan)
    path = write_plan(plan)
    print(f"\nPlan written to {path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path}")
    return 0


def seed(settings: Settings) -> int:
    with OdooJson2Client.from_settings(settings) as client:
        reader = OdooReader(client)
        _prerequisite_checks, company_exists = _prerequisites(reader, settings)
    guard = odoo_write_guard(settings, sandbox_company_exists=company_exists)
    if not guard.allowed:
        print("Seed refused by the write guard. Nothing was written.")
        for check in guard.checks:
            print(f"  [{'x' if check.passed else ' '}] {check.name}: {check.detail}")
        return 2
    print("Write guard passed, but the seed executor is not part of this delivery yet: nothing was written.")
    print("Run seed-odoo-dry-run and review the plan; the executor is built and verified on this sandbox next.")
    return 3
