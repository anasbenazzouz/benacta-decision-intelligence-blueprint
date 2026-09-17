"""Governed document registry for the investigation corpus.

Revision ID: 0006_governed_documents
Revises: 0005_decision_workflow
"""

from alembic import op

revision = "0006_governed_documents"
down_revision = "0005_decision_workflow"
branch_labels = None
depends_on = None

UPGRADE = r"""
-- Only registered, authorised documents can be retrieved and cited. Content stays in the repository; the registry
-- holds provenance and the content hash so a citation can be re-verified.
create table semantic.governed_document (
    doc_id         text primary key,
    title          text not null,
    source         text not null,
    owner          text not null,
    effective_date date not null,
    version        integer not null check (version >= 1),
    authorised     boolean not null,
    path           text not null,
    content_hash   char(64) not null,
    sections       integer not null,
    indexed_at     timestamptz not null default now()
);
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    raise NotImplementedError("create a new database instead")
