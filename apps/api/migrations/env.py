"""Alembic environment. Migrations only ever run against a verified BENACTA analytics database."""

from __future__ import annotations

from alembic import context

from app.config import get_settings
from app.db.engine import analytics_engine

config = context.config


def run_migrations_online() -> None:
    engine = config.attributes.get("engine")
    owns_engine = engine is None
    if owns_engine:
        engine = analytics_engine(get_settings(), url=config.attributes.get("url"))
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, version_table_schema="public")
            with context.begin_transaction():
                context.run_migrations()
    finally:
        if owns_engine:
            engine.dispose()


if context.is_offline_mode():
    raise SystemExit("offline SQL generation is disabled: migrations must verify their live target")
run_migrations_online()
