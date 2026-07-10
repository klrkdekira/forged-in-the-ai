from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.llm_client import LLMClient
from state.models import CapabilityProbe

_PROBE_TOOL = {
    "type": "function",
    "function": {
        "name": "ping",
        "description": "Call this to confirm you can use tools.",
        "parameters": {"type": "object", "properties": {}},
    },
}


async def probe_tool_calling(client: LLMClient) -> bool:
    """One-shot probe: does this backend/model actually call a tool when
    told to, rather than just describing what it would do (NFR-6)?"""
    response = await client.chat(
        messages=[
            {
                "role": "system",
                "content": "You must call the ping tool now. Do not respond with text.",
            },
            {"role": "user", "content": "ping"},
        ],
        tools=[_PROBE_TOOL],
    )
    return any(call.name == "ping" for call in response.tool_calls)


async def get_or_probe_tool_calling(
    session: AsyncSession, client: LLMClient, base_url: str, model: str
) -> bool:
    """Cached in app.db (ADR-0005) so a session doesn't re-probe every turn."""
    cached = await session.scalar(
        select(CapabilityProbe).where(
            CapabilityProbe.base_url == base_url, CapabilityProbe.model == model
        )
    )
    if cached is not None:
        return cached.supports_tool_calling

    supports_tool_calling = await probe_tool_calling(client)
    session.add(
        CapabilityProbe(base_url=base_url, model=model, supports_tool_calling=supports_tool_calling)
    )
    await session.commit()
    return supports_tool_calling
