from pathlib import Path

from pydantic import ValidationError

from engine.packs import ContentPack

# The single source of the forbidden-term list (NOTICE.md "Content
# policy"); cli/licensing_grep.py imports it from here. The firewall is
# about distribution: licensing-grep blocks these terms from being
# committed, and load_pack refuses them in distribution-bound packs as a
# runtime backstop. Private packs (a user's own modules under their data
# dir, NOTICE.md's "Owners of the game may load their own copies")
# are exempt: pass private=True to the loaders.
FORBIDDEN_TERMS = ("Doskvol", "Duskwall")


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

    try:
        return ContentPack.model_validate_json(raw)
    except ValidationError as error:
        raise PackLoadError(f"{path} does not match the content-pack schema: {error}") from error


def load_packs_dir(directory: Path, *, private: bool = False) -> list[ContentPack]:
    """Loads every *.json file directly under `directory` as a content
    pack, in filename order. `private` as in `load_pack`."""
    return [load_pack(path, private=private) for path in sorted(directory.glob("*.json"))]


def forbidden_terms_in(text: str) -> list[str]:
    """The firewall's actual check, exposed on its own for callers that
    don't have a pack *file* to load, instead of it being an
    implementation detail of `load_pack`."""
    return [term for term in FORBIDDEN_TERMS if term in text]


def _check_licensing_firewall(raw_text: str, path: Path) -> None:
    hits = forbidden_terms_in(raw_text)
    if hits:
        raise PackLoadError(
            f"{path} contains forbidden core-book content ({', '.join(hits)}); see NOTICE.md"
        )
