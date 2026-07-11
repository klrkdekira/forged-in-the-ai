import asyncio
import sqlite3
from pathlib import Path

from sqlalchemy import text

from state.db import app_db_path, campaign_db_path, make_engine, make_session_factory
from state.migrations import run_app_migrations, run_campaign_migrations


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_db_paths(tmp_path: Path) -> None:
    assert app_db_path(tmp_path) == tmp_path / "app.db"
    assert campaign_db_path(tmp_path, "abc123") == tmp_path / "campaign-abc123.db"


def test_run_app_migrations_creates_file_sets_wal_and_is_idempotent(tmp_path: Path) -> None:
    db_path = app_db_path(tmp_path)

    run_app_migrations(db_path)
    run_app_migrations(db_path)  # ADR-0005: migrations run per file on open

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        assert conn.execute("SELECT version_num FROM alembic_version").fetchall()
        assert "campaigns" in _table_names(conn)
    finally:
        conn.close()


def test_run_campaign_migrations_creates_event_and_snapshot_tables(tmp_path: Path) -> None:
    db_path = campaign_db_path(tmp_path, "abc123")

    run_campaign_migrations(db_path)
    run_campaign_migrations(db_path)  # ADR-0005: migrations run per file on open

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        assert {"events", "snapshots"} <= _table_names(conn)
    finally:
        conn.close()


def test_async_engine_uses_wal_and_can_query(tmp_path: Path) -> None:
    db_path = app_db_path(tmp_path)

    async def query() -> str:
        engine = make_engine(db_path)
        try:
            session_factory = make_session_factory(engine)
            async with session_factory() as session:
                result = await session.execute(text("PRAGMA journal_mode"))
                return result.scalar_one()
        finally:
            await engine.dispose()

    assert asyncio.run(query()) == "wal"
