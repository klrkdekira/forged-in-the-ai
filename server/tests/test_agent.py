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
async def test_agent_reports_an_error_instead_of_crashing_when_the_llm_call_fails():
    # Discovered live: a slow/unreachable backend raised httpx.HTTPError
    # straight out of handle_player_message, uncaught - session_ws.py's
    # driving loop had no handler for it either, so it crashed the WS
    # connection outright, leaving the client stuck showing
    # "Disconnected" with no explanation and no way to recover short of
    # reloading the page.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "backend unavailable"})

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )
    agent = GmAgent(client, _executor())

    events = [event async for event in agent.handle_player_message(_state(), "hi")]
    await client.aclose()

    assert events[-1].type == "error"
    assert "LLM request failed" in events[-1].payload["message"]
    assert not any(e.type == "narration_done" for e in events)


@pytest.mark.anyio
async def test_agent_reports_an_error_instead_of_crashing_when_streaming_narration_fails():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("stream"):
            return httpx.Response(500, json={"error": "backend unavailable"})
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "placeholder"}}]}
        )

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )
    agent = GmAgent(client, _executor())

    events = [event async for event in agent.handle_player_message(_state(), "hi")]
    await client.aclose()

    assert events[-1].type == "error"
    assert "LLM request failed" in events[-1].payload["message"]
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


@pytest.mark.anyio
async def test_agent_logs_the_player_message_and_narration_as_structured_events():
    # FR-31: every turn is a structured event, not just its dice - the
    # journal (and FR-18's resume recap below) needs the player's input
    # and the GM's narration too.
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("stream"):
            return httpx.Response(
                200,
                text='data: {"choices":[{"delta":{"content":"You see a door."}}]}\n\n'
                "data: [DONE]\n\n",
            )
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "placeholder"}}]}
        )

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )
    agent = GmAgent(client, _executor())

    events = [event async for event in agent.handle_player_message(_state(), "I look around.")]
    await client.aclose()

    done_event = next(e for e in events if e.type == "narration_done")
    logged = done_event.payload["state"]["log"]["events"]

    player_events = [e for e in logged if e["event_type"] == "player_message"]
    narration_events = [e for e in logged if e["event_type"] == "narration"]
    assert player_events[-1]["entity_type"] == "session"
    assert player_events[-1]["entity_id"] == "current"
    assert player_events[-1]["payload"]["text"] == "I look around."
    assert narration_events[-1]["payload"]["text"] == "You see a door."


@pytest.mark.anyio
async def test_agent_resumes_with_prior_turns_in_context_from_persisted_state():
    # FR-18: resuming a campaign restores the AI's context via a
    # structured recap - here, a second GmAgent instance (standing in for
    # a fresh WS connection after a reconnect) picks up the transcript
    # from the persisted state's event log, not from anything held on the
    # agent instance.
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        if body.get("stream"):
            return httpx.Response(
                200, text='data: {"choices":[{"delta":{"content":"Noted."}}]}\n\ndata: [DONE]\n\n'
            )
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "placeholder"}}]}
        )

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )
    first_agent = GmAgent(client, _executor())
    first_turn = [
        event async for event in first_agent.handle_player_message(_state(), "I pick the lock.")
    ]
    persisted_state = next(e for e in first_turn if e.type == "narration_done").payload["state"]

    second_agent = GmAgent(client, _executor())
    async for _ in second_agent.handle_player_message(
        GameState.model_validate(persisted_state), "What do I see?"
    ):
        pass
    await client.aclose()

    second_turn_prompt = requests[-1]["messages"][-1]["content"]
    assert "Player: I pick the lock." in second_turn_prompt
    assert "GM: Noted." in second_turn_prompt
    assert "Player: What do I see?" in second_turn_prompt


@pytest.mark.anyio
async def test_agent_runs_session_zero_before_regular_play():
    # FR-17/FR-36: a fresh campaign (no canon, no session_zero) should see
    # the session-zero procedure in its system prompt, and the model
    # completing it (set_session_zero_config, then set_campaign_canon)
    # should make the procedure disappear from later turns.
    from ai.procedures import SESSION_ZERO_PROCEDURE

    requests = []
    # One non-streaming response per tool round, in order: turn 1 calls
    # set_session_zero_config then stops (no more tool calls, so the loop
    # breaks and narrates); turn 2 calls set_campaign_canon then stops;
    # turn 3 has nothing to call.
    non_stream_responses = iter(
        [
            _tool_call_message(
                "set_session_zero_config",
                {"lines": ["no animal harm"], "veils": [], "tone": "noir"},
            ),
            {"role": "assistant", "content": "placeholder"},
            _tool_call_message(
                "set_campaign_canon",
                {
                    "setting_name": "Harrow's Reach",
                    "factions": ["The Rustworks Combine"],
                    "locations": ["The Sunken Market"],
                },
            ),
            {"role": "assistant", "content": "placeholder"},
            {"role": "assistant", "content": "placeholder"},
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        if body.get("stream"):
            return httpx.Response(
                200, text='data: {"choices":[{"delta":{"content":"Noted."}}]}\n\ndata: [DONE]\n\n'
            )
        return httpx.Response(200, json={"choices": [{"message": next(non_stream_responses)}]})

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )
    agent = GmAgent(client, _executor())
    state = _state()

    turn_1 = [event async for event in agent.handle_player_message(state, "Let's begin.")]
    state = GameState.model_validate(
        next(e for e in turn_1 if e.type == "narration_done").payload["state"]
    )
    assert SESSION_ZERO_PROCEDURE.title in requests[0]["messages"][0]["content"]
    assert state.session_zero.lines == ["no animal harm"]
    assert state.canon is None

    requests.clear()
    turn_2 = [event async for event in agent.handle_player_message(state, "Go on.")]
    state = GameState.model_validate(
        next(e for e in turn_2 if e.type == "narration_done").payload["state"]
    )
    # session_zero is set but canon isn't yet - still needs session zero.
    assert SESSION_ZERO_PROCEDURE.title in requests[0]["messages"][0]["content"]
    assert state.canon.setting_name == "Harrow's Reach"

    requests.clear()
    async for _ in agent.handle_player_message(state, "What do I see?"):
        pass
    await client.aclose()

    assert SESSION_ZERO_PROCEDURE.title not in requests[0]["messages"][0]["content"]
