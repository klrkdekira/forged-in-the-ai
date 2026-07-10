import pytest

from engine.consequences import (
    ArmorAlreadyUsedError,
    ArmorTrack,
    HarmEntry,
    HarmTrack,
    StressTrack,
    TraumaTrack,
)


def test_marking_stress_below_the_last_box_does_not_trigger_trauma():
    # SRD: "Trauma": "When a PC marks their last stress box, they suffer a
    # level of trauma."
    result = StressTrack(marked=3).mark(4)

    assert result.track.marked == 7
    assert not result.triggered_trauma


def test_marking_the_last_stress_box_triggers_trauma_and_resets_to_zero():
    # SRD: "Trauma": "When you return, you have zero stress."
    result = StressTrack(marked=7).mark(2)

    assert result.triggered_trauma
    assert result.track.marked == 0


def test_clearing_stress_cannot_go_below_zero():
    result = StressTrack(marked=1).mark(-5)

    assert result.track.marked == 0
    assert not result.triggered_trauma


def test_a_fourth_trauma_condition_retires_the_character():
    # SRD: "Trauma Conditions": "When you mark your fourth trauma
    # condition, your character cannot continue as a daring scoundrel."
    trauma = TraumaTrack()
    for condition in ("cold", "haunted", "obsessed"):
        trauma = trauma.add(condition)
        assert not trauma.is_retired

    trauma = trauma.add("paranoid")

    assert trauma.is_retired


def test_harm_fills_the_named_level_when_there_is_room():
    # SRD: "Consequences and Harm": harm is recorded at the level suffered.
    result = HarmTrack().mark(1, "Battered")

    assert result.track.entries == [HarmEntry(level=1, name="Battered")]
    assert not result.catastrophic


def test_harm_cascades_up_when_a_level_is_full():
    # SRD: "Consequences and Harm": "If you need to mark a harm level, but
    # the row is already filled, the harm moves up to the next row above."
    track = HarmTrack().mark(1, "Battered").track.mark(1, "Drained").track

    result = track.mark(1, "Distracted")

    assert result.track.entries[-1].level == 2
    assert result.track.entries[-1].name == "Distracted"


def test_overflowing_the_top_harm_level_is_catastrophic():
    # SRD: "Consequences and Harm": "If you run out of spaces on the top
    # row and need to mark harm there, your character suffers a
    # catastrophic, permanent consequence."
    track = HarmTrack(entries=[{"level": 3, "name": "Shattered Right Leg"}])

    result = track.mark(3, "Impaled")

    assert result.catastrophic


def test_direct_level_four_harm_is_catastrophic():
    result = HarmTrack().mark(4, "Stabbed in the Heart")

    assert result.catastrophic


def test_heal_one_level_reduces_and_clears_harm():
    # SRD: "Recover": "When you fill your healing clock, reduce each
    # instance of harm on your sheet by one level."
    track = HarmTrack(
        entries=[
            {"level": 3, "name": "Shattered Right Leg"},
            {"level": 1, "name": "Battered"},
        ]
    )

    healed = track.heal_one_level()

    assert [e.level for e in healed.entries] == [2]


def test_armor_can_only_be_used_once_until_restored():
    # SRD: "Armor": "When an armor box is marked, it can't be used again
    # until it's restored."
    armor = ArmorTrack(has_armor=True).use_armor()

    with pytest.raises(ArmorAlreadyUsedError):
        armor.use_armor()

    assert not armor.restored().armor_used


def test_armor_cannot_be_used_without_the_item():
    with pytest.raises(ArmorAlreadyUsedError):
        ArmorTrack(has_armor=False).use_armor()
