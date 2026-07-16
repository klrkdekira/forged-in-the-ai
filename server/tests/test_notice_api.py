from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.settings import Settings, get_settings

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_get_notice_serves_the_real_notice_md_content():
    # C1: "the required attribution text ... must appear in any distributed
    # UI's credits" - served from NOTICE.md itself, not a hand-copied string.
    response = client.get("/api/notice")

    assert response.status_code == 200
    text = response.json()["text"]
    assert "Creative Commons Attribution 3.0" in text
    assert "Blades in the Dark" in text


def test_get_notice_degrades_when_the_file_is_missing(tmp_path: Path):
    app.dependency_overrides[get_settings] = lambda: Settings(notice_path=tmp_path / "missing.md")

    response = client.get("/api/notice")

    assert response.status_code == 200
    assert "not available" in response.json()["text"]
