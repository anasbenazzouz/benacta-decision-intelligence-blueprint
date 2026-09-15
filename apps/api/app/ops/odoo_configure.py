"""Instance configuration authorised by the owner: modules, currencies and BENACTA extension fields.

Without `--confirm` the command only reads and prints what it would change. Every change is idempotent (already
installed, active or present is skipped) and recorded in the audit journal. Business data is never written here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.audit.log import append_event
from app.config import Settings
from app.connectors.guards import odoo_write_guard
from app.connectors.odoo import OdooJson2Client, OdooReader, OdooWriter
from app.db import migrate
from app.db.engine import analytics_engine

# Owner decisions of 2026-09-15 (ADR-0005). Extend only with a new decision.
MODULES = ("hr_timesheet",)
CURRENCIES = ("USD",)
EXTENSION_FIELDS: tuple[tuple[str, str, str, str], ...] = (
    ("project.project", "x_benacta_contract_type", "char", "BENACTA contract type"),
    ("project.project", "x_benacta_phase", "char", "BENACTA project phase"),
    ("project.project", "x_benacta_fixed_rate_per_eur", "float", "BENACTA fixed project rate per EUR"),
    ("project.task", "x_benacta_wbs_code", "char", "BENACTA WBS code"),
    ("project.task", "x_benacta_change_order", "boolean", "BENACTA change order scope"),
    ("project.milestone", "x_benacta_milestone_code", "char", "BENACTA milestone code"),
    ("hr.employee", "x_benacta_employee_code", "char", "BENACTA employee code"),
    ("hr.employee", "x_benacta_is_external", "boolean", "BENACTA external resource"),
    ("purchase.order.line", "x_benacta_work_package", "char", "BENACTA work package"),
)
INSTALL_TIMEOUT_SECONDS = 900.0


@dataclass
class Change:
    kind: str
    target: str
    state: str  # PRESENT, TO_APPLY, APPLIED


def _company_exists(reader: OdooReader, settings: Settings) -> bool | None:
    if not settings.odoo_sandbox_company:
        return None
    return bool(reader.search_count("res.company", [["name", "=", settings.odoo_sandbox_company]]))


def _pending(reader: OdooReader) -> list[Change]:
    changes: list[Change] = []
    states = {m["name"]: m["state"] for m in reader.search_read("ir.module.module", [["name", "in", list(MODULES)]], ["name", "state"])}
    for module in MODULES:
        if module not in states:
            raise RuntimeError(f"module {module} is not available on this instance")
        changes.append(Change("module", module, "PRESENT" if states[module] == "installed" else "TO_APPLY"))
    active = {c["name"]: c["active"] for c in reader.search_read(
        "res.currency", [["name", "in", list(CURRENCIES)]], ["name", "active"], context={"active_test": False})}
    for code in CURRENCIES:
        changes.append(Change("currency", code, "PRESENT" if active.get(code) else "TO_APPLY"))
    existing = {(f["model"], f["name"]) for f in reader.search_read(
        "ir.model.fields", [["name", "=like", "x_benacta_%"]], ["model", "name"])}
    for model, name, _ttype, _label in EXTENSION_FIELDS:
        changes.append(Change("field", f"{model}.{name}", "PRESENT" if (model, name) in existing else "TO_APPLY"))
    return changes


def _apply(writer: OdooWriter, reader: OdooReader, change: Change) -> dict[str, Any]:
    if change.kind == "module":
        ids = [m["id"] for m in reader.search_read("ir.module.module", [["name", "=", change.target]], ["id"])]
        writer.call("ir.module.module", "button_immediate_install", ids=ids)
        state = reader.search_read("ir.module.module", [["id", "in", ids]], ["state"])[0]["state"]
        if state != "installed":
            raise RuntimeError(f"{change.target} is {state} after installation")
        return {"module": change.target, "state": state}
    if change.kind == "currency":
        ids = [c["id"] for c in reader.search_read("res.currency", [["name", "=", change.target]], ["id"], context={"active_test": False})]
        writer.write("res.currency", ids, {"active": True})
        return {"currency": change.target, "active": True}
    model, name = change.target.rsplit(".", 1)
    _model, _name, ttype, label = next(f for f in EXTENSION_FIELDS if f[0] == model and f[1] == name)
    model_id = reader.search_read("ir.model", [["model", "=", model]], ["id"])[0]["id"]
    [field_id] = writer.create("ir.model.fields", [{
        "model_id": model_id, "name": name, "field_description": label, "ttype": ttype, "state": "manual", "store": True,
    }])
    return {"field": change.target, "ttype": ttype, "field_id": field_id}


def run(settings: Settings, *, confirm: bool) -> int:
    with OdooJson2Client.from_settings(settings, max_retries=0) as client:
        reader = OdooReader(client)
        changes = _pending(reader)
        guard = odoo_write_guard(settings, sandbox_company_exists=_company_exists(reader, settings), require_backup=False)
        print(f"Odoo configuration for {settings.odoo_target} ({'apply' if confirm else 'dry run, nothing written'})")
        for change in changes:
            print(f"  {change.state:9} {change.kind:8} {change.target}")
        to_apply = [c for c in changes if c.state == "TO_APPLY"]
        if not to_apply:
            print("Nothing to change.")
            return 0
        if not confirm:
            print("Run again with --confirm to apply.")
            return 0
        if not guard.allowed:
            print("Refused by the configuration guard. Nothing was written.")
            for check in guard.checks:
                print(f"  [{'x' if check.passed else ' '}] {check.name}: {check.detail}")
            return 2

    # Module installation reloads the registry and can take minutes: a dedicated client with a long timeout.
    with OdooJson2Client.from_settings(settings, max_retries=0) as client:
        client._http.timeout = INSTALL_TIMEOUT_SECONDS  # noqa: SLF001 local override for this command only
        reader, writer = OdooReader(client), OdooWriter(client, guard)
        engine = analytics_engine(settings)
        try:
            migrate.upgrade(engine)
            for change in to_apply:
                detail = _apply(writer, reader, change)
                change.state = "APPLIED"
                with engine.begin() as conn:
                    append_event(conn, actor="owner-authorised:odoo-configure", action=f"odoo.configure_{change.kind}",
                                 object_type="odoo_instance", object_id=settings.odoo_target or "unknown", payload=detail)
                print(f"  APPLIED   {change.kind:8} {change.target}")
        finally:
            engine.dispose()
    return 0
