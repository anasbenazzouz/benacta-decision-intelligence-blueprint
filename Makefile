# V2 Decision System Lab commands. Only implemented targets are listed.
# Every target delegates to the `benacta` CLI, so on a machine without make:
#   uv run --project apps/api benacta <command>

API := uv run --project apps/api

.PHONY: doctor discover-odoo migrate seed-fixtures ingest marts reconcile verify-audit \
        seed-odoo-dry-run seed-odoo local-db-stop test test-live lint api

doctor:
	$(API) benacta doctor

discover-odoo:
	$(API) benacta discover-odoo

migrate:
	$(API) benacta migrate

# Fixture mode, no external credential: migrate, ingest the demo dataset, build marts, reconcile.
seed-fixtures:
	$(API) benacta seed-fixtures

ingest:
	$(API) benacta ingest

marts:
	$(API) benacta marts

reconcile:
	$(API) benacta reconcile

# Governed commercial terms: fixture terms in fixture mode, data/policies/margin_policy_register.yml otherwise.
load-policies:
	$(API) benacta load-policies

# Margin Control: deterministic rules on the latest snapshot, then the CFO views.
exceptions:
	$(API) benacta exceptions

margin-overview:
	$(API) benacta margin-overview

margin-exceptions:
	$(API) benacta margin-exceptions

reconciliation-report:
	$(API) benacta reconciliation-report

verify-audit:
	$(API) benacta verify-audit --export

# Reads Odoo and writes nothing.
seed-odoo-dry-run:
	$(API) benacta seed-odoo-dry-run

# Refused unless every write guard check passes.
seed-odoo:
	$(API) benacta seed-odoo

local-db-stop:
	$(API) benacta local-db-stop

test:
	cd apps/api && uv run pytest -q

test-live:
	cd apps/api && BENACTA_LIVE_ODOO=1 uv run pytest -q -m odoo_live

lint:
	cd apps/api && uv run ruff check app tests migrations && uv run ruff format --check app tests migrations

api:
	$(API) benacta serve
