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
