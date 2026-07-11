from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ai.replay import replay_state
from ai.tools import GameState
from engine.events import Event
from state.db import make_engine, make_session_factory
from state.migrations import run_campaign_migrations
from state.models import EventRow, Snapshot

_BASE_SNAPSHOT_ID = 0
_LATEST_SNAPSHOT_ID = 1


async def save_state(db_path: Path, state: GameState) -> None:
    """FR-18/FR-19: upsert the cached (latest) snapshot, and append only
    the tail of the event log past what's already stored - the log is
    append-only, so every event up to the last stored sequence is already
    there."""
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
                .values(id=_LATEST_SNAPSHOT_ID, state_json=state_json)
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
            row = await session.get(Snapshot, _LATEST_SNAPSHOT_ID)
            return GameState.model_validate_json(row.state_json) if row is not None else None
    finally:
        await engine.dispose()


async def load_base_state(db_path: Path) -> GameState:
    """The campaign's original starting state, written once at creation
    and never overwritten - `undo_to`'s fold-from point. Distinct from
    the "latest" snapshot `load_state` returns, which is a cache that
    changes on every save."""
    engine = make_engine(db_path)
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            row = await session.get(Snapshot, _BASE_SNAPSHOT_ID)
            return GameState.model_validate_json(row.state_json)
    finally:
        await engine.dispose()


async def create_campaign(db_path: Path, initial_state: GameState) -> None:
    """Migrates a fresh campaign-<id>.db to head and writes its starting
    snapshot as both the base (immutable) and the latest cache, so a WS
    connection can always find a loadable state."""
    run_campaign_migrations(db_path)
    await save_state(db_path, initial_state)
    engine = make_engine(db_path)
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session, session.begin():
            session.add(Snapshot(id=_BASE_SNAPSHOT_ID, state_json=initial_state.model_dump_json()))
    finally:
        await engine.dispose()


async def undo_to(db_path: Path, sequence: int) -> GameState:
    """FR-19: truncate the event log back to `sequence` (inclusive) and
    replay what survives onto the campaign's base state - undo, via the
    same event-sourcing the log's authoritative status already promises.
    Irreversible: truncated events are actually deleted, not just hidden,
    so there's no redo."""
    base = await load_base_state(db_path)
    engine = make_engine(db_path)
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session, session.begin():
            await session.execute(delete(EventRow).where(EventRow.sequence > sequence))
            rows = await session.scalars(select(EventRow).order_by(EventRow.sequence))
            events = [
                Event(
                    sequence=row.sequence,
                    entity_type=row.entity_type,
                    entity_id=row.entity_id,
                    event_type=row.event_type,
                    payload=row.payload,
                    occurred_at=row.occurred_at,
                )
                for row in rows
            ]
            new_state = replay_state(base, events)
            state_json = new_state.model_dump_json()
            await session.execute(
                sqlite_insert(Snapshot)
                .values(id=_LATEST_SNAPSHOT_ID, state_json=state_json)
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={"state_json": state_json, "updated_at": func.now()},
                )
            )
    finally:
        await engine.dispose()
    return new_state
