import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

from ai.canon import render_canon
from ai.context import assemble_turn_context
from ai.llm_client import LLMClient
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
        self._transcript: list[str] = []

    async def handle_player_message(
        self, state: GameState, text: str
    ) -> AsyncIterator[AgentTurnEvent]:
        self._transcript.append(f"Player: {text}")
        context = assemble_turn_context(
            system_prompt=build_system_prompt(),
            canon_sections=render_canon(state),
            retrieved=[],
            transcript_lines=self._transcript,
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
            response = await self._client.chat(messages, tools=tool_definitions())
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
                    proposal = RollActionArgs.model_validate_json(call.arguments)
                    pool_size = state.character.action_ratings.get(proposal.action, 0)
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
        async for chunk in self._client.stream_chat(messages):
            narration_chunks.append(chunk)
            yield AgentTurnEvent(type="narration_chunk", payload={"text": chunk})

        self._transcript.append(f"GM: {''.join(narration_chunks)}")
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
            state = self._executor.mark_stress(state, MarkStressArgs(amount=stress_spent)).state

        bonus_dice = int(decision.push_dice) + int(bool(decision.devils_bargain))
        roll_result = self._executor.roll_action(
            state,
            RollActionArgs(action=proposal.action, position=position, effect=effect),
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
