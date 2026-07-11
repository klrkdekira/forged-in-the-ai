# Specification: Forged in the AI

An AI referee (GM) for Forged in the Dark games, starting with Blades in the
Dark. A human player (later several) plays their scoundrel; the AI runs
everything else: the fiction, the NPCs, the factions, and the rules as
written.

Status: **draft / pre-implementation**. This document defines the scope.
See [TODO.md](TODO.md) for the phased plan and [NOTICE.md](NOTICE.md) for licensing.

---

## 1. Vision

Sit down alone (or with friends), open your existing Blades in the Dark
character sheet, and play a real session: free play, a score, downtime,
entanglements. An AI GM makes judgement calls the way the book tells a GM to,
while a deterministic rules engine rolls the dice, tracks the clocks, and
keeps the world state so nothing is forgotten or fudged.

## 2. Goals

- **G1: Faithful play.** Sessions follow the SRD's structure and procedures
  (`Blades-in-the-Dark-SRD.md`): action rolls with position/effect, resistance,
  fortune rolls, stress/trauma, harm, progress clocks, the loop of score,
  payoff, heat, entanglements and downtime, and the faction game.
- **G2: Character sheets as-is.** Players bring their existing BitD character
  (and crew) sheets. The system models the standard sheet fields verbatim, so a
  paper or PDF sheet maps 1:1 onto the digital one.
- **G3: Living world.** NPCs, factions, locations, clocks, scores, and items
  are created during play, persisted, and reused. The AI references established
  facts instead of reinventing them.
- **G4: Honest referee.** Dice are rolled by code, not by the language model.
  Every mechanical outcome is auditable: what was rolled, why, at what
  position/effect, and what changed as a result.
