import json

import httpx2 as httpx
import pytest

from ai.llm_client import LLMClient
from ingestion.module_extraction import (
    EXTRACTION_TEXT_BUDGET_TOKENS,
    _fit_text,
    extract_module_draft,
)


def test_fit_text_leaves_short_text_untouched():
    text, truncated = _fit_text("a short rulebook excerpt", budget_tokens=1000)

    assert text == "a short rulebook excerpt"
    assert truncated is False


def test_fit_text_cuts_text_over_budget():
    long_text = "x" * 100
    text, truncated = _fit_text(long_text, budget_tokens=10)

    assert len(text) == 40  # budget_tokens * 4 (ai.context.estimate_tokens's inverse)
    assert truncated is True


@pytest.mark.anyio
async def test_extract_module_draft_parses_the_models_structured_response():
    draft_payload = {
        "playbooks": [{"id": "prowler", "name": "Prowler", "xp_trigger": "..."}],
        "items": [{"id": "grapple_gun", "name": "Grapple Gun"}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        # messages[0] is structured_completion's own schema instruction
        # (NFR-6); [1]/[2] are this module's own system/user messages.
        assert "rulebook" in body["messages"][1]["content"]
        assert "starter text" in body["messages"][2]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": json.dumps(draft_payload)}}
                ]
            },
        )

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )

    result = await extract_module_draft(client, "starter text")
    await client.aclose()

    assert result.truncated is False
    assert result.draft.playbooks[0].name == "Prowler"
    assert result.draft.items[0].name == "Grapple Gun"
    assert result.draft.factions == []


@pytest.mark.anyio
async def test_extract_module_draft_reports_truncation():
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        # the fitted text, not the original, reaches the model
        assert len(body["messages"][2]["content"]) == EXTRACTION_TEXT_BUDGET_TOKENS * 4
        return httpx.Response(
            200, json={"choices": [{"message": {"role": "assistant", "content": "{}"}}]}
        )

    client = LLMClient(
        base_url="http://fake-llm/v1", model="test-model", transport=httpx.MockTransport(handler)
    )

    result = await extract_module_draft(client, "x" * (EXTRACTION_TEXT_BUDGET_TOKENS * 4 + 1000))
    await client.aclose()

    assert result.truncated is True
