import json
from pathlib import Path

from pydantic import ValidationError

from engine.packs import ContentPack

# The single source of the forbidden-term list (NOTICE.md "Content
# policy"); cli/licensing_grep.py imports it from here. The firewall is
# about distribution: licensing-grep blocks these terms from being
# committed, and load_pack refuses them in distribution-bound packs as a
# runtime backstop. Private packs (a user's own modules under their data
# dir, NOTICE.md's "Owners of the game may load their own copies")
# are exempt: pass private=True to the loaders. Matching is case-insensitive
# (forbidden_terms_in lowercases both sides) - "doskvol"/"DOSKVOL" are just
# as forbidden as "Doskvol".
FORBIDDEN_TERMS = ("Doskvol", "Duskwall")

# C3: the real Blades in the Dark playbook and crew-type names - checked
# against Blades-in-the-Dark-SRD.md and bladesinthedark.com's own crew/
# playbook pages before being added here. There are seven playbooks
# (Cutter, Hound, Leech, Lurk, Slide, Spider, Whisper) and six crew types
# (Assassins, Bravos, Cult, Hawkers, Shadows, Smugglers) in the core book -
# the 2026-07-17 backlog item that asked for this guessed "six" playbooks
# and "seven" crew types; both counts were the wrong way round, corrected
# here after checking rather than carried over unverified.
#
# These are deliberately NOT in FORBIDDEN_TERMS: they're common English
# words/proper nouns already used throughout this project's own committed
# tests as placeholder Character.playbook/Crew.crew_type values (e.g.
# `Character(name="Anders", playbook="Cutter")` in test_agent.py,
# test_ai_replay.py, test_campaigns_api.py, and others; `crew_type="Assassins"`
# similarly) - a blanket text search would false-positive dozens of
# legitimate fixtures that use the bare word as an arbitrary string, not as
# assembled core-book content. The actual C3 risk is a content *pack*
# assembling a full playbook/crew-type entry under one of these names
# (special abilities, starting dots, claim names) - checked narrowly below,
# against parsed pack data (PlaybookTemplate.name/CrewTypeTemplate.name),
# not as a line-based text match.
FORBIDDEN_PLAYBOOK_NAMES = frozenset(
    {"cutter", "hound", "leech", "lurk", "slide", "spider", "whisper"}
)
FORBIDDEN_CREW_TYPE_NAMES = frozenset(
    {"assassins", "bravos", "cult", "hawkers", "shadows", "smugglers"}
)

# C3: committed packs contain structured rules and original seed data, not
# core-book presentation assets or named-NPC collections. These are exact
# JSON keys, not a text search, so ordinary prose may still mention a map or
# an NPC in a private module and SRD-derived tables remain valid.
FORBIDDEN_PACK_ROOT_KEYS = frozenset(
    {
        "art",
        "artwork",
        "claim_map",
        "claim_maps",
        "image",
        "images",
        "map",
        "maps",
        "named_npc",
        "named_npcs",
        "npc_names",
        "official_sheet_pdf",
        "official_sheet_pdfs",
        "pdf",
        "pdfs",
        "sheet_pdf",
        "sheet_pdfs",
    }
)
FORBIDDEN_PACK_FILE_STEMS = frozenset(
    {"art", "artwork", "claim-map", "claim-maps", "map", "maps", "sheet", "sheets"}
)


class PackLoadError(Exception):
    """A content pack file is missing, not valid JSON, doesn't match the
    content-pack schema, or is refused for containing forbidden core-book
    content (NOTICE.md). The loader may refuse a pack; it never guesses."""


def load_pack(path: Path, *, private: bool = False) -> ContentPack:
    """`private=True` is for packs that live in the user's own data
    directory and never leave it (FR-23, C6): the licensing firewall
    guards distribution, not what an owner of the book keeps locally."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise PackLoadError(f"cannot read pack {path}: {error}") from error

    if not private:
        _check_licensing_firewall(raw, path)
        _check_pack_structure(raw, path)

    try:
        pack = ContentPack.model_validate_json(raw)
    except ValidationError as error:
        raise PackLoadError(f"{path} does not match the content-pack schema: {error}") from error

    if not private:
        _check_named_playbooks_and_crew_types(pack, path)

    return pack


def load_packs_dir(directory: Path, *, private: bool = False) -> list[ContentPack]:
    """Loads every *.json file directly under `directory` as a content
    pack, in filename order. `private` as in `load_pack`."""
    return [load_pack(path, private=private) for path in sorted(directory.glob("*.json"))]


def forbidden_terms_in(text: str) -> list[str]:
    """The firewall's actual check, exposed on its own for callers that
    don't have a pack *file* to load, instead of it being an
    implementation detail of `load_pack`. Case-insensitive."""
    lowered = text.lower()
    return [term for term in FORBIDDEN_TERMS if term.lower() in lowered]


def _check_licensing_firewall(raw_text: str, path: Path) -> None:
    hits = forbidden_terms_in(raw_text)
    if hits:
        raise PackLoadError(
            f"{path} contains forbidden core-book content ({', '.join(hits)}); see NOTICE.md"
        )


def _check_pack_structure(raw_text: str, path: Path) -> None:
    """Reject distribution-bound pack shapes that can carry prohibited assets."""
    if path.stem.lower() in FORBIDDEN_PACK_FILE_STEMS:
        raise PackLoadError(f"{path} has a prohibited committed-pack asset name; see NOTICE.md")
    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError:
        return
    if not isinstance(raw, dict):
        return
    keys = sorted(set(raw) & FORBIDDEN_PACK_ROOT_KEYS)
    if keys:
        joined = ", ".join(keys)
        raise PackLoadError(
            f"{path} contains prohibited committed-pack field(s): {joined}; see NOTICE.md"
        )


def _check_named_playbooks_and_crew_types(pack: ContentPack, path: Path) -> None:
    hits = [
        playbook.name
        for playbook in pack.playbooks
        if playbook.name.lower() in FORBIDDEN_PLAYBOOK_NAMES
    ] + [
        crew_type.name
        for crew_type in pack.crew_types
        if crew_type.name.lower() in FORBIDDEN_CREW_TYPE_NAMES
    ]
    if hits:
        raise PackLoadError(
            f"{path} assembles a real Blades in the Dark playbook/crew type "
            f"({', '.join(hits)}); see NOTICE.md"
        )
