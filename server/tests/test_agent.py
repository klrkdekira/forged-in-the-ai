import json
import random
from datetime import UTC, datetime
from pathlib import Path

import httpx2 as httpx
import pytest

from ai.agent import GmAgent
from ai.llm_client import LLMClient
from ai.tools import GameState, ToolExecutor
from engine.character import Action, Character
from engine.controller import Controller
from engine.crew import Crew
from engine.packs import EntanglementEntry
from engine.rolls import Effect
from engine.session import Session
from state.db import app_db_path, make_engine, make_session_factory
from state.migrations import run_app_migrations
from state.srd_index import chunk_srd, index_srd_chunks

AT = datetime(2026, 1, 1, tzinfo=UTC)


def _state() -> GameState:
    return GameState(
        character=Character(name="Test", playbook="Test Playbook"),
        crew=Crew(name="Test Crew", crew_type="Test Type"),
        session=Session(),
    )


def _state_with_ai_companion() -> GameState:
    # FR-35: pc-2 is an AI-controlled crewmate, wired the same way
    # create_character registers one - a distinct seat, kind "ai".
    return GameState(
        characters={
            "pc-1": Character(name="Anders", playbook="Cutter"),
            "pc-2": Character(name="Vex", playbook="Whisper", action_ratings={Action.PROWL: 2}),
        },
        crew=Crew(name="Test Crew", crew_type="Test Type"),
        session=Session(),
        controllers={
            "seat:pc-2": Controller(seat_id="seat:pc-2", kind="ai", character_ids=["pc-2"])
        },
    )


def _executor() -> ToolExecutor:
    return ToolExecutor(rng=random.Random(1), clock=lambda: AT)


_ENTANGLEMENTS = [
    EntanglementEntry(
        heat_band=heat_band, roll_result=roll_result, entanglement=f"{heat_band}/{roll_result}"
    )
    for heat_band in ("0-3", "4-5", "6")
    for roll_result in ("1-3", "4/5", "6")
]


def _executor_with_entanglements() -> ToolExecutor:
    return ToolExecutor(rng=random.Random(1), clock=lambda: AT, entanglements=_ENTANGLEMENTS)


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


def _tool_calls_message(calls: list[tuple[str, dict]]) -> dict:
    # Several tool calls bundled into a single response - the agent's loop
    # runs all of them within one round (one call to _client.chat), not
    # one round each.
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": f"call_{i}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
            for i, (name, arguments) in enumerate(calls)
        ],
    }


def _final_message() -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": "placeholder"}}]}


def _narration_response(text: str) -> httpx.Response:
    return httpx.Response(
        200, text=f'data: {{"choices":[{{"delta":{{"content":"{text}"}}}}]}}\n\ndata: [DONE]\n\n'
    )


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


@pytest.mark.anyio
async def test_agent_lets_the_ai_player_decide_its_own_roll_instead_of_pausing():
    # FR-35: pc-2 is AI-controlled - the tool-calling loop must not pause
    # for a WS reply that would never come; PlayerAgent decides instead.
    tool_round_calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("stream"):
            return httpx.Response(
                200, text='data: {"choices":[{"delta":{"content":"Noted."}}]}\n\ndata: [DONE]\n\n'
            )
        if body.get("tools"):
            tool_round_calls.append(body)
            if len(tool_round_calls) == 1:
                return httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "message": _tool_call_message(
                                    "roll_action",
                                    {
                                        "action": "prowl",
                                        "position": "risky",
                                        "effect": "standard",
                                        "character_id": "pc-2",
                                    },
                                )
                            }
                        ]
                    },
                )
            return httpx.Response(
                200,
                json={"choices": [{"message": {"role": "assistant", "content": "placeholder"}}]},
            )
        # PlayerAgent.decide_roll's structured completion (no "tools" key)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": json.dumps({"push_dice": True})}}
                ]
            },
        )

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )
    agent = GmAgent(client, _executor())

    events = [
        event async for event in agent.handle_player_message(_state_with_ai_companion(), "Go, Vex.")
    ]
    await client.aclose()

    assert not any(e.type == "roll_proposed" for e in events)
    decided = next(e for e in events if e.type == "companion_roll_decision")
    assert decided.payload["character_id"] == "pc-2"
    assert decided.payload["decision"]["push_dice"] is True

    done_event = next(e for e in events if e.type == "narration_done")
    logged = done_event.payload["state"]["log"]["events"]
    stress_events = [e for e in logged if e["event_type"] == "stress_marked"]
    assert stress_events[-1]["entity_id"] == "pc-2"  # not pc-1, the other PC
    assert stress_events[-1]["payload"]["amount"] == 2  # push_dice cost
    roll_events = [e for e in logged if e["event_type"] == "action_roll"]
    assert roll_events[-1]["entity_id"] == "pc-2"


