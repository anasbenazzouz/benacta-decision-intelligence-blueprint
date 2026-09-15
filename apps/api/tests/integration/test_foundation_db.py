from __future__ import annotations

import pytest
import sqlalchemy as sa

from app.audit.log import append_event, export_jsonl, verify_chain
from app.connectors.guards import TargetGuardError
from app.db import migrate
from app.db.engine import analytics_engine
from tests.conftest import make_settings
from tests.integration.conftest import scalar


def test_migration_from_empty_database_creates_every_schema_and_pgvector(engine):
    assert migrate.current_revision(engine) == "0005_decision_workflow"
    expected = {"raw", "staging", "marts", "semantic", "decision", "audit", "planning"}
    assert expected <= set(sa.inspect(engine).get_schema_names())
    assert scalar(engine, "select extversion from pg_extension where extname = 'vector'")


def test_migration_is_idempotent(engine):
    migrate.upgrade(engine)
    assert migrate.current_revision(engine) == "0005_decision_workflow"


def test_engine_refuses_a_database_with_another_name(analytics_url):
    wrong = sa.engine.make_url(analytics_url).set(database="postgres").render_as_string(hide_password=False)
    with pytest.raises(TargetGuardError):
        analytics_engine(make_settings(benacta_mode="fixture"), url=wrong)


def test_engine_refuses_a_database_carrying_odoo_tables(analytics_url):
    admin_url = sa.engine.make_url(analytics_url).set(database="postgres")
    admin = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(sa.text('drop database if exists "odoo_lookalike"'))
        c.execute(sa.text('create database "odoo_lookalike"'))
    admin.dispose()
    lookalike_url = admin_url.set(database="odoo_lookalike")
    seeded = sa.create_engine(lookalike_url)
    with seeded.begin() as c:
        c.execute(sa.text("create table public.ir_module_module (id int)"))
    seeded.dispose()

    settings = make_settings(benacta_mode="fixture", analytics_db_expected_name="odoo_lookalike")
    with pytest.raises(TargetGuardError, match="no_odoo_signature"):
        analytics_engine(settings, url=lookalike_url.render_as_string(hide_password=False))


def test_audit_chain_appends_verifies_and_exports(engine):
    with engine.begin() as c:
        append_event(c, actor="test", action="chain.check", object_type="test", object_id="1", payload={"n": 1})
        append_event(c, actor="test", action="chain.check", object_type="test", object_id="2", payload={"n": 2})
    with engine.connect() as c:
        result = verify_chain(c)
        exported = export_jsonl(c)
    assert result.valid, result
    assert result.events_checked >= 2
    assert exported.count("\n") == result.events_checked


def test_audit_rejects_update_delete_and_truncate(engine):
    with engine.begin() as c:
        append_event(c, actor="test", action="immutability", object_type="test", object_id="x", payload={})
    for statement in (
        "update audit.event set actor = 'intruder'",
        "delete from audit.event",
        "truncate audit.event",
    ):
        with pytest.raises(sa.exc.DBAPIError, match="append-only"), engine.begin() as c:
            c.execute(sa.text(statement))


def test_audit_tampering_is_detected_when_trigger_is_bypassed(engine):
    with engine.begin() as c:
        append_event(c, actor="test", action="tamper.target", object_type="test", object_id="t", payload={"v": "a"})
    with engine.begin() as c:
        # A privileged actor disables the trigger and rewrites content: the chain must expose it.
        c.execute(sa.text("alter table audit.event disable trigger event_no_update"))
        c.execute(
            sa.text(
                'update audit.event set payload = \'{"v": "b"}\'::jsonb'
                " where sequence = (select max(sequence) from audit.event)"
            )
        )
        c.execute(sa.text("alter table audit.event enable trigger event_no_update"))
        result = verify_chain(c)
        assert not result.valid
        assert result.reason == "event content altered"
        # Restore so later tests keep a valid chain.
        c.execute(sa.text("alter table audit.event disable trigger event_no_update"))
        c.execute(
            sa.text(
                'update audit.event set payload = \'{"v": "a"}\'::jsonb'
                " where sequence = (select max(sequence) from audit.event)"
            )
        )
        c.execute(sa.text("alter table audit.event enable trigger event_no_update"))
    with engine.connect() as c:
        assert verify_chain(c).valid


def test_audit_payload_refuses_secret_keys(engine):
    with pytest.raises(ValueError, match="secrets"), engine.begin() as c:
        append_event(c, actor="test", action="x", object_type="t", object_id="1", payload={"nested": {"api_key": "k"}})
