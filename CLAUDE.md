# forged-in-the-ai: agent guide

AI referee (GM) for Forged in the Dark games (Blades in the Dark first).
Python/FastAPI server plus React/TS web client, single container image.

## Read before implementing

- `SPECIFICATION.md`: requirements (FR-x), constraints (C-x), NFRs, domain model. Defines the scope; authoritative.
- `TODO.md`: phased plan; your task maps to items here.
- `docs/adr/`: 0001 LLM API, 0002 stack, 0003 grounding/model choice, 0004 containers, 0005 SQLite/services, 0006 web libraries. Do not contradict an accepted ADR; if you must, write a superseding one.
- `Blades-in-the-Dark-SRD.md`: the rules text (CC-BY 3.0). Cite section headings when encoding rules. Local-only and gitignored, never committed; if missing, fetch it (see the SRD section in README.md).

## Hard rules

1. **Licensing firewall (C3/C4, NOTICE.md).** Never commit core-book content: the Doskvol setting, named NPCs, assembled playbooks/crew sheets (name, starting dots, ability selection, friends lists, claim maps), core-book art, or the sheet PDFs from bladesinthedark.com. SRD text and data derived from it are fine. This applies to code, fixtures, and test data.
2. **The engine adjudicates, the model narrates.** The rules engine (in `server/`, pure Python, no web/LLM imports) is the only writer of game state. The LLM acts through tools; the UI acts through engine-operation endpoints. No free-form state edits anywhere (FR-10, FR-12).
3. **Event sourcing (FR-19).** State changes append entity-tagged events; snapshots are caches. The same log and seed produce the same state (NFR-1). No `datetime.now()` or `random()` inside engine logic; clock and RNG are injected.
4. **Engine tests cite the SRD.** Each rules test names the SRD section it encodes (NFR-2), e.g. `# SRD: "Action Roll": 6 = full success`.
5. **Schemas are the contract.** Pydantic models generate the OpenAPI spec; web types are generated from it (`openapi-typescript`). Never hand-write TS types for server data; never mirror server models in Zod (Zod is for form UX only, ADR-0006).

## Layout & commands

```
Makefile  single entry point: make check / make check-all / make build / make dev
server/   FastAPI + engine (uv project)      -> uv run pytest ; uv run ruff check
web/      React SPA (pnpm + Vite)            -> pnpm test ; pnpm lint ; pnpm build
packs/    committed content packs (SRD-derived + fixtures only)
docs/adr/ decisions
```

Root `Dockerfile` (multi-stage: web build, then Python runtime serving the
SPA) and `compose.yml` (`docker compose up`; `dev` profile for hot reload)
per ADR-0004.

## Conventions

- UK English, plain prose in all docs, comments, and commit messages. No em
  dashes; no arrows or ellipses in prose (diagrams and code blocks excepted);
  bold only for IDs and lead-in labels; no rhetorical flourishes or stock
  metaphors. Exceptions kept verbatim: SRD quotes and term spellings (e.g.
  "Armor"), the CC-BY attribution text, and code/file identifiers such as
  LICENSE.
- Python 3.12+, ruff for lint and format, pytest. TS: oxlint, vitest, strict TS.
- Engine code raises typed errors for illegal operations (e.g. ticking a full
  clock); the API translates them to 4xx. The engine may refuse; it never
  guesses.
- Keep PRs phase-scoped and small; update `TODO.md` checkboxes when a task
  completes its items.
- The repo is public GitHub with no hosted CI: run `make check` (lint, tests,
  drift check, licensing grep) before finishing any task, and treat every
  commit as distribution under the licensing policy. The root Makefile is the
  single build entry point; CI, if ever added, runs the same targets.
- Storage layout (ADR-0005): one SQLite file per campaign plus one app-level
  db; the server binds localhost only and has no auth before multiplayer.
- LLM access only through the client abstraction (ADR-0001): base URL and
  model from settings, never hardcoded; streaming; tool-calling with a
  structured-output fallback (NFR-6).
