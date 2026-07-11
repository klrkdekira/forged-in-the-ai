import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ai.tools import GameState
from engine.character import Character
from engine.crew import Crew
from engine.session import Session
from state.campaign_store import create_campaign, load_state, save_state
from state.db import campaign_db_path


def _starter_state() -> GameState:
    return GameState(
        character=Character(name="Scoundrel", playbook="Original Playbook"),
        crew=Crew(name="The Crew", crew_type="Original Crew Type"),
        session=Session(),
    )


@pytest.mark.anyio
async def test_load_state_returns_none_for_a_campaign_that_was_never_created(
    tmp_path: Path,
) -> None:
    assert await load_state(campaign_db_path(tmp_path, "nope")) is None


@pytest.mark.anyio
async def test_create_then_load_round_trips_the_full_state(tmp_path: Path) -> None:
    # NFR-5: the operational store round-trips a campaign's state exactly.
    db_path = campaign_db_path(tmp_path, "abc123")
    state = _starter_state()

    await create_campaign(db_path, state)
    loaded = await load_state(db_path)

    assert loaded == state


@pytest.mark.anyio
async def test_save_state_appends_only_the_new_event_tail(tmp_path: Path) -> None:
    # FR-19: the log is append-only; a second save must not re-insert
    # events already stored.
    db_path = campaign_db_path(tmp_path, "abc123")
    state = _starter_state()
    await create_campaign(db_path, state)

    state = state.model_copy(
        update={
            "log": state.log.append("character", "Scoundrel", "test_event", {}, datetime.now(UTC))
        }
    )
    await save_state(db_path, state)
    await save_state(db_path, state)  # same log again - must not duplicate

    loaded = await load_state(db_path)
    assert loaded == state

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT count(*) FROM events").fetchone() == (1,)
    finally:
        conn.close()
