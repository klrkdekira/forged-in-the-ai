from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ADR-0004: DATA_DIR is the user-data volume mount point in compose.yml.
    data_dir: Path = Path("./data")

    # ADR-0001: OpenAI-compatible endpoint, configured by base URL/model/key.
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
