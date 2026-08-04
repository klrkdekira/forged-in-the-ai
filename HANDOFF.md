# Project Handoff & Audit Documentation

This document provides a comprehensive analysis of current progress, system architecture, test harness details, licensing constraints, and an audited list of open backlog gaps for **forged-in-the-ai**.

---

## 1. Executive Summary & Architecture Overview

**forged-in-the-ai** is an AI referee (Game Master) for *Forged in the Dark* tabletop roleplaying games (starting with *Blades in the Dark*). It combines a deterministic rules engine with an LLM narrative layer.

### System Architecture Highlights
- **Rules Engine Core (`server/engine`)**: Pure Python rules adjudication with no web/LLM imports. The engine is the sole writer of game state. State transitions generate structured, entity-tagged events.
- **Event Sourcing & Replay (`server/engine/events.py`, `server/ai/replay.py`)**: All state mutations append to an event log (`events`). State snapshots are optional caches. `replay_state()` accurately folds logs into full game state deterministically (NFR-1).
- **AI Referee (`server/ai`)**: `GmAgent` coordinates turn context assembly, SRD FTS5 retrieval, procedure injection, and tool executions. Weak models fall back to structured JSON completions (NFR-6).
- **Web UI (`web/`)**: React SPA built with Vite, TypeScript, TanStack Router/Query, Tailwind CSS, shadcn/ui, and Konva.js (`react-konva`) for interactive canvas maps.
- **Single Container Image (ADR-0004)**: Multi-stage `Dockerfile` compiles the React SPA and serves it from the FastAPI backend runtime.

---

## 2. Progress Matrix & Feature Status

| Phase / Scope | Description | Status | Verification & Artifacts |
| :--- | :--- | :---: | :--- |
| **Phase 0: Foundations** | Project skeleton, Dockerfile, OpenAPI TS generation, SQLite WAL setup, SRD retrieval index, content pack loader | **Done** | `make check`, `packs/srd_base.json` |
| **Phase 1: Rules Engine Core** | Dice pools, action/resistance/fortune rolls, progress clocks, event log export/import | **Done** | `server/tests/test_rolls.py`, `test_clocks.py` |
| **Phase 2: World State** | Character & crew sheet schemas, entity models, relationship edges, markdown renderers | **Done** | `server/engine/character.py`, `crew.py` |
| **Phase 3: Score & Campaign Loop** | Engagement roll, score state machine, flashbacks, downtime activity engine, XP advancement | **Done** | `test_downtime.py`, `test_headless_session.py` |
| **Phase 4: AI Referee MVP** | GM agent system prompt, SRD FTS5 retrieval, WebSocket streaming, interactive sheet/table/journal panels | **Done** | `server/ai/agent.py`, `app/session_ws.py` |
| **Phase 5: Campaign Continuity** | SQLite campaign persistence (`campaign-<id>.db`), recap export, log rewind/undo, Konva maps, multi-PC & AI player companion agent | **Done** | `server/state/campaign_store.py`, `test_agent.py` |
| **Phase 6: Rulebook Ingestion** | PDF/markdown text extraction, LLM module draft extraction, review & private storage (`server/data/modules`), module prose retrieval index | **Done** | `server/ingestion/`, `web/src/components/ingestion/` |
| **Gap Alignment Pass 1** | Score/downtime GM tools, score entity wiring, crew interactive sheet, assist maneuver, crafting quality, end-of-session XP triggers, character import, CC-BY credits UI | **Done** | `server/ai/tools.py`, `server/engine/operations.py` |
| **Gap Alignment Pass 2** | Ingestion UI, multi-PC UI, companion chat/decision rendering, licensing grep fixes, API drift checks | **Done** | `web/src/components/ingestion/`, `server/cli/licensing_grep.py` |
| **Gap Alignment Pass 3** | Player Safety Tools (FR-17: X-Card WS message, `XCardDialog`, Lines & Veils rendering), Roll Negotiation Decline Path & Offered Bargains (FR-16), Referential Integrity (`create_npc` faction validation) | **Done** | `server/app/session_ws.py`, `web/src/components/play/x-card-dialog.tsx` |

---

## 3. Test Harness & Verification Guide

The codebase uses a strict, zero-suppression test harness enforced by a single root Makefile entry point.

### Verification Commands (`Makefile`)
```bash
# Run all lints, unit tests, OpenAPI drift checks, and licensing checks
make check

# Launch the local hot-reloading development environment (FastAPI + Vite)
make dev

# Interactive dev harness for driving engine sessions headlessly
make dev-session

# Guided character sheet creator (outputs to server/data/characters/)
make guided-entry

# Re-build the SRD FTS5 search index from source SRD text
make index-srd
```

