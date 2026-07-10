from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import mount_spa, resolve_static_path


def make_static_dir(tmp_path: Path) -> Path:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>spa</html>")
    (static_dir / "favicon.svg").write_text("<svg/>")
    return static_dir


def test_spa_serves_real_files_and_falls_back_to_index(tmp_path: Path) -> None:
    static_dir = make_static_dir(tmp_path)
    app = FastAPI()
    mount_spa(app, static_dir)
    client = TestClient(app)

    real_file = client.get("/favicon.svg")
    assert real_file.status_code == 200
    assert real_file.text == "<svg/>"

    spa_route = client.get("/campaigns/123")
    assert spa_route.status_code == 200
    assert spa_route.text == "<html>spa</html>"


def test_resolve_static_path_blocks_traversal(tmp_path: Path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>spa</html>")
    secret = tmp_path / "secret.txt"
    secret.write_text("do not serve me")

    resolved = resolve_static_path("../secret.txt", static_dir)

    assert resolved == static_dir / "index.html"
