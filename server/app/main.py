from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.campaigns import router as campaigns_router
from app.ingestion import router as ingestion_router
from app.notice import router as notice_router
from app.session_ws import router as session_ws_router
from app.settings import get_settings
from state.db import app_db_path
from state.migrations import run_app_migrations
from state.srd_bootstrap import ensure_srd_indexed


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    db_path = app_db_path(settings.data_dir)
    run_app_migrations(db_path)
    if settings.srd_autoindex:
        await ensure_srd_indexed(db_path)
    yield


app = FastAPI(title="forged-in-the-ai", lifespan=lifespan)
app.include_router(campaigns_router)
app.include_router(ingestion_router)
app.include_router(notice_router)
app.include_router(session_ws_router)


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

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        return FileResponse(resolve_static_path(full_path, static_dir))


# The image build (ADR-0004) copies the built web SPA in here; local dev via
# `uvicorn --reload` has no static dir and serves the API only.
STATIC_DIR = (Path(__file__).parent / "static").resolve()
if STATIC_DIR.is_dir():
    mount_spa(app, STATIC_DIR)
