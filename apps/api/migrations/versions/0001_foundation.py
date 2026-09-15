"""Analytical foundation: schemas, versioned raw layer, marts, append-only audit.

Revision ID: 0001_foundation
Revises:
"""

from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None

SCHEMAS = ("raw", "staging", "marts", "semantic", "decision", "audit")

UPGRADE = r"""
create extension if not exists vector;

-- ---------------------------------------------------------------- raw
create table raw.ingestion_batch (
    batch_id        uuid primary key,
    batch_seq       bigint generated always as identity unique,
    source_instance text not null,
    source_kind     text not null check (source_kind in ('odoo', 'fixture')),
    status          text not null check (status in ('RUNNING', 'SUCCEEDED', 'FAILED')),
    started_at      timestamptz not null default now(),
    finished_at     timestamptz,
    overlap_seconds integer not null check (overlap_seconds >= 0),
    models          text[] not null,
    stats           jsonb not null default '{}'::jsonb,
    error           text
);
create index ingestion_batch_instance_idx on raw.ingestion_batch (source_instance, batch_seq);

create table raw.batch_model_state (
    batch_id             uuid not null references raw.ingestion_batch (batch_id),
    source_model         text not null,
    status               text not null check (status in ('SUCCEEDED', 'FAILED')),
    extracted            integer not null default 0,
    new_versions         integer not null default 0,
    unchanged            integer not null default 0,
    deletions            integer not null default 0,
    missing_fields       text[] not null default '{}',
    watermark_write_date timestamp,
    watermark_id         bigint,
    finished_at          timestamptz not null default now(),
    primary key (batch_id, source_model)
);

-- Odoo write_date values are UTC without zone; they are stored as timestamp (UTC).
create table raw.source_record_version (
    version_id        bigint generated always as identity primary key,
    source_instance   text not null,
    source_model      text not null,
    source_id         bigint not null,
    version_no        integer not null check (version_no >= 1),
    company_id        bigint,
    source_write_date timestamp,
    record_hash       char(64) not null,
    is_deletion       boolean not null default false,
    payload           jsonb,
    batch_id          uuid not null references raw.ingestion_batch (batch_id),
    batch_seq         bigint not null,
    extracted_at      timestamptz not null,
    unique (source_instance, source_model, source_id, version_no),
    check (is_deletion or payload is not null)
);
create index source_record_version_snapshot_idx
    on raw.source_record_version (source_instance, source_model, batch_seq);

create table raw.source_record_current (
    source_instance    text not null,
    source_model       text not null,
    source_id          bigint not null,
    version_id         bigint not null references raw.source_record_version (version_id),
    version_no         integer not null,
    record_hash        char(64) not null,
    is_deleted         boolean not null,
    last_seen_batch_id uuid not null references raw.ingestion_batch (batch_id),
    primary key (source_instance, source_model, source_id)
);

create table raw.watermark (
    source_instance text not null,
    source_model    text not null,
    write_date      timestamp not null,
    last_id         bigint not null,
    batch_id        uuid not null references raw.ingestion_batch (batch_id),
    updated_at      timestamptz not null default now(),
    primary key (source_instance, source_model)
);

-- ---------------------------------------------------------------- staging
-- Consistent view of a model as of a snapshot: latest version at or before the batch, deletions removed.
create function staging.records_at(p_instance text, p_model text, p_batch_seq bigint)
returns table (source_id bigint, company_id bigint, version_id bigint, payload jsonb)
language sql stable as $$
    select v.source_id, v.company_id, v.version_id, v.payload
    from (
        select distinct on (source_id) *
        from raw.source_record_version
        where source_instance = p_instance and source_model = p_model and batch_seq <= p_batch_seq
        order by source_id, version_no desc
    ) v
    where not v.is_deletion
$$;

-- ---------------------------------------------------------------- marts
create table marts.snapshot (
    snapshot_id     uuid primary key references raw.ingestion_batch (batch_id),
    source_instance text not null,
    batch_seq       bigint not null,
    built_at        timestamptz not null default now(),
    stats           jsonb not null default '{}'::jsonb
);

create table marts.dim_date (
    date_day   date primary key,
    year       smallint not null,
    quarter    smallint not null,
    month      smallint not null,
    iso_week   smallint not null,
    period     char(7) not null
);

create table marts.dim_company (
    snapshot_id   uuid not null references marts.snapshot (snapshot_id),
    company_id    bigint not null,
    name          text not null,
    currency_code text not null,
    primary key (snapshot_id, company_id)
);

create table marts.dim_currency (
    snapshot_id    uuid not null references marts.snapshot (snapshot_id),
    currency_id    bigint not null,
    code           text not null,
    rounding       numeric(24, 6) not null,
    decimal_places smallint not null,
    primary key (snapshot_id, currency_id)
);

-- Odoo convention: rate = units of the currency for one unit of the company currency.
create table marts.fx_rate (
    snapshot_id  uuid not null references marts.snapshot (snapshot_id),
    company_id   bigint not null,
    currency_id  bigint not null,
    rate_date    date not null,
    rate         numeric(24, 12) not null check (rate > 0),
    source_id    bigint not null,
    primary key (snapshot_id, company_id, currency_id, rate_date)
);

create table marts.dim_uom (
    snapshot_id uuid not null references marts.snapshot (snapshot_id),
    uom_id      bigint not null,
    name        text not null,
    factor      numeric(24, 12) not null check (factor > 0),
    primary key (snapshot_id, uom_id)
);

create table marts.dim_partner (
    snapshot_id           uuid not null references marts.snapshot (snapshot_id),
    partner_id            bigint not null,
    commercial_partner_id bigint not null,
    name                  text not null,
    company_id            bigint,
    is_customer           boolean not null,
    is_supplier           boolean not null,
    primary key (snapshot_id, partner_id)
);
create view marts.dim_customer as select * from marts.dim_partner where is_customer;
create view marts.dim_supplier as select * from marts.dim_partner where is_supplier;

create table marts.dim_product (
    snapshot_id  uuid not null references marts.snapshot (snapshot_id),
    product_id   bigint not null,
    template_id  bigint not null,
    default_code text,
    name         text not null,
    product_type text not null,
    is_storable  boolean,
    category_id  bigint,
    cost_method  text,
    valuation    text,
    uom_id       bigint,
    primary key (snapshot_id, product_id)
);

create table marts.dim_account (
    snapshot_id  uuid not null references marts.snapshot (snapshot_id),
    account_id   bigint not null,
    code         text not null,
    name         text not null,
    account_type text not null,
    primary key (snapshot_id, account_id)
);

create table marts.fact_sales_order_line (
    snapshot_id            uuid not null references marts.snapshot (snapshot_id),
    sale_line_id           bigint not null,
    sale_order_id          bigint not null,
    order_name             text not null,
    company_id             bigint not null,
    customer_id            bigint not null,
    product_id             bigint,
    order_date             date not null,
    order_state            text not null,
    currency_code          text not null,
    uom_id                 bigint,
    qty_ordered            numeric(24, 6) not null,
    qty_ordered_product_uom numeric(24, 6),
    price_unit             numeric(24, 6) not null,
    discount_pct           numeric(9, 4) not null,
    subtotal               numeric(24, 6) not null,
    subtotal_company_ccy   numeric(24, 6),
    fx_rate                numeric(24, 12),
    fx_rate_date           date,
    qty_delivered          numeric(24, 6) not null,
    qty_invoiced           numeric(24, 6) not null,
    primary key (snapshot_id, sale_line_id)
);

create table marts.fact_invoice_line (
    snapshot_id         uuid not null references marts.snapshot (snapshot_id),
    invoice_line_id     bigint not null,
    invoice_id          bigint not null,
    invoice_name        text not null,
    move_type           text not null check (move_type in ('out_invoice', 'out_refund')),
    company_id          bigint not null,
    customer_id         bigint,
    product_id          bigint,
    account_id          bigint not null,
    invoice_date        date,
    accounting_date     date not null,
    currency_code       text not null,
    uom_id              bigint,
    quantity_signed     numeric(24, 6) not null,
    price_unit          numeric(24, 6) not null,
    discount_pct        numeric(9, 4) not null,
    subtotal_signed     numeric(24, 6) not null,
    revenue_company_ccy numeric(24, 6) not null,
    reversed_entry_id   bigint,
    primary key (snapshot_id, invoice_line_id)
);

create table marts.fact_posted_cogs_line (
    snapshot_id      uuid not null references marts.snapshot (snapshot_id),
    move_line_id     bigint not null,
    invoice_id       bigint not null,
    company_id       bigint not null,
    product_id       bigint,
    account_id       bigint not null,
    accounting_date  date not null,
    balance          numeric(24, 6) not null,
    primary key (snapshot_id, move_line_id)
);

create table marts.fact_stock_move (
    snapshot_id       uuid not null references marts.snapshot (snapshot_id),
    move_id           bigint not null,
    direction         text not null check (direction in ('incoming', 'outgoing', 'internal', 'unknown')),
    picking_id        bigint,
    company_id        bigint not null,
    product_id        bigint not null,
    sale_line_id      bigint,
    purchase_line_id  bigint,
    move_date         timestamp not null,
    state             text not null,
    qty_product_uom   numeric(24, 6) not null,
    value_company_ccy numeric(24, 6),
    primary key (snapshot_id, move_id)
);

create table marts.fact_cost_allocation (
    snapshot_id      uuid not null references marts.snapshot (snapshot_id),
    delivery_move_id bigint not null,
    receipt_move_id  bigint,
    allocation_no    integer not null,
    company_id       bigint not null,
    product_id       bigint not null,
    sale_line_id     bigint,
    quantity         numeric(24, 6) not null,
    unit_cost        numeric(24, 6),
    amount           numeric(24, 6),
    method           text not null,
    status           text not null check (status in ('ATTRIBUTED', 'UNDETERMINED')),
    reason           text,
    primary key (snapshot_id, delivery_move_id, allocation_no)
);

create table marts.bridge_sale_invoice_line (
    snapshot_id       uuid not null references marts.snapshot (snapshot_id),
    sale_line_id      bigint not null,
    invoice_line_id   bigint not null,
    link_cardinality  text not null check (link_cardinality in ('1:1', '1:N', 'N:1', 'N:M')),
    allocation_weight numeric(9, 6),
    primary key (snapshot_id, sale_line_id, invoice_line_id)
);

create table marts.data_quality_issue (
    snapshot_id  uuid not null references marts.snapshot (snapshot_id),
    issue_code   text not null,
    source_model text not null,
    source_id    bigint not null,
    detail       text not null,
    primary key (snapshot_id, issue_code, source_model, source_id)
);

create table marts.reconciliation_result (
    snapshot_id  uuid not null references marts.snapshot (snapshot_id),
    check_id     text not null,
    company_id   bigint not null,
    period       text not null,
    status       text not null check (status in ('RECONCILED', 'PARTIAL', 'UNRECONCILED', 'UNAVAILABLE')),
    independence text not null check (independence in ('SERVER_AGGREGATE', 'FIXTURE_CONTROL_TOTAL', 'NONE')),
    expected     numeric(24, 6),
    actual       numeric(24, 6),
    difference   numeric(24, 6),
    explanation  text not null,
    primary key (snapshot_id, check_id, company_id, period)
);

-- ---------------------------------------------------------------- audit
create table audit.event (
    sequence       bigint primary key,
    event_id       uuid not null unique,
    occurred_at    timestamptz not null,
    actor          text not null,
    action         text not null,
    object_type    text not null,
    object_id      text not null,
    correlation_id text,
    run_id         text,
    payload        jsonb not null,
    prev_hash      char(64) not null,
    event_hash     char(64) not null unique
);

create function audit.refuse_mutation() returns trigger language plpgsql as $$
begin
    raise exception 'audit.event is append-only';
end
$$;
create trigger event_no_update before update or delete on audit.event
    for each row execute function audit.refuse_mutation();
create trigger event_no_truncate before truncate on audit.event
    for each statement execute function audit.refuse_mutation();
"""


def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(f"create schema if not exists {schema}")
    op.execute(UPGRADE)


def downgrade() -> None:
    raise NotImplementedError("the foundation is not downgraded; create a new database instead")
