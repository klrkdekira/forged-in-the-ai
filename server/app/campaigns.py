import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from ai.recap import render_recap
from ai.tools import GameState
from app.settings import Settings, get_settings
from engine.character import Character
from engine.crew import Crew
from engine.session import Session
from state.campaign_store import create_campaign as write_campaign_files
from state.campaign_store import load_state
from state.db import app_db_path, campaign_db_path, make_engine, make_session_factory
from state.models import CampaignIndex

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


class CampaignSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    name: str
    created_at: datetime
    updated_at: datetime


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


@router.post("", response_model=CampaignSummary)
async def create_campaign(
    body: CreateCampaignRequest, settings: Settings = Depends(get_settings)
) -> CampaignSummary:
    """FR-18: registers the campaign in app.db's directory, then creates
    its own campaign-<id>.db with a starting snapshot so a WS connection
    can load it immediately."""
    campaign_id = uuid.uuid4().hex
    engine = make_engine(app_db_path(settings.data_dir))
    try:
        session_factory = make_session_factory(engine)
        async with session_factory() as session:
            row = CampaignIndex(id=campaign_id, name=body.name)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            summary = CampaignSummary.model_validate(row)
    finally:
        await engine.dispose()

    await write_campaign_files(
        campaign_db_path(settings.data_dir, campaign_id),
        _new_game_state(body.character, body.crew),
    )
    return summary


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
