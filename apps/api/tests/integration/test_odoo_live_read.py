"""Live read-only checks against the configured Odoo. Opt-in: BENACTA_LIVE_ODOO=1."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.connectors.odoo import OdooJson2Client, OdooReader, ReadOnlyViolation

pytestmark = pytest.mark.odoo_live


@pytest.fixture
def reader():
    settings = Settings()
    if not settings.odoo_api_configured:
        pytest.skip("Odoo API not configured")
    with OdooJson2Client.from_settings(settings) as client:
        yield OdooReader(client)


def test_version_and_company_are_readable(reader):
    assert reader.version()["version"].startswith("saas~19")
    assert reader.search_count("res.company", []) >= 1


def test_invoice_to_order_line_bridge_is_a_many_to_many_table(reader):
    rows = reader.search_read(
        "ir.model.fields",
        [["model", "=", "account.move.line"], ["name", "=", "sale_line_ids"]],
        ["ttype", "relation_table"],
    )
    assert rows == [{"id": rows[0]["id"], "ttype": "many2many", "relation_table": "sale_order_line_invoice_rel"}]


def test_reader_cannot_write_to_the_live_instance(reader):
    with pytest.raises(ReadOnlyViolation):
        reader.call("res.partner", "write", ids=[1], vals={"name": "must never happen"})
