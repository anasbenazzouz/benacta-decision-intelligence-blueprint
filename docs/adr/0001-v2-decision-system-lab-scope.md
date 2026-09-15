# ADR-0001: V2 Decision System Lab lives next to V1 in this repository

## Status

Accepted, 2026-09-14.

## Context

V1 is a released thin slice: a Streamlit Monthly Performance Review on CSV data, with a public demo. Its
anti-patterns file excludes, for V1, a Next.js frontend, vector infrastructure, an ontology engine and production
authentication.

The V2 brief asks for a Finance Decision Command Center connected to a real Odoo instance, with an executable
semantic layer, an ontology projection, sourced retrieval, human approval with controlled write-back and a
tamper-evident audit trail. Those capabilities are exactly what V1 deliberately left out.

Two repositories were candidates: this one (doctrine, brand charter, public history) and an earlier Odoo data
generation project under another account.

## Decision

- V2 is built in this repository under `apps/api`, `apps/web`, `semantic/`, `ontology/`, `data/{mappings,discovery,fixtures,golden,documents}`.
- V1 files are not modified by V2 work and V1 tests keep passing.
- The doctrine in `.claude/benacta/` still governs V2: trust boundary, vocabulary, brand charter, editorial rules.
- The V1 scope list in `anti-patterns.md` does not apply to V2 components, which are bounded by the brief instead:
  one orchestrator, no swarm, no Kubernetes, no streaming platform, no generic chat as home screen.
- Useful parts of the earlier Odoo project (connection facts, synthetic business domain) are reused as knowledge,
  not copied as code: it used XML-RPC, which Odoo 22 removes.

## Consequences

- One public repository tells the whole story from blueprint to connected system.
- Two Python environments coexist: V1 (`requirements.txt`) and V2 (`apps/api/pyproject.toml`, `uv.lock`).
- V2 approval states follow the brief (`DRAFT, VALIDATED, PENDING_REVIEW, APPROVED, REJECTED`); V1 keeps its own.
