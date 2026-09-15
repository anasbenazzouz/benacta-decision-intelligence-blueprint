from __future__ import annotations

from typing import Any

from app.connectors.odoo import OdooError, ReadOnlyViolation
from app.ops import discover_odoo
from app.ops.discovery_report import findings, render_markdown
from tests.conftest import make_settings

SPEC = {
    "schema_version": 1,
    "models": {
        "sale.order.line": {
            "meaning": "Order line",
            "fields": {
                "id": {"role": "pk"},
                "invoice_lines": {"role": "bridge"},
                "purchase_price": {"role": "measure", "needed_for": ["COST-001"]},
            },
        },
        "stock.valuation.layer": {"meaning": "Legacy layers", "fields": {"value": {"role": "measure"}}},
    },
}


class FakeReader:
    """In-memory stand-in for OdooReader with the same read-only surface."""

    def version(self) -> dict[str, Any]:
        return {"version": "saas~19.4+e", "version_info": ["saas~19", 4, 0, "final", 0, "e"]}

    def call(self, model: str, method: str, **kwargs: Any) -> Any:
        raise ReadOnlyViolation(method)

    def fields_get(self, model: str, attributes: list[str]) -> dict[str, Any]:
        if model == "res.company":
            return {"name": {}, "fiscalyear_lock_date": {}, "account_peppol_proxy_state": {}}
        return {
            "id": {"type": "integer", "string": "ID", "store": True},
            "invoice_lines": {
                "type": "many2many",
                "string": "Invoice Lines",
                "relation": "account.move.line",
                "store": True,
            },
            "write_date": {"type": "datetime", "string": "Last Updated", "store": True},
        }

    def has_access(self, model: str, operation: str) -> bool:
        return operation == "read"

    def search_count(self, model: str, domain: list) -> int:
        return 0 if model in {"account.move.line", "product.template"} else 3

    def search_read(self, model, domain, fields, order=None, limit=None, offset=0, context=None):
        if model == "ir.module.module":
            return [{"name": "sale"}, {"name": "account"}, {"name": "account_peppol"}]
        if model == "res.company":
            return [
                {
                    "id": 1,
                    "name": "Benacta",
                    "currency_id": [1, "EUR"],
                    "country_id": [75, "France"],
                    "parent_id": False,
                    "fiscalyear_lock_date": False,
                    "account_peppol_proxy_state": "not_registered",
                }
            ]
        if model == "res.currency":
            return [{"id": 1, "name": "EUR", "decimal_places": 2, "rounding": 0.01}]
        if model == "res.users":
            return [
                {
                    "id": 2,
                    "tz": "Europe/Paris",
                    "lang": "en_US",
                    "company_id": [1, "Benacta"],
                    "company_ids": [1],
                    "share": False,
                    "group_ids": [10],
                }
            ]
        if model == "res.groups":
            return [{"id": 10, "display_name": "Sales / Administrator"}]
        if model == "ir.model":
            return [{"model": "sale.order.line"}]
        if model == "ir.model.fields":
            return [
                {
                    "model": "sale.order.line",
                    "name": "invoice_lines",
                    "relation": "account.move.line",
                    "relation_table": "sale_order_line_invoice_rel",
                    "column1": "order_line_id",
                    "column2": "invoice_line_id",
                }
            ]
        if model == "account.payment.method.line":
            return [
                {
                    "name": "Manual Payment",
                    "journal_id": [14, "Bank"],
                    "payment_type": "inbound",
                    "payment_account_id": False,
                }
            ]
        if model == "product.category":
            return [{"complete_name": "Goods", "property_cost_method": "standard", "property_valuation": "periodic"}]
        if model == "ir.cron":
            raise OdooError(403, "odoo.exceptions.AccessError", "denied", model, "search_read")
        if model == "ir.mail_server":
            return []
        if limit == 1:
            return [{fields[0]: "2026-01-01"}]
        return []


def _snapshot():
    settings = make_settings(odoo_username="bot@example.invalid", odoo_api_key="secret-key-xyz")
    return discover_odoo.collect(FakeReader(), settings, SPEC)


def test_fields_are_verified_against_the_live_schema_not_assumed():
    fields = _snapshot()["models"]["sale.order.line"]["fields"]
    assert fields["invoice_lines"]["status"] == "AVAILABLE"
    assert fields["invoice_lines"]["cardinality"] == "M:N"
    assert fields["invoice_lines"]["relation"] == "account.move.line"
    assert fields["purchase_price"]["status"] == "MISSING"
    assert fields["purchase_price"]["needed_for"] == ["COST-001"]


def test_missing_model_is_recorded_for_every_field():
    model = _snapshot()["models"]["stock.valuation.layer"]
    assert model["status"] == "MODEL_MISSING"
    assert model["fields"]["value"]["status"] == "MODEL_MISSING"


def test_access_rights_and_denied_reads_are_recorded_not_raised():
    snapshot = _snapshot()
    assert snapshot["models"]["sale.order.line"]["access"] == {
        "read": True,
        "create": False,
        "write": False,
        "unlink": False,
    }
    assert snapshot["side_effects"]["active_crons"]["status"] == "ACCESS_DENIED"


def test_snapshot_and_report_contain_no_login_or_key():
    snapshot = _snapshot()
    text = repr(snapshot) + render_markdown(snapshot)
    assert "bot@example.invalid" not in text
    assert "secret-key-xyz" not in text


def test_findings_derive_design_consequences_from_observations():
    observed = " ".join(f for f, _ in findings(_snapshot()))
    assert "`stock.valuation.layer` does not exist" in observed
    assert "`sale_margin` not installed" in observed
    assert "No product category uses perpetual valuation" in observed
    assert "No payment method line has an outstanding account" in observed
    assert "A single company exists" in observed
    assert "administrator groups" in observed
    assert "E-invoicing modules are installed" in observed


def test_report_lists_relation_table_behind_mapped_bridge():
    report = render_markdown(_snapshot())
    assert "`sale_order_line_invoice_rel`" in report
    assert "\u2014" not in report, "public documents use no em dash"
