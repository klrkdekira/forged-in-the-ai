import json
from pathlib import Path

import pytest

from cli.licensing_grep import find_pack_hits
from engine.pack_loader import FORBIDDEN_TERMS, PackLoadError, load_pack, load_packs_dir
from engine.packs import ContentPack


def _write_pack(path: Path, **overrides) -> Path:
    data = {"id": "example", "name": "Example Pack", "description": "d", "version": "1.0.0"}
    data.update(overrides)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_pack_reads_a_valid_pack(tmp_path: Path) -> None:
    pack_path = _write_pack(tmp_path / "example.json")

    pack = load_pack(pack_path)

    assert isinstance(pack, ContentPack)
    assert pack.id == "example"


def test_load_pack_rejects_invalid_json(tmp_path: Path) -> None:
    pack_path = tmp_path / "broken.json"
    pack_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(PackLoadError):
        load_pack(pack_path)


def test_load_pack_rejects_schema_mismatch(tmp_path: Path) -> None:
    pack_path = tmp_path / "incomplete.json"
    pack_path.write_text(json.dumps({"id": "example"}), encoding="utf-8")

    with pytest.raises(PackLoadError):
        load_pack(pack_path)


def test_load_pack_rejects_forbidden_core_book_content(tmp_path: Path) -> None:
    # Drawn from FORBIDDEN_TERMS rather than hardcoded, so this test file
    # doesn't itself carry the forbidden term as source text (licensing-grep).
    forbidden_term = FORBIDDEN_TERMS[0]
    pack_path = _write_pack(tmp_path / "forbidden.json", description=f"A tale of {forbidden_term}.")

    with pytest.raises(PackLoadError, match=forbidden_term):
        load_pack(pack_path)


def test_load_pack_rejects_forbidden_core_book_content_case_insensitively(
    tmp_path: Path,
) -> None:
    forbidden_term = FORBIDDEN_TERMS[0].upper()
    pack_path = _write_pack(tmp_path / "forbidden.json", description=f"A tale of {forbidden_term}.")

    with pytest.raises(PackLoadError, match="forbidden core-book content"):
        load_pack(pack_path)


def test_licensing_grep_rejects_non_text_assets_under_committed_packs() -> None:
    hits = find_pack_hits("packs/reference.pdf")

    assert "unsupported committed-pack file extension" in hits[0]


def test_load_pack_rejects_a_committed_map_field(tmp_path: Path) -> None:
    pack_path = _write_pack(tmp_path / "map_data.json", maps=[{"name": "original"}])

    with pytest.raises(PackLoadError, match="prohibited committed-pack field"):
        load_pack(pack_path)


def test_load_pack_rejects_a_committed_art_asset_name(tmp_path: Path) -> None:
    pack_path = _write_pack(tmp_path / "art.json")

    with pytest.raises(PackLoadError, match="prohibited committed-pack asset name"):
        load_pack(pack_path)


def test_private_pack_may_use_a_map_field(tmp_path: Path) -> None:
    pack_path = _write_pack(tmp_path / "map_data.json", maps=[{"name": "private"}])

    pack = load_pack(pack_path, private=True)

    assert pack.id == "example"


def test_load_pack_rejects_a_real_playbook_name(tmp_path: Path) -> None:
    pack_path = _write_pack(
        tmp_path / "real_playbook.json",
        playbooks=[{"id": "cutter", "name": "Cutter", "xp_trigger": "violence"}],
    )

    with pytest.raises(PackLoadError, match="Cutter"):
        load_pack(pack_path)


def test_load_pack_rejects_a_real_crew_type_name_case_insensitively(tmp_path: Path) -> None:
    pack_path = _write_pack(
        tmp_path / "real_crew_type.json",
        crew_types=[{"id": "hawkers", "name": "hawkers"}],
    )

    with pytest.raises(PackLoadError, match="hawkers"):
        load_pack(pack_path)


def test_load_pack_allows_a_real_playbook_name_when_private(tmp_path: Path) -> None:
    # FR-23/C6: a book owner's own private module may legitimately name a
    # real playbook - the firewall guards distribution, not local use.
    pack_path = _write_pack(
        tmp_path / "private_playbook.json",
        playbooks=[{"id": "cutter", "name": "Cutter", "xp_trigger": "violence"}],
    )

    pack = load_pack(pack_path, private=True)

    assert pack.playbooks[0].name == "Cutter"


def test_load_pack_allows_an_original_playbook_name(tmp_path: Path) -> None:
    pack_path = _write_pack(
        tmp_path / "original_playbook.json",
        playbooks=[{"id": "wayfarer", "name": "Wayfarer", "xp_trigger": "travel"}],
    )

    pack = load_pack(pack_path)

    assert pack.playbooks[0].name == "Wayfarer"


def test_load_packs_dir_loads_all_json_files_in_order(tmp_path: Path) -> None:
    _write_pack(tmp_path / "b.json", id="b")
    _write_pack(tmp_path / "a.json", id="a")
    (tmp_path / "README.md").write_text("not a pack", encoding="utf-8")

    packs = load_packs_dir(tmp_path)

    assert [pack.id for pack in packs] == ["a", "b"]


def test_load_packs_dir_the_committed_srd_base_pack() -> None:
    packs_dir = Path(__file__).parents[2] / "packs"

    packs = load_packs_dir(packs_dir)

    assert any(pack.id == "srd" for pack in packs)
