from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.settings import Settings, get_settings
from engine.character import Character
from state.character_store import CharacterIdError, list_characters, load_character

router = APIRouter(prefix="/api/characters", tags=["characters"])


class CharacterSummary(BaseModel):
    id: str
    name: str
    playbook: str


@router.get("", response_model=list[CharacterSummary])
async def list_characters_endpoint(
    settings: Settings = Depends(get_settings),
) -> list[CharacterSummary]:
    """FR-8: saved guided-entry characters (`cli/guided_entry.py`) the
    campaign picker's import step can select from, rather than requiring
    the owner to re-upload the JSON file it already wrote."""
    return [
        CharacterSummary(id=character_id, name=character.name, playbook=character.playbook)
        for character_id, character in list_characters(settings.data_dir)
    ]


@router.get("/{character_id}", response_model=Character)
async def get_character_endpoint(
    character_id: str, settings: Settings = Depends(get_settings)
) -> Character:
    try:
        character = load_character(settings.data_dir, character_id)
    except CharacterIdError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if character is None:
        raise HTTPException(status_code=404, detail=f"unknown character {character_id!r}")
    return character
