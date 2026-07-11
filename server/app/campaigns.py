import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from ai.tools import GameState
from app.settings import Settings, get_settings
from engine.character import Character
from engine.crew import Crew
from engine.session import Session
from state.campaign_store import create_campaign as write_campaign_files
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


def _new_game_state() -> GameState:
    """FR-30/FR-36 MVP simplification: one fixed starter character/crew
    until session-zero and guided-entry feed a campaign's real starting
    sheet in here instead."""
    return GameState(
        character=Character(name="Scoundrel", playbook="Original Playbook"),
        crew=Crew(name="The Crew", crew_type="Original Crew Type"),
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

    await write_campaign_files(campaign_db_path(settings.data_dir, campaign_id), _new_game_state())
    return summary
