from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

app = FastAPI(title="forged-in-the-ai")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def resolve_static_path(full_path: str, static_dir: Path) -> Path:
    """Vite's build emits both hashed assets (assets/*) and unhashed public
    files (favicon.svg, icons.svg) at the dist root, so a real file is
    served as-is; anything else (a genuine SPA route, or a path-traversal
    attempt) falls back to index.html."""
    candidate = (static_dir / full_path).resolve()
    if full_path and candidate.is_relative_to(static_dir) and candidate.is_file():
        return candidate
    return static_dir / "index.html"


def mount_spa(app: FastAPI, static_dir: Path) -> None:
    """Routed last so it never shadows /api or (later) the WebSocket path."""

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        return FileResponse(resolve_static_path(full_path, static_dir))


# The image build (ADR-0004) copies the built web SPA in here; local dev via
# `uvicorn --reload` has no static dir and serves the API only.
STATIC_DIR = (Path(__file__).parent / "static").resolve()
if STATIC_DIR.is_dir():
    mount_spa(app, STATIC_DIR)
