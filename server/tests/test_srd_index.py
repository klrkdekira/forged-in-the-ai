from pathlib import Path

import pytest

from state.db import app_db_path, make_engine, make_session_factory
from state.migrations import run_migrations
from state.srd_index import SrdChunkRecord, chunk_srd, index_srd_chunks, search_srd

_SAMPLE_SRD = """\
# Resistance and Armor

When your PC suffers a consequence you don't like, you can resist it.

## Armor

Mark an armor box to reduce or avoid a consequence instead of rolling.

# Fortune Roll

The fortune roll is a tool the GM can use to disclaim decision making.
"""


def test_chunk_srd_splits_on_every_heading():
    # FR-13/ADR-0003: one chunk per heading, body up to the next heading.
    chunks = chunk_srd(_SAMPLE_SRD)

    assert [c.heading for c in chunks] == ["Resistance and Armor", "Armor", "Fortune Roll"]
    assert "resist it" in chunks[0].body
    assert "armor box" in chunks[1].body


def test_chunk_srd_skips_headings_with_no_body():
    chunks = chunk_srd("# A\n# B\ntext\n")

    assert [c.heading for c in chunks] == ["B"]


@pytest.mark.anyio
async def test_index_and_search_srd_chunks(tmp_path: Path) -> None:
    db_path = app_db_path(tmp_path)
    run_migrations(db_path)
    engine = make_engine(db_path)
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            await index_srd_chunks(session, chunk_srd(_SAMPLE_SRD))

            hits = await search_srd(session, "armor")

            assert any(hit.heading == "Armor" for hit in hits)
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_search_srd_returns_nothing_for_an_unmatched_query(tmp_path: Path) -> None:
    db_path = app_db_path(tmp_path)
    run_migrations(db_path)
    engine = make_engine(db_path)
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            await index_srd_chunks(session, chunk_srd(_SAMPLE_SRD))

            hits = await search_srd(session, "nonexistentxyz")

            assert hits == []
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_index_srd_chunks_replaces_previous_contents(tmp_path: Path) -> None:
    db_path = app_db_path(tmp_path)
    run_migrations(db_path)
    engine = make_engine(db_path)
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            await index_srd_chunks(
                session, [SrdChunkRecord(heading="Old", level=1, line=1, body="old text")]
            )
            await index_srd_chunks(session, chunk_srd(_SAMPLE_SRD))

            hits = await search_srd(session, "old")

            assert hits == []
    finally:
        await engine.dispose()
