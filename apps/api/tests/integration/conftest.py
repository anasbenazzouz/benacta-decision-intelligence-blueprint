"""Ephemeral PostgreSQL (pgvector included) for integration tests. No external credential."""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from app.db import migrate
from app.db.engine import analytics_engine, local_database_url, local_server
from tests.conftest import make_settings


@pytest.fixture(scope="session")
def pg_settings():
    return make_settings(benacta_mode="fixture")


@pytest.fixture(scope="session")
def analytics_url(tmp_path_factory, pg_settings) -> str:
    # "delete" stops the server and removes its data when the session ends; None would leak a server per run.
    server = local_server(tmp_path_factory.mktemp("pgdata"), cleanup_mode="delete")
    try:
        yield local_database_url(pg_settings.analytics_db_expected_name, server=server)
    finally:
        server.cleanup()


@pytest.fixture(scope="session")
def engine(analytics_url, pg_settings):
    engine = analytics_engine(pg_settings, url=analytics_url)
    migrate.upgrade(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def conn(engine):
    with engine.begin() as connection:
        yield connection


def scalar(engine, sql: str, **params):
    with engine.connect() as c:
        return c.execute(sa.text(sql), params).scalar()
