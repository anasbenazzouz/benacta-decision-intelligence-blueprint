"""Render the discovery snapshot as docs/odoo_discovery.md.

Findings are derived from the snapshot by explicit rules, so the report can
be regenerated and diffed after every discovery run.
"""

from __future__ import annotations

from typing import Any


def _cell(value: Any) -> str:
    if value is None or value is False:
        return ""
    if isinstance(value, list):
        if len(value) == 2 and isinstance(value[0], int):
            return str(value[1])
        return ", ".join(str(v) for v in value)
    return str(value).replace("|", "\\|")


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(_cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def _value(section: dict[str, Any]) -> Any:
    return section.get("value") if section.get("status") == "OK" else None


def findings(snapshot: dict[str, Any]) -> list[tuple[str, str]]:
    """(finding, design consequence) pairs."""
    out: list[tuple[str, str]] = []
    models = snapshot["models"]
    volumes = snapshot["volumes"]

    if models.get("stock.valuation.layer", {}).get("status") == "MODEL_MISSING":
        out.append(
            (
                "`stock.valuation.layer` does not exist on this version.",
                "Cost attribution reads valuation from `stock.move` (`value`, `price_unit`, `account_move_id`). "
                "No adapter may assume the Odoo 13 to 18 layer model.",
            )
        )
    if models.get("delivery.carrier", {}).get("status") == "MODEL_MISSING":
        out.append(
            (
                "The `delivery` module is not installed (`delivery.carrier` missing).",
                "FREIGHT-001 is modelled at order and delivery level with a rebillable freight service product "
                "and a contract clause. Installing `delivery` requires explicit approval.",
            )
        )
    purchase_price = models.get("sale.order.line", {}).get("fields", {}).get("purchase_price", {})
    if purchase_price.get("status") == "MISSING":
        out.append(
            (
                "`sale.order.line.purchase_price` is absent (`sale_margin` not installed).",
                "There is no line-level cost snapshot in Odoo. Realised cost must come from valued stock moves, "
                "otherwise the result is UNDETERMINED.",
            )
        )
    categories = _value(snapshot["accounting"]["product_categories"]) or []
    if categories and all(c.get("property_valuation") != "real_time" for c in categories):
        methods = sorted({f"{c.get('property_cost_method')}/{c.get('property_valuation')}" for c in categories})
        out.append(
            (
                f"No product category uses perpetual valuation (observed: {', '.join(methods)}).",
                "Existing data produces no valuation entries. The sandbox company needs its own category "
                "configuration; existing categories are not modified.",
            )
        )
    if volumes.get("storable_products") == 0:
        out.append(
            (
                "No product is storable (`is_storable` false everywhere).",
                "Existing orders generate no valued deliveries. COST-001 cannot be demonstrated on existing data.",
            )
        )
    if volumes.get("posted_cogs_lines") == 0:
        out.append(
            (
                "No posted COGS journal item exists.",
                "Gross margin on existing data can only be a management proxy, never a reconciled closing margin.",
            )
        )
    lines = _value(snapshot["accounting"]["payment_method_lines"]) or []
    if lines and all(not line.get("payment_account_id") for line in lines):
        out.append(
            (
                "No payment method line has an outstanding account.",
                "Payments create no journal entry and invoices stay `in_payment` until bank reconciliation. "
                "This is standard Odoo 18+ behaviour, not a platform fault.",
            )
        )
    companies = _value(snapshot["companies"]) or []
    if len(companies) == 1:
        out.append(
            (
                f"A single company exists ({companies[0]['name']}).",
                "No sandbox company exists yet, so the Odoo write guard blocks every seed.",
            )
        )
    currencies = _value(snapshot["currencies"]) or []
    if len(currencies) == 1:
        out.append(
            (
                f"One active currency ({currencies[0]['name']}); no dated exchange rates.",
                "The foreign currency negative control runs in fixtures until a currency is authorised in the sandbox.",
            )
        )
    groups = snapshot["api_user"].get("groups", [])
    if any(g.endswith("/ Administrator") for g in groups):
        out.append(
            (
                "The API key belongs to a user with administrator groups.",
                "Acceptable for discovery. Before automated ingestion, a dedicated bot user with read-only rights "
                "should own the ingestion key.",
            )
        )
    if snapshot["side_effects"].get("outgoing_mail_servers", {}).get("value") == 0:
        out.append(
            (
                "No custom outgoing mail server is configured.",
                "Odoo Online can still send mail through its default service. Seeds must disable tracking and "
                "notifications and must use non-deliverable partner addresses.",
            )
        )
    if any(snapshot["side_effects"].get("e_invoicing_modules_installed", {}).values()):
        states = sorted({str(c.get("account_peppol_proxy_state")) for c in companies})
        out.append(
            (
                f"E-invoicing modules are installed (Peppol proxy state: {', '.join(states)}).",
                "The seed must verify the sandbox company is not registered for e-invoicing before posting invoices.",
            )
        )
    out.append(
        (
            "Direct PostgreSQL access is not offered by Odoo Online.",
            "ODOO_READ_DSN stays unset; ingestion uses the JSON-2 read adapter.",
        )
    )
    return out


def render_markdown(snapshot: dict[str, Any]) -> str:
    server = snapshot["server"]
    parts = [
        "# Odoo discovery",
        "",
        f"Generated by `benacta discover-odoo` at {snapshot['generated_at']} (UTC) on source instance "
        f"`{snapshot['source_instance']}`.",
        f"Method: {snapshot['method']}. Nothing was written to Odoo. Regenerate rather than edit.",
        "",
        "Machine-readable result: `data/discovery/odoo_discovery_snapshot.json`. "
        "Candidate mapping: `data/mappings/odoo_source_mapping.yml`.",
        "",
        "## 1. Findings that shape the design",
        "",
        _table(["Observed", "Consequence"], [list(f) for f in findings(snapshot)]),
        "",
        "## 2. Server",
        "",
        _table(["Version", "Edition"], [[server["version"], server["edition"]]]),
        "",
        "## 3. Companies, currencies, API user",
        "",
    ]

    companies = _value(snapshot["companies"]) or []
    parts += [
        _table(
            ["id", "Company", "Currency", "Country", "Peppol state", "Fiscal year lock"],
            [
                [
                    c["id"],
                    c["name"],
                    c["currency_id"],
                    c["country_id"],
                    c.get("account_peppol_proxy_state"),
                    c.get("fiscalyear_lock_date") or "none",
                ]
                for c in companies
            ],
        ),
        "",
        _table(
            ["Active currency", "Decimal places"],
            [[c["name"], c["decimal_places"]] for c in _value(snapshot["currencies"]) or []],
        ),
        "",
    ]
    user = snapshot["api_user"]
    if user.get("status") == "OK":
        parts += [
            _table(
                ["API user id", "Timezone", "Language", "Allowed companies", "Portal user"],
                [[user["user_id"], user["tz"], user["lang"], user["company_ids"], "yes" if user["share"] else "no"]],
            ),
            "",
            f"Groups: {', '.join(user['groups'])}.",
            "",
        ]
    else:
        parts += [f"API user: {user.get('status')}", ""]

    modules = snapshot["modules"]
    parts += ["## 4. Modules", ""]
    if modules.get("status") == "OK":
        parts += [
            f"{modules['installed_count']} modules installed. Relevant to this journey:",
            "",
            _table(
                ["Module", "Installed"], [[name, "yes" if ok else "no"] for name, ok in modules["relevant"].items()]
            ),
            "",
        ]
    else:
        parts += [f"Module list: {modules.get('status')}", ""]

    volumes = snapshot["volumes"]
    parts += ["## 5. Volumes and date ranges", ""]
    by_type = volumes.get("account_move_by_type_state", {})
    parts += [
        _table(
            ["move_type", "draft", "posted", "cancel"],
            [[t, s.get("draft"), s.get("posted"), s.get("cancel")] for t, s in by_type.items()],
        ),
        "",
        _table(
            ["Measure", "Value"],
            [
                [
                    "Posted invoice dates",
                    f"{volumes.get('invoice_date_range', {}).get('min')} to {volumes.get('invoice_date_range', {}).get('max')}",
                ],
                [
                    "Sale order dates",
                    f"{volumes.get('sale_order_date_range', {}).get('min')} to {volumes.get('sale_order_date_range', {}).get('max')}",
                ],
                ["Sale orders by state", volumes.get("sale_order_by_state")],
                ["Stock moves by state", volumes.get("stock_move_by_state")],
                ["Stock moves with a non-zero value", volumes.get("stock_move_with_value")],
                ["Posted COGS journal items", volumes.get("posted_cogs_lines")],
                ["Storable product templates", volumes.get("storable_products")],
            ],
        ),
        "",
        "## 6. Model coverage",
        "",
    ]

    coverage = []
    for model, data in snapshot["models"].items():
        fields = data["fields"]
        available = sum(1 for f in fields.values() if f["status"] == "AVAILABLE")
        access = data.get("access") or {}
        coverage.append(
            [
                f"`{model}`",
                data["status"],
                data.get("record_count"),
                "/".join("y" if access.get(op) is True else "n" for op in ("read", "create", "write", "unlink"))
                if access
                else "",
                f"{available}/{len(fields)}",
            ]
        )
    parts += [
        _table(["Model", "Status", "Records", "Access r/c/w/u", "Mapped fields available"], coverage),
        "",
        "Access is the API user's model-level right, checked with `has_access`. Record rules can still restrict rows.",
        "",
        "## 7. Field mapping",
        "",
    ]
    for model, data in snapshot["models"].items():
        parts += [f"### `{model}`", "", data.get("meaning") or "", ""]
        rows = [
            [
                f"`{name}`",
                f["role"],
                f["status"],
                f.get("type"),
                f.get("cardinality"),
                f.get("relation"),
                f.get("meaning"),
                f.get("needed_for"),
            ]
            for name, f in data["fields"].items()
        ]
        parts += [
            _table(["Field", "Role", "Status", "Type", "Cardinality", "Relation", "Meaning", "Needed for"], rows),
            "",
        ]

    bridges = {
        (m, n) for m, d in snapshot["models"].items() for n, f in d["fields"].items() if f.get("role") == "bridge"
    }
    relations = [r for r in _value(snapshot["relation_tables"]) or [] if (r["model"], r["name"]) in bridges]
    parts += [
        "## 8. Relation tables behind mapped bridges",
        "",
        "Only stored many-to-many fields have a relation table. One-to-many bridges are resolved through the child's foreign key.",
        "",
        _table(
            ["Model", "Field", "Relation", "Table", "column1", "column2"],
            [
                [f"`{r['model']}`", r["name"], r["relation"], f"`{r['relation_table']}`", r["column1"], r["column2"]]
                for r in relations
            ],
        ),
        "",
        "## 9. Accounting configuration (read only, never modified by BENACTA)",
        "",
    ]
    accounting = snapshot["accounting"]
    parts += [
        _table(
            ["Journal", "Code", "Type", "Company"],
            [[j["name"], j["code"], j["type"], j["company_id"]] for j in _value(accounting["journals"]) or []],
        ),
        "",
        _table(
            ["Payment method line", "Journal", "Direction", "Outstanding account"],
            [
                [p["name"], p["journal_id"], p["payment_type"], p["payment_account_id"] or "none"]
                for p in _value(accounting["payment_method_lines"]) or []
            ],
        ),
        "",
        _table(
            ["Product category", "Costing method", "Valuation"],
            [
                [c["complete_name"], c["property_cost_method"], c["property_valuation"]]
                for c in _value(accounting["product_categories"]) or []
            ],
        ),
        "",
        f"Sale and purchase taxes configured: {len(_value(accounting['sale_purchase_taxes']) or [])}.",
        "",
        "## 10. Side effects to neutralise before any seed",
        "",
    ]
    side = snapshot["side_effects"]
    crons = _value(side["active_crons"]) or []
    parts += [
        _table(
            ["Check", "Observed"],
            [
                ["Custom outgoing mail servers", _value(side["outgoing_mail_servers"])],
                ["base_automation installed", "yes" if side["base_automation_installed"] else "no"],
                [
                    "E-invoicing modules",
                    ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in side["e_invoicing_modules_installed"].items()),
                ],
                ["Active scheduled actions", len(crons)],
            ],
        ),
        "",
        "<details><summary>Active scheduled actions</summary>",
        "",
        *[f"- {name}" for name in crons],
        "",
        "</details>",
        "",
    ]
    return "\n".join(parts)
