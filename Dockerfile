# Multi-stage build (ADR-0004): web assets, then the Python server that
# serves them. One image, one process, one port.

FROM python:3.12-slim AS server-base
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

# Dependencies first so they cache independently of app code changes.
COPY server/pyproject.toml server/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY server/app ./app
COPY server/ai ./ai
COPY server/engine ./engine
COPY server/ingestion ./ingestion
COPY server/state ./state
COPY packs ./packs
RUN uv sync --locked --no-dev

FROM server-base AS openapi-export
RUN uv run python -m app.export_openapi > /openapi.json

FROM node:24-slim AS web-build
WORKDIR /web
RUN corepack enable
COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
COPY --from=openapi-export /openapi.json /server/openapi.json
# Schema contract (TODO.md Phase 0): fails the build if schema.d.ts is stale.
RUN pnpm run check:api-drift
RUN pnpm build

FROM server-base AS runtime
# Alembic runs at startup (app/main.py lifespan), not needed for the OpenAPI
# export, so it's copied only here.
COPY server/alembic ./alembic
COPY server/alembic_campaign ./alembic_campaign
COPY server/alembic.ini ./alembic.ini
COPY --from=web-build /web/dist ./app/static

RUN useradd --create-home --uid 1000 app && chown -R app:app /app
# /data is where compose.yml mounts the user-data volume; a named volume
# takes on a directory's ownership from the image the first time it's
# created, so this needs to happen before that mount, as root.
RUN mkdir -p /data && chown app:app /data
USER app

ENV PATH="/app/.venv/bin:$PATH"
# The image has no local SRD copy and no dev CLI, so the SRD retrieval
# index (FR-13) is fetched and built on first start instead (app/main.py
# lifespan via state/srd_bootstrap.py); a no-op once app.db has it.
ENV SRD_AUTOINDEX=1
# Settings.packs_dir defaults to "../packs" (dev's cwd is server/); the
# image's layout is flattened (no server/ nesting), so packs/ lands at
# /app/packs instead (app/packs.py::load_entanglements).
ENV PACKS_DIR=/app/packs
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
