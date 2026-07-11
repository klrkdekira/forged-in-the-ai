from pathlib import Path

import pytest

from state.db import app_db_path, make_engine, make_session_factory
from state.migrations import run_app_migrations
from state.srd_index import (
    SrdChunkRecord,
    build_match_query,
    chunk_module_prose,
    chunk_srd,
    index_module_chunks,
    index_srd_chunks,
    search_srd,
)

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
    run_app_migrations(db_path)
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
    run_app_migrations(db_path)
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
    run_app_migrations(db_path)
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


def test_chunk_module_prose_groups_paragraphs_up_to_the_size_cap():
    # FR-24: no markdown headings to rely on, so it groups by size instead.
    text = "\n\n".join(["a" * 500, "b" * 500, "c" * 10])

    chunks = chunk_module_prose("my-hack", text, target_chunk_chars=800)

    assert len(chunks) == 2
    assert chunks[0].body == "a" * 500
    assert chunks[1].body == ("b" * 500) + "\n\n" + ("c" * 10)
    assert all(c.source == "module:my-hack" for c in chunks)


def test_chunk_module_prose_skips_blank_paragraphs():
    chunks = chunk_module_prose("my-hack", "one\n\n\n\ntwo")

    assert [c.body for c in chunks] == ["one\n\ntwo"]


def test_build_match_query_quotes_and_ors_each_token():
    assert build_match_query("I pick the lock!") == '"I" OR "pick" OR "the" OR "lock"'


def test_build_match_query_is_empty_for_text_with_no_word_tokens():
    assert build_match_query("...   !!!") == ""


@pytest.mark.anyio
async def test_search_srd_ranks_srd_and_module_chunks_together(tmp_path: Path) -> None:
    # FR-24: "module prose joins the GM retrieval corpus alongside the
    # SRD" - one query, one ranked result set across both.
    db_path = app_db_path(tmp_path)
    run_app_migrations(db_path)
    engine = make_engine(db_path)
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            await index_srd_chunks(session, chunk_srd(_SAMPLE_SRD))
            await index_module_chunks(
                session, "my-hack", chunk_module_prose("my-hack", "A house rule about armor.")
            )

            hits = await search_srd(session, "armor")

            sources = {hit.source for hit in hits}
            assert sources == {"srd", "module:my-hack"}
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_index_module_chunks_does_not_touch_srd_or_other_modules(tmp_path: Path) -> None:
    db_path = app_db_path(tmp_path)
    run_app_migrations(db_path)
    engine = make_engine(db_path)
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            await index_srd_chunks(session, chunk_srd(_SAMPLE_SRD))
            await index_module_chunks(
                session, "hack-a", chunk_module_prose("hack-a", "Hack A's own rule.")
            )
            await index_module_chunks(
                session, "hack-b", chunk_module_prose("hack-b", "Hack B's own rule.")
            )

            # re-indexing hack-a shouldn't drop hack-b's chunks or the SRD's
            await index_module_chunks(
                session, "hack-a", chunk_module_prose("hack-a", "Hack A's revised rule.")
            )

            armor_hits = await search_srd(session, "armor")
            hack_b_hits = await search_srd(session, "Hack")

            assert any(hit.source == "srd" for hit in armor_hits)
            assert any(hit.source == "module:hack-b" for hit in hack_b_hits)
    finally:
        await engine.dispose()