### Component Test Suites
1. **Backend Tests (`server/`)**:
   - Framework: `pytest` executed via `uv run pytest`. Total 508 tests passing.
   - Convention: Every engine test cites the specific SRD passage it encodes (NFR-2), e.g., `# SRD: "Action Roll": 6 = full success`.
2. **Frontend Tests (`web/`)**:
   - Framework: `vitest` executed via `pnpm test` (or `pnpm test:ui`).
   - Covers UI components, form validation, map layout math (`map-layout`), relationship graphs (`relationship-graph`), and socket message parsing (`use-session-socket`).
3. **OpenAPI TypeScript Contract Guard**:
   - Schema generation: `uv run python -m app.export_openapi > openapi.json` then `pnpm run generate:api` in `web/`.
   - Drift validation: `pnpm run check:api-drift` fails if frontend TypeScript types diverge from backend Pydantic models.
4. **Licensing Firewall Audit (`licensing-grep`)**:
   - CLI Tool: `uv run python -m cli licensing-grep`.
   - Purpose: Scans tracked files to prevent committing forbidden core-book content (setting lore, named NPCs, core-book art) per `NOTICE.md` and constraints C3/C4. Allowlist in `server/cli/licensing_grep.py` includes documentation files (`NOTICE.md`, `CLAUDE.md`, `TODO.md`, `HANDOFF.md`, etc.).

---

## 4. Audited Gaps & Prioritized Backlog

The following backlog items were audited against `SPECIFICATION.md` and `TODO.md`. They represent remaining open items for future development passes.

### Priority 1: Engine Mechanics Parity
- **Dead Engine Mechanics**: Wire unreachable SRD engine functions into GM tools, sheet operations, and replay cases:
  - *Trauma conditions*: Record chosen condition on stress overflow (`mark_trauma`).
  - *Armor track*: Spending and restoring armor (`ArmorTrack.use_armor`/`restored`).
  - *Stash & Profit*: Character/crew stash mutations and downtime profit share.
  - *Crew development*: Tier/Hold advancement (`develop_crew`) and turf acquisition (`add_turf`).
  - *Load level caps*: Storing and enforcing light/normal/heavy load limits.

### Priority 2: Data Integrity & Governance
- **Faction Canon Growth (FR-14, FR-15)**: Implement `CampaignCanon.with_faction`, `add_canon_faction` tool, replay fold case, and automated faction clock enumeration during downtime transitions.
- **Campaign Export/Import (NFR-5)**: Endpoint `GET /api/campaigns/{id}/export` (JSONL + snapshots) and `POST /api/campaigns/import` are fully built and tested in `server/app/campaigns.py`. Web UI download/upload controls remain to be wired in.

### Priority 3: UI Parity & Polish
- **Official Sheet Parity (G2, FR-28)**: Expand `CharacterSheetPanel` to display and edit all twelve action ratings, trauma, armor, special abilities, vice, contacts, heritage/background, and healing clocks.
- **Sheet Export (FR-8)**: Expose JSON and Markdown export controls in the web UI for characters and crews.
- **Journal Filter Buckets (FR-32)**: Update `journal-summarize.ts` to categorize `xp_marked`, `coin_adjusted`, `item_carried_set`, and `companion_roll_decision` into appropriate filter buckets.

### Priority 4: Ingestion & Operations
- **Module Lifecycle (FR-23, FR-24)**: Add `DELETE /api/ingestion/modules/{id}` with FTS index chunk cleanup, atomic file writes (`os.replace`), and re-indexing guards on module update.
- **Ingestion Robustness**: Implement file size limits for upload endpoints, return clean 4xx errors for encrypted/malformed PDFs, and flag empty text extractions in UI.
- **Module Content Integration (FR-9)**: Wire structured module templates (playbooks, crew types, items) into campaign creation.
- **Container & Headed Visual Verification**: Test Konva canvas views in a headed browser, and verify `make build` / `docker compose up` on a Docker host.

---

## 5. Licensing Firewall & Policy Reminder

- **Forbidden Content (C3/C4)**: NEVER commit Doskvol setting details, named core-book NPCs, assembled playbooks/crew sheets, or PDF sheet files from bladesinthedark.com.
- **Allowed Content**: SRD text (CC-BY 3.0), code, and original/session-zero generated fixture content (`packs/example_base.json`).
- **Private Modules (C6)**: Local users may ingest core-book PDFs for private, local play (`server/data/modules/`). Licensing grep guards distribution, not private user data.
