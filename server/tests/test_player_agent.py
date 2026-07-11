import json

import httpx2 as httpx
import pytest

from ai.llm_client import LLMClient
from ai.player_agent import PlayerAgent, build_player_system_prompt
from ai.tools import GameState, RollActionArgs
from engine.character import Action, Character
from engine.crew import Crew
from engine.rolls import Effect, Position
from engine.session import Session


def _state() -> GameState:
    return GameState(
        characters={
            "pc-1": Character(name="Anders", playbook="Cutter"),
            "pc-2": Character(name="Vex", playbook="Whisper", action_ratings={Action.PROWL: 2}),
        },
        crew=Crew(name="Test Crew", crew_type="Test Type"),
        session=Session(),
    )


def test_build_player_system_prompt_names_the_character():
    prompt = build_player_system_prompt(Character(name="Vex", playbook="Whisper"))

    assert "Vex" in prompt
    assert "playing Vex" in prompt  # scoped to this one character, not the wider table


@pytest.mark.anyio
async def test_decide_roll_returns_a_structured_decision():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        # messages[0] is structured_completion's own schema instruction
        # (NFR-6); [1]/[2] are PlayerAgent's own system/user messages.
        assert "Vex" in body["messages"][1]["content"]
        assert "prowl" in body["messages"][2]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({"push_dice": True}),
                        }
                    }
                ]
            },
        )

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )
    agent = PlayerAgent(client, "pc-2")
    proposal = RollActionArgs(action=Action.PROWL, position=Position.RISKY, effect=Effect.STANDARD)

    decision = await agent.decide_roll(_state(), proposal, pool_size=2)
    await client.aclose()

    assert decision.push_dice is True
    assert decision.push_effect is False


@pytest.mark.anyio
async def test_maybe_roleplay_returns_none_when_the_model_stays_quiet():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": json.dumps({"speaks": False})}}
                ]
            },
        )

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )
    agent = PlayerAgent(client, "pc-2")

    line = await agent.maybe_roleplay(_state(), "The door creaks open.")
    await client.aclose()

    assert line is None


@pytest.mark.anyio
async def test_maybe_roleplay_returns_the_line_when_the_model_speaks():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {"speaks": True, "line": "Vex tenses at the sound."}
                            ),
                        }
                    }
                ]
            },
        )

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )
    agent = PlayerAgent(client, "pc-2")

    line = await agent.maybe_roleplay(_state(), "The door creaks open.")
    await client.aclose()

    assert line == "Vex tenses at the sound."