@pytest.mark.anyio
async def test_agent_logs_a_companion_roleplay_line_after_narration():
    # FR-35: an AI-controlled crewmate may add an in-character line once
    # the GM's narration lands - queued for the *next* turn's transcript,
    # not answered live.
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("stream"):
            return httpx.Response(
                200,
                text='data: {"choices":[{"delta":{"content":"You proceed."}}]}\n\ndata: [DONE]\n\n',
            )
        if body.get("tools"):
            return httpx.Response(
                200,
                json={"choices": [{"message": {"role": "assistant", "content": "placeholder"}}]},
            )
        # PlayerAgent.maybe_roleplay's structured completion
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({"speaks": True, "line": "Vex nods."}),
                        }
                    }
                ]
            },
        )

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )
    agent = GmAgent(client, _executor())

    events = [
        event
        async for event in agent.handle_player_message(_state_with_ai_companion(), "We move in.")
    ]
    await client.aclose()

    companion_event = next(e for e in events if e.type == "companion_message")
    assert companion_event.payload == {
        "character_id": "pc-2",
        "name": "Vex",
        "text": "Vex nods.",
    }

    done_event = next(e for e in events if e.type == "narration_done")
    logged = done_event.payload["state"]["log"]["events"]
    player_events = [e for e in logged if e["event_type"] == "player_message"]
    assert player_events[-1]["entity_id"] == "pc-2"
    assert player_events[-1]["payload"] == {"text": "Vex nods.", "speaker": "Vex"}


@pytest.mark.anyio
async def test_agent_returns_an_ambiguous_roll_action_to_the_model_instead_of_crashing():
    # FR-25: with two PCs, a roll_action without a character_id is refused
    # by resolve_character_id - that refusal must reach the model as a tool
    # error it can retry (the same path every other tool's errors take),
    # not escape the generator and kill the WS connection.
    tool_round_calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("stream"):
            return httpx.Response(
                200, text='data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n'
            )
        tool_round_calls.append(body)
        if len(tool_round_calls) == 1:
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
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "placeholder"}}]},
        )

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )
    agent = GmAgent(client, _executor())

    events = [
        event
        async for event in agent.handle_player_message(_state_with_ai_companion(), "Sneak in.")
    ]
    await client.aclose()

    tool_event = next(e for e in events if e.type == "tool_call")
    assert "character_id is required" in tool_event.payload["result"]["error"]
    assert not any(e.type == "roll_proposed" for e in events)
    assert any(e.type == "narration_done" for e in events)


