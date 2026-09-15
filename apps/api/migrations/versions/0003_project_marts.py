"""Project controlling marts: projects, work packages, milestones, people, time, commitments, bills, receivables.

Revision ID: 0003_project_marts
Revises: 0002_planning_and_reports
"""

from alembic import op

revision = "0003_project_marts"
down_revision = "0002_planning_and_reports"
branch_labels = None
depends_on = None

UPGRADE = r"""
create table marts.dim_project (
    snapshot_id         uuid not null references marts.snapshot (snapshot_id),
    project_id          bigint not null,
    project_code        text not null,
    name                text not null,
    company_id          bigint not null,
    business_unit       text,
    is_internal         boolean not null,
    hour_category       text not null,
    customer_id         bigint,
    manager_user_id     bigint,
    manager_name        text,
    customer_name       text,
    contract_type       text,
    phase               text,
    date_start          date,
    date_end            date,
    analytic_account_id bigint,
    contract_sale_line_id bigint,
    contract_currency   text,
    fixed_rate_per_eur  numeric(24, 12),
    primary key (snapshot_id, project_id)
);

create table marts.dim_work_package (
    snapshot_id   uuid not null references marts.snapshot (snapshot_id),
    task_id       bigint not null,
    project_id    bigint not null,
    wbs_code      text not null,
    name          text not null,
    allocated_hours numeric(24, 6),
    is_change_order_scope boolean not null,
    primary key (snapshot_id, task_id)
);

create table marts.dim_milestone (
    snapshot_id         uuid not null references marts.snapshot (snapshot_id),
    milestone_id        bigint not null,
    project_id          bigint not null,
    milestone_code      text,
    name                text not null,
    deadline            date,
    is_reached          boolean not null,
    reached_date        date,
    sale_line_id        bigint,
    quantity_percentage numeric(12, 6),
    billing_amount      numeric(24, 6),
    primary key (snapshot_id, milestone_id)
);

create table marts.dim_employee (
    snapshot_id   uuid not null references marts.snapshot (snapshot_id),
    employee_id   bigint not null,
    employee_code text not null,
    name          text not null,
    company_id    bigint not null,
    department    text,
    role          text,
    hourly_cost   numeric(24, 6),
    is_external   boolean not null,
    hours_per_day numeric(8, 4),
    primary key (snapshot_id, employee_id)
);

create table marts.fact_timesheet (
    snapshot_id  uuid not null references marts.snapshot (snapshot_id),
    line_id      bigint not null,
    entry_date   date not null,
    company_id   bigint not null,
    employee_id  bigint not null,
    project_id   bigint not null,
    task_id      bigint,
    hours        numeric(24, 6) not null,
    cost_amount  numeric(24, 6) not null,
    primary key (snapshot_id, line_id)
);

create table marts.fact_purchase_commitment (
    snapshot_id      uuid not null references marts.snapshot (snapshot_id),
    purchase_line_id bigint not null,
    purchase_order_id bigint not null,
    order_date       date not null,
    company_id       bigint not null,
    project_id       bigint,
    work_package     text,
    supplier_id      bigint,
    cost_category    text not null,
    ordered_quantity numeric(24, 6) not null,
    received_quantity numeric(24, 6) not null,
    price_unit       numeric(24, 6) not null,
    ordered_amount   numeric(24, 6) not null,
    primary key (snapshot_id, purchase_line_id)
);

create table marts.fact_vendor_bill_line (
    snapshot_id      uuid not null references marts.snapshot (snapshot_id),
    move_line_id     bigint not null,
    move_id          bigint not null,
    bill_name        text not null,
    move_type        text not null check (move_type in ('in_invoice', 'in_refund')),
    accounting_date  date not null,
    company_id       bigint not null,
    project_id       bigint,
    analytic_project_id bigint,
    purchase_line_id bigint,
    cost_category    text not null,
    quantity         numeric(24, 6) not null,
    amount           numeric(24, 6) not null,
    primary key (snapshot_id, move_line_id)
);

create table marts.fact_receivable (
    snapshot_id      uuid not null references marts.snapshot (snapshot_id),
    invoice_id       bigint not null,
    invoice_name     text not null,
    move_type        text not null check (move_type in ('out_invoice', 'out_refund')),
    company_id       bigint not null,
    project_id       bigint,
    customer_id      bigint,
    invoice_date     date not null,
    due_date         date,
    currency_code    text not null,
    amount_untaxed_ccy numeric(24, 6) not null,
    amount_total_ccy numeric(24, 6) not null,
    amount_untaxed_company numeric(24, 6) not null,
    amount_total_company numeric(24, 6) not null,
    primary key (snapshot_id, invoice_id)
);

create table marts.fact_customer_payment (
    snapshot_id   uuid not null references marts.snapshot (snapshot_id),
    payment_id    bigint not null,
    invoice_id    bigint not null,
    payment_date  date not null,
    company_id    bigint not null,
    currency_code text not null,
    amount_ccy    numeric(24, 6) not null,
    primary key (snapshot_id, payment_id, invoice_id)
);

create table marts.fact_change_order (
    snapshot_id    uuid not null references marts.snapshot (snapshot_id),
    sale_order_id  bigint not null,
    project_id     bigint not null,
    order_name     text not null,
    state          text not null,
    order_date     date not null,
    is_contract    boolean not null,
    currency_code  text not null,
    amount_untaxed_ccy numeric(24, 6) not null,
    primary key (snapshot_id, sale_order_id, project_id)
);
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    raise NotImplementedError("create a new database instead")
