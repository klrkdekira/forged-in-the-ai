# 0004: Container-first packaging (single image, compose at the root)

- Status: accepted
- Date: 2026-07-10

## Context

Refines the repo layout in ADR-0002. The project owner works with containers
as the default runtime and wants one command to build and run everything (no
starting the web build and the Python server as separate processes) and a
single deployable artefact.

## Decision

- `Dockerfile` and `compose.yml` live at the project root.
- One image carries both the compiled web assets and the Python server,
  via a multi-stage build:
  1. `web-build` stage: pnpm install plus `vite build`, producing static
     `dist/`
  2. runtime stage: Python 3.12 with the uv-installed server; `dist/` is
     copied in and FastAPI serves it as static files alongside the API and
     WebSocket endpoints. One process, one port.
- `compose.yml` is the entrypoint for running the app: `docker compose up`
  builds the image and starts the game server, bound to 127.0.0.1 only. The
  MVP has no auth; the app trusts whoever reaches it, and auth arrives with
  multiplayer (Phase 7). Volumes mount the user data
  directory (campaign saves, private modules; NFR-5, C6) so state survives
  container replacement. The LLM backend is configured by env vars (base URL,
  model, key; ADR-0001); an optional compose profile can add a local Ollama
  service for offline play.
- Development keeps hot reload: a `dev` compose profile (or compose watch)
  runs `uvicorn --reload` and the Vite dev server with the API proxied, so
  container-first does not mean rebuild-per-change.

## Consequences

- Deployment is `docker compose up` on anything with a container runtime;
  the future multiplayer server (Phase 7) ships the same way.
- The image build enforces the schema contract: TS type generation from the
  server schemas runs before `vite build`, so drift fails during the image
  build rather than at runtime.
- FastAPI serving the SPA means no separate web server or CDN in the simple
  case; SPA routing needs a catch-all route that never shadows `/api` or the
  WebSocket path.
- A single image couples web and server release cadence. Acceptable at this
  scale; revisit only if the clients multiply (FR-27).
