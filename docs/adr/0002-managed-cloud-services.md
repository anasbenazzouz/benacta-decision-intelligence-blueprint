# ADR-0002: Managed cloud services instead of Docker Compose

## Status

Accepted, 2026-09-14. Embedded PostgreSQL validated in S1 (PostgreSQL 16.2, pgvector 0.6.2). Provider accounts pending (see `docs/progress.md`).

## Context

The brief defaults to Docker Compose with PostgreSQL, pgvector and Neo4j. The development machine is a Windows
Server VM with no Docker engine, no WSL distribution, 2 vCPU and 8 GB of memory, of which about 1 GB was free
during diagnosis. Running PostgreSQL, Neo4j, the API, a worker and a Next.js dev server locally would compete with
that budget.

## Decision

- Analytics database: managed PostgreSQL with the pgvector extension, database name `benacta_analytics`.
- Ontology projection: Neo4j AuraDB Free.
- API, worker and web run as local processes during development, bound to loopback.
- Fixture mode must still run with no external credential. Integration tests start an ephemeral local PostgreSQL
  from the test harness. The candidate is the `pgserver` Python package, which ships PostgreSQL with pgvector
  for Windows, macOS and Linux. Fixture commands keep one development server under `.benacta/pgdata`
  (`benacta local-db-stop` stops it); test sessions start a temporary server and delete it at the end.
- Only synthetic or authorised content is sent to cloud services.

## Consequences

- No container build to maintain; the provider accounts become a prerequisite for connected mode.
- A `docker-compose.yml` is not provided in this delivery. Adding one later changes only connection URLs.
- Neo4j stays optional at runtime: the graph view announces unavailability instead of simulating answers.
