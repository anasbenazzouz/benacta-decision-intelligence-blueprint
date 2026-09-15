"""Read-only discovery of a connected Odoo instance.

Checks the candidate mapping in data/mappings/odoo_source_mapping.yml against
the live schema and records what is really there: version, modules, companies,
currencies, rights, volumes, relation tables, accounting and side-effect
configuration. Nothing is inferred when a read fails; the failure is recorded.

No login, API key or personal name is written to the outputs.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from app.config import REPO_ROOT, Settings
from app.connectors.odoo import OdooError, OdooJson2Client, OdooReader
from app.ops.discovery_report import render_markdown

SPEC_PATH = REPO_ROOT / "data" / "mappings" / "odoo_source_mapping.yml"
SNAPSHOT_PATH = REPO_ROOT / "data" / "discovery" / "odoo_discovery_snapshot.json"
REPORT_PATH = REPO_ROOT / "docs" / "odoo_discovery.md"

RELEVANT_MODULES = (
    "account",
    "account_accountant",
    "analytic",
    "sale",
    "sale_management",
    "sale_stock",
    "sale_margin",
    "purchase",
    "purchase_stock",
    "stock",
    "stock_account",
    "delivery",
    "uom",
    "currency_rate_live",
    "base_automation",
    "mrp",
    "account_peppol",
    "l10n_fr_pdp",
    "account_edi_ubl_cii",
    "ai",
    "ai_mcp",
    "saas_trial",
)
ACCESS_OPERATIONS = ("read", "create", "write", "unlink")
CARDINALITY = {"many2one": "N:1", "one2many": "1:N", "many2many": "M:N"}


def _attempt(fn: Callable[[], Any]) -> dict[str, Any]:
    try:
        return {"status": "OK", "value": fn()}
    except OdooError as exc:
        status = "ACCESS_DENIED" if exc.access_denied else "NOT_FOUND" if exc.not_found else "ERROR"
        return {"status": status, "error": f"{exc.name}: {exc.message[:200]}"}


def load_spec(path: Path = SPEC_PATH) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def collect(reader: OdooReader, settings: Settings, spec: dict[str, Any]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_instance": settings.odoo_source_instance,
        "method": "Odoo JSON-2 external API, read-only allowlist",
    }

    version = reader.version()
    snapshot["server"] = {
        "version": version.get("version"),
        "version_info": version.get("version_info"),
        "edition": "enterprise" if str(version.get("version", "")).endswith("+e") else "community",
    }

    snapshot["modules"] = _modules(reader)
    snapshot["companies"] = _companies(reader)
    snapshot["currencies"] = _attempt(
        lambda: reader.search_read(
            "res.currency", [["active", "=", True]], ["name", "decimal_places", "rounding"], order="name"
        )
    )
    snapshot["api_user"] = _api_user(reader, settings)

    existing = _existing_models(reader, list(spec["models"]))
    snapshot["models"] = {
        model: _model(reader, model, model_spec, model in existing) for model, model_spec in spec["models"].items()
    }
    snapshot["relation_tables"] = _relation_tables(reader, sorted(existing))
    snapshot["volumes"] = _volumes(reader, existing)
    snapshot["accounting"] = _accounting(reader)
    snapshot["side_effects"] = _side_effects(reader, snapshot["modules"])
    return snapshot


def _modules(reader: OdooReader) -> dict[str, Any]:
    result = _attempt(lambda: reader.search_read("ir.module.module", [["state", "=", "installed"]], ["name"]))
    if result["status"] != "OK":
        return result
    installed = {row["name"] for row in result["value"]}
    return {
        "status": "OK",
        "installed_count": len(installed),
        "relevant": {name: name in installed for name in RELEVANT_MODULES},
        "installed": sorted(installed),
    }


def _companies(reader: OdooReader) -> dict[str, Any]:
    fields = _attempt(lambda: reader.fields_get("res.company", ["type"]))
    extra = []
    if fields["status"] == "OK":
        extra = sorted(
            name for name in fields["value"] if "lock_date" in name or ("peppol" in name and "state" in name)
        )
    return _attempt(
        lambda: reader.search_read(
            "res.company", [], ["name", "currency_id", "country_id", "parent_id", *extra], order="id"
        )
    )


def _api_user(reader: OdooReader, settings: Settings) -> dict[str, Any]:
    result = _attempt(
        lambda: reader.search_read(
            "res.users",
            [["login", "=", settings.odoo_username]],
            ["tz", "lang", "company_id", "company_ids", "share", "group_ids"],
        )
    )
    if result["status"] != "OK" or not result["value"]:
        return result if result["status"] != "OK" else {"status": "NOT_FOUND"}
    user = result["value"][0]
    groups = _attempt(lambda: reader.search_read("res.groups", [["id", "in", user["group_ids"]]], ["display_name"]))
    return {
        "status": "OK",
        "user_id": user["id"],
        "tz": user["tz"],
        "lang": user["lang"],
        "company_id": user["company_id"],
        "company_ids": user["company_ids"],
        "share": user["share"],
        "groups": sorted(g["display_name"] for g in groups.get("value", [])),
    }


def _existing_models(reader: OdooReader, models: list[str]) -> set[str]:
    rows = reader.search_read("ir.model", [["model", "in", models]], ["model"])
    return {row["model"] for row in rows}


def _model(reader: OdooReader, model: str, model_spec: dict[str, Any], exists: bool) -> dict[str, Any]:
    fields_spec = model_spec.get("fields", {})
    if not exists:
        return {
            "status": "MODEL_MISSING",
            "meaning": model_spec.get("meaning"),
            "fields": {name: {**spec, "status": "MODEL_MISSING"} for name, spec in fields_spec.items()},
        }

    access = {op: _attempt(lambda op=op: reader.has_access(model, op)) for op in ACCESS_OPERATIONS}
    described = _attempt(
        lambda: reader.fields_get(model, ["type", "string", "relation", "store", "required", "readonly"])
    )
    live_fields = described.get("value", {})
    fields = {}
    for name, spec in fields_spec.items():
        live = live_fields.get(name)
        if described["status"] != "OK":
            fields[name] = {**spec, "status": described["status"]}
        elif live is None:
            fields[name] = {**spec, "status": "MISSING"}
        else:
            fields[name] = {
                **spec,
                "status": "AVAILABLE",
                "type": live.get("type"),
                "label": live.get("string"),
                "relation": live.get("relation") or None,
                "cardinality": CARDINALITY.get(live.get("type"), "attribute"),
                "stored": live.get("store"),
            }

    count = _attempt(lambda: reader.search_count(model, []))
    write_range = {}
    if "write_date" in live_fields:
        write_range = _range(reader, model, "write_date")
    return {
        "status": "OK",
        "meaning": model_spec.get("meaning"),
        "access": {op: result.get("value", result["status"]) for op, result in access.items()},
        "record_count": count.get("value", count["status"]),
        "write_date_range": write_range,
        "field_count": len(live_fields),
        "fields": fields,
    }


def _range(reader: OdooReader, model: str, field: str, domain: list | None = None) -> dict[str, Any]:
    domain = [*(domain or []), [field, "!=", False]]

    def edge(direction: str) -> Any:
        rows = reader.search_read(model, domain, [field], order=f"{field} {direction}", limit=1)
        return rows[0][field] if rows else None

    first = _attempt(lambda: edge("asc"))
    last = _attempt(lambda: edge("desc"))
    return {"min": first.get("value", first["status"]), "max": last.get("value", last["status"])}


def _relation_tables(reader: OdooReader, models: list[str]) -> dict[str, Any]:
    return _attempt(
        lambda: reader.search_read(
            "ir.model.fields",
            [["model", "in", models], ["ttype", "=", "many2many"], ["store", "=", True]],
            ["model", "name", "relation", "relation_table", "column1", "column2"],
            order="model, name",
        )
    )


def _volumes(reader: OdooReader, existing: set[str]) -> dict[str, Any]:
    volumes: dict[str, Any] = {}
    if "account.move" in existing:
        by_type = {}
        for move_type in ("out_invoice", "out_refund", "in_invoice", "in_refund", "entry"):
            by_type[move_type] = {
                state: _attempt(
                    lambda t=move_type, s=state: reader.search_count(
                        "account.move", [["move_type", "=", t], ["state", "=", s]]
                    )
                ).get("value")
                for state in ("draft", "posted", "cancel")
            }
        volumes["account_move_by_type_state"] = by_type
        volumes["invoice_date_range"] = _range(reader, "account.move", "invoice_date", [["state", "=", "posted"]])
    if "sale.order" in existing:
        volumes["sale_order_by_state"] = {
            state: _attempt(lambda s=state: reader.search_count("sale.order", [["state", "=", s]])).get("value")
            for state in ("draft", "sent", "sale", "cancel")
        }
        volumes["sale_order_date_range"] = _range(reader, "sale.order", "date_order")
    if "stock.move" in existing:
        # is_valued and remaining_value are computed, not stored: they cannot be filtered on.
        volumes["stock_move_by_state"] = {
            state: _attempt(lambda s=state: reader.search_count("stock.move", [["state", "=", s]])).get("value")
            for state in ("draft", "confirmed", "assigned", "done", "cancel")
        }
        volumes["stock_move_with_value"] = _attempt(
            lambda: reader.search_count("stock.move", [["value", "!=", 0]])
        ).get("value")
    if "account.move.line" in existing:
        volumes["posted_cogs_lines"] = _attempt(
            lambda: reader.search_count(
                "account.move.line", [["display_type", "=", "cogs"], ["parent_state", "=", "posted"]]
            )
        ).get("value")
    if "product.template" in existing:
        volumes["storable_products"] = _attempt(
            lambda: reader.search_count("product.template", [["is_storable", "=", True]])
        ).get("value")
    return volumes


def _accounting(reader: OdooReader) -> dict[str, Any]:
    return {
        "journals": _attempt(
            lambda: reader.search_read(
                "account.journal", [], ["name", "code", "type", "company_id", "currency_id"], order="company_id, code"
            )
        ),
        "payment_method_lines": _attempt(
            lambda: reader.search_read(
                "account.payment.method.line",
                [],
                ["name", "journal_id", "payment_type", "payment_account_id"],
                order="journal_id, payment_type",
            )
        ),
        "sale_purchase_taxes": _attempt(
            lambda: reader.search_read(
                "account.tax",
                [["type_tax_use", "in", ["sale", "purchase"]]],
                ["name", "type_tax_use", "amount_type", "amount", "company_id"],
                order="company_id, type_tax_use, amount",
            )
        ),
        "product_categories": _attempt(
            lambda: reader.search_read(
                "product.category", [], ["complete_name", "property_cost_method", "property_valuation"], order="id"
            )
        ),
    }


def _side_effects(reader: OdooReader, modules: dict[str, Any]) -> dict[str, Any]:
    relevant = modules.get("relevant", {})
    return {
        "active_crons": _attempt(
            lambda: sorted(
                row["cron_name"] for row in reader.search_read("ir.cron", [["active", "=", True]], ["cron_name"])
            )
        ),
        "outgoing_mail_servers": _attempt(lambda: reader.search_count("ir.mail_server", [])),
        "base_automation_installed": relevant.get("base_automation"),
        "e_invoicing_modules_installed": {
            name: relevant.get(name) for name in ("account_peppol", "l10n_fr_pdp", "account_edi_ubl_cii")
        },
    }


def write_outputs(snapshot: dict[str, Any]) -> tuple[Path, Path]:
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    REPORT_PATH.write_text(render_markdown(snapshot), encoding="utf-8")
    return SNAPSHOT_PATH, REPORT_PATH


def run(settings: Settings) -> tuple[Path, Path]:
    with OdooJson2Client.from_settings(settings) as client:
        snapshot = collect(OdooReader(client), settings, load_spec())
    return write_outputs(snapshot)
