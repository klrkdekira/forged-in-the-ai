import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

from ai.canon import render_canon
from ai.context import assemble_turn_context
from ai.llm_client import LLMClient
from ai.system_prompt import build_system_prompt
from ai.tools import TOOL_SPECS, GameState, ToolExecutor, tool_definitions

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
