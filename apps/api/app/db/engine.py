"""Analytics database engine with target verification.

Connected mode requires ANALYTICS_DATABASE_URL. Fixture mode without a URL
uses an embedded PostgreSQL (pgserver, pgvector included) under `.benacta/`,
so the fixture path needs no external credential.

Every engine handed to migrations or seeds is verified twice: static URL
checks (`analytics_target_guard`) and live checks on the connection itself.
"""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.engine import Engine, make_url

from app.config import REPO_ROOT, Settings
from app.connectors.guards import (
    ODOO_SIGNATURE_TABLES,
    GuardReport,
    TargetGuardError,
    analytics_target_guard,
)

LOCAL_PGDATA = REPO_ROOT / ".benacta" / "pgdata"


def _psycopg(url: str) -> str:
    parsed = make_url(url)
    if parsed.drivername in {"postgresql", "postgres"}:
        parsed = parsed.set(drivername="postgresql+psycopg")
    return parsed.render_as_string(hide_password=False)


def local_server(pgdata: Path = LOCAL_PGDATA, *, cleanup_mode: str | None = None):
    """Start or reuse the embedded server.

    cleanup_mode None keeps the development server running between commands
    (stop it with `benacta local-db-stop`); tests pass "delete" and call cleanup().
    """
    import pgserver

    pgdata.mkdir(parents=True, exist_ok=True)
    _clear_stale_lock(pgdata)
    return pgserver.get_server(str(pgdata), cleanup_mode=cleanup_mode)


def _postmaster_alive(pgdata: Path) -> bool | None:
    """None when no lock file exists; otherwise whether its PID is a running postgres process."""
    import psutil

    pid_file = pgdata / "postmaster.pid"
    if not pid_file.exists():
        return None
    pid = int(pid_file.read_text(encoding="utf-8").splitlines()[0])
    try:
        return "postgres" in psutil.Process(pid).name().lower()
    except psutil.NoSuchProcess:
        return False


def _clear_stale_lock(pgdata: Path) -> None:
    # A killed server leaves postmaster.pid behind; PostgreSQL treats such a file as stale, pgserver does not.
    if _postmaster_alive(pgdata) is False:
        (pgdata / "postmaster.pid").unlink()


def stop_local_server(pgdata: Path = LOCAL_PGDATA) -> bool:
    """Stop the development server if its data directory exists. Data is kept."""
    from pgserver._commands import pg_ctl

    alive = _postmaster_alive(pgdata)
    if not alive:
        if alive is False:
            _clear_stale_lock(pgdata)
        return False
    pg_ctl(["-w", "stop"], pgdata=pgdata)
    return True


def local_database_url(database: str, pgdata: Path = LOCAL_PGDATA, *, server=None) -> str:
    """Ensure `database` exists on the embedded server and return its URL."""
    server = server or local_server(pgdata)
    admin_url = make_url(_psycopg(server.get_uri()))
    admin = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(sa.text("select 1 from pg_database where datname = :d"), {"d": database}).scalar()
            if not exists:
                conn.execute(sa.text(f'create database "{database}"'))
    finally:
        admin.dispose()
    return admin_url.set(database=database).render_as_string(hide_password=False)


def resolve_analytics_url(settings: Settings) -> str:
    if settings.analytics_database_url is not None:
        return _psycopg(settings.analytics_database_url.get_secret_value())
    # Without a managed database, every mode uses the embedded development server (.benacta/pgdata).
    return local_database_url(settings.analytics_db_expected_name)


def verify_live_target(engine: Engine, settings: Settings) -> GuardReport:
    """Checks run on the connection: right database name, pgvector available, not an Odoo database."""
    report = GuardReport("analytics_live_target")
    with engine.connect() as conn:
        name = conn.execute(sa.text("select current_database()")).scalar()
        report.add(
            "current_database",
            name == settings.analytics_db_expected_name,
            f"connected to {name}, expected {settings.analytics_db_expected_name}",
        )
        odoo_tables = (
            conn.execute(
                sa.text(
                    "select table_name from information_schema.tables where table_schema = 'public' and table_name = any(:t)"
                ),
                {"t": list(ODOO_SIGNATURE_TABLES)},
            )
            .scalars()
            .all()
        )
        report.add(
            "no_odoo_signature", not odoo_tables, f"Odoo tables found: {sorted(odoo_tables)}" if odoo_tables else "none"
        )
        vector = conn.execute(sa.text("select 1 from pg_available_extensions where name = 'vector'")).scalar()
        report.add("pgvector_available", bool(vector), "extension 'vector' must be installable")
    return report


def analytics_engine(settings: Settings, *, url: str | None = None, verify: bool = True) -> Engine:
    """Engine for the BENACTA analytics database. `verify` runs static and live target checks."""
    resolved = url or resolve_analytics_url(settings)
    if verify:
        if settings.analytics_database_url is not None and url is None:
            analytics_target_guard(settings).raise_if_blocked()
        elif make_url(resolved).database != settings.analytics_db_expected_name:
            raise TargetGuardError(f"database must be {settings.analytics_db_expected_name}")
    engine = sa.create_engine(resolved, pool_pre_ping=True, future=True)
    if verify:
        report = verify_live_target(engine, settings)
        if not report.allowed:
            engine.dispose()
            report.raise_if_blocked()
    return engine
