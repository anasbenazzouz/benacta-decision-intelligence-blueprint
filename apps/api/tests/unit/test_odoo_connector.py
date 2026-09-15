from __future__ import annotations

import json

import httpx
import pytest

from app.connectors import odoo as odoo_module
from app.connectors.odoo import OdooError, OdooJson2Client, OdooReader, ReadOnlyViolation

API_KEY = "0123456789abcdef-test-key"


def _client(handler) -> OdooJson2Client:
    return OdooJson2Client(
        "https://example.odoo.com/", "example", API_KEY, transport=httpx.MockTransport(handler), max_retries=2
    )


def test_request_uses_json2_path_bearer_key_and_database_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers["Authorization"]
        seen["db"] = request.headers["X-Odoo-Database"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=[{"id": 1, "name": "Benacta"}])

    reader = OdooReader(_client(handler))
    rows = reader.search_read("res.company", [["id", "=", 1]], ["name"], limit=1, context={"lang": "en_US"})

    assert rows == [{"id": 1, "name": "Benacta"}]
    assert seen["path"] == "/json/2/res.company/search_read"
    assert seen["auth"] == f"bearer {API_KEY}"
    assert seen["db"] == "example"
    assert seen["body"] == {
        "domain": [["id", "=", 1]],
        "fields": ["name"],
        "offset": 0,
        "limit": 1,
        "context": {"lang": "en_US"},
    }


def test_has_access_sends_empty_ids_for_model_level_check():
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {"ids": [], "operation": "write"}
        return httpx.Response(200, json=True)

    assert OdooReader(_client(handler)).has_access("sale.order", "write") is True


@pytest.mark.parametrize("method", ["write", "create", "unlink", "action_post", "action_confirm", "generate"])
def test_reader_refuses_every_method_outside_the_read_allowlist(method):
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must never be called
        raise AssertionError("a refused method reached the network")

    with pytest.raises(ReadOnlyViolation):
        OdooReader(_client(handler)).call("sale.order", method, ids=[1])


def test_error_is_typed_and_drops_server_traceback():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "name": "odoo.exceptions.AccessError",
                "message": "You are not allowed to access this document",
                "arguments": ["You are not allowed"],
                "debug": "Traceback (most recent call last): secret internals",
            },
        )

    with pytest.raises(OdooError) as caught:
        OdooReader(_client(handler)).search_count("account.move", [])
    error = caught.value
    assert error.access_denied
    assert "Traceback" not in str(error)
    assert API_KEY not in str(error)


def test_reads_retry_transient_status_then_succeed(monkeypatch):
    monkeypatch.setattr(odoo_module.time, "sleep", lambda _: None)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503, text="busy") if len(calls) < 3 else httpx.Response(200, json=7)

    assert OdooReader(_client(handler)).search_count("sale.order", []) == 7
    assert len(calls) == 3


def test_client_calls_are_not_retried_by_default(monkeypatch):
    monkeypatch.setattr(odoo_module.time, "sleep", lambda _: None)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503, text="busy")

    with pytest.raises(OdooError):
        _client(handler).call("sale.order", "action_confirm", ids=[1])
    assert len(calls) == 1


def test_iter_search_read_paginates_on_id_without_offset_drift():
    records = [{"id": i} for i in range(1, 8)]
    domains = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        domains.append(body["domain"])
        last_id = body["domain"][-1][2]
        page = [r for r in records if r["id"] > last_id][: body["limit"]]
        return httpx.Response(200, json=page)

    rows = list(
        OdooReader(_client(handler)).iter_search_read("res.partner", [["active", "=", True]], ["id"], page_size=3)
    )
    assert [r["id"] for r in rows] == list(range(1, 8))
    assert [d[-1] for d in domains] == [["id", ">", 0], ["id", ">", 3], ["id", ">", 6]]
    assert all(d[0] == ["active", "=", True] for d in domains)


class _Guard:
    def __init__(self, allowed: bool):
        self.allowed = allowed

    def raise_if_blocked(self):
        raise odoo_module.WriteNotAllowed("guard blocked")


def test_writer_cannot_be_built_from_a_blocked_guard():
    with pytest.raises(PermissionError):
        odoo_module.OdooWriter(_client(lambda request: httpx.Response(200, json=True)), _Guard(False))


@pytest.mark.parametrize(("model", "method"), [("sale.order", "unlink"), ("account.move", "button_draft"),
                                               ("account.move.line", "write"), ("res.users", "action_reset_password")])
def test_writer_refuses_methods_outside_its_allowlist(model, method):
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover - must never be called
        raise AssertionError("a refused write reached the network")

    with pytest.raises(odoo_module.WriteNotAllowed):
        odoo_module.OdooWriter(_client(handler), _Guard(True)).call(model, method, ids=[1])


def test_writer_disables_mail_and_tracking_and_never_retries():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(503, json={"name": "unavailable", "message": "busy"})

    writer = odoo_module.OdooWriter(_client(handler), _Guard(True))
    with pytest.raises(OdooError):
        writer.create("res.partner", [{"name": "X"}], context={"lang": "fr_FR"})
    assert len(calls) == 1
    assert calls[0]["vals_list"] == [{"name": "X"}]
    assert calls[0]["context"]["tracking_disable"] is True and calls[0]["context"]["lang"] == "fr_FR"
