from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ADR-0004: DATA_DIR is the user-data volume mount point in compose.yml.
    data_dir: Path = Path("./data")

    # The committed content packs directory (packs/srd_base.json and any
    # others). Relative to the server process's cwd (`server/`, per the
    # Makefile), the same convention data_dir already uses - the container
    # image sets PACKS_DIR since its layout is flattened rather than a
    # checkout of this repo (Dockerfile).
    packs_dir: Path = Path("../packs")

    # FR-13: fetch and index the SRD at startup if app.db has no SRD
    # chunks. Off by default (dev uses `make index-srd` against the local
    # copy, and tests must never touch the network); the container image
    # sets SRD_AUTOINDEX=1, since it has neither a local SRD nor the CLI.
    srd_autoindex: bool = False

    # ADR-0001: OpenAI-compatible endpoint, configured by base URL/model/key.
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
