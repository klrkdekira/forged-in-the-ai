.PHONY: lint test licensing-grep drift-check check check-all build dev

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

# Placeholder: becomes a real check once the schema contract (TODO.md
# Phase 0, "Schema contract") generates TS types from the server OpenAPI
# spec and there is something for generated code to drift from.
drift-check:
	@echo "drift-check: no generated types yet (TODO.md Phase 0 schema contract)"

check: lint test licensing-grep drift-check

build:
	docker build -t forged-in-the-ai .

check-all: check build

# Placeholder: runs both dev servers directly until compose.yml (TODO.md
# Phase 0) provides the `dev` profile described in ADR-0004.
dev:
	@trap 'kill 0' EXIT; \
	(cd server && uv run uvicorn app.main:app --reload) & \
	(cd web && pnpm dev) & \
	wait
