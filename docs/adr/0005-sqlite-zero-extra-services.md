# 0005: SQLite in-process; zero additional services

- Status: accepted
- Date: 2026-07-10

## Context

With `server/` and `web/` scaffolded, the remaining infrastructure question is
which backing services the compose stack needs: database, retrieval index,
cache, queue, object storage. The system is single-process and
server-authoritative (FR-30), event-sourced (FR-19), container-first
(ADR-0004), with plain-file portability promised (NFR-5) and a BM25 retrieval
index required by ADR-0003.

## Decision

No additional compose services. SQLite, in-process, covers everything.

- **Database: SQLite** via SQLAlchemy 2 (async, `aiosqlite`) with Alembic
  migrations, WAL mode, on the user-data volume. Layout: one database file
  per campaign (`campaign-<id>.db`: event log, snapshots, entities,
  relationships) plus one app-level database (`app.db`: SRD/FTS retrieval
  index, settings, capability cache, installed content-pack state).
  A campaign is one file: copy it to back up, delete it to remove.
  Migrations run per file on open.
- **Retrieval: SQLite FTS5**, whose built-in BM25 is the first-version index
  ADR-0003 calls for, over SRD chunks and ingested module text. If semantic
  search is ever warranted, `sqlite-vec` adds vectors without a new service.
- **No Redis, queue, or cache**: one process; ingestion jobs run as async
  background tasks; WebSocket connections are in-process state.
- **No object storage**: uploaded rulebooks (FR-21) are files on the
  user-data volume, referenced by the database.
- **No auth service** until multiplayer (Phase 7); then start with invite
  tokens, still without an extra service.

NFR-5 (plain files) is met by the export contract rather than the storage
format: the canonical campaign export is a JSONL event-log bundle (plus JSON
snapshots) that round-trips through import. SQLite is the operational store;
the export is the user-owned portable artefact.

## Consequences

- `compose.yml` stays one service (plus the optional Ollama profile).
  Deployment remains `docker compose up`; backups are file copies of the
  volume or a JSONL export.
- Single-writer SQLite matches the engine's single-writer design; it becomes
  a bottleneck only under hosted multi-tenant multiplayer, and SQLAlchemy
  with Alembic keeps a Postgres migration path open if that day comes.
- The JSONL export/import round-trip needs a test from Phase 1 to hold the
  portability guarantee.
