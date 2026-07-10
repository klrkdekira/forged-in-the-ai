from pathlib import Path

from pydantic import ValidationError

from engine.packs import ContentPack

# Kept in sync with scripts/licensing-grep.sh's forbidden-term list
# (NOTICE.md "Content policy"): core-book content that must never load,
# committed or not. This is a runtime backstop; licensing-grep is what
# blocks it from being committed in the first place.
FORBIDDEN_TERMS = ("Doskvol", "Duskwall")


class PackLoadError(Exception):
    """A content pack file is missing, not valid JSON, doesn't match the
    content-pack schema, or is refused for containing forbidden core-book
    content (NOTICE.md). The loader may refuse a pack; it never guesses."""


def load_pack(path: Path) -> ContentPack:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise PackLoadError(f"cannot read pack {path}: {error}") from error

    _check_licensing_firewall(raw, path)

    try:
        return ContentPack.model_validate_json(raw)
    except ValidationError as error:
        raise PackLoadError(f"{path} does not match the content-pack schema: {error}") from error


def load_packs_dir(directory: Path) -> list[ContentPack]:
    """Loads every *.json file directly under `directory` as a content
    pack, in filename order."""
    return [load_pack(path) for path in sorted(directory.glob("*.json"))]


def _check_licensing_firewall(raw_text: str, path: Path) -> None:
    hits = [term for term in FORBIDDEN_TERMS if term in raw_text]
    if hits:
        raise PackLoadError(
            f"{path} contains forbidden core-book content ({', '.join(hits)}); see NOTICE.md"
        )
