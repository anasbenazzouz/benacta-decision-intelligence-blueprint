"""Programmatic Alembic upgrade on an engine that already passed the target checks."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Engine

API_ROOT = Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    return config


def upgrade(engine: Engine, revision: str = "head") -> None:
    config = alembic_config()
    config.attributes["engine"] = engine
    command.upgrade(config, revision)


def current_revision(engine: Engine) -> str | None:
    from alembic.runtime.migration import MigrationContext

    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()
