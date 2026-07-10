import random
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, WebSocketException, status

from ai.agent import GmAgent
from ai.llm_client import LLMClient
from ai.tools import GameState, ToolExecutor
from app.settings import Settings, get_settings
from engine.character import Character
from engine.crew import Crew
from engine.session import Session

router = APIRouter()


def get_llm_client(settings: Settings = Depends(get_settings)) -> LLMClient:
    """A dependency (rather than constructed inline) so tests can override
    it with a client pointed at a mock transport, per ADR-0001. Refuses to
    connect at all if the backend isn't configured, rather than opening a
    session that can never call the model."""
    if not settings.llm_base_url or not settings.llm_model:
        raise WebSocketException(
            code=status.WS_1011_INTERNAL_ERROR, reason="LLM_BASE_URL/LLM_MODEL not configured"
        )
    return LLMClient(
        base_url=settings.llm_base_url, model=settings.llm_model, api_key=settings.llm_api_key
    )


def _new_game_state() -> GameState:
    """FR-30: single-player MVP starts a fresh in-memory session per
    connection. FR-36's session-zero setting generation and Phase 5's
    persistence replace this placeholder."""
    return GameState(
        character=Character(name="Scoundrel", playbook="Original Playbook"),
        crew=Crew(name="The Crew", crew_type="Original Crew Type"),
        session=Session(),
    )


@router.websocket("/ws/session")
async def session_ws(websocket: WebSocket, client: LLMClient = Depends(get_llm_client)) -> None:
    """FR-30: server-authoritative state deltas from the event log,
    single-player first. Every state change comes from a tool call
    (FR-12); the client only ever sends player messages."""
    await websocket.accept()
    executor = ToolExecutor(rng=random.Random(), clock=lambda: datetime.now(UTC))
    agent = GmAgent(client, executor)
    state = _new_game_state()

    try:
        await websocket.send_json({"type": "state", "state": state.model_dump(mode="json")})
        while True:
            message = await websocket.receive_json()
            if message.get("type") != "player_message":
                continue

            async for event in agent.handle_player_message(state, message.get("text", "")):
                await websocket.send_json({"type": event.type, **event.payload})
                if event.type == "narration_done":
                    state = GameState.model_validate(event.payload["state"])
    except WebSocketDisconnect:
        pass
    finally:
        await client.aclose()
