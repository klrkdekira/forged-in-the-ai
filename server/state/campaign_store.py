from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ai.tools import GameState
from state.db import make_engine, make_session_factory
from state.migrations import run_campaign_migrations
from state.models import EventRow, Snapshot

_SNAPSHOT_ID = 1


async def save_state(db_path: Path, state: GameState) -> None:
    """FR-18/FR-19: upsert the cached snapshot, and append only the tail of
    the event log past what's already stored - the log is append-only, so
    every event up to the last stored sequence is already there."""
    engine = make_engine(db_path)
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session, session.begin():
            max_sequence = await session.scalar(select(func.max(EventRow.sequence))) or 0
            session.add_all(
                EventRow(
                    sequence=event.sequence,
                    entity_type=event.entity_type,
                    entity_id=event.entity_id,
                    event_type=event.event_type,
                    payload=event.payload,
                    occurred_at=event.occurred_at,
                )
                for event in state.log.events
                if event.sequence > max_sequence
            )
            state_json = state.model_dump_json()
            await session.execute(
                sqlite_insert(Snapshot)
                .values(id=_SNAPSHOT_ID, state_json=state_json)
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={"state_json": state_json, "updated_at": func.now()},
                )
            )
    finally:
        await engine.dispose()


async def load_state(db_path: Path) -> GameState | None:
    """None if the campaign has no snapshot yet (a file that doesn't exist,
    or exists but was never saved to). The snapshot embeds the full event
    log, so it alone is enough to resume from."""
    if not db_path.exists():
        return None
    engine = make_engine(db_path)
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            row = await session.get(Snapshot, _SNAPSHOT_ID)
            return GameState.model_validate_json(row.state_json) if row is not None else None
    finally:
        await engine.dispose()


async def create_campaign(db_path: Path, initial_state: GameState) -> None:
    """Migrates a fresh campaign-<id>.db to head and writes its starting
    snapshot, so a WS connection can always find a loadable state."""
    run_campaign_migrations(db_path)
    await save_state(db_path, initial_state)
