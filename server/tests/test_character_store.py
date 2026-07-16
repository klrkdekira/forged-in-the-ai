from pathlib import Path

import pytest

from engine.character import Character
from state.character_store import CharacterIdError, characters_dir, list_characters, load_character


def _save(data_dir: Path, character_id: str, **overrides) -> None:
    overrides.setdefault("name", "Test")
    character = Character(playbook="Cutter", **overrides)
    directory = characters_dir(data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{character_id}.json").write_text(character.model_dump_json())


def test_load_character_reads_back_a_saved_file(tmp_path: Path) -> None:
    _save(tmp_path, "test", alias="The Ghost")

    loaded = load_character(tmp_path, "test")

    assert loaded is not None
    assert loaded.alias == "The Ghost"


def test_load_character_returns_none_for_an_unknown_id(tmp_path: Path) -> None:
    assert load_character(tmp_path, "nope") is None


def test_load_character_returns_none_when_the_directory_does_not_exist(tmp_path: Path) -> None:
    assert load_character(tmp_path, "test") is None


def test_list_characters_returns_every_saved_character(tmp_path: Path) -> None:
    _save(tmp_path, "anders", name="Anders")
    _save(tmp_path, "vex", name="Vex")

    characters = list_characters(tmp_path)

    assert {character_id for character_id, _ in characters} == {"anders", "vex"}


def test_list_characters_returns_empty_when_nothing_has_been_saved(tmp_path: Path) -> None:
    assert list_characters(tmp_path) == []


@pytest.mark.parametrize("bad_id", ["", ".", "..", "../escape", "a/b", "a\\b"])
def test_load_character_refuses_an_unsafe_id(tmp_path: Path, bad_id: str) -> None:
    with pytest.raises(CharacterIdError):
        load_character(tmp_path, bad_id)
