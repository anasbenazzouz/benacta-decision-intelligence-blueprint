# ADR-0005: the synthetic project company is written into the existing Odoo company

## Status

Accepted, 2026-09-15. Amends ADR-0003 on the write target.

## Context

ADR-0003 confined every write to a new fictional company. On review, the owner pointed out that the connected
database is already a synthetic demo database: its only company, Benacta, carries a synthetic industrial group.
A second company would add cost and friction:

- multi-company usually requires the Odoo Custom plan;
- every internal Odoo user is a paid seat, so the 40 synthetic people cannot be users;
- the project controlling track needs time entries per project, which requires the Timesheets module
  (`hr_timesheet`, not installed on 2026-09-15).

## Decision

- Project controlling data of dataset `demo_v2` (projects, tasks, milestones, employees, time entries, purchases,
  customer and vendor invoices, payments) is written into the existing company **Benacta**.
- The owner authorised on 2026-09-15: installing `hr_timesheet`, activating USD (contract of PRJ-07), and creating
  the `x_benacta_*` extension fields listed in `app/ops/odoo_configure.py`.
- Instance configuration runs through `benacta odoo-configure`: dry run by default, idempotent, audited, guarded
  by `odoo_write_guard(require_backup=False)`. Business data writes keep the full guard, including an attested
  backup.
- All writes go through `OdooWriter`: built only from a passing guard, method allowlist, no `unlink`, no raw
  write on journal items, mail and tracking disabled, no retry.
- No internal user is created. Synthetic people are employees without users; project manager attribution comes
  from BENACTA planning assignments, not from `project.project.user_id`.
- Every created record receives an external identifier under module `benacta_demo`, so a replay creates nothing
  twice. Existing records of the company are never modified.
- Local configuration: `ODOO_SANDBOX_COMPANY=Benacta`, `ODOO_PROTECTED_COMPANIES` empty,
  `ODOO_SANDBOX_ALLOWLIST=benacta.odoo.com/benacta`. `ODOO_WRITES_ENABLED` stays false in `.env` and is enabled
  only for the command that writes.

## Consequences

- Synthetic project data and the existing demo data share one ledger. Project metrics are unaffected because they
  are scoped by project analytic account; company-level finance marts mix both populations and must filter by
  `benacta_demo` identifiers when a figure is compared with the oracle.
- Posted invoices cannot be deleted in Odoo, only reversed: a faulty seed is corrected by a new versioned batch.
- The trading golden cases of S1 (perpetual valuation, `Dozens` unit) stay fixture-only; changing the accounting
  configuration of Benacta is still excluded.
