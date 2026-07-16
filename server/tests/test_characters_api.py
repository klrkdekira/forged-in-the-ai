from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.settings import get_settings
from engine.character import Character
from state.character_store import characters_dir


@pytest.fixture(autouse=True)
def _tmp_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _save(tmp_path: Path, character_id: str, **overrides) -> None:
    overrides.setdefault("name", "Test")
    overrides.setdefault("playbook", "Cutter")
    character = Character(**overrides)
    directory = characters_dir(tmp_path)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{character_id}.json").write_text(character.model_dump_json())


def test_list_characters_returns_saved_guided_entry_files(tmp_path: Path) -> None:
    _save(tmp_path, "anders", name="Anders", playbook="Cutter")

    with TestClient(app) as client:
        response = client.get("/api/characters")

    assert response.status_code == 200
    assert response.json() == [{"id": "anders", "name": "Anders", "playbook": "Cutter"}]


def test_list_characters_is_empty_when_nothing_has_been_saved() -> None:
    with TestClient(app) as client:
        response = client.get("/api/characters")

    assert response.status_code == 200
    assert response.json() == []


def test_get_character_returns_the_full_sheet(tmp_path: Path) -> None:
    _save(tmp_path, "anders", name="Anders", alias="The Ghost")

    with TestClient(app) as client:
        response = client.get("/api/characters/anders")

    assert response.status_code == 200
    assert response.json()["alias"] == "The Ghost"


def test_get_character_404s_for_an_unknown_id() -> None:
    with TestClient(app) as client:
        response = client.get("/api/characters/nope")

    assert response.status_code == 404
