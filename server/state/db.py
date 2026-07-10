from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def app_db_path(data_dir: Path) -> Path:
    return data_dir / "app.db"


def campaign_db_path(data_dir: Path, campaign_id: str) -> Path:
    return data_dir / f"campaign-{campaign_id}.db"


def make_engine(db_path: Path) -> AsyncEngine:
    """One SQLite file, WAL mode, async driver (ADR-0005)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_wal(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
