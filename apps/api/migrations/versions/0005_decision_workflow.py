"""Decision workflow: recommendations, decisions, controlled actions and impact on exception cases.

Revision ID: 0005_decision_workflow
Revises: 0004_margin_control
"""

from alembic import op

revision = "0005_decision_workflow"
down_revision = "0004_margin_control"
branch_labels = None
depends_on = None

UPGRADE = r"""
alter table decision.exception_case
    add column assigned_to        text,
    add column defer_until        date,
    add column estimated_recovery numeric(24, 6),
    add column decided_at         timestamptz,
    add column actioned_at        timestamptz;

create function decision.refuse_mutation() returns trigger language plpgsql as $$
begin
    raise exception '% is append-only', tg_table_name;
end
$$;

-- One recommendation per case version. A deterministic template today (source DETERMINISTIC_TEMPLATE); the
-- AI investigation of milestone 3 drafts LLM_DRAFT rows through the same table and the same approval path.
create table decision.margin_recommendation (
    recommendation_id  uuid primary key,
    case_id            uuid not null references decision.exception_case (case_id),
    version            integer not null check (version >= 1),
    source             text not null check (source in ('DETERMINISTIC_TEMPLATE', 'LLM_DRAFT')),
    action_key         text not null,
    title              text not null,
    rationale          text not null,
    requires_role      text not null,
    estimated_recovery numeric(24, 6),
    recovery_basis     text not null check (recovery_basis in ('BILLING_EXPOSURE', 'NOT_RECEIVABLE', 'UNKNOWN')),
    expected_impact    jsonb not null default '{}'::jsonb,
    evidence_refs      jsonb not null default '[]'::jsonb,
    status             text not null check (status in ('PENDING_REVIEW', 'APPROVED', 'REJECTED', 'EVIDENCE_REQUESTED',
                                                       'DEFERRED', 'SUPERSEDED')),
    snapshot_id        uuid not null,
    rule_version       integer not null,
    thresholds_version text not null,
    payload_hash       char(64) not null,
    created_at         timestamptz not null default now(),
    unique (case_id, version)
);

-- Every human decision, append-only. The case version before and after gives optimistic concurrency.
create table decision.case_decision (
    decision_id         uuid primary key,
    case_id             uuid not null references decision.exception_case (case_id),
    recommendation_id   uuid references decision.margin_recommendation (recommendation_id),
    decision_type       text not null check (decision_type in ('APPROVE', 'REJECT', 'REQUEST_EVIDENCE', 'ASSIGN', 'DEFER',
                                                                'COMMENT', 'REOPEN', 'CLOSE')),
    actor               text not null,
    actor_roles         text[] not null,
    status_before       text not null,
    status_after        text not null,
    case_version_before integer not null,
    case_version_after  integer not null,
    reason              text,
    comment             text,
    assigned_to         text,
    defer_until         date,
    decided_at          timestamptz not null default now(),
    check (decision_type not in ('REJECT', 'DEFER', 'REQUEST_EVIDENCE', 'REOPEN') or reason is not null)
);
create trigger case_decision_append_only before update or delete on decision.case_decision
    for each row execute function decision.refuse_mutation();

-- Controlled actions: what was sent to which system, with the guard report and the response. An external
-- identifier makes execution idempotent; only one EXECUTED row can exist per identifier.
create table decision.case_action (
    action_id     uuid primary key,
    case_id       uuid not null references decision.exception_case (case_id),
    decision_id   uuid references decision.case_decision (decision_id),
    action_key    text not null,
    target_system text not null check (target_system in ('odoo', 'fixture')),
    target_model  text,
    target_res_id bigint,
    external_id   text not null,
    status        text not null check (status in ('PLANNED', 'EXECUTED', 'REFUSED', 'FAILED')),
    request       jsonb not null,
    response      jsonb,
    guard         jsonb,
    error         text,
    actor         text not null,
    created_at    timestamptz not null default now(),
    executed_at   timestamptz
);
create unique index case_action_executed_once on decision.case_action (external_id) where status = 'EXECUTED';
create trigger case_action_append_only before update or delete on decision.case_action
    for each row execute function decision.refuse_mutation();

-- Impact: estimated when approved, realised only from posted documents dated after the decision.
create table decision.case_impact (
    case_id              uuid primary key references decision.exception_case (case_id),
    snapshot_id          uuid not null,
    estimated_recovery   numeric(24, 6),
    approved_at          timestamptz,
    executed_at          timestamptz,
    realised_recovery    numeric(24, 6),
    realised_at          date,
    realisation_status   text not null check (realisation_status in ('NOT_MEASURED', 'NOT_MEASURABLE', 'MEASURED', 'PARTIAL')),
    realisation_evidence jsonb not null default '[]'::jsonb,
    reason               text,
    variance             numeric(24, 6),
    measured_at          timestamptz not null default now()
);
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    raise NotImplementedError("create a new database instead")
