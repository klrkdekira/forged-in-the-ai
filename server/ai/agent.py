import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx2 as httpx
from pydantic import BaseModel, Field
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai.canon import render_canon
from ai.context import assemble_turn_context
from ai.llm_client import ChatResponse, LLMClient, ToolCall
from ai.player_agent import PlayerAgent
from ai.structured import StructuredOutputError, structured_completion
from ai.system_prompt import build_system_prompt
from ai.tools import (
    TOOL_SPECS,
    GameState,
    MarkStressArgs,
    RollActionArgs,
    RollDecision,
    ToolExecutor,
    tool_definitions,
)
from ai.transcript import render_transcript
from engine.controller import is_ai_controlled
from engine.rolls import ASSIST_BONUS_DICE, ASSIST_STRESS_COST, step_position
from state.srd_index import SrdSearchHit, build_match_query, search_srd

MAX_TOOL_ROUNDS = 6


@dataclass
class AgentTurnEvent:
    """One piece of a GM turn, streamed to the caller as it happens."""

    type: str
    payload: dict


class ToolChoice(BaseModel):
    """NFR-6 fallback schema: the same round-by-round decision a native
    `tool_calls` response encodes (which tool, if any, and what
    arguments), expressed as plain JSON for a backend/model whose tool
    calling isn't reliable (`ai/capability.py`'s probe). Without this, a
    weak tool-caller told to use `tools=` anyway will sometimes print its
    own ad hoc tool-call syntax as plain content - which then sails
    straight through to the player as if it were narration, and the tool
    it meant to call never actually runs (discovered live)."""

    tool: str | None = Field(
        None, description="Exact tool name to call, or null if you're ready to narrate instead"
    )
    arguments: dict = Field(default_factory=dict)


