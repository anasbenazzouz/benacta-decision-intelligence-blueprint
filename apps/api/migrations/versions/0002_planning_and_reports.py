"""Planning (budget and forecast versions), imports, status reports and investigations.

Revision ID: 0002_planning_and_reports
Revises: 0001_foundation
"""

from alembic import op

revision = "0002_planning_and_reports"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None

UPGRADE = r"""
create schema if not exists planning;

-- ---------------------------------------------------------------- imports
create table planning.import_batch (
    import_id     uuid primary key,
    source        text not null check (source in ('CSV', 'SPREADSHEET', 'UI', 'SEED')),
    file_name     text,
    file_hash     char(64) not null,
    author        text not null,
    received_at   timestamptz not null default now(),
    status        text not null check (status in ('VALIDATED', 'REJECTED')),
    row_count     integer not null,
    error_count   integer not null,
    version_id    uuid,
    totals        jsonb not null default '{}'::jsonb
);

create table planning.import_error (
    import_id  uuid not null references planning.import_batch (import_id),
    row_number integer not null,
    field      text,
    code       text not null,
    message    text not null,
    primary key (import_id, row_number, code, field)
);

-- ---------------------------------------------------------------- versions
create table planning.plan_version (
    version_id         uuid primary key,
    company_id         bigint not null,
    source_instance    text not null,
    project_code       text not null,
    version_type       text not null check (version_type in ('BUDGET_BASELINE', 'BUDGET_REVISED', 'FORECAST')),
    scenario           text not null check (scenario in ('BASE', 'FAVOURABLE', 'UNFAVOURABLE', 'PENDING_CO')),
    label              text not null,
    cutoff_date        date,
    currency           char(3) not null,
    status             text not null check (status in ('DRAFT', 'SUBMITTED', 'APPROVED', 'LOCKED')),
    parent_version_id  uuid references planning.plan_version (version_id),
    etc_includes_commitments boolean not null default true,
    author             text not null,
    source             text not null,
    import_id          uuid references planning.import_batch (import_id),
    created_at         timestamptz not null default now(),
    submitted_by       text,
    submitted_at       timestamptz,
    approved_by        text,
    approved_at        timestamptz,
    locked_by          text,
    locked_at          timestamptz,
    unique (source_instance, company_id, project_code, version_type, scenario, label),
    check (version_type <> 'FORECAST' or cutoff_date is not null),
    check (approved_by is null or approved_by <> submitted_by)
);

create table planning.plan_line (
    line_id           bigint generated always as identity primary key,
    version_id        uuid not null references planning.plan_version (version_id),
    business_unit     text not null,
    work_package      text not null,
    cost_category     text not null check (cost_category in ('LABOUR', 'SUBCONTRACT', 'MATERIALS', 'CONTINGENCY', 'OTHER', 'REVENUE')),
    resource_or_role  text not null default '',
    period            date not null check (extract(day from period) = 1),
    currency          char(3) not null,
    planned_hours     numeric(24, 6),
    planned_rate      numeric(24, 6),
    planned_cost      numeric(24, 6),
    planned_revenue   numeric(24, 6),
    planned_billing   numeric(24, 6),
    planned_cash_collection numeric(24, 6),
    unique (version_id, work_package, cost_category, resource_or_role, period)
);
create index plan_line_version_idx on planning.plan_line (version_id, period);

-- Employee-level planned hours supporting capacity views; must add up to role hours of the same version.
create table planning.assignment (
    version_id    uuid not null references planning.plan_version (version_id),
    work_package  text not null,
    employee_code text not null,
    role          text not null,
    period        date not null check (extract(day from period) = 1),
    planned_hours numeric(24, 6) not null check (planned_hours >= 0),
    primary key (version_id, work_package, employee_code, period)
);

-- Assumptions and declarations attached to a version (physical progress, notes, risks).
create table planning.assumption (
    version_id   uuid not null references planning.plan_version (version_id),
    key          text not null,
    work_package text not null default '',
    value_numeric numeric(24, 6),
    value_text   text,
    author       text not null,
    evidence_ref text,
    recorded_at  timestamptz not null default now(),
    primary key (version_id, key, work_package)
);

create function planning.refuse_frozen_change() returns trigger language plpgsql as $$
declare
    v_status text;
begin
    select status into v_status from planning.plan_version
    where version_id = coalesce(new.version_id, old.version_id);
    if v_status in ('APPROVED', 'LOCKED') then
        raise exception 'version % is %: create a revision instead', coalesce(new.version_id, old.version_id), v_status;
    end if;
    return coalesce(new, old);
end
$$;
create trigger plan_line_frozen before insert or update or delete on planning.plan_line
    for each row execute function planning.refuse_frozen_change();
create trigger assignment_frozen before insert or update or delete on planning.assignment
    for each row execute function planning.refuse_frozen_change();
create trigger assumption_frozen before insert or update or delete on planning.assumption
    for each row execute function planning.refuse_frozen_change();

-- Status only moves forward; identity and scope of a submitted version never change.
create function planning.guard_version_update() returns trigger language plpgsql as $$
declare
    rank_old int := array_position(array['DRAFT', 'SUBMITTED', 'APPROVED', 'LOCKED'], old.status);
    rank_new int := array_position(array['DRAFT', 'SUBMITTED', 'APPROVED', 'LOCKED'], new.status);
begin
    if rank_new < rank_old or rank_new > rank_old + 1 then
        raise exception 'invalid status transition % -> %', old.status, new.status;
    end if;
    if old.status <> 'DRAFT' and (new.project_code, new.version_type, new.scenario, new.label, new.cutoff_date, new.currency)
        is distinct from (old.project_code, old.version_type, old.scenario, old.label, old.cutoff_date, old.currency) then
        raise exception 'version % is % and cannot change its scope', old.version_id, old.status;
    end if;
    return new;
end
$$;
create trigger plan_version_guard before update on planning.plan_version
    for each row execute function planning.guard_version_update();
create function planning.refuse_version_delete() returns trigger language plpgsql as $$
begin
    if old.status <> 'DRAFT' then
        raise exception 'version % is % and cannot be deleted', old.version_id, old.status;
    end if;
    return old;
end
$$;
create trigger plan_version_no_delete before delete on planning.plan_version
    for each row execute function planning.refuse_version_delete();

-- ---------------------------------------------------------------- decision: status reports, investigations
create table decision.project_status_report (
    psr_id          uuid primary key,
    source_instance text not null,
    company_id      bigint not null,
    project_code    text not null,
    period          char(7) not null,
    revision        integer not null check (revision >= 1),
    cutoff_date     date not null,
    snapshot_id     uuid not null,
    forecast_version_id uuid references planning.plan_version (version_id),
    previous_forecast_version_id uuid references planning.plan_version (version_id),
    budget_version_id uuid references planning.plan_version (version_id),
    status          text not null check (status in ('DRAFT', 'PUBLISHED')),
    content         jsonb not null,
    content_hash    char(64) not null,
    prepared_by     text not null,
    prepared_at     timestamptz not null default now(),
    approved_by     text,
    approved_at     timestamptz,
    validated_comment text,
    unique (source_instance, company_id, project_code, period, revision),
    check (approved_by is null or approved_by <> prepared_by)
);

create function decision.refuse_published_psr_change() returns trigger language plpgsql as $$
begin
    if old.status = 'PUBLISHED' then
        raise exception 'status report % is published and immutable', old.psr_id;
    end if;
    if tg_op = 'DELETE' then
        return old;
    end if;
    return new;
end
$$;
create trigger psr_immutable before update or delete on decision.project_status_report
    for each row execute function decision.refuse_published_psr_change();

create table decision.investigation (
    investigation_id uuid primary key,
    subject_type     text not null,
    subject_id       text not null,
    question         text not null,
    mode             text not null check (mode in ('DETERMINISTIC_NO_LLM', 'LLM')),
    snapshot_id      uuid not null,
    status           text not null check (status in ('COMPLETED', 'ABSTAINED', 'FAILED')),
    report           jsonb not null,
    report_hash      char(64) not null,
    created_at       timestamptz not null default now()
);

create table decision.recommendation (
    recommendation_id uuid primary key,
    investigation_id  uuid not null references decision.investigation (investigation_id),
    action_key        text not null,
    version           integer not null check (version >= 1),
    status            text not null check (status in ('DRAFT', 'VALIDATED', 'PENDING_REVIEW', 'APPROVED', 'REJECTED')),
    proposed_action   jsonb not null,
    payload_hash      char(64) not null,
    reviewed_by       text,
    reviewed_at       timestamptz,
    review_reason     text,
    unique (investigation_id, action_key, version)
);
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    raise NotImplementedError("create a new database instead")