@pytest.mark.anyio
async def test_agent_rolls_as_proposed_when_the_companion_decision_call_fails():
    # FR-35: a companion's own LLM call failing (here: garbage instead of
    # JSON, twice, so structured_completion gives up) must not crash the
    # turn - the roll happens as the GM proposed it, with no stress spent.
    tool_round_calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("stream"):
            return httpx.Response(
                200, text='data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n'
            )
        if body.get("tools"):
            tool_round_calls.append(body)
            if len(tool_round_calls) == 1:
                return httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "message": _tool_call_message(
                                    "roll_action",
                                    {
                                        "action": "prowl",
                                        "position": "risky",
                                        "effect": "standard",
                                        "character_id": "pc-2",
                                    },
                                )
                            }
                        ]
                    },
                )
            return httpx.Response(
                200,
                json={"choices": [{"message": {"role": "assistant", "content": "placeholder"}}]},
            )
        # Every structured completion (decide_roll, then maybe_roleplay)
        # returns something that will never validate.
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "not json at all"}}]},
        )

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )
    agent = GmAgent(client, _executor())

    events = [
        event async for event in agent.handle_player_message(_state_with_ai_companion(), "Go.")
    ]
    await client.aclose()

    decided = next(e for e in events if e.type == "companion_roll_decision")
    assert decided.payload["decision"]["push_dice"] is False
    assert decided.payload["decision"]["devils_bargain"] is None

    done_event = next(e for e in events if e.type == "narration_done")
    logged = done_event.payload["state"]["log"]["events"]
    assert not any(e["event_type"] == "stress_marked" for e in logged)
    roll_events = [e for e in logged if e["event_type"] == "action_roll"]
    assert roll_events[-1]["entity_id"] == "pc-2"
    assert roll_events[-1]["payload"]["bonus_dice"] == 0
    # maybe_roleplay hit the same failing completion and stayed quiet.
    assert not any(e.type == "companion_message" for e in events)


@pytest.mark.anyio
async def test_agent_retrieves_matching_chunks_into_the_prompt(tmp_path: Path) -> None:
    # FR-13/FR-24: retrieval was built (state/srd_index.py) but never
    # actually queried by the GM agent loop - this is that wiring.
    db_path = app_db_path(tmp_path)
    run_app_migrations(db_path)
    engine = make_engine(db_path)
    session_factory = make_session_factory(engine)
    async with session_factory() as session:
        await index_srd_chunks(
            session, chunk_srd("# Armor\n\nMark an armor box to reduce a consequence.\n")
        )

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
    agent = GmAgent(client, _executor(), session_factory)

    async for _ in agent.handle_player_message(_state(), "I check my armor."):
        pass
    await client.aclose()
    await engine.dispose()

    system_message = requests[0]["messages"][0]["content"]
    assert "Mark an armor box" in system_message


@pytest.mark.anyio
async def test_agent_skips_retrieval_with_no_session_factory_configured():
    # The default - no regression for every other test in this file that
    # constructs a GmAgent without one.
    def handler(request: httpx.Request) -> httpx.Response:
        if json.loads(request.content).get("stream"):
            return httpx.Response(
                200, text='data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n'
            )
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "placeholder"}}]}
        )

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )
    agent = GmAgent(client, _executor())

    events = [event async for event in agent.handle_player_message(_state(), "hi")]
    await client.aclose()

    assert any(e.type == "narration_done" for e in events)


