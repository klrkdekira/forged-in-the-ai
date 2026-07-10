from pathlib import Path

from engine.packs import ContentPack

# SRD: "Trauma" (character traumas), "Vice" character sections (vices),
# "Reputation" (crew reputations), "Setting Position & Effect" (the
# controlled/risky/desperate outcome bands), "Magnitude", "Downtime
# activities" - packs/srd_base.json is generated from these by
# server/cli/extract_srd.py (`make extract-srd`).
PACK_PATH = Path(__file__).parents[2] / "packs" / "srd_base.json"


def load_pack() -> ContentPack:
    return ContentPack.model_validate_json(PACK_PATH.read_text(encoding="utf-8"))


def test_srd_base_pack_matches_schema() -> None:
    pack = load_pack()

    assert pack.id == "srd"
    assert len(pack.special_abilities) > 0


def test_srd_base_pack_has_a_known_special_ability() -> None:
    pack = load_pack()

    battleborn = next(a for a in pack.special_abilities if a.id == "battleborn")
    assert "push yourself" in battleborn.description


def test_srd_base_pack_traumas_and_vices_are_the_fixed_srd_lists() -> None:
    pack = load_pack()

    assert {t.id for t in pack.traumas} == {
        "cold",
        "haunted",
        "obsessed",
        "paranoid",
        "reckless",
        "soft",
        "unstable",
        "vicious",
    }
    assert {v.id for v in pack.vices} == {
        "faith",
        "gambling",
        "luxury",
        "obligation",
        "pleasure",
        "stupor",
        "weird",
    }


def test_srd_base_pack_has_all_three_position_bands() -> None:
    pack = load_pack()

    assert {p.position for p in pack.action_outcomes} == {"controlled", "risky", "desperate"}


def test_srd_base_pack_has_all_seven_magnitude_levels() -> None:
    pack = load_pack()

    assert {level.level for level in pack.magnitude_levels} == set(range(7))
    legendary = next(level for level in pack.magnitude_levels if level.level == 6)
    assert legendary.quality_tier == "Legendary"


def test_srd_base_pack_has_the_six_downtime_activities() -> None:
    pack = load_pack()

    assert {a.id for a in pack.downtime_activities} == {
        "acquire_asset",
        "long_term_project",
        "recover",
        "reduce_heat",
        "train",
        "indulge_vice",
    }
    acquire_asset = next(a for a in pack.downtime_activities if a.id == "acquire_asset")
    assert {r.level for r in acquire_asset.results} == {"critical", "6", "4/5", "1-3"}


def test_srd_base_pack_has_a_section_index() -> None:
    pack = load_pack()

    assert any(s.heading == "Magnitude" and s.level == 1 for s in pack.srd_sections)
