import httpx2 as httpx
import pytest
from pydantic import BaseModel

from ai.llm_client import LLMClient
from ai.structured import StructuredOutputError, structured_completion


class Roll(BaseModel):
    dice: int
    take_highest: bool


def _content_response(content: str) -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"message": {"role": "assistant", "content": content}}]}
    )


@pytest.mark.anyio
async def test_parses_plain_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _content_response('{"dice": 4, "take_highest": true}')

    client = LLMClient("http://fake-llm/v1", "m", transport=httpx.MockTransport(handler))
    result = await structured_completion(client, [{"role": "user", "content": "roll"}], Roll)

    assert result == Roll(dice=4, take_highest=True)
    await client.aclose()


@pytest.mark.anyio
async def test_parses_json_in_markdown_fence() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _content_response('Sure thing:\n```json\n{"dice": 6, "take_highest": false}\n```')

    client = LLMClient("http://fake-llm/v1", "m", transport=httpx.MockTransport(handler))
    result = await structured_completion(client, [{"role": "user", "content": "roll"}], Roll)

    assert result == Roll(dice=6, take_highest=False)
    await client.aclose()


@pytest.mark.anyio
async def test_retries_once_then_succeeds() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _content_response("not json at all")
        return _content_response('{"dice": 2, "take_highest": true}')

    client = LLMClient("http://fake-llm/v1", "m", transport=httpx.MockTransport(handler))
    result = await structured_completion(client, [{"role": "user", "content": "roll"}], Roll)

    assert result == Roll(dice=2, take_highest=True)
    assert calls == 2
    await client.aclose()


@pytest.mark.anyio
async def test_raises_after_exhausting_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _content_response("still not json")

    client = LLMClient("http://fake-llm/v1", "m", transport=httpx.MockTransport(handler))

    with pytest.raises(StructuredOutputError):
        await structured_completion(client, [{"role": "user", "content": "roll"}], Roll)
    await client.aclose()
