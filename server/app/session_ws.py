import asyncio
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, WebSocketException, status
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from ai.agent import GmAgent
from ai.capability import get_or_probe_tool_calling
from ai.llm_client import LLMClient
from ai.tools import SHEET_OPERATIONS, GameState, ToolExecutor
from app.llm import build_llm_client
from app.packs import load_entanglements
from app.settings import Settings, get_settings
from engine.errors import EngineError
from state.campaign_store import load_state, save_state, undo_to
from state.db import app_db_path, campaign_db_path, make_engine, make_session_factory
from state.migrations import run_campaign_migrations

router = APIRouter()


class PlayerMessage(BaseModel):
    type: Literal["player_message"]
    text: str = ""


class SheetOperationMessage(BaseModel):
    type: Literal["sheet_operation"]
    name: str
    args: dict[str, object] = Field(default_factory=dict)


class UndoMessage(BaseModel):
    type: Literal["undo"]
    sequence: int


class XCardMessage(BaseModel):
    type: Literal["x_card"]
    sequence: int | None = None
    note: str | None = None
    text: str | None = None


class RollDecisionMessage(BaseModel):
    type: Literal["roll_decision"]
    decision: dict[str, object] = Field(default_factory=dict)


ClientMessage = Annotated[
    PlayerMessage | SheetOperationMessage | UndoMessage | XCardMessage | RollDecisionMessage,
    Field(discriminator="type"),
]
_CLIENT_MESSAGE_ADAPTER = TypeAdapter(ClientMessage)


def _parse_client_message(raw: object) -> tuple[dict, str | None]:
    try:
        return _CLIENT_MESSAGE_ADAPTER.validate_python(raw).model_dump(exclude_none=True), None
    except ValidationError as error:
        return {}, f"invalid client message: {error.errors()[0]['msg']}"

# 2026-07-17 backlog item 2a: two WS connections open on the same
# campaign_id each load their own GameState and mutate it independently -
# `save_state`'s "sequence > max_sequence" filter then silently drops
# whichever connection's events lose the race, and the snapshot upsert is
# last-writer-wins, so the loser's play is gone with no error anywhere.
# One in-process `asyncio.Lock` per campaign (keyed by db_path, so app.db
# and every campaign-<id>.db each get an independent lock), held for the
# whole connection: a second connection to the same campaign simply waits
# for the first to disconnect rather than racing it - the coarsest
# correct fix, appropriate here since GameState itself is a per-connection
# in-memory copy, not a shared/lockable object a finer-grained lock could
# protect mid-turn. Cross-connection fan-out (both seeing live updates at
# once) stays out of scope (Phase 7 multiplayer); this only prevents
# corruption. The dict is never evicted - fine for the small, long-lived
# set of campaigns one process serves; a bounded cache would only matter
# at a scale this single-player server doesn't operate at.
_campaign_locks: dict[str, asyncio.Lock] = {}
_active_campaigns: set[str] = set()


