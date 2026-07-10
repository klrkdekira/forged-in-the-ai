import asyncio

import click

from app.settings import get_settings
from cli.paths import SRD_PATH
from state.db import app_db_path, make_engine, make_session_factory
from state.migrations import run_migrations
from state.srd_index import chunk_srd, index_srd_chunks


async def _index(srd_text: str) -> int:
    db_path = app_db_path(get_settings().data_dir)
    run_migrations(db_path)
    engine = make_engine(db_path)
    try:
        session_factory = make_session_factory(engine)
        chunks = chunk_srd(srd_text)
        async with session_factory() as session:
            await index_srd_chunks(session, chunks)
        return len(chunks)
    finally:
        await engine.dispose()


@click.command("index-srd")
def index_srd() -> None:
    """FR-13/ADR-0003: (re)build the SRD retrieval index in app.db from
    the local SRD copy."""
    if not SRD_PATH.exists():
        raise click.ClickException(f"SRD file not found at {SRD_PATH}; run `fid fetch-srd` first")

    count = asyncio.run(_index(SRD_PATH.read_text(encoding="utf-8")))
    click.echo(f"index-srd: indexed {count} chunks into {app_db_path(get_settings().data_dir)}")
