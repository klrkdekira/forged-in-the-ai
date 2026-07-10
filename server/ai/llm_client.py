import json
from collections.abc import AsyncIterator

import httpx2 as httpx
from pydantic import BaseModel


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: str


class ChatResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = []


class LLMClient:
    """Any OpenAI-compatible chat-completions endpoint (ADR-0001): Ollama,
    vLLM, and hosted APIs are interchangeable via base_url/model/api_key.
    `transport` is an injection point for tests (httpx.MockTransport)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._model = model
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), headers=headers, transport=transport
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ChatResponse:
        payload: dict = {"model": self._model, "messages": messages}
        if tools:
            payload["tools"] = tools
        response = await self._http.post("/chat/completions", json=payload)
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]
        tool_calls = [
            ToolCall(
                id=call["id"],
                name=call["function"]["name"],
                arguments=call["function"]["arguments"],
            )
            for call in message.get("tool_calls") or []
        ]
        return ChatResponse(content=message.get("content"), tool_calls=tool_calls)

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        payload = {"model": self._model, "messages": messages, "stream": True}
        async with self._http.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line.removeprefix("data: ").strip()
                if data == "[DONE]":
                    break
                delta = json.loads(data)["choices"][0]["delta"].get("content")
                if delta:
                    yield delta