@pytest.mark.anyio
async def test_agent_runs_a_full_score_and_downtime_loop_through_tools():
    # TODO.md gap backlog: "GM score and downtime tool surface" - mirrors
    # test_headless_session.py's engine-only loop (plan, engagement,
    # action, payoff, heat, entanglement, one of each downtime activity),
    # but end to end through the GM agent's tool-calling loop instead of
    # calling engine functions directly.
    non_stream_round = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal non_stream_round
        body = json.loads(request.content)
        if body.get("stream"):
            return _narration_response("Noted.")
        non_stream_round += 1
        if non_stream_round == 1:
            message = _tool_calls_message(
                [
                    ("transition_phase", {"phase": "score"}),
                    ("roll_engagement", {"pool_size": 1}),
                ]
            )
        elif non_stream_round == 3:
            message = _tool_call_message(
                "roll_action", {"action": "prowl", "position": "risky", "effect": "standard"}
            )
        elif non_stream_round == 5:
            message = _tool_calls_message(
                [
                    ("transition_phase", {"phase": "downtime"}),
                    ("resolve_payoff", {"target_tier": 2, "coin": 4}),
                    ("add_crew_heat", {"amount": 4}),
                    ("roll_entanglement", {}),
                ]
            )
        elif non_stream_round == 7:
            message = _tool_calls_message(
                [
                    (
                        "create_clock",
                        {"clock_id": "heal-1", "name": "Healing", "kind": "healing", "segments": 8},
                    ),
                    (
                        "create_clock",
                        {
                            "clock_id": "vault",
                            "name": "Crack the Vault",
                            "kind": "long_term_project",
                            "segments": 8,
                        },
                    ),
                    ("acquire_asset", {}),
                    ("indulge_vice", {}),
                    ("recover", {"clock_id": "heal-1", "pool_size": 2}),
                    ("reduce_heat", {"pool_size": 2}),
                    ("long_term_project", {"clock_id": "vault", "pool_size": 2}),
                    ("mark_xp", {"track": "playbook", "amount": 1}),
                ]
            )
        else:
            return httpx.Response(200, json=_final_message())
        return httpx.Response(200, json={"choices": [{"message": message}]})

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )
    agent = GmAgent(client, _executor_with_entanglements())
    state = GameState(
        character=Character(
            name="Test", playbook="Test Playbook", action_ratings={Action.PROWL: 2}
        ),
        crew=Crew(name="Test Crew", crew_type="Test Type", tier=1),
        session=Session(),
    )

    def _tool_names(events: list) -> list[str]:
        return [e.payload["name"] for e in events if e.type == "tool_call"]

    def _final_state(events: list) -> GameState:
        done = next(e for e in events if e.type == "narration_done")
        return GameState.model_validate(done.payload["state"])

    # Turn 1: plan and engagement.
    events = [event async for event in agent.handle_player_message(state, "Let's plan the job.")]
    state = _final_state(events)
    assert _tool_names(events) == ["transition_phase", "roll_engagement"]
    assert state.session.phase.value == "score"
    assert any(ev.event_type == "engagement_roll" for ev in state.log.events)

    # Turn 2: the action roll, paused for the player's decision (FR-16).
    turn = agent.handle_player_message(state, "We strike now.")
    proposed = await anext(turn)
    assert proposed.type == "roll_proposed"
    tool_event = await turn.asend({})
    assert tool_event.type == "tool_call"
    remaining = [event async for event in turn]
    state = _final_state(remaining)
    assert any(ev.event_type == "action_roll" for ev in state.log.events)

    # Turn 3: downtime opens - payoff, heat, entanglement.
    events = [event async for event in agent.handle_player_message(state, "Time for downtime.")]
    state = _final_state(events)
    assert _tool_names(events) == [
        "transition_phase",
        "resolve_payoff",
        "add_crew_heat",
        "roll_entanglement",
    ]
    assert state.session.phase.value == "downtime"
    assert state.crew.rep.rep == 3  # payoff_rep(tier=1, target_tier=2) = 2 + (2-1)
    assert state.crew.coin == 4
    assert state.crew.heat.heat == 4
    assert any(ev.event_type == "entanglement_roll" for ev in state.log.events)

    # Turn 4: downtime activities - one of each.
    events = [event async for event in agent.handle_player_message(state, "We spend our downtime.")]
    await client.aclose()
    state = _final_state(events)
    assert _tool_names(events) == [
        "create_clock",
        "create_clock",
        "acquire_asset",
        "indulge_vice",
        "recover",
        "reduce_heat",
        "long_term_project",
        "mark_xp",
    ]
    logged_types = {ev.event_type for ev in state.log.events}
    assert {"asset_acquired", "vice_indulged", "downtime_activity_rolled", "clock_ticked"} <= (
        logged_types
    )
    assert state.character.playbook_xp.marked == 1
