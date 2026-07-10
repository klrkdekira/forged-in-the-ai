import json
import random
from datetime import UTC, datetime

import httpx2 as httpx
import pytest

from ai.agent import GmAgent
from ai.llm_client import LLMClient
from ai.tools import GameState, ToolExecutor
from engine.character import Character
from engine.crew import Crew
from engine.rolls import Effect
from engine.session import Session

AT = datetime(2026, 1, 1, tzinfo=UTC)


def _state() -> GameState:
    return GameState(
        character=Character(name="Test", playbook="Test Playbook"),
        crew=Crew(name="Test Crew", crew_type="Test Type"),
        session=Session(),
    )


def _executor() -> ToolExecutor:
    return ToolExecutor(rng=random.Random(1), clock=lambda: AT)


def _tool_call_message(name: str, arguments: dict) -> dict:
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
        ],
    }


@pytest.mark.anyio
async def test_agent_executes_a_tool_call_then_streams_narration():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if body.get("stream"):
            sse_body = (
                'data: {"choices":[{"delta":{"content":"You "}}]}\n\n'
                'data: {"choices":[{"delta":{"content":"succeed."}}]}\n\n'
                "data: [DONE]\n\n"
            )
            return httpx.Response(200, text=sse_body)
        if len(calls) == 1:
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": _tool_call_message("roll_fortune", {"pool_size": 2})}]
                },
            )
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "placeholder"}}]}
        )

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )
    agent = GmAgent(client, _executor())

    events = [event async for event in agent.handle_player_message(_state(), "I pick the lock.")]

    await client.aclose()

    tool_events = [e for e in events if e.type == "tool_call"]
    narration_events = [e for e in events if e.type == "narration_chunk"]
    done_events = [e for e in events if e.type == "narration_done"]

    assert tool_events[0].payload["name"] == "roll_fortune"
    assert "band" in tool_events[0].payload["result"]
    assert "".join(e.payload["text"] for e in narration_events) == "You succeed."
    assert done_events[0].payload["state"]["character"]["name"] == "Test"


@pytest.mark.anyio
async def test_agent_handles_an_unknown_tool_gracefully():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("stream"):
            return httpx.Response(
                200, text='data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n'
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": _tool_call_message("not_a_real_tool", {})}]},
        )

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )
    agent = GmAgent(client, _executor())

    events = [event async for event in agent.handle_player_message(_state(), "hi")]
    await client.aclose()

    tool_event = next(e for e in events if e.type == "tool_call")
    assert "unknown tool" in tool_event.payload["result"]["error"]


@pytest.mark.anyio
async def test_agent_stops_after_too_many_tool_rounds():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": _tool_call_message("roll_fortune", {"pool_size": 1})}]},
        )

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )
    agent = GmAgent(client, _executor())

    events = [event async for event in agent.handle_player_message(_state(), "hi")]
    await client.aclose()

    assert events[-1].type == "error"
    assert not any(e.type == "narration_done" for e in events)


@pytest.mark.anyio
async def test_agent_pauses_a_roll_action_for_the_players_decision():
    # FR-16: the GM agent proposes position/effect (Action Roll steps 1-4)
    # but pauses before rolling so the player can add bonus dice or trade
    # position for effect (step 5, "Add Bonus Dice"/"Trading Position for
    # Effect") - it should never resolve the roll on its own.
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if body.get("stream"):
            return httpx.Response(
                200, text='data: {"choices":[{"delta":{"content":"Rolled."}}]}\n\ndata: [DONE]\n\n'
            )
        if len(calls) == 1:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": _tool_call_message(
                                "roll_action",
                                {"action": "prowl", "position": "risky", "effect": "standard"},
                            )
                        }
                    ]
                },
            )
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "placeholder"}}]}
        )

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )
    agent = GmAgent(client, _executor())
    turn = agent.handle_player_message(_state(), "I sneak past the guards.")

    proposed = await anext(turn)
    assert proposed.type == "roll_proposed"
    assert proposed.payload == {
        "action": "prowl",
        "position": "risky",
        "effect": "standard",
        "pool_size": 0,
    }

    tool_event = await turn.asend({"push_dice": True, "trade": "worse_position_better_effect"})
    assert tool_event.type == "tool_call"
    # trading risky/standard for desperate/great, then pushing for +1d
    assert tool_event.payload["result"]["position"] == "desperate"
    assert tool_event.payload["result"]["effect"] == Effect.GREAT.value

    remaining = [event async for event in turn]
    await client.aclose()

    done_event = next(e for e in remaining if e.type == "narration_done")
    stress_events = [
        event
        for event in done_event.payload["state"]["log"]["events"]
        if event["event_type"] == "stress_marked"
    ]
    assert stress_events[-1]["payload"]["amount"] == 2  # push_dice cost


@pytest.mark.anyio
async def test_agent_skips_tool_round_when_the_model_answers_directly():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("stream"):
            return httpx.Response(
                200, text='data: {"choices":[{"delta":{"content":"Sure."}}]}\n\ndata: [DONE]\n\n'
            )
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "Sure."}}]}
        )

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )
    agent = GmAgent(client, _executor())

    events = [event async for event in agent.handle_player_message(_state(), "What's my name?")]
    await client.aclose()

    assert not any(e.type == "tool_call" for e in events)
    assert "".join(e.payload["text"] for e in events if e.type == "narration_chunk") == "Sure."
