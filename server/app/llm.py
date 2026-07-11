from ai.llm_client import LLMClient
from app.settings import Settings


def build_llm_client(settings: Settings) -> LLMClient | None:
    """ADR-0001: base URL/model/key from settings, never hardcoded. Returns
    None rather than raising when unconfigured, so each transport-specific
    dependency (WS vs HTTP) can refuse in whatever way fits that transport
    - a WebSocketException here would be meaningless to an HTTP route, and
    vice versa."""
    if not settings.llm_base_url or not settings.llm_model:
        return None
    return LLMClient(
        base_url=settings.llm_base_url, model=settings.llm_model, api_key=settings.llm_api_key
    )
