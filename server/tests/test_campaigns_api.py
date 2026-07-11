import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.campaigns import _new_game_state
from app.main import app
from app.settings import get_settings
from state.campaign_store import load_state
from state.db import campaign_db_path


@pytest.fixture(autouse=True)
def _tmp_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # The lifespan's own migration call reads get_settings() directly
    # (not via Depends), so the override has to be the env var + cache
    # clear the app itself would see, not app.dependency_overrides.
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_create_campaign_returns_a_summary_and_writes_a_loadable_snapshot(tmp_path: Path) -> None:
    with TestClient(app) as client:
        response = client.post("/api/campaigns", json={"name": "The Reckoning"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "The Reckoning"
    assert body["id"]

    loaded = asyncio.run(load_state(campaign_db_path(tmp_path, body["id"])))
    assert loaded == _new_game_state()


def test_list_campaigns_returns_every_created_campaign() -> None:
    with TestClient(app) as client:
        first = client.post("/api/campaigns", json={"name": "First"}).json()
        second = client.post("/api/campaigns", json={"name": "Second"}).json()

        response = client.get("/api/campaigns")

    assert response.status_code == 200
    ids = {row["id"] for row in response.json()}
    assert {first["id"], second["id"]} <= ids
