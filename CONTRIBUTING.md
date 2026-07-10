# Contributing

## Content policy

This is the most important rule in the project. Read
[NOTICE.md](NOTICE.md) in full before adding anything to `packs/`, fixtures,
or test data.

In short: the Blades in the Dark System Reference Document is CC-BY 3.0 and
may be committed as content-pack data. The Doskvol/Duskwall setting, named
NPCs, core-book art, and assembled playbook/crew sheets (starting dots,
ability selection, friends lists, claim maps) are not in the SRD and must
never be committed, in code, fixtures, or test data, even as an example.
`make check` runs `make licensing-grep` (`server/cli/licensing_grep.py`),
which fails a check on forbidden terms in tracked files; `server/engine/pack_loader.py`
refuses to load a pack containing them at runtime. Neither is a substitute for reading
NOTICE.md before you write content.

If you're unsure whether something you want to add is SRD-derived or
core-book, ask before committing it.

## Before opening a PR

- Read [SPECIFICATION.md](SPECIFICATION.md) and [TODO.md](TODO.md); your
  change should map to a TODO item and not contradict an accepted ADR
  (`docs/adr/`).
- Run `make check` (lint, tests, drift check, licensing grep). There is no
  hosted CI, so this is the only gate.
- Keep PRs phase-scoped and small; tick off the TODO.md items your PR
  completes.
- UK English, plain prose, no em dashes, in docs, comments, and commit
  messages (see CLAUDE.md "Conventions" for the full style list).

## Licensing of your contribution

Original software you contribute is licensed under this repository's
[BSD 2-Clause licence](LICENSE). Do not include content you don't have the
right to relicense this way.
