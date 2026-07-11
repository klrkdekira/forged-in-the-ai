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


def _create_campaign(test_client: TestClient) -> str:
    response = test_client.post("/api/campaigns", json={"name": "Test Campaign"})
    return response.json()["id"]


@pytest.fixture(autouse=True)
def _tmp_data_dir(tmp_path, monkeypatch: pytest.MonkeyPatch):
    # The lifespan's own migration call, and the WS route's campaign-file
    # lookup, both read get_settings() directly rather than via Depends
    # (the WS dependency still needs Depends for test overrides to reach
    # it, but the underlying Settings has to be the same tmp_path either
    # way), so this has to be an env var + cache clear, not
    # app.dependency_overrides.
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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

    with TestClient(app) as test_client:
        campaign_id = _create_campaign(test_client)
        with test_client.websocket_connect(f"/ws/session/{campaign_id}") as ws:
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

    with TestClient(app) as test_client:
        campaign_id = _create_campaign(test_client)
        with test_client.websocket_connect(f"/ws/session/{campaign_id}") as ws:
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

    with TestClient(app) as test_client:
        campaign_id = _create_campaign(test_client)
        with test_client.websocket_connect(f"/ws/session/{campaign_id}") as ws:
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


def test_session_ws_applies_a_sheet_operation_without_the_llm():
    # FR-28: the sheet panel calls engine operations directly - no chat
    # turn, no LLM call at all.
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("the LLM should never be called for a sheet operation")

    app.dependency_overrides[get_llm_client] = lambda: _mock_client(handler)

    with TestClient(app) as test_client:
        campaign_id = _create_campaign(test_client)
        with test_client.websocket_connect(f"/ws/session/{campaign_id}") as ws:
            ws.receive_json()  # initial state
            ws.send_json({"type": "sheet_operation", "name": "mark_stress", "args": {"amount": 3}})

            state_update = ws.receive_json()
            assert state_update["type"] == "state"
            assert state_update["state"]["character"]["stress"]["marked"] == 3


def test_session_ws_reports_an_error_for_an_illegal_sheet_operation():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("the LLM should never be called for a sheet operation")

    app.dependency_overrides[get_llm_client] = lambda: _mock_client(handler)

    with TestClient(app) as test_client:
        campaign_id = _create_campaign(test_client)
        with test_client.websocket_connect(f"/ws/session/{campaign_id}") as ws:
            ws.receive_json()  # initial state
            ws.send_json({"type": "sheet_operation", "name": "adjust_coin", "args": {"amount": -1}})

            error = ws.receive_json()
            assert error["type"] == "error"
            assert "cannot spend" in error["message"]


def test_session_ws_ticks_a_clock_the_gm_created_via_a_sheet_operation():
    # FR-29: the table view ticks a clock the GM created, no LLM call.
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        if body.get("stream"):
            return httpx.Response(
                200, text='data: {"choices":[{"delta":{"content":"Noted."}}]}\n\ndata: [DONE]\n\n'
            )
        if len(calls) == 1:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": _tool_call_message(
                                "create_clock",
                                {
                                    "clock_id": "alert",
                                    "name": "Alert",
                                    "kind": "danger",
                                    "segments": 4,
                                },
                            )
                        }
                    ]
                },
            )
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "placeholder"}}]}
        )

    app.dependency_overrides[get_llm_client] = lambda: _mock_client(handler)

    with TestClient(app) as test_client:
        campaign_id = _create_campaign(test_client)
        with test_client.websocket_connect(f"/ws/session/{campaign_id}") as ws:
            ws.receive_json()  # initial state
            ws.send_json({"type": "player_message", "text": "We case the joint."})

            ws.receive_json()  # tool_call: create_clock
            ws.receive_json()  # narration_chunk
            ws.receive_json()  # narration_done

            ws.send_json(
                {
                    "type": "sheet_operation",
                    "name": "tick_clock",
                    "args": {"clock_id": "alert", "amount": 2},
                }
            )
            state_update = ws.receive_json()

            assert state_update["type"] == "state"
            assert state_update["state"]["clocks"]["alert"]["filled"] == 2


