from pathlib import Path

import httpx2 as httpx
import pytest

from ai.capability import get_or_probe_tool_calling, probe_tool_calling
from ai.llm_client import LLMClient
from state.db import app_db_path, make_engine, make_session_factory
from state.migrations import run_migrations


def _tool_calling_handler(request: httpx.Request) -> httpx.Response:
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
                                "id": "1",
                                "type": "function",
                                "function": {"name": "ping", "arguments": "{}"},
                            }
                        ],
                    }
                }
            ]
        },
    )


def _plain_text_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"role": "assistant", "content": "sure, I would call ping"}}]
        },
    )


@pytest.mark.anyio
async def test_probe_tool_calling_true_when_model_calls_tool() -> None:
    client = LLMClient(
        "http://fake-llm/v1", "m", transport=httpx.MockTransport(_tool_calling_handler)
    )
    assert await probe_tool_calling(client) is True
    await client.aclose()


@pytest.mark.anyio
async def test_probe_tool_calling_false_when_model_just_talks() -> None:
    client = LLMClient(
        "http://fake-llm/v1", "m", transport=httpx.MockTransport(_plain_text_handler)
    )
    assert await probe_tool_calling(client) is False
    await client.aclose()


@pytest.mark.anyio
async def test_get_or_probe_caches_result(tmp_path: Path) -> None:
    call_count = 0

    def counting_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return _tool_calling_handler(request)

    db_path = app_db_path(tmp_path)
    run_migrations(db_path)
    engine = make_engine(db_path)
    session_factory = make_session_factory(engine)
    client = LLMClient("http://fake-llm/v1", "m", transport=httpx.MockTransport(counting_handler))

    try:
        async with session_factory() as session:
            first = await get_or_probe_tool_calling(session, client, "http://fake-llm/v1", "m")
        async with session_factory() as session:
            second = await get_or_probe_tool_calling(session, client, "http://fake-llm/v1", "m")

        assert first is True
        assert second is True
        assert call_count == 1  # second call hit the cache, not the LLM
    finally:
        await client.aclose()
        await engine.dispose()
