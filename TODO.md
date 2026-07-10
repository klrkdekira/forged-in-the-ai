# TODO

Phased plan for [SPECIFICATION.md](SPECIFICATION.md). Requirement IDs (FR-x, C-x, D-x)
refer to that document. Each phase should end in something playable/testable.

## Phase 0: Foundations

- [x] Decide language & tooling (D1): Python/FastAPI and React/TS, see
      `docs/adr/0002-tech-stack.md`
- [x] Decide LLM interface (D2): OpenAI-compatible API (Ollama/vLLM/hosted),
      see `docs/adr/0001-openai-compatible-llm-api.md`
- [x] Monorepo skeleton per ADR-0002: `server/` (uv, FastAPI, ruff, pytest),
      `web/` (pnpm, Vite, React, vitest), `packs/`; a root Makefile is the
      single entry point for lint, tests, drift check, licensing grep, and
      the image build (no hosted CI; if CI is ever added it runs the same
      Makefile targets)
- [x] Multi-stage `Dockerfile` at root: web build stage, then Python runtime
      stage; FastAPI serves the built SPA from a single image (NFR-7, ADR-0004)
- [x] `compose.yml` at root: one-command run with user-data volume; `dev`
      profile with uvicorn --reload and the Vite dev server; optional Ollama
      profile (NFR-7, ADR-0004)
- [x] Schema contract: generate TS types from server OpenAPI/JSON Schema
      (openapi-typescript plus openapi-fetch client); the drift-check script
      and the image build fail on drift
- [x] Server foundations: FastAPI and pydantic-settings; SQLite via
      SQLAlchemy 2 async and Alembic, WAL mode, on the user-data volume
      (ADR-0005)
- [x] Web foundations: TanStack Router (file-based) and Query, React Hook Form
      with Zod resolvers, Tailwind v4 and shadcn/ui init (ADR-0006)
- [x] LLM client abstraction: base URL and model config, streaming,
      tool-calling capability probe, structured-output fallback for weak
      tool-callers (NFR-6)
- [x] SRD fetch script: download the SRD from its official source to the
      repo root (gitignored), for dev setup; document in README (C1)
- [x] Extract a machine-usable rules reference from the SRD: section index
      plus the key tables (position/effect, heat, entanglements, magnitude,
      downtime activities) as structured data (D3 groundwork). All done in
      `packs/srd_base.json` (`make extract-srd`): special abilities, items,
      traumas, vices, reputations, crew upgrades, position/effect, heat,
      entanglements, magnitude, downtime activities, and a full heading
      index of the source SRD.
- [x] Define content-pack format and licensing firewall (C3/C4): schema and
      loader contract, documented "what may never be committed" policy
      (`ContentPack` in `server/engine/packs.py`; `load_pack`/`load_packs_dir`
      in `server/engine/pack_loader.py`, which also refuses forbidden content
      at runtime; documented in `packs/README.md`)
- [x] CONTRIBUTING.md note on the content policy. UI credits path (C1) is
      deferred: no distributed UI exists yet to carry NOTICE.md attribution
      (Phase 4 web play UI); re-check this once one does

## Phase 1: Rules engine core (no AI)

- [x] Dice: d6 pools, take-highest, crits, 0d, seeded RNG (FR-2, NFR-1)
      (`engine/dice.py`)
