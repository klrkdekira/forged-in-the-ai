import json

import httpx2 as httpx
import pytest

from ai.llm_client import DEFAULT_TIMEOUT_SECONDS, LLMClient


def test_default_timeout_is_generous_enough_for_a_real_completion() -> None:
    # httpx's own default (5s) is far too short for LLM inference; this
    # was discovered live against a real backend, not by the mocked tests.
    client = LLMClient(base_url="http://fake-llm/v1", model="test-model")

    assert client._http.timeout.read == DEFAULT_TIMEOUT_SECONDS
    assert DEFAULT_TIMEOUT_SECONDS >= 60


def test_timeout_is_configurable() -> None:
    client = LLMClient(base_url="http://fake-llm/v1", model="test-model", timeout=5.0)

    assert client._http.timeout.read == 5.0


async def _make_client(handler) -> LLMClient:
    return LLMClient(
        base_url="http://fake-llm/v1",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.anyio
async def test_chat_returns_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["model"] == "test-model"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "hello there"}}]},
        )

    client = await _make_client(handler)
    response = await client.chat(messages=[{"role": "user", "content": "hi"}])

    assert response.content == "hello there"
    assert response.tool_calls == []
    await client.aclose()


@pytest.mark.anyio
async def test_chat_parses_tool_calls() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": "ping", "arguments": "{}"},
                                }
                            ],
                        }
                    }
                ]
            },
        )

    client = await _make_client(handler)
    response = await client.chat(
        messages=[{"role": "user", "content": "hi"}], tools=[{"type": "function"}]
    )

    assert response.content is None
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "ping"
    assert response.tool_calls[0].arguments == "{}"
    await client.aclose()


@pytest.mark.anyio
async def test_chat_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = await _make_client(handler)
    with pytest.raises(httpx.HTTPStatusError):
        await client.chat(messages=[{"role": "user", "content": "hi"}])
    await client.aclose()


@pytest.mark.anyio
async def test_stream_chat_yields_content_deltas() -> None:
    sse_body = (
        'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n'
        'data: {"choices":[{"delta":{}}]}\n\n'
        "data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(200, text=sse_body)

    client = await _make_client(handler)
    chunks = [
        chunk async for chunk in client.stream_chat(messages=[{"role": "user", "content": "hi"}])
    ]

    assert chunks == ["Hel", "lo"]
    await client.aclose()
