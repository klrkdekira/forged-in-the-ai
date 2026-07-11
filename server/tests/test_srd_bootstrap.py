from pathlib import Path

import httpx2 as httpx
import pytest

from state.db import make_engine, make_session_factory
from state.migrations import run_app_migrations
from state.srd_bootstrap import ensure_srd_indexed
from state.srd_index import chunk_srd, index_srd_chunks, search_srd

_SRD_TEXT = "# Action Roll\n\nRoll your dice pool; 6 is a full success.\n"


def _db(tmp_path: Path) -> Path:
    db_path = tmp_path / "app.db"
    run_app_migrations(db_path)
    return db_path


@pytest.mark.anyio
async def test_ensure_srd_indexed_fetches_and_indexes_when_empty(tmp_path: Path):
    # FR-13: a fresh app.db (the container's first start) gets its
    # retrieval corpus from the official SRD source.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_SRD_TEXT)

    db_path = _db(tmp_path)
    count = await ensure_srd_indexed(db_path, transport=httpx.MockTransport(handler))

    assert count == 1
    engine = make_engine(db_path)
    try:
        async with make_session_factory(engine)() as session:
            hits = await search_srd(session, '"success"')
    finally:
        await engine.dispose()
    assert hits[0].heading == "Action Roll"


@pytest.mark.anyio
async def test_ensure_srd_indexed_skips_when_chunks_already_exist(tmp_path: Path):
    # A no-op on every start after the first: no re-download.
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not fetch when the index is already populated")

    db_path = _db(tmp_path)
    engine = make_engine(db_path)
    try:
        async with make_session_factory(engine)() as session:
            await index_srd_chunks(session, chunk_srd(_SRD_TEXT))
    finally:
        await engine.dispose()

    count = await ensure_srd_indexed(db_path, transport=httpx.MockTransport(handler))

    assert count is None


@pytest.mark.anyio
async def test_ensure_srd_indexed_degrades_when_the_download_fails(tmp_path: Path):
    # Offline first start: no retrieval rather than a crashed startup;
    # the index stays empty so the next start tries again.
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no network")

    db_path = _db(tmp_path)
    count = await ensure_srd_indexed(db_path, transport=httpx.MockTransport(handler))

    assert count is None
    engine = make_engine(db_path)
    try:
        async with make_session_factory(engine)() as session:
            hits = await search_srd(session, '"success"')
    finally:
        await engine.dispose()
    assert hits == []
