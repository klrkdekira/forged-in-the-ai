import json
import re

from pydantic import BaseModel, ValidationError

from ai.llm_client import LLMClient

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

_MAX_ATTEMPTS = 2


class StructuredOutputError(RuntimeError):
    """The model's response wasn't valid JSON matching the given schema,
    after one corrective retry."""


def _extract_json(text: str) -> str:
    match = _JSON_FENCE.search(text)
    return match.group(1) if match else text


async def structured_completion[T: BaseModel](
    client: LLMClient, messages: list[dict], schema: type[T]
) -> T:
    """Fallback for models whose native tool-calling is unreliable (NFR-6):
    ask for JSON matching schema in the prompt instead of via `tools`, and
    validate the response. One corrective retry on a malformed reply."""
    request = [
        {
            "role": "system",
            "content": (
                "Respond with ONLY a JSON object matching this schema, no "
                f"other text:\n{json.dumps(schema.model_json_schema())}"
            ),
        },
        *messages,
    ]
    last_error: Exception | None = None

    for attempt in range(_MAX_ATTEMPTS):
        if attempt:
            request = [
                *request,
                {
                    "role": "user",
                    "content": (
                        f"That wasn't valid JSON matching the schema: {last_error}. "
                        "Try again."
                    ),
                },
            ]
        response = await client.chat(messages=request)
        try:
            return schema.model_validate_json(_extract_json(response.content or ""))
        except (ValidationError, ValueError) as error:
            last_error = error

    raise StructuredOutputError(str(last_error))
