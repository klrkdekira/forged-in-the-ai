# forged-in-the-ai

An AI referee (GM) for Forged in the Dark tabletop games, starting with
Blades in the Dark. Play your scoundrel with your existing character sheet;
the AI runs the fiction, NPCs, and factions while a deterministic rules
engine rolls the dice and keeps an auditable record of the world state.
Single-player first, multiplayer later.

**Status: Phase 0 (foundations).** Monorepo skeleton in place; see
[TODO.md](TODO.md) for progress.

**Stack** (ADR-0002): Python/FastAPI and Pydantic server, React and TypeScript
(Vite) web client with interactive sheets and maps, monorepo, LLM via any
OpenAI-compatible endpoint (ADR-0001). Container-first (ADR-0004): one image
with server and built web assets, run with `docker compose up`.

## Running

```
docker compose up                                    # build and run, http://127.0.0.1:8000
docker compose --profile dev up server-dev web-dev   # hot reload: http://127.0.0.1:5173
docker compose --profile ollama up                   # adds a local Ollama backend
```

Copy [.env.example](.env.example) to `.env` to set `LLM_BASE_URL`/`LLM_MODEL`/
`LLM_API_KEY`. Campaign data lives on the `user-data` volume, so it survives
container replacement.

## Documents

| Document | Purpose |
|---|---|
| [SPECIFICATION.md](SPECIFICATION.md) | Scope, requirements, architecture principles, open decisions |
| [TODO.md](TODO.md) | Phased implementation plan |
| [NOTICE.md](NOTICE.md) | SRD attribution and content policy (what may never be committed) |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute; content policy for PRs |

## The SRD

The Blades in the Dark System Reference Document (CC-BY 3.0, One Seven
Design) is not committed to this repository. Development expects a local copy
at the repo root as `Blades-in-the-Dark-SRD.md` (gitignored). Run
`make fetch-srd` to download it (source: the SRD content repo linked from
<https://bladesinthedark.com/downloads>). Only data derived from the SRD
ships in `packs/`, with attribution per NOTICE.md; `make extract-srd`
regenerates `packs/srd_base.json` from the local copy.

## Core design ideas

- **The engine adjudicates, the model narrates.** The LLM never rolls or
  fabricates mechanical outcomes; it drives a rules engine through tools.
- **Content as data.** Playbooks, crews, and settings load from content packs.
  The repo ships only SRD mechanics and original example content; core-book
  material stays with people who own the book.
- **Event-sourced campaigns.** An append-only log makes every session
  replayable, auditable, and resumable.
- **Bring your own model.** Any OpenAI-compatible endpoint (Ollama, vLLM,
  hosted) works; configure a base URL and model name.
- **Bring your own book.** Upload rulebooks you own and they are parsed into
  private local modules; nothing derived from them ever leaves your machine.

## License

Original software in this repository: [BSD 2-Clause](LICENSE).

This work is based on Blades in the Dark (found at
<http://www.bladesinthedark.com/>), product of One Seven Design, developed and
authored by John Harper, and licensed for our use under the Creative Commons
Attribution 3.0 Unported license. See [NOTICE.md](NOTICE.md).
