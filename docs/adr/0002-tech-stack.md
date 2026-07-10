# 0002: Tech stack (Python/FastAPI backend, React/TypeScript frontend)

- Status: accepted
- Date: 2026-07-10

## Context

Resolves D1 and D4 in SPECIFICATION.md §9. The first client must present
interactive playbook sheets and maps to players, which is richer than a CLI,
and multiplayer (Phase 7) will need real-time state sync. The LLM backend is
an OpenAI-compatible API (ADR-0001), which any stack can call, but SRD/module
retrieval and rulebook ingestion (PDF extraction) favour Python tooling.

## Decision

**Backend: Python 3.12+ / FastAPI.**

- Pydantic v2 models are the single schema source for character/crew sheets,
  content packs, and event-log entries.
- FastAPI serves REST for CRUD and WebSockets for live session events;
  the server is authoritative. The rules engine is the only writer of game
  state (FR-10, FR-12).
- The engine is a pure Python package with no web dependencies, importable by
  the API server, tests, and a thin dev CLI harness.
- Tooling: `uv` for environments and deps, `ruff` for lint and format,
  `pytest`.

**Frontend: React + TypeScript SPA (Vite).**

- Interactive sheet UI (stress/harm/XP ticks, load, clocks) and map/table
  views; canvas library for maps (Pixi or Konva, decided when the map view is
  built, not now).
- TypeScript types are generated from the backend's OpenAPI/JSON Schema
  (e.g. `openapi-typescript`), never hand-duplicated.
- Tooling: `pnpm`, Vite, `vitest`.

**Repo layout: monorepo.**

```
server/   FastAPI app + engine + ai packages (uv project)
web/      React SPA (pnpm project)
packs/    committed content packs (SRD base pack, example pack)
docs/     ADRs, design notes
```

## Consequences

- Two toolchains to maintain; type generation is the contract between them.
  The drift check, run via the root Makefile and by the image build, fails
  when the generated types drift (there is no hosted CI; the owner builds
  with make, and any future CI runs the same targets).
- The web client replaces the CLI as the primary client (D4); a minimal
  CLI harness remains for engine development and headless session tests.
- The WebSocket session channel is built single-player first, so the
  multiplayer phase (FR-25 to FR-27) adds subscribers rather than requiring a
  rewrite.
- Map content is rendered from original or generated data only; the official
  Doskvol map is core-book content and never ships (C3).
