from pathlib import Path

import pytest

from engine.packs import ContentPack
from state.module_store import ModuleIdError, list_modules, load_module, modules_dir, save_module


def _pack(**overrides) -> ContentPack:
    data = {
        "id": "my-hack",
        "name": "My Hack",
        "description": "A homebrew hack",
        "version": "0.1.0",
    }
    data.update(overrides)
    return ContentPack(**data)


def test_save_module_writes_under_the_modules_subdirectory(tmp_path: Path) -> None:
    path = save_module(tmp_path, _pack())

    assert path == modules_dir(tmp_path) / "my-hack.json"
    assert path.exists()


def test_load_module_reads_back_what_was_saved(tmp_path: Path) -> None:
    save_module(tmp_path, _pack(description="Round-tripped"))

    loaded = load_module(tmp_path, "my-hack")

    assert loaded is not None
    assert loaded.description == "Round-tripped"


def test_load_module_returns_none_for_an_unknown_id(tmp_path: Path) -> None:
    assert load_module(tmp_path, "nope") is None


def test_list_modules_returns_every_saved_module(tmp_path: Path) -> None:
    save_module(tmp_path, _pack(id="hack-a", name="Hack A"))
    save_module(tmp_path, _pack(id="hack-b", name="Hack B"))

    modules = list_modules(tmp_path)

    assert {m.id for m in modules} == {"hack-a", "hack-b"}


def test_list_modules_returns_empty_when_nothing_has_been_saved(tmp_path: Path) -> None:
    assert list_modules(tmp_path) == []


@pytest.mark.parametrize("bad_id", ["", ".", "..", "../escape", "a/b", "a\\b"])
def test_save_module_refuses_an_unsafe_module_id(tmp_path: Path, bad_id: str) -> None:
    with pytest.raises(ModuleIdError):
        save_module(tmp_path, _pack(id=bad_id))


@pytest.mark.parametrize("bad_id", ["", ".", "..", "../escape", "a/b", "a\\b"])
def test_load_module_refuses_an_unsafe_module_id(tmp_path: Path, bad_id: str) -> None:
    with pytest.raises(ModuleIdError):
        load_module(tmp_path, bad_id)