def _campaign_lock(db_path: Path) -> asyncio.Lock:
    key = str(db_path)
    lock = _campaign_locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _campaign_locks[key] = lock
    return lock


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
    # Single-player semantics are explicit: a second client is refused
    # immediately instead of being accepted and waiting behind a lock for an
    # unbounded connection lifetime. The set check and insert are atomic on
    # this event loop because there is no await between them.
    campaign_key = str(db_path)
    if campaign_key in _active_campaigns:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="campaign is in use")
        return
    _active_campaigns.add(campaign_key)
    async with _campaign_lock(db_path):
        executor = ToolExecutor(
            rng=random.Random(),
            clock=lambda: datetime.now(UTC),
            entanglements=load_entanglements(settings),
        )
        # FR-13/FR-24: the SRD-plus-modules retrieval index lives in
        # app.db, a separate file from this campaign's own db_path
        # (ADR-0005) - its own short-lived engine/session factory,
        # disposed with the connection rather than reused across
        # connections.
        retrieval_engine = make_engine(app_db_path(settings.data_dir))
        retrieval_sessions = make_session_factory(retrieval_engine)
        # NFR-6: probed once per (base_url, model) and cached in app.db - a
        # weak tool-caller told to use `tools=` anyway will sometimes print
        # its own ad hoc tool-call syntax as plain narration instead of the
        # tool ever actually running (discovered live); GmAgent falls back
        # to a structured-completion tool choice instead when this is
        # False.
        async with retrieval_sessions() as probe_session:
            supports_tool_calling = await get_or_probe_tool_calling(
                probe_session, client, client.base_url, client.model
            )
        agent = GmAgent(client, executor, retrieval_sessions, supports_tool_calling)
        state = await load_state(db_path)

        try:
            await websocket.send_json({"type": "state", "state": state.model_dump(mode="json")})
            while True:
                message, protocol_error = _parse_client_message(await websocket.receive_json())
                if protocol_error is not None:
                    await websocket.send_json({"type": "error", "message": protocol_error})
                    continue
                if message.get("type") == "sheet_operation":
                    state, reply = await _apply_sheet_operation(db_path, executor, state, message)
                    await websocket.send_json(reply)
                    continue
                if message.get("type") == "undo":
                    # FR-19: an engine operation like any other (CLAUDE.md)
                    # - bypasses the GM agent entirely, and undo_to already
                    # persists (truncates events, overwrites the snapshot)
                    # before returning, so there's nothing left to save
                    # here.
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
                if message.get("type") == "x_card":
                    # FR-17: safety tool invocation - optionally rewinds to a safe sequence
                    # and logs an x_card_invoked event before notifying the client and GM.
                    sequence = message.get("sequence")
                    if isinstance(sequence, int):
                        state = await undo_to(db_path, sequence)
                    note = message.get("note") or "X-card invoked by player"
                    from ai.tools import InvokeXCardArgs

                    res = executor.invoke_x_card(state, InvokeXCardArgs(note=note))
                    state = res.state
                    await save_state(db_path, state)
                    await websocket.send_json(
                        {
                            "type": "x_card_done",
                            "state": state.model_dump(mode="json"),
                            "note": note,
                        }
                    )
                    redirect_text = message.get("text")
                    if redirect_text:
                        message = {
                            "type": "player_message",
                            "text": f"[SAFETY / X-CARD REDIRECT]: {redirect_text}",
                        }
                    else:
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
                    except Exception as error:
                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": f"Turn execution error: {error}",
                                "state": state.model_dump(mode="json"),
                            }
                        )
                        break
                    to_send = None
                    if "state" in event.payload:
                        # 2026-07-17 backlog item 2b: every event that
                        # carries a "state" key just mutated it (tool
                        # calls, companion rolls/messages, narration_done,
                        # and an error that still logged the player's own
                        # message before failing) - persisted before the
                        # client is told, same ordering
                        # `_apply_sheet_operation` already uses, so a
                        # disconnect right after a shown roll/tool result
                        # can't lose it.
                        state = GameState.model_validate(event.payload["state"])
                        await save_state(db_path, state)
                    await websocket.send_json({"type": event.type, **event.payload})
                    if event.type == "roll_proposed":
                        # FR-16: pause the tool-calling loop for the
                        # player's push/assist/Devil's Bargain/trade-off
                        # decision before the proposed roll actually
                        # executes.
                        decision_message, protocol_error = _parse_client_message(
                            await websocket.receive_json()
                        )
                        if protocol_error is not None:
                            await websocket.send_json({"type": "error", "message": protocol_error})
                            decision_message = {}
                        to_send = (
                            decision_message.get("decision", {})
                            if decision_message.get("type") == "roll_decision"
                            else {}
                        )
        except WebSocketDisconnect:
            _active_campaigns.discard(campaign_key)
        finally:
            await client.aclose()
            await retrieval_engine.dispose()
            _active_campaigns.discard(campaign_key)
