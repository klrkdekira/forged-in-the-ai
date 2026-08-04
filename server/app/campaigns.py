import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from ai.recap import render_recap
from ai.replay import replay_state
from ai.tools import GameState
from app.settings import Settings, get_settings
from engine.character import Character
from engine.crew import Crew
from engine.events import EventLog
from engine.session import Session
from state.campaign_store import create_campaign as write_campaign_files
from state.campaign_store import load_base_state, load_state, save_state
from state.db import app_db_path, campaign_db_path, make_engine, make_session_factory
from state.models import CampaignIndex

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


class CampaignSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    name: str
    created_at: datetime
    updated_at: datetime


class CampaignExport(BaseModel):
    """NFR-5/ADR-0005: the promised portable artefact - a JSONL event log
    (`EventLog.to_jsonl`, the authoritative source) plus the base and
    latest JSON snapshots (the cache). `import_campaign` reconstructs a
    fresh campaign from this alone by replaying `log_jsonl` onto
    `base_state` (`ai/replay.py`, the same fold `undo_to` uses) - it does
    not need this server's own database file, only what this model
    carries, which is the portability guarantee NFR-5 asks for."""

    campaign_id: str
    name: str
    log_jsonl: str
    base_state: GameState
    latest_state: GameState


class CreateCampaignRequest(BaseModel):
    name: str
    character: Character | None = Field(
        None,
        description="FR-8: an imported character sheet (an uploaded JSON file, or a saved "
        "guided-entry file via GET /api/characters); a fixed starter is used if omitted",
    )
    crew: Crew | None = Field(
        None,
        description="FR-8/G2: an imported crew sheet (an uploaded JSON file); a fixed starter "
        "is used if omitted",
    )


def _new_game_state(character: Character | None = None, crew: Crew | None = None) -> GameState:
    """FR-8: an imported character/crew sheet if the campaign picker's
    import step supplied one, else the FR-30/FR-36 MVP's fixed starter -
    a fallback now, not the only option."""
    return GameState(
        character=character or Character(name="Scoundrel", playbook="Original Playbook"),
        crew=crew or Crew(name="The Crew", crew_type="Original Crew Type"),
        session=Session(),
    )


@router.get("", response_model=list[CampaignSummary])
async def list_campaigns(settings: Settings = Depends(get_settings)) -> list[CampaignSummary]:
    """FR-18: the campaign picker's data source - app.db's directory of
    campaigns, newest first."""
    engine = make_engine(app_db_path(settings.data_dir))
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            rows = await session.scalars(
                select(CampaignIndex).order_by(CampaignIndex.created_at.desc())
            )
            return [CampaignSummary.model_validate(row) for row in rows]
    finally:
        await engine.dispose()


async def _register_campaign_index(
    settings: Settings, campaign_id: str, name: str
) -> CampaignSummary:
    """FR-18/2026-07-17 backlog item 2c: the campaign picker's directory
    row, added only after the campaign's own file write has already
    succeeded (called last by both `create_campaign` and
    `import_campaign`) - an index row with no backing campaign-<id>.db
    would be an orphan the picker offers but no WS connection can open."""
    engine = make_engine(app_db_path(settings.data_dir))
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            row = CampaignIndex(id=campaign_id, name=name)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return CampaignSummary.model_validate(row)
    finally:
        await engine.dispose()


@router.post("", response_model=CampaignSummary)
async def create_campaign(
    body: CreateCampaignRequest, settings: Settings = Depends(get_settings)
) -> CampaignSummary:
    """FR-18: creates the campaign-<id>.db with a starting snapshot first,
    then registers it in app.db's directory - so a WS connection can
    always load an id the picker lists (2c: never the other way round)."""
    campaign_id = uuid.uuid4().hex
    await write_campaign_files(
        campaign_db_path(settings.data_dir, campaign_id),
        _new_game_state(body.character, body.crew),
    )
    return await _register_campaign_index(settings, campaign_id, body.name)


@router.get("/{campaign_id}/export", response_model=None)
async def export_campaign(campaign_id: str, settings: Settings = Depends(get_settings)) -> Response:
    """NFR-5/ADR-0005: the portability contract as a downloadable JSON
    bundle (`CampaignExport`) - `import_campaign` is the other half."""
    db_path = campaign_db_path(settings.data_dir, campaign_id)
    latest_state = await load_state(db_path)
    if latest_state is None:
        raise HTTPException(status_code=404, detail=f"unknown campaign {campaign_id!r}")
    base_state = await load_base_state(db_path)

    engine = make_engine(app_db_path(settings.data_dir))
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            index_row = await session.get(CampaignIndex, campaign_id)
    finally:
        await engine.dispose()
    name = index_row.name if index_row is not None else campaign_id

    export = CampaignExport(
        campaign_id=campaign_id,
        name=name,
        log_jsonl=latest_state.log.to_jsonl(),
        base_state=base_state,
        latest_state=latest_state,
    )
    return Response(
        content=export.model_dump_json(),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{campaign_id}-export.json"'},
    )


@router.post("/import", response_model=CampaignSummary)
async def import_campaign(
    body: CampaignExport, settings: Settings = Depends(get_settings)
) -> CampaignSummary:
    """NFR-5/ADR-0005: rebuilds a *new* campaign (its own fresh id, never
    overwriting an existing one) from a previously exported bundle. The
    log is authoritative (FR-19), so the imported state is reconstructed
    by replaying `log_jsonl` onto `base_state` with the same `replay_state`
    fold `undo_to` uses - not by trusting `latest_state` as-is, which keeps
    a hand-edited or stale export honest against its own log."""
    events = EventLog.from_jsonl(body.log_jsonl).events
    reconstructed = replay_state(body.base_state, events)

    campaign_id = uuid.uuid4().hex
    db_path = campaign_db_path(settings.data_dir, campaign_id)
    await write_campaign_files(db_path, body.base_state)
    await save_state(db_path, reconstructed)

    return await _register_campaign_index(settings, campaign_id, body.name)


@router.delete("/{campaign_id}", status_code=204, response_model=None)
async def delete_campaign(campaign_id: str, settings: Settings = Depends(get_settings)) -> Response:
    """FR-18: removes the campaign's own db file (plus WAL-mode's -wal/-shm
    siblings, ADR-0005) and its app.db index row, file first (2c's
    file-then-index ordering, reversed for delete: a leftover index row
    with no file is a recoverable orphan a second delete call clears; the
    reverse would silently strand a file no picker could reach)."""
    db_path = campaign_db_path(settings.data_dir, campaign_id)
    sibling_paths = (db_path.with_name(db_path.name + suffix) for suffix in ("", "-wal", "-shm"))
    for path in sibling_paths:
        path.unlink(missing_ok=True)

    engine = make_engine(app_db_path(settings.data_dir))
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session, session.begin():
            await session.execute(delete(CampaignIndex).where(CampaignIndex.id == campaign_id))
    finally:
        await engine.dispose()
    return Response(status_code=204)


@router.get("/{campaign_id}/recap")
async def export_recap(campaign_id: str, settings: Settings = Depends(get_settings)) -> Response:
    """FR-20: a human-readable "story so far", exported from the
    campaign's own event log (ai/recap.py) as a downloadable markdown
    file - no separate export pipeline, the log already carries it."""
    state = await load_state(campaign_db_path(settings.data_dir, campaign_id))
    if state is None:
        raise HTTPException(status_code=404, detail=f"unknown campaign {campaign_id!r}")

    return Response(
        content=render_recap(state),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{campaign_id}-recap.md"'},
    )
