import json

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from ai.llm_client import LLMClient
from app.main import app
from app.session_ws import get_llm_client
from app.settings import get_settings


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


def _mock_client(handler) -> LLMClient:
    return LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_session_ws_sends_initial_state_then_streams_narration():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if body.get("stream"):
            return httpx.Response(
                200,
                text='data: {"choices":[{"delta":{"content":"Go ahead."}}]}\n\ndata: [DONE]\n\n',
            )
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "Go ahead."}}]}
        )

    app.dependency_overrides[get_llm_client] = lambda: _mock_client(handler)

    with TestClient(app) as test_client, test_client.websocket_connect("/ws/session") as ws:
        initial = ws.receive_json()
        assert initial["type"] == "state"
        assert initial["state"]["character"]["name"] == "Scoundrel"

        ws.send_json({"type": "player_message", "text": "I look around."})

        chunk = ws.receive_json()
        assert chunk == {"type": "narration_chunk", "text": "Go ahead."}

        done = ws.receive_json()
        assert done["type"] == "narration_done"
        assert done["state"]["character"]["name"] == "Scoundrel"


def test_session_ws_runs_a_tool_call_before_narrating():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if body.get("stream"):
            return httpx.Response(
                200,
                text='data: {"choices":[{"delta":{"content":"You succeed."}}]}\n\ndata: [DONE]\n\n',
            )
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

    app.dependency_overrides[get_llm_client] = lambda: _mock_client(handler)

    with TestClient(app) as test_client, test_client.websocket_connect("/ws/session") as ws:
        ws.receive_json()  # initial state
        ws.send_json({"type": "player_message", "text": "I search the room."})

        tool_event = ws.receive_json()
        assert tool_event["type"] == "tool_call"
        assert tool_event["name"] == "roll_fortune"
        assert "band" in tool_event["result"]


def test_session_ws_pauses_for_a_roll_decision_then_resolves_it():
    # FR-16: the WS handler drives the agent's negotiation pause - it must
    # wait for a roll_decision message before the proposed roll executes.
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if body.get("stream"):
            return httpx.Response(
                200,
                text='data: {"choices":[{"delta":{"content":"You slip past."}}]}\n\n'
                "data: [DONE]\n\n",
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

    app.dependency_overrides[get_llm_client] = lambda: _mock_client(handler)

    with TestClient(app) as test_client, test_client.websocket_connect("/ws/session") as ws:
        ws.receive_json()  # initial state
        ws.send_json({"type": "player_message", "text": "I sneak past the guards."})

        proposed = ws.receive_json()
        assert proposed["type"] == "roll_proposed"
        assert proposed["position"] == "risky"
        assert proposed["effect"] == "standard"

        ws.send_json({"type": "roll_decision", "decision": {"push_effect": True}})

        tool_event = ws.receive_json()
        assert tool_event["type"] == "tool_call"
        assert tool_event["name"] == "roll_action"
        assert tool_event["result"]["effect"] == 3  # standard, pushed +1


def test_session_ws_closes_when_the_llm_is_not_configured(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("LLM_MODEL", "")
    get_settings.cache_clear()

    try:
        with TestClient(app) as test_client:
            with pytest.raises(WebSocketDisconnect):
                with test_client.websocket_connect("/ws/session"):
                    pass
    finally:
        get_settings.cache_clear()
