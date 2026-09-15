"""Margin Control: governed reference data, price lists, rule evaluations, period KPIs, exception cases.

Revision ID: 0004_margin_control
Revises: 0003_project_marts
"""

from alembic import op

revision = "0004_margin_control"
down_revision = "0003_project_marts"
branch_labels = None
depends_on = None

UPGRADE = r"""
-- ---------------------------------------------------------------- marts: snapshot provenance and price lists
alter table marts.snapshot add column transformation_version text;
alter table marts.dim_partner add column ref text, add column pricelist_id bigint;
alter table marts.dim_product add column list_price numeric(24, 6);
alter table marts.fact_sales_order_line add column pricelist_id bigint;

create table marts.dim_pricelist (
    snapshot_id   uuid not null references marts.snapshot (snapshot_id),
    pricelist_id  bigint not null,
    name          text not null,
    currency_code text not null,
    company_id    bigint,
    active        boolean not null,
    primary key (snapshot_id, pricelist_id)
);

create table marts.dim_pricelist_item (
    snapshot_id         uuid not null references marts.snapshot (snapshot_id),
    item_id             bigint not null,
    pricelist_id        bigint not null,
    applied_on          text not null,
    product_template_id bigint,
    product_id          bigint,
    category_id         bigint,
    min_quantity        numeric(24, 6) not null default 0,
    compute_price       text not null,
    fixed_price         numeric(24, 6),
    percent_price       numeric(9, 4),
    currency_code       text,
    date_start          date,
    date_end            date,
    primary key (snapshot_id, item_id)
);

-- ---------------------------------------------------------------- marts: reconciliation report fields
alter table marts.reconciliation_result
    add column tolerance              numeric(24, 6),
    add column source_timestamp       timestamp,
    add column ingested_at            timestamptz,
    add column transformation_version text,
    add column detail                 jsonb not null default '{}'::jsonb;
alter table marts.reconciliation_result drop constraint reconciliation_result_independence_check;
alter table marts.reconciliation_result add constraint reconciliation_result_independence_check
    check (independence in ('SERVER_AGGREGATE', 'FIXTURE_CONTROL_TOTAL', 'SOURCE_HEADER', 'NONE'));

-- ---------------------------------------------------------------- semantic: governed reference data
-- BENACTA-owned business terms keyed by business references (partner ref, product code), never by Odoo ids,
-- so the same rules read the same terms whatever the system of record. Every row carries its owner, source
-- and effective dates; a load records provenance.
create table semantic.reference_load (
    load_id         uuid primary key,
    source_instance text not null,
    company_id      bigint not null,
    source_kind     text not null check (source_kind in ('FIXTURE_TERMS', 'POLICY_REGISTER')),
    source_ref      text not null,
    content_hash    char(64) not null,
    loaded_at       timestamptz not null default now(),
    actor           text not null,
    row_counts      jsonb not null default '{}'::jsonb
);

create table semantic.customer_segment (
    source_instance text not null,
    company_id      bigint not null,
    customer_ref    text not null,
    segment         text not null,
    valid_from      date not null,
    valid_to        date,
    owner           text not null,
    source          text not null,
    load_id         uuid not null references semantic.reference_load (load_id),
    primary key (source_instance, company_id, customer_ref, valid_from)
);

create table semantic.discount_policy (
    source_instance    text not null,
    company_id         bigint not null,
    policy_id          text not null,
    version            integer not null check (version >= 1),
    scope_segment      text,
    scope_customer_ref text,
    max_discount_pct   numeric(9, 4) not null check (max_discount_pct >= 0),
    priority           integer not null,
    valid_from         date not null,
    valid_to           date,
    owner              text not null,
    source             text not null,
    load_id            uuid not null references semantic.reference_load (load_id),
    primary key (source_instance, company_id, policy_id, version),
    check (scope_segment is not null or scope_customer_ref is not null)
);

create table semantic.discount_derogation (
    source_instance  text not null,
    company_id       bigint not null,
    derogation_id    text not null,
    order_ref        text not null,
    max_discount_pct numeric(9, 4) not null,
    approved_by_role text not null,
    approved_on      date not null,
    valid_from       date not null,
    valid_to         date,
    evidence_ref     text,
    owner            text not null,
    source           text not null,
    load_id          uuid not null references semantic.reference_load (load_id),
    primary key (source_instance, company_id, derogation_id)
);

create table semantic.freight_contract (
    source_instance text not null,
    company_id      bigint not null,
    contract_id     text not null,
    customer_ref    text not null,
    terms           text not null check (terms in ('rebill', 'waived', 'included')),
    amount          numeric(24, 6) not null,
    currency        char(3) not null,
    trigger         text,
    valid_from      date not null,
    valid_to        date,
    owner           text not null,
    source          text not null,
    load_id         uuid not null references semantic.reference_load (load_id),
    primary key (source_instance, company_id, contract_id)
);

create table semantic.contract_price (
    source_instance text not null,
    company_id      bigint not null,
    contract_id     text not null,
    customer_ref    text not null,
    product_code    text not null,
    unit_price      numeric(24, 6) not null,
    currency        char(3) not null,
    min_quantity    numeric(24, 6) not null default 0,
    valid_from      date not null,
    valid_to        date,
    owner           text not null,
    source          text not null,
    load_id         uuid not null references semantic.reference_load (load_id),
    primary key (source_instance, company_id, contract_id, product_code)
);

create table semantic.cost_reference (
    source_instance text not null,
    company_id      bigint not null,
    reference_id    text not null,
    product_code    text not null,
    unit_cost       numeric(24, 6) not null,
    currency        char(3) not null default 'EUR',
    frozen_on       date not null,
    valid_from      date not null,
    valid_to        date,
    owner           text not null,
    source          text not null,
    load_id         uuid not null references semantic.reference_load (load_id),
    primary key (source_instance, company_id, reference_id, product_code)
);

-- ---------------------------------------------------------------- marts: rule evaluations (computed facts)
-- One row per rule and subject for a snapshot, whatever the outcome, so false positives and abstentions are
-- inspectable. Amounts are in company currency; the order-currency figures live in the evidence.
create table marts.fact_margin_rule_evaluation (
    snapshot_id          uuid not null references marts.snapshot (snapshot_id),
    rule_id              text not null,
    rule_version         integer not null,
    subject_type         text not null check (subject_type in ('sale_order_line', 'sale_order', 'invoice_line')),
    subject_id           bigint not null,
    subject_ref          text not null,
    company_id           bigint not null,
    customer_id          bigint,
    product_id           bigint,
    sale_order_id        bigint,
    order_date           date,
    period               char(7) not null,
    outcome              text not null check (outcome in ('VIOLATION', 'COMPLIANT', 'NOT_DUE', 'EXCLUDED', 'UNDETERMINED',
                                                          'UNKNOWN', 'CONFLICT', 'NO_SALE_LINK')),
    classification       text not null check (classification in ('CONFIRMED_LEAKAGE', 'PROBABLE_LEAKAGE', 'EXPLAINED_VARIANCE',
                                                                  'LEGITIMATE_EXCEPTION', 'DATA_QUALITY_ISSUE',
                                                                  'INSUFFICIENT_EVIDENCE', 'COMPLIANT', 'NOT_APPLICABLE')),
    cause                text not null,
    exposure_type        text check (exposure_type in ('price', 'discount', 'freight', 'cost')),
    component            text check (component in ('billing_leakage', 'cost_variance')),
    expected_amount      numeric(24, 6),
    actual_amount        numeric(24, 6),
    adverse_exposure     numeric(24, 6),
    potential_exposure   numeric(24, 6),
    exposure_stage       text check (exposure_stage in ('ORDERED', 'PARTIALLY_INVOICED', 'INVOICED')),
    currency_code        text not null,
    severity             text not null check (severity in ('HIGH', 'MEDIUM', 'LOW', 'NONE')),
    confidence           text not null check (confidence in ('HIGH', 'MEDIUM', 'LOW')),
    controllability      text not null check (controllability in ('CONTROLLABLE', 'PARTIALLY_CONTROLLABLE',
                                                                  'NOT_CONTROLLABLE', 'NOT_APPLICABLE')),
    material             boolean not null,
    requires_human_review boolean not null default false,
    overlap_group        text,
    evidence             jsonb not null,
    formula              text not null,
    thresholds_version   text not null,
    computed_at          timestamptz not null default now(),
    primary key (snapshot_id, rule_id, subject_type, subject_id)
);
create index fact_margin_rule_evaluation_class_idx
    on marts.fact_margin_rule_evaluation (snapshot_id, classification, period);

-- ---------------------------------------------------------------- marts: gross margin per company and period
create table marts.fact_margin_period (
    snapshot_id                uuid not null references marts.snapshot (snapshot_id),
    company_id                 bigint not null,
    period                     char(7) not null,
    revenue                    numeric(24, 6) not null,
    revenue_goods              numeric(24, 6) not null default 0,
    revenue_services           numeric(24, 6) not null default 0,
    cogs                       numeric(24, 6),
    gross_margin               numeric(24, 6),
    gross_margin_pct           numeric(9, 4),
    margin_basis               text not null check (margin_basis in ('RECONCILED_COGS', 'MANAGEMENT_PROXY', 'UNAVAILABLE')),
    margin_status              text not null check (margin_status in ('OK', 'UNAVAILABLE', 'UNRECONCILED')),
    revenue_reconciliation     text not null,
    cogs_reconciliation        text not null,
    discount_leakage           numeric(24, 6) not null default 0,
    price_leakage              numeric(24, 6) not null default 0,
    freight_leakage            numeric(24, 6) not null default 0,
    cost_leakage               numeric(24, 6) not null default 0,
    total_addressable_leakage  numeric(24, 6) not null default 0,
    recoverable_from_customer  numeric(24, 6) not null default 0,
    untraceable_revenue        numeric(24, 6) not null default 0,
    exceptions_material        integer not null default 0,
    exceptions_review          integer not null default 0,
    invoice_lines              integer not null default 0,
    primary key (snapshot_id, company_id, period)
);

-- ---------------------------------------------------------------- decision: exception cases
-- A case is the stable identity of an exception across snapshots. Its lifecycle (M2) never alters the
-- computed evaluation rows, which are rebuilt per snapshot. NO_LONGER_RAISED records why the newest snapshot
-- stopped raising it (source corrected, or a rule or threshold change), never a deletion.
create sequence decision.exception_case_ref_seq;
create table decision.exception_case (
    case_id              uuid primary key,
    case_ref             text not null unique,
    source_instance      text not null,
    company_id           bigint not null,
    exception_key        text not null,
    rule_id              text not null,
    subject_type         text not null,
    subject_id           bigint not null,
    subject_ref          text not null,
    first_snapshot_id    uuid not null,
    first_detected_at    timestamptz not null default now(),
    last_snapshot_id     uuid not null,
    last_seen_at         timestamptz not null default now(),
    resolved_snapshot_id uuid,
    resolved_note        text,
    classification       text not null,
    cause                text not null,
    severity             text not null,
    adverse_exposure     numeric(24, 6),
    potential_exposure   numeric(24, 6),
    status               text not null default 'NEW' check (status in ('NEW', 'OPEN', 'UNDER_REVIEW', 'EVIDENCE_REQUESTED',
                                                                       'DEFERRED', 'APPROVED', 'REJECTED', 'ACTIONED',
                                                                       'CLOSED', 'NO_LONGER_RAISED')),
    owner                text,
    version              integer not null default 1,
    unique (source_instance, exception_key)
);
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    raise NotImplementedError("create a new database instead")
