# Project Handoff and Audit

Last audited: 2026-08-04

## 1. Audit scope and conclusion

This audit compared the current repository with `SPECIFICATION.md`, `TODO.md`,
the accepted ADRs, the engine and API contracts, the web client, persistence,
ingestion, content packs, and the test harness. Existing completion claims were
treated as hypotheses and checked against reachable play paths, replay, storage,
and UI behaviour.

The project has a substantial, coherent implementation and broad automated
coverage. It is not yet a faithful end-to-end implementation of the stated
scope. The highest-risk gaps are rules integrity in the client, incomplete
engine enforcement of the score and downtime procedures, a broken repeated
healing path, and content packs that cannot seed campaigns. Several older TODO
items have been implemented but were left unchecked, so the historical backlog
is not a reliable status view without this document.

Current assessment:

| Area | Assessment | Main evidence |
| :--- | :--- | :--- |
| Engine primitives | Strong but incomplete | Dice, rolls, clocks, harm, advancement, score helpers, and typed errors exist |
| Complete procedures | Partial | Phase transitions and downtime allowances are enforced, but score ordering and completion state remain open |
| Event sourcing | Broad coverage with operational risks | Replay covers current mutation events; WS and test resource lifecycle still need work |
| AI referee | Broad MVP | Retrieval, tool use, fallback, negotiation, safety, and companions are wired |
| Web client | Functional but contains one critical architecture violation | A client-side dice roller bypasses the engine and log |
| Content packs and ingestion | Extraction, private storage, and committed starter-pack activation work | Private module template selection and broader faction/table activation remain |
| Packaging | Build definition exists | Production web build passes; container build and run remain unverified |

## 2. Verification result

The following checks were run during this audit:

- Backend lint: passed.
- Backend tests: 532 passed in 11.36 seconds when run outside the filesystem
  sandbox. The suite emitted no aiosqlite worker-thread warnings.
- Frontend tests: 40 passed across 12 files.
- Frontend production build: passed.
- Frontend lint: passed.
- OpenAPI drift check: passed.
- Licensing grep: passed.
- `git diff --check`: passed before documentation edits.

The first backend runs inside the restricted sandbox stalled on aiosqlite. An
unsandboxed run completed, confirming that particular stall was environmental.
The previous aiosqlite teardown warnings were eliminated by closing short-lived
SQLite connections with `NullPool`.

`make check` could not be executed as one uninterrupted command because the
host did not initially have the repository-pinned pnpm available through
Corepack. Its constituent checks were run directly after Corepack fetched the
pinned pnpm version.

## 3. Prioritised open gaps

### Priority 0: restore the rules integrity boundary

- [x] **Remove or engine-route the client-side dice roller (G4, FR-2, FR-6,
  FR-10, FR-12).** The standalone client roll control and random result path
  are removed. Dice animation now renders only an engine-supplied result.

### Priority 1: complete deterministic procedure enforcement

- [x] **Make the engine enforce the score and downtime loop (FR-1, FR-4,
  FR-10, FR-12).** Downtime activity allowances are now phase-scoped,
  event-replayed, and typed-refusal guarded: each PC gets two free activities,
  later activities require coin or rep, and each training track is once per
  downtime. Score tools now require score/downtime phases, prevent repeated
  engagement, payoff, and entanglement, and require payoff before entanglement.
  Score-phase action rolls now require that engagement has completed and action
  rolls are refused during downtime. Entering downtime requires an action, and
  entanglement requires payoff and processed heat. Snapshot and event-log
  round-trip coverage now includes the procedure state.
  The prompt must not be the rules boundary.

- [x] **Repair repeated recovery and make healing a character-owned track
  (FR-1, FR-7).** `Character.healing_clock` is now the canonical four-segment
  track. `recover` ticks it directly, resets it after healing one harm level,
  refuses a full-clock tick through the existing typed clock error, and logs
  both progress and reset events for deterministic replay. The old arbitrary
  global healing-clock argument has been removed.