class GmAgent:
    """FR-11/FR-12/FR-30: the GM agent loop. Assembles context, calls the
    LLM with the tool surface, and executes any tool calls the model makes
    - the model never edits state directly, only through the same
    ToolExecutor the dev CLI harness uses - then streams the narration."""

    def __init__(
        self,
        client: LLMClient,
        executor: ToolExecutor,
        retrieval_sessions: async_sessionmaker[AsyncSession] | None = None,
        supports_tool_calling: bool = True,
    ) -> None:
        self._client = client
        self._executor = executor
        self._retrieval_sessions = retrieval_sessions
        self._supports_tool_calling = supports_tool_calling

    async def _get_response(self, messages: list[dict]) -> ChatResponse:
        """NFR-6: native `tools=` when the backend's tool-calling is known
        to work (probed once per (base_url, model) and cached,
        `ai/capability.py`); otherwise a structured-completion fallback
        asking for a `ToolChoice` instead. Either path returns the same
        shape, so the rest of the tool-calling loop below doesn't need to
        know which one produced it."""
        if self._supports_tool_calling:
            return await self._client.chat(messages, tools=tool_definitions())

        tool_menu = "\n".join(
            f"- {name} ({description}) - arguments schema: "
            f"{json.dumps(args_model.model_json_schema())}"
            for name, (args_model, description) in TOOL_SPECS.items()
        )
        fallback_messages = [
            {
                "role": "system",
                "content": (
                    "Available tools:\n"
                    f"{tool_menu}\n\n"
                    "Set tool to the exact name of one to call it with matching arguments, "
                    "or to null if you're ready to narrate instead of calling another tool."
                ),
            },
            *messages,
        ]
        try:
            choice = await structured_completion(self._client, fallback_messages, ToolChoice)
        except StructuredOutputError:
            # The model failed to produce a valid choice twice in a row
            # (structured_completion's own retry) - treat as "nothing more
            # to call" rather than aborting the turn, same reasoning as
            # PlayerAgent's own degrades around this call.
            return ChatResponse()
        if choice.tool is None:
            return ChatResponse()
        return ChatResponse(
            tool_calls=[
                ToolCall(id="fallback", name=choice.tool, arguments=json.dumps(choice.arguments))
            ]
        )

    async def _retrieve(self, query: str) -> list[SrdSearchHit]:
        """FR-13/FR-24: lexical retrieval over the SRD-plus-modules corpus
        (`state/srd_index.py`), keyed on the player's own message. No
        retrieval backend configured, or nothing to search for, both mean
        "nothing retrieved" rather than an error - this is a context-
        assembly nicety, not something a turn should fail over."""
        if self._retrieval_sessions is None:
            return []
        match_query = build_match_query(query)
        if not match_query:
            return []
        async with self._retrieval_sessions() as session:
            try:
                return await search_srd(session, match_query)
            except OperationalError:
                # e.g. the FTS5 table doesn't exist yet in this app.db
                # (migrations not run) - degrade to no retrieval, don't
                # crash the turn over a context-assembly nicety.
                return []

    async def handle_player_message(
        self, state: GameState, text: str
    ) -> AsyncIterator[AgentTurnEvent]:
        # FR-31: logged as a structured event, not held on this instance -
        # a resumed campaign's transcript is derived from state.log below,
        # the same way a live one's is (FR-18's recap is just that: no
        # separate step needed once the event log carries the whole turn).
        state = self._executor.log_event(
            state, "session", "current", "player_message", {"text": text}
        )
        needs_session_zero = state.canon is None or state.session_zero is None
        retrieved = await self._retrieve(text)
        context = assemble_turn_context(
            system_prompt=build_system_prompt(needs_session_zero),
            canon_sections=render_canon(state),
            retrieved=retrieved,
            transcript_lines=render_transcript(state.log),
        )
        messages = [
            {
                "role": "system",
                "content": "\n\n".join(
                    filter(None, (context.system_prompt, context.canon, context.retrieval))
                ),
            },
            {"role": "user", "content": context.transcript},
        ]

        for _ in range(MAX_TOOL_ROUNDS):
            try:
                response = await self._get_response(messages)
            except httpx.HTTPError as error:
                # A slow/unreachable backend must not crash the WS
                # connection outright (discovered live: an uncaught
                # ReadTimeout here left the client stuck showing
                # "Disconnected" with no explanation and no way to
                # recover short of a full page reload).
                yield AgentTurnEvent(
                    type="error", payload={"message": f"LLM request failed: {error}"}
                )
                return
            if not response.tool_calls:
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {"name": call.name, "arguments": call.arguments},
                        }
                        for call in response.tool_calls
                    ],
                }
            )
            for call in response.tool_calls:
                events_before = len(state.log.events)
                if call.name == "roll_action":
                    try:
                        proposal = RollActionArgs.model_validate_json(call.arguments)
                        character_id = self._executor.resolve_character_id(
                            state, proposal.character_id
                        )
                    except Exception as error:
                        # Bad or ambiguous arguments (e.g. no character_id in
                        # a multi-PC session, FR-25) go back to the model as a
                        # tool error to retry, the same path _run_tool gives
                        # every other tool - not raised into the WS handler,
                        # which would kill the connection over a model mistake.
                        result = {"error": str(error)}
                        yield AgentTurnEvent(
                            type="tool_call",
                            payload={"name": call.name, "result": result, "events": []},
                        )
                        messages.append(
                            {"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)}
                        )
                        continue
                    pool_size = state.characters[character_id].action_ratings.get(
                        proposal.action, 0
                    )
                    if is_ai_controlled(state.controllers, character_id):
                        # FR-35: no human at the table for this seat - the
                        # PlayerAgent decides push/bargain/trade-off itself
                        # instead of the tool-calling loop pausing for a
                        # WS reply that would never come.
                        try:
                            decision = await PlayerAgent(self._client, character_id).decide_roll(
                                state, proposal, pool_size
                            )
                        except (httpx.HTTPError, StructuredOutputError):
                            # A companion's failed LLM call must not crash the
                            # turn: fall back to rolling as proposed - the
                            # neutral choice, no stress spent and no bargain -
                            # same degrade-not-crash rule as _retrieve.
                            decision = RollDecision()
                        # FR-31/FR-35: a pure record, like player_message/
                        # narration - without this it only ever reached the
                        # client as a live turn event, never state.log, so
                        # it vanished after a reconnect and never reached
                        # the Journal at all (deeper than "only shows via
                        # the generic fallback" - it didn't show anywhere).
                        # "name" rides alongside the decision fields so the
                        # client can render/rebuild a readable line without
                        # a separate character lookup, same as
                        # companion_message's own "speaker"/"name" fields.
                        decision_payload = {
                            **decision.model_dump(mode="json"),
                            "name": state.characters[character_id].name,
                        }
                        state = self._executor.log_event(
                            state,
                            "character",
                            character_id,
                            "companion_roll_decision",
                            decision_payload,
                        )
                        yield AgentTurnEvent(
                            type="companion_roll_decision",
                            payload={"character_id": character_id, **decision_payload},
                        )
                    else:
                        decision_payload = yield AgentTurnEvent(
                            type="roll_proposed",
                            payload={
                                "character_id": character_id,
                                "action": proposal.action.value,
                                "position": proposal.position.value,
                                "effect": proposal.effect.name.lower(),
                                "pool_size": pool_size,
                            },
                        )
                        decision = RollDecision.model_validate(decision_payload or {})
                    result, state = self._resolve_roll(state, proposal, decision)
                else:
                    result = self._run_tool(state, call.name, call.arguments)
                    if "state" in result:
                        state = result.pop("state")
                # FR-31/FR-32: the same entity-tagged events the Journal
                # view already renders, so the chat's tool-call status can
                # reuse the client's existing summarize() instead of
                # dumping the tool's raw result JSON at the player.
                new_events = [
                    event.model_dump(mode="json") for event in state.log.events[events_before:]
                ]
                yield AgentTurnEvent(
                    type="tool_call",
                    payload={"name": call.name, "result": result, "events": new_events},
                )
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)}
                )
        else:
            yield AgentTurnEvent(type="error", payload={"message": "too many tool calls in a row"})
            return

        # A fresh streaming call for the same context, discarding the
        # non-streamed `response.content` above: it only told us the model
        # was done calling tools, not what the user should actually read
        # (NFR-3 wants real streamed narration, not a repeat of that text).
        narration_chunks = []
        try:
            async for chunk in self._client.stream_chat(messages):
                narration_chunks.append(chunk)
                yield AgentTurnEvent(type="narration_chunk", payload={"text": chunk})
        except httpx.HTTPError as error:
            yield AgentTurnEvent(type="error", payload={"message": f"LLM request failed: {error}"})
            return

        narration_text = "".join(narration_chunks)
        state = self._executor.log_event(
            state, "session", "current", "narration", {"text": narration_text}
        )

        # FR-35: give every AI-controlled companion a chance to add an
        # in-character line reacting to this turn's narration - queued
        # for the GM's *next* turn via the event log, same as a human's
        # chat message, rather than looping the GM back into this one.
        for seat in state.controllers.values():
            if seat.kind != "ai":
                continue
            for character_id in seat.character_ids:
                try:
                    line = await PlayerAgent(self._client, character_id).maybe_roleplay(
                        state, narration_text
                    )
                except (httpx.HTTPError, StructuredOutputError):
                    # Staying quiet over crashing the turn: the narration is
                    # already streamed and logged, a companion's colour line
                    # is never worth losing the connection for.
                    line = None
                if line is None:
                    continue
                character = state.characters[character_id]
                state = self._executor.log_event(
                    state,
                    "character",
                    character_id,
                    "player_message",
                    {"text": line, "speaker": character.name},
                )
                yield AgentTurnEvent(
                    type="companion_message",
                    payload={"character_id": character_id, "name": character.name, "text": line},
                )

        yield AgentTurnEvent(
            type="narration_done", payload={"state": state.model_dump(mode="json")}
        )

    def _resolve_roll(
        self, state: GameState, proposal: RollActionArgs, decision: RollDecision
    ) -> tuple[dict, GameState]:
        """FR-16: applies the player's `RollDecision` to a GM-proposed
        action roll, then executes it. `proposal` carries the GM's
        judgement (goal, action, position, effect - Action Roll steps 1-4);
        this method covers step 5, "Add Bonus Dice", plus "Trading Position
        for Effect"."""
        position, effect = proposal.position, proposal.effect
        if decision.trade == "worse_position_better_effect":
            position, effect = step_position(position, 1), effect.bumped(1)
        elif decision.trade == "better_position_worse_effect":
            position, effect = step_position(position, -1), effect.bumped(-1)
        if decision.push_effect:
            effect = effect.bumped(1)

        stress_spent = 2 * decision.push_dice + 2 * decision.push_effect
        if stress_spent:
            state = self._executor.mark_stress(
                state, MarkStressArgs(amount=stress_spent, character_id=proposal.character_id)
            ).state

        # SRD: "Teamwork"/"Assist" - a different PC helping this roll takes
        # the stress themselves. An unknown id or the roller assisting
        # themselves is silently dropped rather than raised: `decision`
        # comes from a human's own dialog choices or a companion's
        # structured completion, neither of which should be able to crash
        # the turn over a bad choice (same reasoning as the httpx/
        # StructuredOutputError degrades around this call's callers).
        roller_id = self._executor.resolve_character_id(state, proposal.character_id)
        assisted_by = decision.assist_character_id
        if assisted_by is not None and (
            assisted_by not in state.characters or assisted_by == roller_id
        ):
            assisted_by = None
        if assisted_by is not None:
            state = self._executor.mark_stress(
                state, MarkStressArgs(amount=ASSIST_STRESS_COST, character_id=assisted_by)
            ).state

        bonus_dice = (
            int(decision.push_dice)
            + int(bool(decision.devils_bargain))
            + (ASSIST_BONUS_DICE if assisted_by is not None else 0)
        )
        roll_result = self._executor.roll_action(
            state,
            RollActionArgs(
                action=proposal.action,
                position=position,
                effect=effect,
                character_id=proposal.character_id,
            ),
            bonus_dice=bonus_dice,
            devils_bargain=decision.devils_bargain,
            assisted_by=assisted_by,
        )
        return roll_result.result, roll_result.state

    def _run_tool(self, state: GameState, name: str, raw_arguments: str) -> dict:
        spec = TOOL_SPECS.get(name)
        if spec is None:
            return {"error": f"unknown tool {name!r}"}

        args_model, _ = spec
        try:
            args = args_model.model_validate_json(raw_arguments)
            call_result = getattr(self._executor, name)(state, args)
        except Exception as error:  # the model sent bad/illegal arguments
            return {"error": str(error)}

        return {**call_result.result, "state": call_result.state}