- **G5: System-agnostic core.** BitD is the first supported game, but rules
  content (playbooks, crew types, items, factions) is loaded as data ("content
  packs") so other Forged in the Dark games can be added without engine changes.
- **G6: Multiplayer-ready.** Single-player first, but no design decision that
  precludes multiple players joining one session later.

## 3. Non-goals

- Not a tactical VTT: no token combat, no measured grid. Interactive maps
  (claim maps, district/score maps) are in scope as fiction aids, rendered
  from original or generated data only, never core-book art (C3).
- Not a character builder/optimiser beyond what sheet creation requires.
- No redistribution of non-SRD game content (see §4).
- No AI-generated artwork pipeline.
- No voice, real-time audio, or video (not planned for any current phase).

## 4. Licensing and content constraints

These are hard requirements, derived from <https://bladesinthedark.com/licensing>:

- **C1.** The SRD is licensed CC-BY 3.0 Unported. The required attribution
  text ships in [NOTICE.md](NOTICE.md) and must appear in any distributed UI's
  credits.
- **C2.** The product name must not contain "Blades in the Dark".
  (*Forged in the AI* complies.)
- **C3.** The Duskwall/Doskvol setting, named NPCs, maps, and artwork from the
  core book are not in the SRD and must not be shipped in this repository or
  any distribution. The assembled playbooks and crew sheets are likewise
  core-book content: the pairing of playbook name with starting action dots,
  ability selection, starting builds, friends/rivals lists, per-playbook item
  lists, and the crew types' claim maps, upgrades, and cohorts. The official
  sheet PDFs on <https://bladesinthedark.com/downloads> are free to download
  but carry no redistribution licence; never commit them.
- **C3a.** However, the SRD itself contains the special-ability bank with full
  rules text (Battleborn, Mule, Sharpshooter, Alchemist, Infiltrator,
  Mesmerism, Ritual and the rest), plus all mechanics, XP-trigger patterns,
  item rules, and reputation lists. All of this is CC-BY and may be committed
  as a base content pack. Only the assembly (C3) must remain user-supplied.
  The full SRD document itself is not committed: development and CI use a
  local, gitignored copy at the repo root, and only derived pack data ships.
- **C4.** Consequence of C3/C3a: the repo may ship (a) SRD-derived mechanics
  and the committed SRD base pack (ability bank, item rules, tables), (b) an
  original example content pack, and (c) empty schemas into which owners of
  the book can enter their own playbook/crew assemblies for personal use.
  Everything beyond that is user- or AI-supplied data. If written permission
  is ever obtained from One Seven Design (historically friendly to free
  community tools), the assembled playbook data could ship too; until then it
  stays out.
- **C5.** The "Forged in the Dark" logo may only be used alongside the required
  trademark notice; defer any logo use until distribution is a question.
- **C6.** Users may upload rulebooks they own for local parsing into private
  modules (§6.5). Uploaded books and everything derived from them stay on the
  user's machine as user data: never committed, exported, or redistributed.

## 5. Domain model (from the SRD)

The engine must represent, at minimum:

- **Character**: playbook, action ratings (12 actions under Insight/Prowess/
  Resolve), attribute ratings (derived), stress (0–9) and trauma (0–4 plus
  conditions), harm (3 levels plus healing clock), armor uses, load and items,
  special abilities, XP tracks (playbook plus 3 attributes), coin and stash,
  vice, contacts (friend/rival), heritage/background/look.
- **Crew**: type, tier, hold (weak/strong), rep, heat (0–9) and wanted level,
  coin/vaults, claims map, upgrades, cohorts (gangs/experts with type, quality,
  harm), crew special abilities, crew XP.
- **Faction**: name, tier, hold, status with the crew (-3 to +3), faction
  clocks, assets, notable NPCs.
- **Clock**: 4/6/8-segment progress clocks of every SRD flavour (danger, racing,
  linked, tug-of-war, long-term project, faction, healing).
- **NPC / Location / Item**: lightweight entities with tags and the fiction
  established about them.
- **Relationship**: an edge between any two entities (PC to NPC, crew to
  faction, NPC to NPC, and so on) with a type (ally, rival, debt, romance,
  vendetta), a status, and a history; every change references the event that
  caused it. Faction status with the crew (-3 to +3) is a typed special case
  of this.
- **Score**: target, plan type plus detail, engagement roll result, payoff,
  heat, entanglement.
- **Session / Campaign**: event log of everything that happened, current phase
  (free play / score / downtime), and world snapshot.

## 6. Functional requirements

### 6.1 Rules engine (deterministic, no LLM)

- **FR-1** Implement all SRD roll types: action roll (with position: controlled/
  risky/desperate; effect: limited/standard/great), resistance roll, fortune
  roll, engagement roll, acquire asset, vice/overindulgence, healing, crafting,
  and the downtime activity rolls.
- **FR-2** Implement dice mechanics exactly: d6 pools, take highest, critical on
  multiple 6s, 0d rolls 2 and takes the lowest; bonus dice (assist, push,
  Devil's Bargain); stress costs; trauma on stress overflow.
- **FR-3** Implement clocks (create, tick by consequence level, complete) and
  the state transitions they trigger.
- **FR-4** Implement the score loop: engagement roll, flashbacks (stress cost
  0/1/2), payoff (rep plus coin), heat (by table), wanted level, entanglement
  roll (by heat/wanted), then downtime activities (2 free, extra cost
  coin/rep).
- **FR-5** Implement advancement: XP triggers at end of session; a filled track
  grants an advance (action dots or special abilities); crew advancement; tier
  and hold changes.
- **FR-6** Every roll is executed with a seeded RNG and recorded (inputs,
  dice faces, outcome, consequences) in the session event log. The LLM can
  request rolls and interpret outcomes but never fabricates results.

### 6.2 Character & crew sheets

- **FR-7** JSON schema for character and crew sheets mirroring the official
  sheet layout field-for-field, so a player can copy their paper sheet in.
- **FR-8** Import: interactive entry (guided by the AI), or loading a JSON file.
  Export: JSON always; human-readable markdown sheet render.
- **FR-9** Playbooks/crew types are content-pack data (name, action dots,
  special ability list, XP trigger, items, friends), per constraint C4. Ship
  the SRD base pack (C3a) and an original example pack. A user's BitD playbook
  assembly is a thin private overlay (starting dots, ability references into
  the committed SRD ability bank, friends, items) entered via guided entry
  (FR-8); never ship the assemblies themselves.
- **FR-10** Sheet mutations only happen through engine operations (mark stress,
  take harm, spend coin, and so on), never by free-form LLM edits.

### 6.3 AI referee

- **FR-11** The AI GM performs the GM role as the SRD defines it: frames scenes,
  asks "what do you do?", makes judgement calls, sets position and effect with
  stated reasoning, offers Devil's Bargains, narrates consequences, cuts to
  the action, and follows the GM goals/actions/principles in the SRD's
  "Running the Game" guidance.
- **FR-12** The AI interacts with the rules engine exclusively through tools
  (function calls): `roll_action`, `set_clock`, `apply_harm`, `update_faction`,
  `create_npc`, etc. Fiction in prose; mechanics through tools.
- **FR-13** The AI is grounded in the SRD via retrieval: rules questions are
  answered by citing SRD passages, not from model memory.
- **FR-14** The AI plays NPCs and factions with persistent goals; between
  scores it advances faction clocks per the SRD's NPC and faction downtime
  rules.
- **FR-15** World generation: when the fiction needs a new NPC/location/
  faction/score, the AI generates it, the engine persists it, and it becomes
  canon. Established canon is injected into context so the AI stays consistent.
- **FR-16** Player-facing transparency: before any consequential roll the
  player sees position, effect, dice pool, and available bonuses, and chooses
  whether to push, assist, accept a bargain, or trade position for effect,
  which is the negotiation the book prescribes.
- **FR-17** Safety tools: session-zero configuration of lines and veils; an
  X-card style command that rewinds/redirects the fiction without argument.
- **FR-36** Session-zero setting generation: campaigns begin with the AI
  interviewing the players and generating an original setting (city sketch,
  factions, tone) which is persisted as campaign-local content and grows
  during play (FR-15). No setting ships with the product (C3); owners of the
  book can load Doskvol privately as a module (C6).

### 6.4 Sessions & persistence

- **FR-18** Campaigns persist across sessions: full event log (append-only)
  plus derived world snapshot. Resuming a campaign restores the AI's context
  via a structured recap.
- **FR-19** The event log is authoritative; sheet/world state is reproducible
  by replaying it (event sourcing). This also gives undo and auditability (G4).
- **FR-20** Session export: a human-readable session recap ("the story so far")
  generated from the log.

### 6.5 Rulebook ingestion (bring your own book)

- **FR-21** Users can upload rulebooks they own (PDF, markdown, or plain text)
  to be parsed into local content-pack **modules**: playbooks, crew types,
  items, factions, tables, and setting reference material.
- **FR-22** Ingestion pipeline: text extraction, then LLM-assisted structured
  extraction into the content-pack schemas (FR-9), then user review and edit
  before the module is activated in a campaign. Extraction is best-effort;
  the user is the final validator.
- **FR-23** Uploaded books and derived modules live in the user's data
  directory as private packs (C6): excluded from the repo, from campaign
  exports, and from any future sharing features by default.
- **FR-24** A module's prose (setting, GM advice) joins the SRD in the GM
  agent's retrieval corpus (FR-13), so the AI can referee hacks and settings
  from the uploaded book, not just cite its mechanics.

### 6.6 Controllers & multiplayer

- **FR-25** Controller model, in force from the single-player MVP on: every
  controllable entity (PC, cohort, vehicle) is bound to a **controller**,
  which is a human seat or an AI player agent. One human may control any
  number of entities (solo play is one seat controlling the whole crew);
  multiplayer is more seats on the same model, not a new one.
- **FR-35** AI player agent (future phase): an agent distinct from the GM
  that plays a crewmate PC (makes action choices, spends stress, roleplays),
  so a solo human can run one scoundrel alongside AI companions. Mixed tables
  (humans plus AI PCs) follow from the controller model.
- **FR-26** Turn/spotlight management: the AI directs the spotlight between
  controllers; simultaneous free-play chat is out of scope until the
  multiplayer phase begins.
- **FR-27** Transport-agnostic core: the engine and AI loop expose an API that
  a CLI, web client, or chat bridge (e.g. Discord) can drive.

### 6.7 Interactive client

- **FR-28** Interactive character and crew sheets mirroring the official layout
  (G2): stress, harm, XP, load, coin, and clocks are clickable, and every
  interaction goes through engine operations (FR-10); the UI never edits
  state directly.
- **FR-29** Table view: active clocks, the crew's claim map, and generated
  district/score maps as shared fiction aids. All map imagery is original or
  generated (C3).
- **FR-30** Real-time sync: the client subscribes to a session WebSocket
  channel; the server is authoritative and pushes state deltas from the event
  log. Built single-player first; multiplayer (§6.6) adds subscribers to the
  same channel.

### 6.8 Journal & relationships

- **FR-31** Turn-by-turn logging: every turn (GM narration, player input,
  rolls, state changes, phase transitions) is a structured event tagged with
  the entities involved. The journal is fully reconstructible from the event
  log (FR-19); everything that happens at the table is recorded.
- **FR-32** Journal view in the client: a chronological turn log, filterable
  by type (narration / rolls / consequences / downtime), phase, or entity.
  Mechanical entries expand to their full audit record: dice faces, position,
  effect, consequences (G4, FR-6).
- **FR-33** Relationships (§5) are created and updated only through engine
  operations and AI tools (e.g. `update_relationship`), like all other state
  (FR-10, FR-12). The AI records relationship changes as they happen in the
  fiction: a betrayal, a favour owed, a new contact.
- **FR-34** Relationship map view: an interactive graph of PCs, NPCs, factions,
  and the crew. Selecting an entity shows its details; selecting an edge shows
  the relationship's type, status, and what transpired between them: the
  linked journal entries that shaped it, in order.

## 7. Architecture principles

1. **The engine adjudicates, the model narrates.** Deterministic rules engine
   as the single writer of game state; the LLM is a client of it through tools.
2. **Content as data.** Mechanics in code; playbooks, crews, items, factions,
   and setting in versioned content packs (JSON/YAML). This is both the
   licensing firewall (C4) and the path to other FitD games (G5).
3. **Event-sourced state.** Append-only campaign log; snapshots are caches.
4. **Engine before interface.** The engine is a pure library, exercised
   headless (tests, dev CLI) before and alongside the web client; other
   clients attach to the same API later (FR-27).

Layering (stack per ADR-0002: Python/FastAPI server, React/TS web client):

```
clients:    web SPA (React/TS)  ·  dev CLI harness  ·  (later) chat bridge
            |  REST + WebSocket; TS types generated from server schemas
app:        FastAPI server - session orchestrator (game loop, AI GM loop, recaps)
            |
ai:         GM agent - prompts, SRD/module retrieval, tool definitions
            | tools only
engine:     rules (rolls, clocks, score loop, advancement) - pure, deterministic
            |
state:      SQLite (event log, snapshots, entities, FTS5 retrieval index)
            + content packs + JSONL export (Pydantic schemas throughout)
```

## 8. Non-functional requirements

- **NFR-1 Determinism/replayability**: the same event log and seed yield the
  same state.
- **NFR-2 Rules coverage**: engine behaviour traceable to SRD sections; test
  cases quote the SRD passage they encode.
- **NFR-3 Latency**: AI narration streaming; a play turn should feel
  conversational (under a few seconds to first token).
- **NFR-4 Context budget**: the working backend context is 64k–128k tokens
  (ADR-0003). Each GM turn is assembled from structured state plus retrieval
  under an explicit per-section budget (procedures, canon, retrieval, recent
  transcript with older play summarised), never by replaying whole
  transcripts, and sized to fit the 64k floor.
- **NFR-5 Portability of saves**: the operational store is SQLite on the
  user-data volume (ADR-0005); portability is guaranteed by a canonical JSONL
  event-log export (plus JSON snapshots) that round-trips through import; a
  test enforces the round-trip.
- **NFR-6 Model agnosticism**: any OpenAI-compatible endpoint (Ollama, vLLM,
  hosted) is a valid backend, configured by base URL and model name. Where a
  model's native tool-calling is unreliable, fall back to constrained/
  structured output; where context is small, lean on retrieval (NFR-4).
- **NFR-7 Container-first** (ADR-0004): root `Dockerfile` and `compose.yml`;
  one image holds the compiled web assets and the Python server (FastAPI
  serves the SPA). The app runs with `docker compose up`, bound to localhost
  only, with no auth before multiplayer; user data (saves, private modules)
  lives on mounted volumes; a dev profile keeps hot reload.

## 9. Open decisions

Record outcomes as short ADRs in `docs/adr/` when decided.

- **D1: Language/stack. DECIDED** (ADR-0002): Python 3.12+/FastAPI/Pydantic
  backend; React and TypeScript (Vite) frontend; monorepo with generated TS
  types as the schema contract.
- **D2: LLM interface. DECIDED** (ADR-0001): OpenAI-compatible chat
  completions API, so local/self-hosted backends (Ollama, vLLM) and hosted
  providers are interchangeable via base URL and model name. Follow-on
  concern: tool-calling reliability varies widely across local models, so
  FR-12 needs a structured-output fallback path and a per-model capability
  check.
- **D3: SRD grounding. DECIDED** (ADR-0003): hybrid. Hand-distilled GM
  procedure docs are always in the system prompt; retrieval over the full
  SRD/modules covers lookups and citations. Primary backend is hosted
  frontier-class models; local backends supported best-effort via the
  capability probe and fallback (NFR-6).
- **D4: First client. DECIDED** (ADR-0002): the React web app, with
  interactive sheets and maps (§6.7). A thin dev CLI harness remains for
  engine development and headless tests. Canvas library for maps: Konva.js
  via `react-konva` (ADR-0007).
- **D5: Multiplayer transport** (when the phase arrives): self-hosted web vs.
  Discord bridge.
- **D6: Sheet ingestion. LARGELY DECIDED**: for BitD, guided manual entry is
  the path. With the SRD ability bank committed (C3a), the remaining gap per
  playbook is small and structured (name, starting dots, about 8 ability
  references, 5 friends, about 6 items; plus 6 crew types). PDF parsing of
  the official sheets is not worth building for BitD; the rulebook ingestion
  pipeline (§6.5) targets third-party FitD books that have no SRD.
