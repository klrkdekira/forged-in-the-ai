import random
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, WebSocketException, status
from pydantic import ValidationError

from ai.agent import GmAgent
from ai.llm_client import LLMClient
from ai.tools import SHEET_OPERATIONS, GameState, ToolExecutor
from app.settings import Settings, get_settings
from engine.character import Character
from engine.crew import Crew
from engine.errors import EngineError
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


async def _apply_sheet_operation(
    websocket: WebSocket, executor: ToolExecutor, state: GameState, message: dict
) -> GameState:
    """FR-28: the sheet panel's own engine-operation calls - stress, harm,
    XP, coin, and load ticks - bypass the GM agent entirely (CLAUDE.md:
    "the UI acts through engine-operation endpoints"). Replies with a
    `state` message (the same one used for the initial snapshot) rather
    than a `tool_call`, since there's no LLM turn around this."""
    name = message.get("name")
    args_model = SHEET_OPERATIONS.get(name)
    if args_model is None:
        await websocket.send_json({"type": "error", "message": f"unknown sheet operation {name!r}"})
        return state

    try:
        args = args_model.model_validate(message.get("args", {}))
        result = getattr(executor, name)(state, args)
    except (ValidationError, EngineError) as error:
        await websocket.send_json({"type": "error", "message": str(error)})
        return state

    await websocket.send_json({"type": "state", "state": result.state.model_dump(mode="json")})
    return result.state


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
            if message.get("type") == "sheet_operation":
                state = await _apply_sheet_operation(websocket, executor, state, message)
                continue
            if message.get("type") != "player_message":
                continue

            turn = agent.handle_player_message(state, message.get("text", ""))
            to_send = None
            while True:
                try:
                    event = await (turn.asend(to_send) if to_send is not None else anext(turn))
                except StopAsyncIteration:
                    break
                to_send = None
                await websocket.send_json({"type": event.type, **event.payload})
                if event.type == "roll_proposed":
                    # FR-16: pause the tool-calling loop for the player's
                    # push/assist/Devil's Bargain/trade-off decision before
                    # the proposed roll actually executes.
                    decision_message = await websocket.receive_json()
                    to_send = (
                        decision_message.get("decision", {})
                        if decision_message.get("type") == "roll_decision"
                        else {}
                    )
                elif event.type == "narration_done":
                    state = GameState.model_validate(event.payload["state"])
    except WebSocketDisconnect:
        pass
    finally:
        await client.aclose()
