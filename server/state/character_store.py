from pathlib import Path

from engine.character import Character


class CharacterIdError(ValueError):
    """A character id becomes a filename component (`<character_id>.json`) -
    refused if it isn't safe to use as one, same reasoning as
    `state.module_store.ModuleIdError`."""


def characters_dir(data_dir: Path) -> Path:
    """FR-8: where `cli/guided_entry.py` saves a completed character, and
    where the campaign picker's import step (FR-8) looks for one to
    offer - private user data (ADR-0005), never committed."""
    return data_dir / "characters"


def _validate_character_id(character_id: str) -> None:
    if (
        not character_id
        or character_id in (".", "..")
        or "/" in character_id
        or "\\" in character_id
    ):
        raise CharacterIdError(f"invalid character id {character_id!r}")


def list_characters(data_dir: Path) -> list[tuple[str, Character]]:
    """Every saved character, filename order - the id is the filename
    stem, matching `cli/guided_entry.py`'s own naming
    (`name.lower().replace(' ', '_')`)."""
    directory = characters_dir(data_dir)
    if not directory.exists():
        return []
    return [
        (path.stem, Character.model_validate_json(path.read_text()))
        for path in sorted(directory.glob("*.json"))
    ]


def load_character(data_dir: Path, character_id: str) -> Character | None:
    """None for an unknown id - a missing character is a normal case here
    (never saved, or removed outside this process), same as
    `state.module_store.load_module`."""
    _validate_character_id(character_id)
    path = characters_dir(data_dir) / f"{character_id}.json"
    if not path.exists():
        return None
    return Character.model_validate_json(path.read_text())
