# packs/

Content packs: playbooks, crew types, items, factions, tables, and settings,
as versioned data rather than code (SPECIFICATION.md §7, principle 2).

## Format and loader contract

A pack is a JSON file matching the `ContentPack` schema in
`server/engine/packs.py` (id, name, description, version, plus the
mechanics collections: special abilities, items, reputations, traumas,
vices, crew upgrades, action-outcome/heat/entanglement tables). The
playbook and crew-type sections of that schema grow in Phase 2 ("SRD base
content pack" / "Example fixture pack" in TODO.md).

`server/engine/pack_loader.py` loads packs:

- `load_pack(path)` reads one file, validates it against the schema, and
  refuses it (raising `PackLoadError`) if it contains forbidden core-book
  terms, as a runtime backstop to the `licensing-grep` commit-time check.
- `load_packs_dir(directory)` loads every `*.json` file directly under a
  directory, in filename order. Used for both this committed directory and,
  from Phase 6, a user's private pack directory (FR-23, C6) - the loader
  itself doesn't distinguish committed from private packs; only where you
  point it does.

Regenerate `srd_base.json` from a local SRD copy with `make extract-srd`
(see the root README's "The SRD" section).

## Content policy

Only SRD-derived mechanics and original example content may be committed
here. See [NOTICE.md](../NOTICE.md) for the full content policy: no Doskvol
setting, named NPCs, assembled core-book playbooks/crew sheets, or core-book
art.
