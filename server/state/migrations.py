from pathlib import Path

from alembic.config import Config

from alembic import command

SERVER_ROOT = Path(__file__).resolve().parent.parent
ALEMBIC_INI = SERVER_ROOT / "alembic.ini"


def _run(db_path: Path, script_location: Path) -> None:
    """Upgrade db_path to head, creating it if new (ADR-0005: migrations run
    per file on open). Alembic runs synchronously, so this uses the plain
    sqlite driver rather than the app's async aiosqlite engine."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(script_location))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")


def run_app_migrations(db_path: Path) -> None:
    """app.db lineage (ADR-0005): capability cache, settings, SRD/FTS
    retrieval index, the campaign directory."""
    _run(db_path, SERVER_ROOT / "alembic")


def run_campaign_migrations(db_path: Path) -> None:
    """campaign-<id>.db lineage (ADR-0005): one file per campaign, its own
    Alembic lineage since its tables are unrelated to app.db's."""
    _run(db_path, SERVER_ROOT / "alembic_campaign")
