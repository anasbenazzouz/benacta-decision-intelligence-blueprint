# ADR-0003: Odoo through JSON-2, seeds confined to a sandbox company

## Status

Accepted, 2026-09-14.

## Context

The connected instance is an existing Odoo Online database, version `saas~19.4+e`, already populated with a
synthetic industrial group over roughly three years. Odoo 19 documents the JSON-2 API
(`POST /json/2/<model>/<method>`, bearer API key, `X-Odoo-Database` header) and schedules XML-RPC and JSON-RPC
for removal in Odoo 22. Each JSON-2 call runs in its own transaction; chaining calls is not transactional.
Odoo Online offers no direct PostgreSQL access and no custom module deployment.

The brief requires that the existing environment is resumed and verified, never recreated or overwritten, and
that nothing is written when the sandbox nature is ambiguous.

## Decision

- All reads go through `OdooReader`, which refuses any method outside
  `search_read, search_count, read, fields_get, has_access, formatted_read_group`.
- Discovery is reproducible (`benacta discover-odoo`) and its report is regenerated, never hand-edited.
- Multi-step business operations use Odoo business methods (`action_confirm`, `action_post`, validation of
  pickings) instead of raw state writes, so each step is one server transaction.
- Seeds and write-back target one fictional company only, created for BENACTA, and pass `odoo_write_guard`.
  The existing company is protected by name.
- Accounting configuration of the existing company is never changed. The sandbox company receives its own
  product categories with perpetual valuation so COST-001 can be proven.
- Modules that are missing (`delivery`, `sale_margin`) are not installed without explicit approval.

## Consequences

- The integration survives the Odoo 22 removal of XML-RPC.
- Some golden cases depend on sandbox company configuration; until it exists they run in fixtures and are
  reported `NOT_VERIFIED` against Odoo.
- The Odoo 19 documentation limits manually generated keys to three months. The key in use reports no expiration
  date. Key rotation, and a separate read-only bot user for scheduled ingestion, are operational tasks.