- [x] Action roll with position/effect matrix and outcome bands (FR-1)
      (`engine/rolls.py`; position/effect are GM-supplied inputs, a
      critical bumps effect per the SRD's position tables)
- [x] Resistance and armor, stress, trauma, harm levels, healing clock
      (FR-1, FR-2) (`engine/rolls.py` resistance roll; `engine/consequences.py`
      for stress/trauma/harm/armor tracks)
- [x] Fortune roll and its uses (quality, magnitude, NPC toughness) (FR-1)
      (`engine/rolls.py`; the mechanic is trait-agnostic, so quality/
      magnitude/toughness are just whatever pool size the caller supplies)
- [x] Progress clocks: all SRD flavours, tick-by-consequence (FR-3)
      (`engine/clocks.py`; flavours are a `ClockKind` label on one generic
      tickable Clock, consequence severity maps to the tick amount)
- [x] Event log: append-only, entity-tagged structured events, replay to
      state (FR-19, FR-31, NFR-1) (`engine/events.py`; `engine/replay.py`
      demonstrates replay-to-state for clocks - the concrete entity this
      phase has; later phases add their own replay functions)
- [x] JSONL export/import round-trip with test; this is the NFR-5 portability
      contract (ADR-0005) (`EventLog.to_jsonl`/`from_jsonl`)
- [x] Engine test suite where each test cites the SRD passage it encodes (NFR-2)

## Phase 2: Characters, crew, and world state

- [ ] Character sheet JSON schema, field-for-field with the official sheet (FR-7)
- [ ] Crew sheet schema: tier, hold, rep, heat/wanted, claims, upgrades,
      cohorts (FR-7)
- [ ] Faction, NPC, Location, Item, Score entities (§5)
- [ ] Relationship edges as data of their own with event-referenced history;
      faction status (-3 to +3) as a typed edge (FR-33)
- [ ] Sheet mutations as engine operations only (FR-10)
- [ ] JSON import/export plus markdown sheet render (FR-8)
- [ ] SRD base content pack: extract the special-ability bank (full rules
      text), item rules, and reputation lists from the SRD into committed
      pack data (FR-9, C3a)
- [ ] Example fixture pack (one playbook, one crew type) proving the pack
      format without core-book content; no shipped setting, settings are
      session-zero generated (FR-9, FR-36, C4)
- [ ] Guided sheet entry flow for owners of the book: build a private playbook
      assembly (starting dots, ability references into the SRD bank, friends,
      items) in minutes (FR-8, D6)

## Phase 3: Score & campaign loop (still no AI)

- [ ] Engagement roll and score phase state machine (FR-4)
- [ ] Flashbacks with stress costs (FR-4)
- [ ] Payoff, heat, wanted level, entanglement tables (FR-4)
- [ ] Downtime activities: recover, reduce heat, long-term project, acquire
      asset, train, indulge vice with overindulgence (FR-1, FR-4)
- [ ] XP triggers and advancement, character and crew (FR-5)
- [ ] Faction clocks and NPC downtime progression (FR-14 engine side)
- [ ] Scriptable "headless session" test: run a full score loop from a fixture

## Phase 4: AI referee MVP (single player, web client)

- [ ] GM agent system prompt from SRD GM guidance: goals, actions, principles (FR-11)
- [ ] Tool surface for the agent: rolls, clocks, harm, entities,
      relationships, phase transitions (FR-12, FR-33)
- [ ] Distilled GM procedure docs (always in-prompt), citing the SRD sections
      they compress (FR-13, ADR-0003, NFR-2)
- [ ] SRD retrieval index: SQLite FTS5 (BM25) over SRD chunks (FR-13,
      ADR-0003, ADR-0005)
- [ ] Canon injection: structured world-state context assembly under the
      explicit per-turn budget sized for the 64k floor; procedures, canon,
      retrieval, and summarised transcript sections (FR-15, NFR-4)
- [ ] Session zero flow: lines and veils, tone; X-card command; original
      setting generation interview persisted as campaign canon (FR-17, FR-36)
- [ ] Controller model: one human seat controls any number of PCs/cohorts;
      solo play is the whole crew under one seat (FR-25)
- [ ] Session WebSocket channel: server-authoritative state deltas from the
      event log, single-player first (FR-30)
- [ ] Web play UI: chat with streaming narration (NFR-3) and a roll
      negotiation dialog; pool/position/effect shown, push/assist/devil's
      bargain/trade-off offered before rolling (FR-16)
- [ ] Interactive sheet panel: stress/harm/XP/load/coin ticks via engine
      operations only (FR-28)
- [ ] Table view v1: active clocks and crew claim map (FR-29)
- [ ] Journal view v1: chronological turn log with expandable roll audit
      records (FR-31, FR-32)
- [ ] Dev CLI harness for headless engine sessions (kept from Phases 1–3)
- [ ] Playtest: one full solo session (free play, score, downtime)

## Phase 5: Persistence & campaign continuity

- [ ] Campaign save/load from event log and snapshots (FR-18, FR-19, NFR-5)
- [ ] Structured recap generation on resume (FR-18)
- [ ] Session recap export (FR-20)
- [ ] Undo/rewind via event log truncation (FR-19, supports FR-17)
- [ ] Table view v2: generated district/score maps (FR-29); pick canvas
      library (Pixi vs. Konva, D4 leftover) and record an ADR
- [ ] Journal view v2: filters by type, phase, and entity (FR-32)
- [ ] Relationship map view: entity graph with edge drill-down into the
      linked journal entries, showing what transpired between them (FR-34)
- [ ] AI player agent v1: an AI-controlled crewmate PC, distinct from the GM
      agent; action choices, stress spends, roleplay (FR-35)
- [ ] Playtest: multi-session campaign, verify canon consistency (G3)

## Phase 6: Rulebook ingestion (bring your own book)

Primary target: third-party FitD books with no SRD (D6). BitD itself is served
by the committed SRD base pack plus guided entry from Phase 2.

- [ ] Upload and text extraction: PDF/markdown/plain text to normalised text (FR-21)
- [ ] LLM-assisted extraction into content-pack schemas: playbooks, crew
      types, items, factions, tables (FR-22)
- [ ] Review/edit step before a module activates in a campaign (FR-22)
- [ ] Private-module storage in user data dir; excluded from repo, exports,
      and sharing by default (FR-23, C6)
- [ ] Module prose joins the GM retrieval corpus alongside the SRD (FR-24)
- [ ] Acceptance test: ingest a rulebook and play a session using its content

## Phase 7: Multiplayer

- [ ] Decide transport (D5); record an ADR
- [ ] Seats: N human controllers in one session, mixed with AI PCs (FR-25,
      FR-35)
- [ ] Spotlight management by the GM agent (FR-26)
- [ ] Client/server split over the core API (FR-27)
- [ ] Playtest with 2+ humans

## Phase 8: Beyond Blades

- [ ] Second content pack (another FitD hack or homebrew) to prove G5
- [ ] Community pack authoring docs
- [ ] Revisit distribution/licensing checklist (C1–C5) before any public release

## Conventions

- Work happens on branches; each phase lands as reviewable PRs
- No hosted CI: verification is `make check` and `make build`; CI, if ever
  added, runs the same Makefile targets
- The repo is public GitHub; every commit is distribution, so the licensing
  policy (NOTICE.md) applies to every push
- ADRs in `docs/adr/NNNN-title.md` for decisions D1–D6 and anything comparable
- No core-book content in commits, fixtures, or test data; SRD text only (C3)
