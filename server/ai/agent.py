import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx2 as httpx

from ai.canon import render_canon
from ai.context import assemble_turn_context
from ai.llm_client import LLMClient
from ai.player_agent import PlayerAgent
from ai.structured import StructuredOutputError
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
from engine.rolls import step_position

MAX_TOOL_ROUNDS = 6


@dataclass
class AgentTurnEvent:
    """One piece of a GM turn, streamed to the caller as it happens."""

    type: str
    payload: dict


class GmAgent:
    """FR-11/FR-12/FR-30: the GM agent loop. Assembles context, calls the
    LLM with the tool surface, and executes any tool calls the model makes
    - the model never edits state directly, only through the same
    ToolExecutor the dev CLI harness uses - then streams the narration."""

    def __init__(self, client: LLMClient, executor: ToolExecutor) -> None:
        self._client = client
        self._executor = executor

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
        context = assemble_turn_context(
            system_prompt=build_system_prompt(needs_session_zero),
            canon_sections=render_canon(state),
            retrieved=[],
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
                response = await self._client.chat(messages, tools=tool_definitions())
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
                            type="tool_call", payload={"name": call.name, "result": result}
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
                        yield AgentTurnEvent(
                            type="companion_roll_decision",
                            payload={
                                "character_id": character_id,
                                "decision": decision.model_dump(mode="json"),
                            },
                        )
                    else:
                        decision_payload = yield AgentTurnEvent(
                            type="roll_proposed",
                            payload={
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
                yield AgentTurnEvent(
                    type="tool_call", payload={"name": call.name, "result": result}
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

        bonus_dice = int(decision.push_dice) + int(bool(decision.devils_bargain))
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
