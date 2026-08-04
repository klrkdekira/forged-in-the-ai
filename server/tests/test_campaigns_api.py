import asyncio
import random
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai.tools import MarkStressArgs, ToolExecutor
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


def test_export_campaign_returns_the_log_and_both_snapshots(tmp_path: Path) -> None:
    with TestClient(app) as client:
        campaign = client.post("/api/campaigns", json={"name": "The Reckoning"}).json()

        db_path = campaign_db_path(tmp_path, campaign["id"])
        state = asyncio.run(load_state(db_path))
        executor = ToolExecutor(rng=random.Random(1), clock=lambda: datetime.now(UTC))
        result = executor.mark_stress(state, MarkStressArgs(amount=2))
        asyncio.run(save_state(db_path, result.state))

        response = client.get(f"/api/campaigns/{campaign['id']}/export")

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    body = response.json()
    assert body["campaign_id"] == campaign["id"]
    assert body["name"] == "The Reckoning"
    assert "stress_marked" in body["log_jsonl"]
    # NFR-5: the base snapshot never picks up the play that happened after
    # creation - only the latest one does.
    assert body["base_state"]["characters"]["pc-1"]["stress"]["marked"] == 0
    assert body["latest_state"]["characters"]["pc-1"]["stress"]["marked"] == 2


def test_export_campaign_404s_for_an_unknown_campaign() -> None:
    with TestClient(app) as client:
        response = client.get("/api/campaigns/does-not-exist/export")

    assert response.status_code == 404


def test_import_campaign_round_trips_a_played_campaign_into_a_fresh_one(
    tmp_path: Path,
) -> None:
    # NFR-5/ADR-0005: "a canonical JSONL event-log export (plus JSON
    # snapshots) that round-trips through import; a test enforces the
    # round-trip."
    with TestClient(app) as client:
        campaign = client.post("/api/campaigns", json={"name": "The Reckoning"}).json()
        campaign_id = campaign["id"]

        db_path = campaign_db_path(tmp_path, campaign_id)
        state = asyncio.run(load_state(db_path))
        executor = ToolExecutor(rng=random.Random(1), clock=lambda: datetime.now(UTC))
        result = executor.mark_stress(state, MarkStressArgs(amount=2))
        state = executor.log_event(result.state, "session", "current", "narration", {"text": "Ok."})
        asyncio.run(save_state(db_path, state))
        original_state = asyncio.run(load_state(db_path))

        bundle = client.get(f"/api/campaigns/{campaign_id}/export").json()

        import_response = client.post("/api/campaigns/import", json=bundle)

    assert import_response.status_code == 200
    new_campaign = import_response.json()
    assert new_campaign["id"] != campaign_id
    assert new_campaign["name"] == "The Reckoning"

    imported_state = asyncio.run(load_state(campaign_db_path(tmp_path, new_campaign["id"])))
    assert imported_state == original_state


def test_delete_campaign_removes_the_index_row_and_the_campaign_file(tmp_path: Path) -> None:
    with TestClient(app) as client:
        campaign = client.post("/api/campaigns", json={"name": "Doomed"}).json()
        campaign_id = campaign["id"]
        db_path = campaign_db_path(tmp_path, campaign_id)
        assert db_path.exists()

        delete_response = client.delete(f"/api/campaigns/{campaign_id}")
        list_response = client.get("/api/campaigns")

    assert delete_response.status_code == 204
    assert not db_path.exists()
    assert campaign_id not in {row["id"] for row in list_response.json()}


def test_delete_campaign_is_idempotent_for_an_already_removed_campaign(tmp_path: Path) -> None:
    with TestClient(app) as client:
        response = client.delete("/api/campaigns/never-existed")

    assert response.status_code == 204
