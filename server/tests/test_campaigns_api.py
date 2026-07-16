import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.campaigns import _new_game_state
from app.main import app
from app.settings import get_settings
from state.campaign_store import load_state, save_state
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


def test_create_campaign_uses_an_imported_character_and_crew(tmp_path: Path) -> None:
    # FR-8/G2: players bring their existing character (and crew) sheets.
    character = {"name": "Anders", "playbook": "Cutter", "alias": "The Ghost"}
    crew = {"name": "The Fifth Foxglove", "crew_type": "Assassins", "tier": 1}

    with TestClient(app) as client:
        response = client.post(
            "/api/campaigns",
            json={"name": "Imported Game", "character": character, "crew": crew},
        )
        campaign_id = response.json()["id"]

    loaded = asyncio.run(load_state(campaign_db_path(tmp_path, campaign_id)))
    assert loaded.character.name == "Anders"
    assert loaded.character.alias == "The Ghost"
    assert loaded.crew.name == "The Fifth Foxglove"
    assert loaded.crew.tier == 1


def test_create_campaign_without_an_import_uses_the_fixed_starter(tmp_path: Path) -> None:
    with TestClient(app) as client:
        campaign_id = client.post("/api/campaigns", json={"name": "Default"}).json()["id"]

    loaded = asyncio.run(load_state(campaign_db_path(tmp_path, campaign_id)))
    assert loaded.character.name == "Scoundrel"
    assert loaded.crew.name == "The Crew"


def test_list_campaigns_returns_every_created_campaign() -> None:
    with TestClient(app) as client:
        first = client.post("/api/campaigns", json={"name": "First"}).json()
        second = client.post("/api/campaigns", json={"name": "Second"}).json()

        response = client.get("/api/campaigns")

    assert response.status_code == 200
    ids = {row["id"] for row in response.json()}
    assert {first["id"], second["id"]} <= ids


def test_export_recap_returns_the_story_so_far_as_a_markdown_download(tmp_path: Path) -> None:
    with TestClient(app) as client:
        campaign = client.post("/api/campaigns", json={"name": "The Reckoning"}).json()

        db_path = campaign_db_path(tmp_path, campaign["id"])
        state = asyncio.run(load_state(db_path))
        log = state.log.append(
            "session", "current", "player_message", {"text": "I pick the lock."}, datetime.now(UTC)
        )
        log = log.append(
            "session", "current", "narration", {"text": "It clicks open."}, datetime.now(UTC)
        )
        asyncio.run(save_state(db_path, state.model_copy(update={"log": log})))

        response = client.get(f"/api/campaigns/{campaign['id']}/recap")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]
    assert "I pick the lock." in response.text
    assert "It clicks open." in response.text


def test_export_recap_404s_for_an_unknown_campaign() -> None:
    with TestClient(app) as client:
        response = client.get("/api/campaigns/does-not-exist/recap")

    assert response.status_code == 404
