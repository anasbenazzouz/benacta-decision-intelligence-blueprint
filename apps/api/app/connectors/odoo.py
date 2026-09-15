"""Odoo external API connector (JSON-2, Odoo 19+).

Odoo 19 documents `POST /json/2/<model>/<method>` with a bearer API key and
schedules XML-RPC / JSON-RPC for removal in Odoo 22. Each call runs in its own
server transaction, so multi-step business operations must use a single
business method (e.g. `action_confirm`) rather than chained raw writes.

`OdooReader` is the only object handed to ingestion, discovery and
investigation tools: it refuses every method outside a read allowlist.
Writes will live in a separate, guarded writer.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import httpx

from app.config import Settings

USER_AGENT = "benacta-decision-system/0.1"

READ_METHODS = frozenset({"search_read", "search_count", "read", "fields_get", "has_access", "formatted_read_group"})
RETRYABLE_STATUS = frozenset({429, 502, 503, 504})


class OdooError(RuntimeError):
    """Typed Odoo failure. Never carries the server traceback or credentials."""

    def __init__(self, status: int, name: str, message: str, model: str, method: str):
        super().__init__(f"{model}.{method} -> HTTP {status} {name}: {message}")
        self.status = status
        self.name = name
        self.message = message
        self.model = model
        self.method = method

    @property
    def access_denied(self) -> bool:
        return self.status == 403 or self.name.endswith("AccessError")

    @property
    def not_found(self) -> bool:
        return self.status == 404


class ReadOnlyViolation(PermissionError):
    pass


class OdooJson2Client:
    def __init__(
        self,
        base_url: str,
        database: str,
        api_key: str,
        *,
        timeout: float = 60.0,
        max_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
    ):
        self._database = database
        self._max_retries = max_retries
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
            headers={
                "Authorization": f"bearer {api_key}",
                "X-Odoo-Database": database,
                "User-Agent": USER_AGENT,
            },
        )

    @classmethod
    def from_settings(cls, settings: Settings, **kwargs: Any) -> OdooJson2Client:
        if not settings.odoo_api_configured:
            raise RuntimeError("Odoo API is not configured (ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY)")
        return cls(
            settings.odoo_url,
            settings.odoo_db,
            settings.odoo_api_key.get_secret_value(),
            timeout=settings.odoo_timeout_seconds,
            **kwargs,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> OdooJson2Client:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def version(self) -> dict[str, Any]:
        response = self._http.get("/web/version")
        response.raise_for_status()
        return response.json()

    def call(
        self,
        model: str,
        method: str,
        *,
        ids: list[int] | None = None,
        context: dict[str, Any] | None = None,
        retry: bool = False,
        **params: Any,
    ) -> Any:
        body: dict[str, Any] = dict(params)
        if ids is not None:
            body["ids"] = ids
        if context:
            body["context"] = context
        attempts = self._max_retries + 1 if retry else 1
        for attempt in range(attempts):
            response = self._http.post(f"/json/2/{model}/{method}", json=body)
            if response.status_code in RETRYABLE_STATUS and attempt < attempts - 1:
                time.sleep(2**attempt)
                continue
            if response.is_success:
                return response.json()
            raise _to_error(response, model, method)
        raise AssertionError("unreachable")


def _to_error(response: httpx.Response, model: str, method: str) -> OdooError:
    try:
        payload = response.json()
        name = str(payload.get("name", "unknown"))
        message = str(payload.get("message", ""))
    except ValueError:
        name, message = "non_json_response", response.text[:200]
    return OdooError(response.status_code, name, message[:500], model, method)


class OdooReader:
    """Read-only facade. Reads are idempotent, so they are safe to retry."""

    def __init__(self, client: OdooJson2Client):
        self._client = client

    def version(self) -> dict[str, Any]:
        return self._client.version()

    def call(self, model: str, method: str, **kwargs: Any) -> Any:
        if method not in READ_METHODS:
            raise ReadOnlyViolation(f"method '{method}' is not in the read allowlist")
        return self._client.call(model, method, retry=True, **kwargs)

    def search_read(
        self,
        model: str,
        domain: list,
        fields: list[str],
        *,
        order: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"domain": domain, "fields": fields, "offset": offset}
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = limit
        return self.call(model, "search_read", context=context, **params)

    def search_count(self, model: str, domain: list) -> int:
        return self.call(model, "search_count", domain=domain)

    def fields_get(self, model: str, attributes: list[str]) -> dict[str, dict[str, Any]]:
        return self.call(model, "fields_get", attributes=attributes)

    def has_access(self, model: str, operation: str) -> bool:
        return bool(self.call(model, "has_access", ids=[], operation=operation))

    def iter_search_read(
        self, model: str, domain: list, fields: list[str], *, page_size: int = 500
    ) -> Iterator[dict[str, Any]]:
        """Stable pagination on (id) so concurrent inserts cannot shift pages."""
        last_id = 0
        while True:
            page = self.search_read(model, [*domain, ["id", ">", last_id]], fields, order="id asc", limit=page_size)
            yield from page
            if len(page) < page_size:
                return
            last_id = page[-1]["id"]
