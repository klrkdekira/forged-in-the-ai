from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.settings import get_settings


def test_startup_migrates_app_db(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()

    try:
        with TestClient(app) as client:
            response = client.get("/api/health")
            assert response.status_code == 200

        assert (tmp_path / "app.db").is_file()
    finally:
        get_settings.cache_clear()
