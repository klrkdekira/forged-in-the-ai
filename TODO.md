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
- [x] `compose.yml` at root: one-command run with user-data volume (NFR-7,
      ADR-0004). Hot-reload dev is `make dev` (uvicorn --reload plus the
      Vite dev server, no Docker) rather than a compose `dev` profile;
      ADR-0004 describes a Docker-based option too, not yet built. No
      Ollama profile yet either.
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

- [x] Character sheet JSON schema, field-for-field with the official sheet
      (FR-7) (`engine/character.py`)
- [x] Crew sheet schema: tier, hold, rep, heat/wanted, claims, upgrades,
      cohorts (FR-7) (`engine/crew.py`, `engine/crew_mechanics.py`)
- [x] Faction, NPC, Location, Item, Score entities (§5) (`engine/entities.py`)
- [x] Relationship edges as data of their own with event-referenced history;
      faction status (-3 to +3) as a typed edge (FR-33) (`engine/relationships.py`)
- [x] Sheet mutations as engine operations only (FR-10) (`engine/operations.py`;
      a representative set - stress/trauma/harm/heat/development - not yet
      the exhaustive tool surface, which is Phase 4's FR-12)
- [x] JSON import/export plus markdown sheet render (FR-8) (Pydantic
      model_dump_json/model_validate_json; `render_markdown` in
      `engine/character.py` and `engine/crew.py`)
- [x] SRD base content pack: extract the special-ability bank (full rules
      text), item rules, and reputation lists from the SRD into committed
      pack data (FR-9, C3a) (done in Phase 0; `packs/srd_base.json`)
- [x] Example fixture pack (one playbook, one crew type) proving the pack
      format without core-book content; no shipped setting, settings are
      session-zero generated (FR-9, FR-36, C4) (`packs/example_base.json`,
      `make build-example-pack`)
- [x] Guided sheet entry flow for owners of the book: build a private playbook
      assembly (starting dots, ability references into the SRD bank, friends,
      items) in minutes (FR-8, D6) (`make guided-entry`; saves to
      `server/data/characters/`, gitignored, never committed)

## Phase 3: Score & campaign loop (still no AI)

- [x] Engagement roll and score phase state machine (FR-4) (`engine/score.py`
      engagement_roll; `engine/session.py` Session/CampaignPhase, the
      free_play -> score -> downtime -> free_play cycle)
- [x] Flashbacks with stress costs (FR-4) (`engine/operations.py` flashback,
      a thin documented wrapper over mark_stress; the coin/rep downtime
      variant spends those directly, no separate operation needed)
- [x] Payoff, heat, wanted level, entanglement tables (FR-4) (`engine/score.py`
      payoff_rep, entanglement_roll; heat/wanted level from Phase 2's
      `engine/crew_mechanics.py` HeatTrack)
- [x] Downtime activities: recover, reduce heat, long-term project, acquire
      asset, train, indulge vice with overindulgence (FR-1, FR-4)
      (`engine/downtime.py` acquire_asset_roll/indulge_vice_roll;
      `engine/score.py` downtime_ticks shared by recover/reduce-heat/
      long-term-project; train is XpTrack.mark from Phase 2)
- [x] XP triggers and advancement, character and crew (FR-5)
      (`engine/advancement.py`; trigger *detection* from play is Phase 4/AI
      judgement, this is the advance mechanic itself plus the desperate-roll
      xp rule)
- [x] Faction clocks and NPC downtime progression (FR-14 engine side)
      (ordinary `Clock`s referenced by `Faction.clock_ids`, ticked and
      replayed like any other clock; see test_faction_clocks.py)
- [x] Scriptable "headless session" test: run a full score loop from a fixture
      (test_headless_session.py: plan/engagement/action/consequence/payoff/
      heat/entanglement/downtime, logged and replayed deterministically)

## Phase 4: AI referee MVP (single player, web client)

- [x] GM agent system prompt from SRD GM guidance: goals, actions, principles
      (FR-11) (`ai/system_prompt.py`; the SRD has no "Running the Game"
      chapter of its own to draw from, C3a - the role framing compresses
      the actual sections it does have, "The Game Master"/"Judgment calls")
- [x] Tool surface for the agent: rolls, clocks, harm, entities,
      relationships, phase transitions (FR-12, FR-33) (`ai/tools.py`
      ToolExecutor: roll_action/fortune/resistance, create/tick_clock,
      apply_harm, mark_stress, transition_phase, create_npc,
      update_faction_status - a representative set, not the final
      exhaustive surface)
- [x] Distilled GM procedure docs (always in-prompt), citing the SRD sections
      they compress (FR-13, ADR-0003, NFR-2) (`ai/procedures.py`; citations
      are checked against the committed SRD section index in tests, so
      drift is caught, not just asserted)
- [x] SRD retrieval index: SQLite FTS5 (BM25) over SRD chunks (FR-13,
      ADR-0003, ADR-0005) (`state/srd_index.py`; the FTS5 virtual table is
      an Alembic migration since it's app.db schema, even though it isn't
      a normal SQLAlchemy-mapped table; `make index-srd` builds it from
      the local SRD copy)
- [x] Canon injection: structured world-state context assembly under the
      explicit per-turn budget sized for the 64k floor; procedures, canon,
      retrieval, and summarised transcript sections (FR-15, NFR-4)
      (`ai/context.py` assemble_turn_context, budget from ADR-0003;
      `ai/canon.py` render_canon builds sections from a GameState, reusing
      Phase 2's markdown renderers)
- [x] Session zero flow: lines and veils, tone; X-card command; original
      setting generation interview persisted as campaign canon (FR-17, FR-36)
      (`engine/campaign.py` SessionZeroConfig/CampaignCanon - neither is
      SRD content, they're generic tabletop safety tools; `add_canon_fact`/
      `invoke_x_card` tools in `ai/tools.py`. The AI-run interview itself
      needs a live model, so isn't testable headlessly - the schema and
      tools it would use are)
- [x] Controller model: one human seat controls any number of PCs/cohorts;
      solo play is the whole crew under one seat (FR-25) (`engine/controller.py`
      Controller/solo_controller; ai/tools.py's single-`character` GameState
      is still the MVP simplification - wiring multiple PCs through the
      tool surface is additive follow-up work, not done here)
- [x] Session WebSocket channel: server-authoritative state deltas from the
      event log, single-player first (FR-30) (`app/session_ws.py`,
      `/ws/session`; verified end to end against the user's real vLLM
      backend, not just mocked)
- [x] Web play UI: chat with streaming narration (NFR-3) and a roll
      negotiation dialog; pool/position/effect shown, push/assist/devil's
      bargain/trade-off offered before rolling (FR-16). Chat with real
      streaming narration is done (`/play`, `ai/agent.py`'s GmAgent) and
      playtest-verified live, with markdown rendering of narration
      (`react-markdown` in `chat-message-view.tsx`). The negotiation dialog
      (`RollNegotiationDialog`) pauses the GM agent's tool-calling loop on
      a `roll_action` proposal - `GmAgent.handle_player_message` yields a
      `roll_proposed` event and resumes via `asend()` once the player
      submits push/Devil's Bargain/trade-off choices (`ai/agent.py`'s
      `_resolve_roll`, `engine/rolls.py`'s `step_position`); verified live
      against the user's real vLLM backend end to end (proposal shown,
      decision applied, roll executed with the right bonus dice/position/
      effect). Assistance is not wired in: the tool surface's GameState is
      still single-PC (FR-25's MVP simplification), so there's no second
      character to take the stress and grant it.
- [x] Interactive sheet panel: stress/harm/XP/load/coin ticks via engine
      operations only (FR-28) (`CharacterSheetPanel`, shown as a side panel
      inside `/play` rather than a separate route - the GameState it
      reflects only exists for the active WS connection's lifetime, no
      persisted/addressable session to share across pages yet, Phase 5's
      job; `/sheet` now links there instead of a placeholder). Adds
      `mark_xp`/`adjust_coin`/`set_item_carried`/`heal_character` engine
      operations (`engine/operations.py`) plus a `SHEET_OPERATIONS`
      registry in `ai/tools.py`, deliberately separate from `TOOL_SPECS`:
      the UI calls these directly over a new `sheet_operation` WS message
      (`app/session_ws.py`), bypassing the GM agent/LLM entirely per
      CLAUDE.md's "the UI acts through engine-operation endpoints".
      Verified live: stress/harm/coin/XP clicks all round-tripped through
      the real WS connection with no console errors. Crew-sheet
      interactivity (heat/rep/coin) isn't wired in - left for Table view
      v1, which owns crew claims/clocks already.
- [x] Table view v1: active clocks and crew claim map (FR-29) (`TableViewPanel`,
      a Sheet/Table tab alongside the character sheet in `/play`'s side
      panel, same reasoning as FR-28 for not being a separate route).
      Clocks are clickable tick boxes (shares `TickBoxes` with the sheet
      panel's stress/XP), reusing `tick_clock` - added to `SHEET_OPERATIONS`
      alongside `mark_stress`/`apply_harm` since it was already a
      `TOOL_SPECS` entry the GM agent calls. Fixed a latent gap this
      exposed: `tick_clock` indexed `state.clocks` directly, so ticking an
      unknown clock id raised a raw `KeyError` instead of a typed
      `EngineError` the WS handler's error path catches; now refuses
      explicitly, matching `set_item_carried`'s pattern. Claims are a
      plain read-only list for v1 - nothing mutates them at runtime yet
      (set at crew creation/guided entry), so there's no operation to
      wire up. The crew's claim map imagery itself (district/score maps)
      is v2 (TODO.md already scopes that separately, canvas library
      still to be picked). Verified live: creating a clock via chat then
      ticking it from the table view round-tripped correctly with no
      console errors.
- [ ] Journal view v1: chronological turn log with expandable roll audit
      records (FR-31, FR-32)
- [x] Dev CLI harness for headless engine sessions (kept from Phases 1–3)
      (`make dev-session`, `server/cli/session.py`: an interactive loop
      over the same ToolExecutor the GM agent uses, `<tool> <json args>`;
      load/create a character and crew, saves the session log as JSONL)
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