- [ ] **Finish sheet-domain parity (G2, FR-7, FR-28).** The character model and
  panel now cover far more than the older audit recorded. The character schema
  now includes its healing clock and enforces four-coin capacity. The crew
  model now represents vault level and enforces 4/8/16 coin capacity. Stash
  conversion is now atomic and sheet-exposed, but the full crew UI remains
  open. The crew table now displays tier, hold, stash, and crew XP. Upgrade,
  cohort, and special-ability presentation plus controller assignment remain
  open. Reconcile the schema with the specification before adding more code.

- [x] **Repair the live WebSocket snapshot contract (FR-28, FR-30,
  ADR-0006).** The hand-written client types do not match `GameState` JSON.
  The client mappings now follow the serialised session phase, armour field
  names, and derived trauma shape, with a server serialisation regression test.
  Trauma overflow now sets an explicit `trauma_pending` snapshot flag, and the
  picker uses it rather than the reset stress value. A reproducible schema
  exporter is available as `make snapshot-schema`, and a browser-level
  CharacterSheet fixture covers trauma pending, armour, and healing fields.

- [ ] **Bind every controllable entity to a controller (FR-25, FR-26).** The
  runtime binds created characters, but cohorts are not wired through creation,
  tools, or UI controller assignment, and vehicles have no represented control
  path. Spotlight management is also not implemented. Keep simultaneous human
  play in Phase 7, but make the single-player state conform to the controller
  invariant now.

### Priority 2: make content and persistence operationally complete

- [x] **Activate committed starter content packs in campaigns (G5, FR-9).**
  `POST /api/campaigns` now accepts `pack_id`, `playbook_id`, and
  `crew_type_id`; it resolves the pack by its declared id, validates it through
  the licensing-aware loader, and seeds the starting character and crew from
  the selected templates. Imported sheets still take precedence. Private module
  template selection and activation of factions/tables remain open follow-up
  work under FR-21/FR-22.

- [x] **Make private-module updates atomic and index-consistent (FR-23,
  FR-24).** Module writes use a flushed temporary file plus `os.replace`.
  Re-saving with omitted or empty source text clears old chunks, and failed
  indexing or deletion restores the previous file. Tests cover updates, empty
  prose, and both failure paths.

- [x] **Complete entity referential integrity (FR-12, FR-15).** `create_npc`
  now refuses unknown faction IDs and records the NPC in the faction's notable
  NPC list. Replay folds that relationship as well. Tests cover live refusal,
  live linking, and event-log reconstruction.

- [ ] **Improve campaign connection semantics (FR-18, FR-30).** A per-campaign
  lock prevents two WebSockets from corrupting one campaign, but it is held for
  the full connection. A second accepted connection waits without receiving its
  initial state until the first disconnects. This is safe for mutation but poor
  protocol behaviour and cannot become multiplayer fan-out. Refuse the second
  connection explicitly for the single-player phase, or introduce a shared
  campaign session and subscriber broadcast model.

- [x] **Complete portability and sheet exports in the client (FR-8, NFR-5).**
  Campaign bundle import/export and independent character and crew JSON and
  Markdown downloads are available in the web controls.

### Priority 3: correctness, quality, and operational hardening

- [x] **Close asynchronous database resources cleanly.** SQLite engines now use
  `NullPool`, so each short-lived operation closes its aiosqlite connection
  before the WebSocket or test event loop can shut down. The full backend suite
  passes without worker-thread teardown warnings.

- [x] **Fix the frontend lint finding.** The result-only dice animation has no
  random generation effect, and frontend lint now passes cleanly.

- [x] **Finish ingestion error reporting (FR-22).** The web client now
  preserves the server's typed `detail` for extraction, draft generation, and
  module-save failures, with a fallback only for unknown error shapes.

