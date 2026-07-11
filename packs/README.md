# packs/

Content packs: playbooks, crew types, items, factions, tables, and settings,
as versioned data rather than code (SPECIFICATION.md §7, principle 2).

## Format and loader contract

A pack is a JSON file matching the `ContentPack` schema in
`server/engine/packs.py` (id, name, description, version, plus the
mechanics collections: special abilities, items, reputations, traumas,
vices, crew upgrades, action-outcome/heat/entanglement/magnitude/downtime
tables, an SRD section index, and `PlaybookTemplate`/`CrewTypeTemplate`
entries). Phase 6's rulebook ingestion (FR-22) added two collections for
what an uploaded book carries that the SRD-shaped fields don't:
`FactionSeed` entries (faction name/description/tier hint, lighter than a
live campaign faction) and free-form `ExtractedTable` entries (a hack's
own tables that don't match the SRD-shaped ones above).

`server/engine/pack_loader.py` loads packs:

- `load_pack(path)` reads one file, validates it against the schema, and
  refuses it (raising `PackLoadError`) if it contains forbidden core-book
  terms, as a runtime backstop to the `licensing-grep` commit-time check.
- `load_packs_dir(directory)` loads every `*.json` file directly under a
  directory, in filename order. Used for both this committed directory and,
  from Phase 6, a user's private pack directory (FR-23, C6).
- Both loaders take `private=True` for packs under the user's own data
  directory: schema validation still applies, the forbidden-term refusal
  does not. NOTICE.md allows owners to keep core-book content they own as
  private modules - the firewall guards distribution (commits and this
  committed directory), not user data.

Two packs are committed here:

- `srd_base.json`: SRD-derived mechanics only (C3a) - regenerate from a
  local SRD copy with `make extract-srd` (see the root README's "The SRD"
  section). Its `playbooks`/`crew_types` lists are empty: the SRD gives us
  the ability bank, not licensed playbook/crew-type assemblies.
- `example_base.json`: one entirely original playbook (Wayfarer) and crew
  type (Couriers), proving the `PlaybookTemplate`/`CrewTypeTemplate` shape
  end to end without any core-book content (FR-9, C4). Regenerate with
  `make build-example-pack` (`server/cli/example_pack.py`).

A real Blades in the Dark playbook/crew-type's own assembly (starting
dots, ability selection, friends, items) is core-book content and must
never be added to either pack; that assembly is private, book-owner-only
data built via guided entry (TODO.md Phase 2), never committed.

## Content policy

Only SRD-derived mechanics and original example content may be committed
here. See [NOTICE.md](../NOTICE.md) for the full content policy: no Doskvol
setting, named NPCs, assembled core-book playbooks/crew sheets, or core-book
art.
