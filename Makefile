.PHONY: lint test licensing-grep generate drift-check check check-all build dev fetch-srd extract-srd

# Single entry point for the whole repo (CLAUDE.md); no hosted CI, so this
# is what the owner runs by hand and what any future CI would call.

lint:
	cd server && uv run ruff check .
	cd web && pnpm lint

test:
	cd server && uv run pytest
	cd web && pnpm test

licensing-grep:
	./scripts/licensing-grep.sh

# Dev tooling lives in server/cli/ (Click commands, one module per command).
# Local dev setup (C1): downloads the gitignored SRD to the repo root.
fetch-srd:
	cd server && uv run python -m cli fetch-srd

# Regenerates packs/srd_base.json from the local SRD copy; commit the result.
extract-srd:
	cd server && uv run python -m cli extract-srd

# Regenerates web/src/api/schema.d.ts from the server's OpenAPI spec; run
# after changing server routes/models and commit the result.
generate:
	cd server && uv run python -m app.export_openapi > openapi.json
	cd web && pnpm run generate:api

drift-check:
	cd server && uv run python -m app.export_openapi > openapi.json
	cd web && pnpm run check:api-drift

check: lint test licensing-grep drift-check

build:
	docker compose build

check-all: check build

# Placeholder: runs both dev servers directly until compose.yml (TODO.md
# Phase 0) provides the `dev` profile described in ADR-0004.
dev:
	@trap 'kill 0' EXIT; \
	(cd server && uv run uvicorn app.main:app --reload) & \
	(cd web && pnpm dev) & \
	wait
