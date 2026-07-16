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
      stage; FastAPI serves the built SPA from a single image (NFR-7, ADR-0004).
      (Phase 6 realignment: the COPY list had never grown past Phase 0's
      `app`/`engine`/`state`, so the image stopped building the moment
      `app/` first imported `ai/` (Phase 4) and nobody ran `make build`
      again to notice; `server/ai`, `server/ingestion`, and
      `server/alembic_campaign` (campaign dbs migrate on open) are now
      copied too. Verified by exporting OpenAPI from a tree containing
      only the copied directories, not by a real `docker compose build` -
      no container runtime on the dev machine this round.)
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
      `invoke_x_card` tools in `ai/tools.py`. Originally shipped as schema
      and tools only - the AI-run interview itself needing a live model
      to actually conduct was flagged as untestable headlessly, and
      nothing ever created canon in the first place: `GameState.canon`
      stayed `None` for every campaign, silently, until Table view v2
      work went looking for setting data to render and found none. Closed
      in Phase 5 (below): `set_session_zero_config`/`set_campaign_canon`
      tools, a `SESSION_ZERO_PROCEDURE` conditionally in the system
      prompt while canon/session_zero aren't set yet, `ai/canon.py`
      rendering both into context once they are, and `ai/replay.py` fold
      cases so undo/rewind doesn't drop them. The mechanism itself (does
      the model see the procedure, does calling the tools update state,
      does the procedure disappear afterwards) is fully tested headlessly
      with a mocked LLM transport, same as every other tool
      (`test_agent.py`); only the quality of a live interview
      conversation needs a real model, not verified this round.)
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
- [x] Journal view v1: chronological turn log with expandable roll audit
      records (FR-31, FR-32) (`JournalPanel`, a third Journal tab alongside
      Sheet/Table in `/play`'s side panel; same reasoning as FR-28/FR-29
      for not being a separate route). No server changes needed - the
      event log was already broadcast in full on every `state` message
      (FR-19's "fully reconstructible from the event log" already made
      this a client-only feature). Each entry gets a one-line
      human-readable summary (`summarize()`'s per-event-type lookup, with
      a generic fallback) and expands via a native `<details>` to its full
      payload - dice/position/effect for rolls, whatever fields any other
      event carries. Filtering by type/phase/entity is v2. Verified live:
      marking stress from the sheet panel produced a correctly summarized,
      expandable journal entry with no console errors.
- [x] Dev CLI harness for headless engine sessions (kept from Phases 1–3)
      (`make dev-session`, `server/cli/session.py`: an interactive loop
      over the same ToolExecutor the GM agent uses, `<tool> <json args>`;
      load/create a character and crew, saves the session log as JSONL)
- [ ] Playtest: one full solo session (free play, score, downtime)

## Phase 5: Persistence & campaign continuity

- [x] Campaign save/load from event log and snapshots (FR-18, FR-19, NFR-5)
      (`state/campaign_store.py`: `save_state`/`load_state` against a
      per-campaign `campaign-<id>.db`, own Alembic lineage in
      `alembic_campaign/` separate from app.db's - `events` (the log,
      kept for future audit/undo) and a single-row `snapshots` cache, per
      ADR-0005. `app/campaigns.py` adds `GET`/`POST /api/campaigns`
      (app.db's `CampaignIndex` directory) so a campaign exists before any
      WS connection can reach it. `app/session_ws.py`'s route is now
      `/ws/session/{campaign_id}`; a `get_campaign_db_path` dependency
      refuses unknown ids before accept, same pattern as the existing
      `get_llm_client` check. State is always persisted before the client
      is told about a mutation, not after - otherwise a client
      disconnecting the instant it sees an update can race ahead of the
      write. Web: `/play/$campaignId` (was `/play`), a campaign
      picker/creator wired up on `/` (the dead buttons FR-18 had left
      there), and a `useLastCampaignId` localStorage hook so sidebar nav
      still resolves without a global "current campaign" store. Verified
      live against a real uvicorn process, not just TestClient: create,
      reconnect, and unknown-campaign rejection all round-trip correctly.)
- [x] Structured recap generation on resume (FR-18) (found and fixed a
      correctness gap along the way: FR-31 requires GM narration and
      player input to be structured events too, but `GmAgent` only ever
      held them in an in-memory `_transcript` list on the agent instance
      - never persisted, and dropped on every reconnect, so the Journal
      view never showed chat and a resumed campaign had no memory of its
      own narration. `ToolExecutor.log_event` (`ai/tools.py`) lets the
      agent log `player_message`/`narration` events the same way tool
      calls already do; `ai/transcript.py`'s `render_transcript` derives
      the context-assembly transcript from `state.log` instead of the
      old `_transcript` field, which is now gone. Since a resumed
      campaign's `GameState` (loaded from its snapshot) carries the same
      log a live one does, `assemble_turn_context` already assembles the
      "recap" as a side effect - no separate recap-building step needed,
      just a durable source for the transcript it always budgeted for
      (`ai/context.py`'s `_fit_transcript` docstring had flagged this as
      pending since Phase 4). `journal-panel.tsx`'s `summarize()` gained
      the two new event types. Covered by two new tests in
      `test_agent.py`: one asserting the events land in the log, one
      spanning two separate `GmAgent` instances (standing in for a
      reconnect) to prove the second's LLM request actually contains the
      first's transcript. Not verified live against a real LLM backend
      this round, only via mocked-transport tests - flagging that
      explicitly since every other Phase 4/5 entry above did get a live
      check.)