def test_session_ws_persists_state_across_reconnects():
    # FR-18: the whole point of a campaign_id - a second connection to the
    # same campaign resumes where the first left off.
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("the LLM should never be called for a sheet operation")

    app.dependency_overrides[get_llm_client] = lambda: _mock_client(handler)

    with TestClient(app) as test_client:
        campaign_id = _create_campaign(test_client)
        with test_client.websocket_connect(f"/ws/session/{campaign_id}") as ws:
            ws.receive_json()  # initial state
            ws.send_json({"type": "sheet_operation", "name": "mark_stress", "args": {"amount": 3}})
            ws.receive_json()  # state

        with test_client.websocket_connect(f"/ws/session/{campaign_id}") as ws:
            resumed = ws.receive_json()
            assert resumed["state"]["character"]["stress"]["marked"] == 3


def test_session_ws_undoes_to_an_earlier_event_sequence():
    # FR-19: undo/rewind is an engine operation like sheet_operation - no
    # LLM call, and the truncation persists (a reconnect afterwards must
    # still see the rewound state, not the original).
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("the LLM should never be called for an undo")

    app.dependency_overrides[get_llm_client] = lambda: _mock_client(handler)

    with TestClient(app) as test_client:
        campaign_id = _create_campaign(test_client)
        with test_client.websocket_connect(f"/ws/session/{campaign_id}") as ws:
            ws.receive_json()  # initial state
            ws.send_json({"type": "sheet_operation", "name": "mark_stress", "args": {"amount": 2}})
            first = ws.receive_json()
            first_sequence = first["state"]["log"]["events"][-1]["sequence"]

            ws.send_json({"type": "sheet_operation", "name": "adjust_coin", "args": {"amount": 5}})
            ws.receive_json()  # state after the coin adjustment

            ws.send_json({"type": "undo", "sequence": first_sequence})
            undone = ws.receive_json()

            assert undone["type"] == "undo_done"
            assert undone["state"]["character"]["stress"]["marked"] == 2
            assert undone["state"]["character"]["coin"] == 0

        with test_client.websocket_connect(f"/ws/session/{campaign_id}") as ws:
            resumed = ws.receive_json()
            assert resumed["state"]["character"]["coin"] == 0


def test_session_ws_reports_an_error_for_a_non_integer_undo_sequence():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("the LLM should never be called for an undo")

    app.dependency_overrides[get_llm_client] = lambda: _mock_client(handler)

    with TestClient(app) as test_client:
        campaign_id = _create_campaign(test_client)
        with test_client.websocket_connect(f"/ws/session/{campaign_id}") as ws:
            ws.receive_json()  # initial state
            ws.send_json({"type": "undo", "sequence": "not-a-number"})

            error = ws.receive_json()
            assert error["type"] == "error"
            assert "integer" in error["message"]


def test_session_ws_closes_for_an_unknown_campaign_id():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("the LLM should never be called")

    app.dependency_overrides[get_llm_client] = lambda: _mock_client(handler)

    with TestClient(app) as test_client:
        with pytest.raises(WebSocketDisconnect):
            with test_client.websocket_connect("/ws/session/does-not-exist"):
                pass


def test_session_ws_closes_when_the_llm_is_not_configured(monkeypatch):
    with TestClient(app) as test_client:
        campaign_id = _create_campaign(test_client)

        monkeypatch.setenv("LLM_BASE_URL", "")
        monkeypatch.setenv("LLM_MODEL", "")
        get_settings.cache_clear()

        try:
            with pytest.raises(WebSocketDisconnect):
                with test_client.websocket_connect(f"/ws/session/{campaign_id}"):
                    pass
        finally:
            get_settings.cache_clear()
