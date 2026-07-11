import random
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, WebSocketException, status
from pydantic import ValidationError

from ai.agent import GmAgent
from ai.llm_client import LLMClient
from ai.tools import SHEET_OPERATIONS, GameState, ToolExecutor
from app.llm import build_llm_client
from app.settings import Settings, get_settings
from engine.errors import EngineError
from state.campaign_store import load_state, save_state, undo_to
from state.db import app_db_path, campaign_db_path, make_engine, make_session_factory
from state.migrations import run_campaign_migrations

router = APIRouter()


def get_llm_client(settings: Settings = Depends(get_settings)) -> LLMClient:
    """A dependency (rather than constructed inline) so tests can override
    it with a client pointed at a mock transport, per ADR-0001. Refuses to
    connect at all if the backend isn't configured, rather than opening a
    session that can never call the model."""
    client = build_llm_client(settings)
    if client is None:
        raise WebSocketException(
            code=status.WS_1011_INTERNAL_ERROR, reason="LLM_BASE_URL/LLM_MODEL not configured"
        )
    return client


def get_campaign_db_path(campaign_id: str, settings: Settings = Depends(get_settings)) -> Path:
    """FR-18: refuses the connection outright for an unknown campaign_id -
    a WS connection never invents a campaign, `POST /api/campaigns` (see
    app/campaigns.py) is the only place one is created. Migrates on every
    open (ADR-0005), same as app.db's lifespan-time migration."""
    db_path = campaign_db_path(settings.data_dir, campaign_id)
    if not db_path.exists():
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason=f"unknown campaign {campaign_id!r}"
        )
    run_campaign_migrations(db_path)
    return db_path


async def _apply_sheet_operation(
    db_path: Path, executor: ToolExecutor, state: GameState, message: dict
) -> tuple[GameState, dict]:
    """FR-28: the sheet panel's own engine-operation calls - stress, harm,
    XP, coin, and load ticks - bypass the GM agent entirely (CLAUDE.md:
    "the UI acts through engine-operation endpoints"). Returns the message
    to send rather than sending it directly, so the caller can persist
    first (a mutation must be saved before the client is told about it -
    otherwise a client that disconnects the instant it sees the update can
    race ahead of the write and the mutation never lands, FR-18)."""
    name = message.get("name")
    args_model = SHEET_OPERATIONS.get(name)
    if args_model is None:
        return state, {"type": "error", "message": f"unknown sheet operation {name!r}"}

    try:
        args = args_model.model_validate(message.get("args", {}))
        result = getattr(executor, name)(state, args)
    except (ValidationError, EngineError) as error:
        return state, {"type": "error", "message": str(error)}

    await save_state(db_path, result.state)
    return result.state, {"type": "state", "state": result.state.model_dump(mode="json")}


@router.websocket("/ws/session/{campaign_id}")
async def session_ws(
    websocket: WebSocket,
    client: LLMClient = Depends(get_llm_client),
    db_path: Path = Depends(get_campaign_db_path),
    settings: Settings = Depends(get_settings),
) -> None:
    """FR-18/FR-30: server-authoritative state deltas from the event log,
    single-player first, backed by the campaign's own SQLite file. Every
    state change comes from a tool call (FR-12); the client only ever
    sends player messages."""
    await websocket.accept()
    executor = ToolExecutor(rng=random.Random(), clock=lambda: datetime.now(UTC))
    # FR-13/FR-24: the SRD-plus-modules retrieval index lives in app.db,
    # a separate file from this campaign's own db_path (ADR-0005) - its
    # own short-lived engine/session factory, disposed with the
    # connection rather than reused across connections.
    retrieval_engine = make_engine(app_db_path(settings.data_dir))
    agent = GmAgent(client, executor, make_session_factory(retrieval_engine))
    state = await load_state(db_path)

    try:
        await websocket.send_json({"type": "state", "state": state.model_dump(mode="json")})
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "sheet_operation":
                state, reply = await _apply_sheet_operation(db_path, executor, state, message)
                await websocket.send_json(reply)
                continue
            if message.get("type") == "undo":
                # FR-19: an engine operation like any other (CLAUDE.md) -
                # bypasses the GM agent entirely, and undo_to already
                # persists (truncates events, overwrites the snapshot)
                # before returning, so there's nothing left to save here.
                sequence = message.get("sequence")
                if not isinstance(sequence, int):
                    await websocket.send_json(
                        {"type": "error", "message": "undo requires an integer sequence"}
                    )
                    continue
                state = await undo_to(db_path, sequence)
                await websocket.send_json(
                    {"type": "undo_done", "state": state.model_dump(mode="json")}
                )
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
                if event.type == "narration_done":
                    # Persisted before the client is told, same reasoning
                    # as _apply_sheet_operation's ordering.
                    state = GameState.model_validate(event.payload["state"])
                    await save_state(db_path, state)
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
    except WebSocketDisconnect:
        pass
    finally:
        await client.aclose()
        await retrieval_engine.dispose()