- [x] Session recap export (FR-20) (`ai/recap.py`'s `render_recap`: "the
      story so far" as markdown, built from the same `player_message`/
      `narration` events FR-18's resume recap already relies on - deliberately
      just the narrated story, not a mechanical audit dump (the Journal
      view/FR-31 already covers that in full detail). `GET
      /api/campaigns/{campaign_id}/recap` (`app/campaigns.py`) serves it
      as a download (`Content-Disposition: attachment`), 404s for an
      unknown campaign. Web: an "Export recap" link in the Journal
      panel's header - a plain `<a download>` straight at the endpoint,
      no JS fetch/blob handling needed. Verified live against a real
      uvicorn process: correct headers, content, and 404.)
- [x] Undo/rewind via event log truncation (FR-19, supports FR-17) (this
      is the first time state is actually *reconstructed by replay*
      rather than mutated incrementally - `ai/replay.py`'s `replay_state`
      folds every state-mutating event type back onto a base `GameState`,
      reusing the exact same `engine/operations.py` functions
      `ToolExecutor` calls live, so replay and live play can never
      disagree about what an event means (NFR-1). Pure-record event types
      (rolls, `player_message`/`narration`, `x_card_invoked`) are skipped -
      nothing to fold. `state/campaign_store.py`: campaign creation now
      writes the starting snapshot twice - once as an immutable "base"
      row (id 0, replay's fold-from point, never overwritten) and once as
      the existing "latest" cache (id 1); `undo_to(db_path, sequence)`
      deletes every `events` row past `sequence` (irreversible - no
      redo), replays the survivors onto the base, and overwrites the
      latest snapshot. `app/session_ws.py` gets a new `undo` WS message,
      handled the same way `sheet_operation` already is (FR-28: bypasses
      the GM agent entirely, an engine operation like any other) - a
      dedicated `undo_done` reply (not the generic `state` message) lets
      the client rebuild the visible chat transcript from the rewound log
      too, not just the mechanical state. Web: an "Undo to here" control
      on every Journal entry, behind a confirm() given how destructive
      truncation is. Verified live against a real uvicorn process: mark
      stress, adjust coin, undo to just after the stress mark - coin
      reverts, stress doesn't.)
- [x] Table view v2: generated district/score maps (FR-29). Canvas library:
      Konva.js via `react-konva` (ADR-0007). Decided against storing
      positions/adjacency at all (the "remaining scope" the ADR and the
      session-zero entry above flagged): `CampaignCanon.locations` stays
      a flat `list[str]` and `ClaimSnapshot` is unchanged - inventing
      pixel coordinates is an odd thing to ask an LLM to generate
      reliably, and §3's non-goals rule out a measured grid anyway, so a
      *computed* layout is both simpler and more honest about what this
      is (a fiction aid, not a geography). `lib/map-layout.ts`'s
      `layoutInRing` (pure, unit-tested) spaces however many
      locations/claims exist evenly around a circle; no connecting lines,
      since there's no adjacency data to draw them from.
      `district-map.tsx`/`claim-map.tsx` render that as Konva nodes -
      claims distinguish controlled (filled) from contested (outline),
      turf gets a second ring - alongside the existing precise text
      list, not replacing it. "Score map" specifically (highlighting a
      score's target location) is out of scope: nothing tracks a score's
      target location at all yet. Not visually verified live - no headed
      browser available in this environment - only via `tsc`/`vite
      build` succeeding and the layout math's own tests; a real visual
      check is worth doing before calling this done-done. The map's
      other half - growing as new areas are discovered, not just at
      session zero (FR-15) - was a real gap: `add_canon_fact` existed
      for free-text facts but nothing added a structured *location*
      after the initial `set_campaign_canon` call.
      `CampaignCanon.with_location` (`engine/campaign.py`) plus an
      `add_canon_location` tool (`ai/tools.py`, same shape as
      `add_canon_fact`) close it, with a replay fold case and a
      `GM role` procedure nudge to call it (and `create_npc`/
      `add_canon_fact`) instead of just narrating new things into
      existence. No web change needed: `DistrictMap` already re-renders
      from `canon.locations` on every state update, so a newly-added
      location shows up automatically.
- [x] Journal view v2: filters by type, phase, and entity (FR-32)
      (`journal-panel.tsx`, client-only - the full log was already
      broadcast, so no server change needed. Type buckets event_types
      into FR-32's named groups (narration/rolls/consequences/downtime);
      "downtime" is reserved but always empty since no downtime GM tool
      is wired up yet (Phase 4 notes), and an "other" bucket not in the
      spec's four names holds everything that doesn't fit rather than
      silently hiding it (npc/canon/phase/safety-tool entries). Phase
      isn't carried on each entry - `phaseAtEachSequence` derives it by
      walking the log in order and tracking `phase_transitioned` events,
      tagging the transition's own row with the phase it entered. Entity
      filters on the existing `entity_type` field directly. Covered by
      `journal-panel.test.tsx` (5 tests: unfiltered render, each filter
      dimension, and the undo confirm still works alongside the new
      filters) rather than a live check, since this is presentation logic
      over data the server already sends.)
- [x] Relationship map view: entity graph with edge drill-down into the
      linked journal entries, showing what transpired between them (FR-34)
      (found the same shape of gap as the canon/session-zero one: FR-33
      names an `update_relationship` tool in its own spec text, but only
      `update_faction_status` - the special-cased crew-to-faction edge -
      was ever built; the generic `Relationship` model
      (`engine/relationships.py`, ally/rival/debt/romance/vendetta between
      any two entities) had no field on `GameState` and no tool at all.
      Closed first: `GameState.relationships` (keyed by
      `"<subject_type>:<subject_id>:<object_type>:<object_id>"`),
      `Relationship.updated()` (kind/status/history, same shape as
      `FactionStatus.changed`), an `update_relationship` tool, a replay
      fold case, and a "Relationships" canon section. Then the view
      itself: `lib/relationship-graph.ts`'s `buildRelationshipGraph`
      (pure, unit-tested) merges `FactionStatus` edges and generic
      `Relationship` edges into one node/edge set; `relationship-map.tsx`
      renders it with Konva - character/crew fixed near centre, every
      other entity in a computed ring (`lib/map-layout.ts`, same as the
      district/claim maps), edges as `Line`s between whichever two node
      positions they connect. Selecting a node shows its label; selecting
      an edge shows its journal history (`history: list[int]` sequence
      numbers matched against the log, reusing `journal-panel.tsx`'s
      `summarize()` - pulled out to `lib/journal-summarize.ts` so both
      files could share it without an oxlint fast-refresh warning). A
      fourth "Ties" tab alongside Sheet/Table/Journal in `/play`'s side
      panel. Not visually verified live, same caveat as the other Konva
      maps - no headed browser available in this environment.)
- [x] AI player agent v1: an AI-controlled crewmate PC, distinct from the GM
      agent; action choices, stress spends, roleplay (FR-35). FR-35 is
      explicitly "future phase" in SPECIFICATION.md's own text, and once
      traced turned out to need a real prerequisite `GameState` never
      had: more than one PC. That foundation went in first - `character`
      (singular) is `characters: dict[str, Character]`, keyed by a
      caller-supplied `character_id` (same convention as `clocks`/
      `npcs`), with a `create_character` tool (mirrors `create_npc`) and
      every PC-mutating tool (`mark_stress`, `apply_harm`, `roll_action`,
      `mark_xp`, `adjust_coin`, `set_item_carried`, `heal_character`,
      `roll_resistance`) taking an optional `character_id` - required
      once a session has more than one PC, refusing rather than guessing
      which one an ambiguous call means (CLAUDE.md). Every existing call
      site (dozens of tests, `app/campaigns.py`'s campaign creation,
      `cli/session.py`'s dev harness) keeps constructing
      `GameState(character=..., ...)` unchanged - a `model_validator`
      wraps it into `characters={"pc-1": ...}`, and a `@computed_field`
      `character` property (the first/primary PC) keeps `ai/canon.py`/
      `ai/recap.py`'s headers and the web client's existing single-PC
      display working with zero further changes, verified live against
      a real uvicorn process. `ai/replay.py` folds `character_created`
      and multi-character mutations correctly (by `character_id`, not
      by name - a small pre-existing inconsistency fixed along the way:
      character-tagged events used to log `character.name` as
      `entity_id` where clocks/npcs always used a caller-supplied id.
      `roll_fortune` was the one leftover, still logging the primary
      PC's name; the realignment pass moved it to `("session",
      "current")`, since the mechanic is trait-agnostic and belongs to
      no character).

      This round closed the remaining three pieces, server-side only (web
      UI - a character switcher, visually distinguishing an AI companion's
      messages - stays deferred, same reasoning as FR-33/34's UI polish).
      `Controller`/seat wiring: `engine/controller.py`'s `Controller`
      (already existed for FR-25) gained a `kind: "human" | "ai"` field
      (default "human", so a character with no seat at all is still
      human-controlled - unassigned never silently means AI) and an
      `is_ai_controlled` lookup; `GameState.controllers: dict[seat_id,
      Controller]` only needs entries for the exceptions. `create_character`
      now takes `controller_kind` (default "ai", since a crewmate the GM
      introduces mid-campaign is the companion case FR-35 is about) and
      registers a seat for it in the same call, folded by `ai/replay.py`
      from `character_created`'s payload so undo/rewind never drops which
      seat a companion belongs to (older-shaped payloads without
      `controller_kind` default to "human", so pre-existing campaigns
      replay unchanged). The AI player agent itself: `ai/player_agent.py`'s
      `PlayerAgent` - a second LLM loop, distinct from `GmAgent`, with its
      own system prompt scoped to one character's own voice. Two jobs, both
      wired into `ai/agent.py`'s `GmAgent.handle_player_message`: when a
      proposed roll's character is AI-controlled, `decide_roll` (a
      structured completion against `RollDecision`, NFR-6) replaces the
      roll-negotiation dialog (FR-16) a human would otherwise answer over
      WS, so the tool-calling loop never pauses for a reply that would
      never come (a `companion_roll_decision` event reports what it chose,
      same audit-trail spirit as `roll_proposed`); after each turn's
      narration, `maybe_roleplay` gives every AI-controlled companion a
      chance to add a short in-character line (defaults to staying quiet
      - most turns don't call for one), logged as a `player_message` event
      tagged with a `speaker` override so it joins the transcript under
      the companion's own name, not "Player" (`ai/transcript.py`'s
      `render_transcript` falls back to the old unconditional "Player"/"GM"
      labels when `speaker` is absent, so every existing log entry renders
      unchanged). Turn-taking/spotlight between controllers (FR-26) stays
      out of scope until multiplayer (Phase 7) - a companion only ever
      acts in response to the GM's own tool calls or narration, never
      competing for the floor. Found and fixed a latent multi-PC gap while
      wiring the roll path: `GmAgent`'s pool-size lookup and
      `_resolve_roll`'s `mark_stress`/re-rolled `RollActionArgs` never
      threaded a proposal's `character_id` through at all, so any push/
      trade-off on a second PC's roll would have marked stress on (or
      outright ambiguity-refused against) the wrong character - dormant
      until this round because nothing had exercised a roll for a
      non-primary PC before. Covered by
      `test_player_agent.py` (`PlayerAgent` unit tests) and new
      `test_agent.py`/`test_controller.py`/`test_ai_replay.py`/
      `test_tools.py` cases (mocked-LLM-transport style, same as every
      other agent test) - not verified live against a real model this
      round, flagging that explicitly per this project's convention of
      calling that out when it hasn't happened.

      (Realignment pass, same day: three uncaught-exception paths in
      `GmAgent.handle_player_message` could kill the WS connection - the
      exact failure mode the Phase 4 `httpx.HTTPError` guard was added
      for. A `roll_action` proposal with bad or ambiguous arguments
      (e.g. no `character_id` with two PCs, newly reachable now that
      multi-PC exists) raised out of the special-cased roll branch
      instead of going back to the model as a tool error the way
      `_run_tool` does for every other tool; and both new `PlayerAgent`
      LLM calls (`decide_roll`, `maybe_roleplay`) were unguarded against
      `httpx.HTTPError`/`StructuredOutputError`. All three now degrade:
      the roll error is fed back to the model to retry, a failed
      companion decision falls back to rolling as proposed (no stress,
      no bargain), a failed roleplay call stays quiet. Two new
      `test_agent.py` regressions cover them.

      Also from the realignment pass: the "deferred web UI" stance had
      an actively misleading edge, not just a missing feature - the
      client's WS switch silently dropped `companion_message`, so a
      companion's line was invisible live, and `messagesFromLog`'s
      post-undo rebuild ignored `speaker`, relabelling companion lines
      as if the human typed them. Fixed minimally: a `companion` chat
      kind rendered under the character's own name, live and on rebuild
      (`use-session-socket.ts`, `chat-message-view.tsx`, covered by
      `use-session-socket.test.ts`). The rest - character switcher,
      companion sheet view, surfacing `companion_roll_decision` - stays
      deferred as before.)
- [ ] Playtest: multi-session campaign, verify canon consistency (G3)

## Phase 6: Rulebook ingestion (bring your own book)

Primary target: third-party FitD books with no SRD (D6). BitD itself is served
by the committed SRD base pack plus guided entry from Phase 2.

- [x] Upload and text extraction: PDF/markdown/plain text to normalised text
      (FR-21) (`ingestion/text_extraction.py`'s `extract_text`: dispatches
      on file extension - `pypdf` for `.pdf`, straight UTF-8 decode for
      `.md`/`.markdown`/`.txt` - then normalises (NFKC, `\r\n`/`\r` to
      `\n`, strips control characters and trailing whitespace, collapses
      3+ blank lines to one). Refuses any other extension
      (`UnsupportedFormatError`) rather than guessing at a format
      (CLAUDE.md). `POST /api/ingestion/extract-text` (`app/ingestion.py`)
      wraps it as a multipart upload endpoint (needed adding
      `python-multipart`, FastAPI's file-upload parser dependency, plus
      `pypdf` itself) - returns the extracted text and its length in the
      response rather than persisting anything: FR-22's LLM-assisted
      structuring and FR-23's private-module storage are their own later
      steps, this one's job stops at "clean text out of whatever was
      uploaded". No web page calls it yet, same reasoning as this phase's
      later steps not existing either - there's nothing to review/store/
      retrieve against until FR-22/23 land. Covered by
      `test_text_extraction.py` (the pure function, including a stubbed
      `PdfReader` rather than a crafted PDF binary fixture - pypdf's
      writer isn't a practical way to author real text content) and
      `test_ingestion_api.py` (the endpoint, success and the unsupported-
      extension 400). Verified `pnpm build` still succeeds against the
      regenerated OpenAPI-derived TS schema (ADR-0006's drift check) -
      the endpoint's request/response shapes aren't consumed by any
      component yet, so there's nothing else to verify live.
- [x] LLM-assisted extraction into content-pack schemas: playbooks, crew
      types, items, factions, tables (FR-22) (`ingestion/module_extraction.py`'s
      `extract_module_draft`: one structured completion (NFR-6) over
      FR-21's normalised text into a `ModuleDraft` - reuses FR-9's actual
      content-pack shapes (`PlaybookTemplate`, `CrewTypeTemplate`, `Item`,
      `SpecialAbility` from `engine/packs.py`) rather than inventing
      parallel ones, plus two new lightweight shapes for what FR-22 names
      but `ContentPack` doesn't yet model: `FactionSeed` (id/name/
      description/tier_hint - deliberately lighter than the live
      `engine.entities.Faction`, which carries clocks/assets/hold a GM
      only fills in during play) and `ExtractedTable` (free-form name/
      columns/rows, since a third-party hack's own tables won't
      necessarily match the SRD-shaped ones `ContentPack` already has -
      heat/entanglement/magnitude/etc). The system prompt is explicit
      that this is best-effort and must not invent content beyond what's
      in the text (FR-22's own "extraction is best-effort; the user is
      the final validator"). Truncates the input to a 40k-token budget
      before sending (`_fit_text`, reusing `ai/context.py`'s
      `estimate_tokens` rather than a second estimator) and reports
      whether it had to, so a later step knows an incomplete draft might
      just be a length problem, not the model's own extraction quality.
      `POST /api/ingestion/extract-module` (`app/ingestion.py`) wraps it,
      taking already-extracted text (from `/extract-text`) rather than a
      re-upload, so the two pipeline steps stay independently callable.
      Refactored `app/session_ws.py`'s `get_llm_client` dependency along
      the way: it used to raise `WebSocketException` directly, which
      would have been the wrong error type reused verbatim in this new
      HTTP-only router, so the actual "read settings, build an
      `LLMClient` or return None if unconfigured" logic moved to a shared
      `app/llm.py::build_llm_client`, and each router keeps its own
      transport-appropriate dependency wrapping it (`WebSocketException`
      for the WS route, `HTTPException(503)` here) (ADR-0001). Draft
      output is returned to the caller, not persisted or activated
      anywhere - review/edit and private storage are their own, still
      separate, next steps. Covered by `test_module_extraction.py`
      (`_fit_text`, and `extract_module_draft` against a mocked LLM
      transport, both the parsed-draft and truncation-reported paths)
      and `test_ingestion_api.py` (the endpoint, success and the 503 when
      no LLM backend is configured) - not verified live against a real
      model, flagging that explicitly per this project's convention.

      Also: the user attached a real BitD core rulebook PDF at the repo
      root for local testing. It was untracked but not yet gitignored -
      `.gitignore` gained a `*.pdf` rule (NOTICE.md's licensing firewall,
      C3/C4: the core rulebook is copyrighted, unlike the CC-BY SRD,
      and must never be committed) covering this file and any future
      full-book PDF a user drops there for the same reason.
- [x] Review/edit step before a module activates in a campaign (FR-22)
      (`ingestion/module_review.py`'s `finalize_module`: assembles a
      reviewed/edited `ModuleDraft` plus user-supplied pack metadata
      (id/name/description/version - a draft has no id of its own, since
      naming the module is the user's call, not the extraction step's)
      into a real `ContentPack` (FR-9). "Review/edit" and "the engine may
      refuse; it never guesses" (CLAUDE.md) come from the same mechanism:
      an edited draft that no longer matches `ModuleDraft`'s schema is
      refused by pydantic before `finalize_module` ever runs - there's no
      separate validation step to build, the schema boundary already is the
      validator FR-22 asks for ("the user is the final validator").
      `ContentPack` gained the two fields `ModuleDraft` already had that
      it didn't (`factions: list[FactionSeed]`, `tables:
      list[ExtractedTable]`, moved from ingestion-only into
      `engine/packs.py` since they're now genuinely part of the
      content-pack schema, not just this pipeline's intermediate shape).
      Originally this step also re-applied the licensing firewall,
      refusing a draft containing core-book terms - the realignment pass
      reversed that as a decided policy call: it contradicted NOTICE.md's
      own "owners may load their own copies of core-book content locally
      as private content packs" (C6), and would have refused the exact
      use case Phase 6 exists for (ingesting a core book the user owns).
      The firewall guards *distribution* surfaces - licensing-grep over
      every commit, and `load_pack`'s check for the committed `packs/`
      directory - not private user data: `finalize_module` doesn't check,
      and `state/module_store.py` loads with `load_pack(...,
      private=True)`. `POST /api/ingestion/finalize-module`
      (`app/ingestion.py`) wraps it - takes the (edited) draft plus pack
      metadata, returns the assembled `ContentPack`. Not persisted or
      associated with any campaign: FR-23's private-module storage is
      still the next, separate step. Covered by `test_module_review.py`
      (assembly, reflecting an edit made to the draft before finalizing,
      and core-book terms being allowed in a private module - drawing
      the term from `FORBIDDEN_TERMS[0]` rather than hardcoding it, same
      as `test_pack_loader.py`'s existing test, so the test file itself
      doesn't trip licensing-grep) and `test_ingestion_api.py` (the
      endpoint: success, the schema-validation 422, and the private
      save/list/get round trip of a module carrying core-book terms).
- [x] Private-module storage in user data dir; excluded from repo, exports,
      and sharing by default (FR-23, C6) (`state/module_store.py`:
      `save_module`/`load_module`/`list_modules` against a `modules/`
      subdirectory of the user's own data directory (ADR-0005) - a
      separate root from the committed `packs/` from the start, not a
      filter applied to it later, and covered by the existing
      `server/data/`-style gitignore the same way `app.db`/campaign `.db`
      files already are, no new ignore rule needed. Reuses
      `engine.pack_loader.load_pack`/`load_packs_dir` for the read side
      with `private=True`, so a saved module gets the same schema
      validation as any other pack file, but not the licensing-firewall
      refusal - a private module may carry core-book content the user
      owns (NOTICE.md, C6; the decided policy from the realignment pass:
      the firewall guards distribution, not user data). `pack_id` (`FinalizeModuleRequest.id`/`ContentPack.id`
      upstream) flows straight from an HTTP request body into a filename,
      so it's validated as a safe path component (`ModuleIdError`: no
      empty string, `.`/`..`, or path separators) before it ever reaches
      the filesystem - a real path-traversal surface, not a theoretical
      one, given where the id comes from. `POST /api/ingestion/modules`
      (`app/ingestion.py`) saves (typically re-posting `/finalize-module`'s
      own response once the user is happy with it) and echoes the pack
      back; `GET /api/ingestion/modules` lists summaries (id/name/
      description/version only - `ModuleSummary`, same reasoning as
      `CampaignSummary` already listing summaries rather than full
      campaign state); `GET /api/ingestion/modules/{id}` fetches one in
      full, 404 for an unknown id. "Excluded from campaign exports" needed
      no code change to verify: FR-20's recap export
      (`ai/recap.py::render_recap`) only ever reads `player_message`/
      `narration` events, nothing pack-shaped, so there was never a path
      for private-module content to leak into an export in the first
      place. Covered by `test_module_store.py` (save/load/list
      round-tripping, and the unsafe-id refusal, parametrised over `""`,
      `"."`, `".."`, `"../escape"`, and both path separators) and
      `test_ingestion_api.py` (all three endpoints, plus the unsafe-id
      400 through the actual HTTP body path, not just the storage
      function directly).
- [x] Module prose joins the GM retrieval corpus alongside the SRD (FR-24).
      Traced this one further than expected: `state/srd_index.py`'s SRD
      retrieval (Phase 4's FTS5/BM25 index) had `search_srd` fully built
      and tested in isolation, but `ai/agent.py`'s `GmAgent` always
      called `assemble_turn_context(..., retrieved=[], ...)` - the live
      GM loop never actually queried it, every turn, since Phase 4. A
      corpus nothing ever reads doesn't become more useful by adding
      module content to it, so closing FR-24 properly meant fixing that
      gap first, then adding modules on top of a retrieval path that
      actually runs.

      Schema: `srd_chunks` (the FTS5 virtual table) gained a `source`
      column (`"srd"` or `"module:<pack_id>"`) - a new Alembic migration
      (`875bd2cd871d`), not an `ALTER TABLE ADD COLUMN`, since this
      SQLite build refuses to alter FTS5 virtual tables at all ("virtual
      tables may not be altered"); safe to drop-and-recreate since the
      table is a derived cache (`make index-srd`/saving a module
      repopulates it), never a source of truth. `index_srd_chunks`
      (SRD-only) and the new `index_module_chunks` (one module's own
      chunks) each replace only their own `source`'s rows, so re-running
      either never drops the other's content or another module's -
      `search_srd` itself needed no change at all: one BM25 query over
      the whole table already ranks every source together, which is the
      actual "joins the corpus" part of FR-24, not two separately-scored
      result sets glued together after the fact. `chunk_module_prose`
      groups paragraphs up to a size cap with a synthetic heading,
      instead of `chunk_srd`'s heading-based splitting - an arbitrary
      uploaded book's normalised text (FR-21) has no reliable markdown
      heading structure once it's out of a PDF. `build_match_query`
      turns free text (a player's own message) into a safe FTS5 MATCH
      expression by quoting and OR-joining word tokens, sidestepping
      FTS5's query syntax entirely rather than trying to escape every
      special character free text might contain.

      Live wiring: `GmAgent` takes an optional `retrieval_sessions`
      (an `async_sessionmaker` against app.db, where the SRD/module index
      lives - a separate file from the campaign's own db, ADR-0005) and
      queries it with the player's message every turn, degrading to no
      retrieval (not a crashed turn) if none is configured or the query
      matches nothing. `app/session_ws.py` constructs one per WS
      connection, disposed alongside the LLM client. `ai/context.py`'s
      retrieval rendering now tags a module hit's heading with its
      module id (`"(from module my-hack)"`) so the GM doesn't cite a
      third-party hack's best-effort text as if it were the SRD itself
      (NFR-2's citation habit is specifically about the SRD).

      Ingestion side: `POST /api/ingestion/modules` gained an optional
      `source_text` field (the module's FR-21 normalised text) - when
      given, it's chunked and indexed right away via
      `index_module_chunks`, so a finalized-and-saved module is
      immediately part of what the GM can retrieve, no separate
      "publish"/"activate" step. Not stored as its own file: the FTS5
      index *is* the durable, chunked representation of that prose for
      retrieval purposes, so keeping a second raw-text copy in
      `modules/` would just be redundant storage for no further use
      anything makes of it yet.

      Verified live: `make index-srd` against the real local SRD copy
      runs the new migration cleanly (275 chunks, all tagged
      `source='srd'`) - first in a scratch data dir, then re-verified by
      the realignment pass against the real dev `server/data/app.db`
      (the migration drops and recreates the FTS table, so any existing
      app.db has an empty index until `make index-srd` re-runs; done
      here). Covered by `test_srd_index.py` (chunking,
      `build_match_query`, and the cross-source ranked
      search/non-interference tests), `test_context.py` (the module-hit
      labelling), `test_agent.py` (retrieval actually reaching the
      prompt, and the no-session-factory default staying a no-op), and
      `test_ingestion_api.py` (source_text indexing through the real
      HTTP save path).

      Container deployments (realignment decision): the image has no
      local SRD copy and no dev CLI, so its retrieval corpus would have
      been silently empty forever. `state/srd_bootstrap.py`'s
      `ensure_srd_indexed` fetches the SRD (CC-BY) from its official
      source and indexes it at startup when app.db has no SRD chunks -
      gated behind `SRD_AUTOINDEX` (default off: dev uses `make
      index-srd`, tests never touch the network), set to 1 in the
      image's runtime stage. A failed download degrades to no retrieval
      and retries next start; a populated index makes it a no-op.
      Covered by `test_srd_bootstrap.py` (indexes when empty, skips when
      populated, degrades offline).
- [ ] Acceptance test: ingest a rulebook and play a session using its content

## Gap backlog (alignment audit, 2026-07-16)

Findings from auditing SPECIFICATION.md against the code, ordered by how much
play each one blocks. Each item is scoped to hand to an implementing agent:
read the named files and the cited spec sections before starting, and follow
the existing patterns they establish (tools wrap engine functions, every new
event type gets a replay fold case in `ai/replay.py`, engine tests cite the
SRD). The unchecked playtest and acceptance items inside Phases 4 to 6 above
stay open as well; most of them are blocked on items here.

- [x] **GM score and downtime tool surface (FR-4, FR-5, FR-12, FR-14).**
      `ai/tools.py` gained fourteen tools wrapping the existing engine
      functions (same pattern as `roll_action` - no new engine code needed
      beyond what Phase 3 already built and tested): `roll_engagement`,
      `resolve_payoff`, `add_crew_heat`, `roll_entanglement`,
      `acquire_asset`, `indulge_vice`, `reduce_heat`, `recover`,
      `long_term_project`, `flashback`, `advance_action_rating`,
      `advance_special_ability`, `advance_crew_special_ability`,
      `advance_crew_upgrades`, plus `mark_xp` (previously `SHEET_OPERATIONS`
      only) is now also in `TOOL_SPECS` for the TRAIN activity - the GM can
      mark a companion's xp during a narrated downtime scene, same as a
      human player clicking their own sheet. `recover`/`reduce_heat`/
      `long_term_project` share the SRD's "roll your action, downtime_ticks
      picks the amount" shape - each logs its own `downtime_activity_rolled`
      record, then chains into `tick_clock`/`add_crew_heat` (reusing those
      tools' own methods and events rather than duplicating the mutation).
      `recover` auto-heals one harm level when its tick fills the clock,
      per the SRD.

      Every new event type got a replay fold case (`ai/replay.py`) -
      most reuse the engine functions directly (`add_heat`,
      `advance_action_rating`, etc., same as the rest of replay.py), except
      `action_advanced`, which now logs its `cap` alongside `new_rating` so
      replay doesn't have to guess the cap a live call used (unlike other
      folded events, `advance_action_rating`'s cap is caller-supplied, not
      derivable from state). A `DOWNTIME_ACTIVITIES_PROCEDURE` doc
      (`ai/procedures.py`) cites the SRD's "DOWNTIME ACTIVITIES SUMMARY"
      section and its per-activity subsections, checked against the
      committed SRD section index by the existing drift test
      (`test_procedures.py`); `SCORE_LOOP_PROCEDURE` now names the actual
      tool to call at each step instead of only describing the mechanic.
      `journal-summarize.ts` and `journal-panel.tsx` gained summaries and a
      populated "downtime" filter bucket (previously permanently empty,
      FR-32) for every new event type.

      `roll_entanglement` needed the SRD base pack's entanglement table at
      runtime, which surfaced a real gap once traced: nothing loaded
      `packs/srd_base.json` at play time at all (the ingestion/retrieval
      pipeline reads SRD *prose* into the FTS5 index, never the pack's
      *structured* tables), and the Dockerfile never copied `packs/` into
      the image in the first place (the same shape of gap Phase 0's COPY
      fix closed for `server/ai`/`server/ingestion`/`server/alembic_campaign`,
      just never hit until now because nothing needed pack data at runtime
      before). Closed with `ToolExecutor(entanglements=...)` - an injected
      dependency, same reasoning as `rng`/`clock` - loaded via a new
      `app/packs.py::load_entanglements`, degrading to an empty list (and a
      clear refusal from `roll_entanglement` itself) rather than crashing
      the WS connection if the pack is missing or malformed, same shape as
      `GmAgent._retrieve`'s no-session-factory no-op. A new
      `Settings.packs_dir` (default `"../packs"`, dev's cwd is `server/`)
      points at it; the Dockerfile now `COPY packs ./packs` and sets
      `PACKS_DIR=/app/packs` (its layout is flattened, no `server/`
      nesting, so the default relative path doesn't resolve there) -
      verified live: `load_entanglements` against the real dev settings
      returns all 9 committed entries. `cli/session.py`'s dev harness wires
      the same loader in.

      Acceptance: `test_agent_runs_a_full_score_and_downtime_loop_through_tools`
      (`test_agent.py`) drives plan, engagement, action (paused for the
      player's push/trade-off decision, FR-16), payoff, heat, entanglement,
      and one of each downtime activity end to end through the GM agent's
      tool-calling loop across four turns, mirroring what
      `test_headless_session.py` proves engine-side - not verified live
      against a real model this round, flagging that explicitly per this
      project's convention. Also covered: per-tool unit tests
      (`test_tools.py`), replay fold-case tests (`test_ai_replay.py`), and
      a `journal-panel.test.tsx` case proving the downtime filter bucket
      now actually filters something.
- [x] **Score entity wiring (spec section 5, FR-4, FR-29).**
      `GameState.scores: dict[str, Score]` (`ai/tools.py`), keyed like
      `clocks`/`npcs`, plus two new tools: `create_score` (target and plan,
      called once the crew commits to a job) and `update_score` (records
      whichever of engagement result/payoff/heat gained/entanglement the
      caller supplies - only the fields actually passed are applied, so
      resolving a score across several turns doesn't clobber earlier
      results with nulls). Kept as its own explicit pair of tools rather
      than folding into `roll_engagement`/`resolve_payoff`/`add_crew_heat`/
      `roll_entanglement` above: `add_crew_heat` in particular is also
      called by `reduce_heat` during downtime, so threading an implicit
      "update the active score" side effect through it would have updated
      a score's heat from an unrelated downtime roll. `SCORE_LOOP_PROCEDURE`
      (`ai/procedures.py`) now names `create_score`/`update_score` at the
      right points in the loop, same pattern as the rest of that doc.
      Replay fold cases for `score_created`/`score_updated`
      (`ai/replay.py`, the update case is a plain `model_copy` over the
      partial payload, mirroring the tool's own partial-update logic) and
      an "Active score" canon section (`ai/canon.py`, priority 1 alongside
      clocks/NPCs/faction status - supplementary state, not core identity
      like the character/crew sections). Covered by new cases in
      `test_tools.py` (creation, partial updates accumulating across two
      calls, refusing an unknown score id), `test_ai_replay.py`, and
      `test_canon.py`.

      Still open, not attempted here: the Table view's score map (FR-29)
      needs a *location* to highlight, and `Score.target` is free prose
      (e.g. "The Silver Vault") with no guaranteed link to a
      `CampaignCanon.locations` entry - closing that needs either a
      structured target-location field or a matching convention, which is
      its own design question, not a mechanical follow-on to this item.
- [x] **Crew mutations and an interactive crew sheet (FR-12, FR-28).**
      Three new engine operations (`engine/operations.py`):
      `adjust_wanted_level` (direct +/-, clamped to the SRD's [0, 4] - a new
      `MAX_WANTED_LEVEL` constant in `engine/crew_mechanics.py`, replacing
      `add_heat`'s previous hardcoded `4`), `adjust_crew_rep` (delegates to
      the existing `RepTrack.add_rep`, which already clamps to the
      turf-reduced threshold), and `adjust_crew_coin` (mirrors the
      character-side `adjust_coin`: refuses rather than letting the crew
      spend coin it doesn't have). `RepTrack.threshold` gained
      `@computed_field` (it was a plain `@property` before, so it never
      serialized) purely so the web rep tick-boxes know their segment
      count without a duplicated copy of the turf formula in TypeScript.

      GM tools (`ai/tools.py`, `TOOL_SPECS`): `adjust_wanted_level`,
      `adjust_crew_rep`, `adjust_crew_coin`, each logging its own
      `wanted_level_adjusted`/`crew_rep_adjusted`/`crew_coin_adjusted`
      event, folded by `ai/replay.py`. Also added to `SHEET_OPERATIONS`
      (FR-28) alongside the pre-existing `add_crew_heat`, which had a GM
      tool already but, per this item's own gap description, was never
      reachable from the sheet panel either - all four are now on both
      surfaces, same shared-method shape as `mark_stress`/`tick_clock`.

      Web: `TableViewPanel` (`table-view-panel.tsx`) gained a crew-stats
      block - heat and wanted level as `TickBoxes` (segments 9 and 4),
      rep as a `TickBoxes` sized to the crew's own threshold, coin as
      +/- buttons matching the character sheet's - immediately after the
      crew name/type header, above the pre-existing setting/clocks/claims
      sections. `CrewSnapshot`/`SheetOperation` (`use-session-socket.ts`)
      typed the new fields and operation names. Covered by new
      `test_operations.py`/`test_tools.py`/`test_ai_replay.py` cases citing
      the SRD sections they encode ("Heat & Wanted Level", "Development",
      "Coin and Stash"); `pnpm build`/`tsc -b` succeeds. Not verified live
      in a headed browser - no headed browser is available in this
      environment, same caveat as the Konva views below.
- [ ] **Assist and teamwork (FR-1, FR-2, FR-16).** No assist, setup, group
      action, or protect mechanics exist anywhere: `engine/rolls.py` has no
      teamwork code and `RollDecision` (`ai/tools.py`) offers only push,
      Devil's Bargain, and the position/effect trade. The old blocker (a
      single-PC `GameState`) is gone since FR-35 landed
      `GameState.characters`. Engine first (SRD "Teamwork", with cited
      tests), then extend `RollDecision` with an assist option (the helper
      takes 1 stress, the roller gains 1d), then offer it in the roll
      negotiation dialog and in `PlayerAgent.decide_roll`.
- [ ] **Crafting (FR-1).** No crafting code at all (SRD "Crafting": the
      tinker long-term project, the quality level formula, inventing). At
      minimum encode the quality formula and a craft downtime path with
      SRD-cited tests; the generic long-term-project clock already covers
      project progress.
- [ ] **End-of-session XP triggers (FR-5).** The advance mechanic exists
      (`engine/advancement.py`) but nothing detects XP triggers from play or
      runs the SRD's end-of-session procedure. Depends on the tool-surface
      item above; add an end-of-session procedure prompt plus a tool for
      marking trigger XP that logs the reason.
- [ ] **Character import at campaign creation (FR-8, G2).**
      `app/campaigns.py` hardcodes a fixed starter character and crew (an
      FR-30/FR-36 MVP simplification), so neither loading a JSON sheet nor
      the guided-entry output (Phase 2, saved under `server/data/characters/`)
      can actually enter a web campaign. Extend campaign creation to accept a
      character (and crew) payload validated against the engine schemas, and
      give the campaign picker an import step that uploads a JSON sheet or
      selects a saved guided-entry file.
- [ ] **CC-BY attribution in the UI (C1).** SPECIFICATION.md requires the
      NOTICE.md attribution text in any distributed UI's credits, and the
      Docker image now distributes the SPA, but no route or component renders
      any attribution. Add a small credits surface (for example a sidebar
      footer link opening a dialog) carrying the CC-BY attribution text
      verbatim from NOTICE.md, then close the deferral note in
      CONTRIBUTING.md and the Phase 0 entry above.
- [ ] **Ingestion web UI (FR-21, FR-22, FR-23).** The ingestion pipeline is
      API only (`app/ingestion.py`); no client page calls it, so FR-22's
      "user review and edit before the module activates" has no user surface.
      This blocks Phase 6's acceptance test. Add an ingestion route: upload
      (extract-text), draft extraction (extract-module), an editable review
      form (Zod for form UX only per ADR-0006, the server schema stays the
      validator), then finalize and save with `source_text` so the module
      joins the retrieval corpus.
- [ ] **Multi-PC UI (FR-25, FR-35).** Deferred from Phase 5: a character
      switcher in `/play`, sheet views for companions (the sheet panel shows
      only the primary PC), and surfacing `companion_roll_decision` events in
      chat rather than only via the Journal's generic fallback.
- [ ] **Visual verification of the Konva views (FR-29, FR-34).** The district
      map, claim map, and relationship map have never been seen rendered (no
      headed browser was available when they were built); only the layout
      maths is unit tested. Run the app in a headed browser, verify all three
      views, and fix whatever that surfaces.
- [ ] **Container build and run verification (NFR-7).** `make build` and
      `docker compose up` have not been executed on a machine with a
      container runtime since the Dockerfile COPY fix (Phase 0 note). Verify
      the image builds, serves the SPA, autoindexes the SRD
      (`SRD_AUTOINDEX=1`), and keeps campaign data across container
      replacement on the named volume.
- [ ] **Compose dev and Ollama profiles (ADR-0004).** Described in the ADR as
      options and never built; `make dev` covers hot reload without Docker
      today. Either build the profiles or amend ADR-0004 to record the
      Makefile path as the supported dev loop.

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