- [ ] **Broaden the licensing firewall carefully (C3, C4).** Matching is now
  case-insensitive and committed packs are checked narrowly for assembled core
  playbook and crew-type names. The automated check still has no coverage for
  named core-book NPCs, maps, art, or official sheet PDFs beyond two setting
  spellings and the pack assembly check. Add filename, binary-extension, and
  narrowly verified name or structure rules without blocking legitimate SRD
  text or ordinary English fixture names.

- [ ] **Type WebSocket client messages.** The server accepts untyped
  dictionaries and can silently ignore unknown message types. Add Pydantic
  message envelopes and explicit protocol errors. Snapshot response drift is a
  separate Priority 1 defect above.

- [ ] **Correct stale documentation and status counts.** `TODO.md` contains
  historical prose that describes now-implemented gaps as open and test counts
  that no longer match the suite. Keep historical analysis if useful, but mark
  completed items and use this audit section as the active backlog.

- [ ] **Complete headed and container verification (FR-29, FR-34, NFR-7).** Run
  the Konva maps in a headed browser, exercise resize and interaction paths,
  then run `make build` and `docker compose up` on a Docker host. Record the
  exact image and compose results.

- [ ] **Run the three outstanding acceptance playtests.** Complete a solo
  score and downtime cycle, a multi-session canon-consistency campaign, and an
  ingested-rulebook session. These should follow the Priority 0 to Priority 2
  fixes so they validate enforced rules rather than prompt compliance.

## 4. Findings verified as closed

The following older audit items are now present in live code and tests:

- Player X-card flow, redirect support, lines and veils prompt guidance, and UI.
- Trauma operations, armor use and restoration, character stash, load limits,
  crew development, turf and claims, and replay cases. The trauma UI remains
  broken by snapshot and overflow-state drift described above.
- Faction creation in canon, faction clock association, and downtime reminders.
- Referential checks for relationships and faction status, plus duplicate NPC
  refusal. Optional NPC faction references still need validation.
- Campaign-level JSON export and replay-based import, campaign deletion, and a
  web campaign export control.
- Persistence before state-bearing WebSocket events and atomic base/latest
  snapshot creation.
- Roll decline, offered Devil's Bargain text, and assist composition.
- Journal summaries and filter buckets for the events named in the older audit.
- Downtime allowance enforcement: activity counts and training tracks reset on
  entering downtime, extra activities require an explicit payment, and replay
  folds the allowance state from the event log.
- Character-owned recovery: healing progress is stored on the character,
  replayed from dedicated events, and reset after each harm level is healed so
  repeated recovery remains legal.
- Basic score ordering: engagement is score-phase-only and single-use; payoff
  and entanglement are downtime-phase-only, single-use, and entanglement cannot
  precede payoff or heat processing. Entering downtime requires an action roll.
- Procedure persistence: campaign snapshot loading and event-log undo have
  explicit coverage for score flags and downtime activity counters.
- Case-insensitive setting term checks and narrow pack-level checks for core
  playbook and crew-type assemblies.
- Upload size limits, clean extraction errors, and empty-text refusal on the
  server. The UI still hides the returned detail.

These closures do not imply that the broader parent requirement is complete.
For example, campaign export works while sheet export and web import remain
open, and module deletion works while atomic module updates remain open.

## 5. Architectural notes for the next implementation pass

- Keep engine operations pure and inject RNG and clocks. New procedure state
  must be event-sourced and replayed from the same operation functions used
  live.
- Every state-changing tool needs an event, replay fold, journal summary, and
  persistence-before-send coverage.
- Tests for encoded rules must cite the relevant SRD section heading.
- Do not solve phase or downtime enforcement in prompts. The AI may propose an
  operation; the engine must accept or refuse it from authoritative state.
- Do not expose private module prose or structured content in campaign exports.
- Preserve the licensing firewall. Do not add assembled core-book playbooks,
  crew sheets, named NPCs, setting material, maps, art, or official PDFs.
