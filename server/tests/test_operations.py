import pytest

from engine.character import Attribute, Character, CharacterItem, LoadLevel, XpTrack
from engine.crew import Claim, Crew
from engine.crew_mechanics import Hold, RepTrack
from engine.errors import EngineError
from engine.operations import (
    InvalidArmorTypeError,
    InvalidTraumaConditionError,
    add_heat,
    adjust_coin,
    adjust_crew_coin,
    adjust_crew_rep,
    adjust_crew_turf,
    adjust_stash,
    adjust_wanted_level,
    develop_crew,
    flashback,
    heal_character,
    mark_attribute_xp,
    mark_crew_xp,
    mark_harm,
    mark_playbook_xp,
    mark_stress,
    mark_trauma,
    restore_armor,
    set_claim_controlled,
    set_item_carried,
    set_load_level,
    use_armor,
)


def _character(**overrides) -> Character:
    return Character(name="Test", playbook="Test Playbook", **overrides)


def test_mark_stress_updates_the_track_without_a_new_object_alias():
    # FR-10: sheet mutations only happen through engine operations.
    character = _character()

    result = mark_stress(character, 3)

    assert result.character.stress.marked == 3
    assert character.stress.marked == 0
    assert not result.triggered_trauma


def test_mark_stress_reports_when_trauma_triggers():
    character = _character(stress={"marked": 7})

    result = mark_stress(character, 2)

    assert result.triggered_trauma
    assert result.character.stress.marked == 0


def test_mark_trauma_rejects_an_unknown_condition():
    with pytest.raises(InvalidTraumaConditionError):
        mark_trauma(_character(), "brave")


def test_flashback_spends_the_gm_set_stress_cost():
    # SRD: "Flashbacks" - "The GM sets a stress cost when you activate a
    # flashback action."
    result = flashback(_character(), 2)

    assert result.character.stress.marked == 2


def test_mark_trauma_records_a_known_condition():
    character = mark_trauma(_character(), "haunted")

    assert character.trauma.conditions == ["haunted"]


def test_mark_harm_cascades_and_reports_catastrophic_overflow():
    character = _character(harm={"entries": [{"level": 3, "name": "Impaled"}]})

    result = mark_harm(character, 3, "Shot in Chest")

    assert result.catastrophic_harm


def test_heal_character_reduces_harm_by_one_level():
    character = _character(harm={"entries": [{"level": 2, "name": "Exhausted"}]})

    healed = heal_character(character)

    assert [e.level for e in healed.harm.entries] == [1]


def _crew(**overrides) -> Crew:
    return Crew(name="Test Crew", crew_type="Test Type", **overrides)


def test_add_heat_increases_wanted_level_on_overflow():
    crew = _crew(heat={"heat": 7})

    result = add_heat(crew, 4)

    assert result.wanted_level_increased
    assert result.crew.wanted_level == 1
    assert result.crew.heat.heat == 2


def test_adjust_wanted_level_clamps_to_the_srd_maximum():
    # SRD: "Heat & Wanted Level" - "The maximum wanted level is 4."
    crew = _crew(wanted_level=4)

    crew = adjust_wanted_level(crew, 1)

    assert crew.wanted_level == 4


def test_adjust_wanted_level_clamps_at_zero():
    # SRD: "Heat & Wanted Level" - incarceration reduces it by 1, never below zero.
    crew = _crew(wanted_level=0)

    crew = adjust_wanted_level(crew, -1)

    assert crew.wanted_level == 0


def test_adjust_crew_rep_clamps_to_the_development_threshold():
    # SRD: "Development" - rep is capped by the crew's threshold (reduced by turf).
    crew = _crew(rep=RepTrack(rep=10, turf=2))

    crew = adjust_crew_rep(crew, 5)

    assert crew.rep.rep == crew.rep.threshold


def test_adjust_crew_coin_refuses_to_go_negative():
    # SRD: "Coin and Stash".
    crew = _crew(coin=2)

    with pytest.raises(EngineError):
        adjust_crew_coin(crew, -3)


def test_adjust_crew_coin_gains_and_spends():
    crew = _crew(coin=2, vault_level=1)

    crew = adjust_crew_coin(crew, 3)
    assert crew.coin == 5

    crew = adjust_crew_coin(crew, -4)
    assert crew.coin == 1


def test_adjust_crew_coin_uses_vault_capacity():
    with pytest.raises(EngineError, match="at most 4 coin"):
        adjust_crew_coin(_crew(coin=4), 1)
    expanded = _crew(coin=4).model_copy(update={"vault_level": 1})
    assert adjust_crew_coin(expanded, 4).coin == 8


def test_mark_crew_xp_clamps_to_the_track_segments():
    # SRD: "Crew Advancement" - the crew xp tracker.
    crew = _crew(xp=XpTrack(marked=7, segments=8))

    marked = mark_crew_xp(crew, 3)

    assert marked.xp.marked == 8


def test_mark_crew_xp_floors_at_zero():
    crew = _crew(xp=XpTrack(marked=1, segments=8))

    cleared = mark_crew_xp(crew, -3)

    assert cleared.xp.marked == 0


def test_develop_crew_refuses_below_threshold():
    with pytest.raises(EngineError):
        develop_crew(_crew())


def test_develop_crew_strengthens_weak_hold():
    crew = _crew(hold=Hold.WEAK, rep=RepTrack(rep=12))

    developed = develop_crew(crew)

    assert developed.hold is Hold.STRONG
    assert developed.rep.rep == 0


def test_develop_crew_pays_coin_to_raise_tier_from_strong_hold():
    crew = _crew(hold=Hold.STRONG, rep=RepTrack(rep=12), coin=8)

    developed = develop_crew(crew)

    assert developed.tier == 1
    assert developed.hold is Hold.WEAK
    assert developed.coin == 0


def test_develop_crew_refuses_without_enough_coin():
    crew = _crew(hold=Hold.STRONG, rep=RepTrack(rep=12), coin=0)

    with pytest.raises(EngineError):
        develop_crew(crew)


def test_mark_playbook_xp_clamps_to_the_track_segments():
    # SRD: "PC Advancement" - marking xp boxes (FR-28 sheet interaction).
    character = _character(playbook_xp=XpTrack(marked=7, segments=8))

    marked = mark_playbook_xp(character, 3)

    assert marked.playbook_xp.marked == 8


def test_mark_playbook_xp_floors_at_zero():
    character = _character(playbook_xp=XpTrack(marked=1, segments=8))

    cleared = mark_playbook_xp(character, -3)

    assert cleared.playbook_xp.marked == 0


def test_mark_attribute_xp_only_touches_the_named_attribute():
    character = _character()

    marked = mark_attribute_xp(character, Attribute.PROWESS, 2)

    assert marked.attribute_xp[Attribute.PROWESS].marked == 2
    assert marked.attribute_xp[Attribute.INSIGHT].marked == 0


def test_adjust_coin_gains_and_spends():
    # SRD: "Coin and Stash".
    character = _character(coin=2)

    gained = adjust_coin(character, 2)
    spent = adjust_coin(gained, -3)

    assert gained.coin == 4
    assert spent.coin == 1


def test_adjust_coin_refuses_to_go_negative():
    character = _character(coin=1)

    with pytest.raises(EngineError):
        adjust_coin(character, -2)


def test_adjust_coin_refuses_to_exceed_four_coin_capacity():
    with pytest.raises(EngineError, match="at most 4 coin"):
        adjust_coin(_character(coin=4), 1)


def test_set_item_carried_toggles_and_recomputes_load():
    # SRD: "Loadout" - "checking the box for the item you want to use...
    # your load also determines your movement speed".
    character = _character(
        items=[
            CharacterItem(item_id="lockpicks"),
            CharacterItem(item_id="pistol"),
        ]
    )

    with_lockpicks = set_item_carried(character, "lockpicks", True)
    assert with_lockpicks.load == 1
    assert next(i for i in with_lockpicks.items if i.item_id == "lockpicks").carried

    with_both = set_item_carried(with_lockpicks, "pistol", True)
    assert with_both.load == 2

    dropped = set_item_carried(with_both, "lockpicks", False)
    assert dropped.load == 1


def test_set_item_carried_refuses_an_unknown_item():
    character = _character()

    with pytest.raises(EngineError):
        set_item_carried(character, "not-an-item", True)


def test_use_armor_marks_the_matching_box():
    # SRD: "Armor" - "you can mark an armor box to reduce or avoid a
    # consequence, instead of rolling to resist".
    character = _character(armor={"has_armor": True, "has_heavy_armor": True})

    used = use_armor(character, "standard")
    assert used.armor.armor_used
    assert not used.armor.heavy_armor_used

    both = use_armor(used, "heavy")
    assert both.armor.heavy_armor_used


def test_use_armor_refuses_an_unknown_armor_type():
    with pytest.raises(InvalidArmorTypeError):
        use_armor(_character(armor={"has_armor": True}), "ceramic")


def test_use_armor_refuses_a_box_already_marked():
    # SRD: "Armor" - "When an armor box is marked, it can't be used again
    # until it's restored."
    character = _character(armor={"has_armor": True, "armor_used": True})

    with pytest.raises(EngineError):
        use_armor(character, "standard")


def test_restore_armor_clears_every_marked_box():
    # SRD: "Armor" - "All of your armor is restored when you choose your
    # load for the next score."
    character = _character(
        armor={
            "has_armor": True,
            "has_special_armor": True,
            "armor_used": True,
            "special_armor_used": True,
        }
    )

    restored = restore_armor(character)

    assert not restored.armor.armor_used
    assert not restored.armor.special_armor_used


def test_adjust_stash_gains_and_removes():
    # SRD: "Stash & Retirement" - "Put coin in your character's stash...
    # If you want to pull coin out of your stash, you may do so, at a cost."
    character = _character(stash=4)

    gained = adjust_stash(character, 3)
    removed = adjust_stash(gained, -2)

    assert gained.stash == 7
    assert removed.stash == 5


def test_adjust_stash_refuses_to_go_negative():
    with pytest.raises(EngineError):
        adjust_stash(_character(stash=1), -2)


def test_adjust_stash_clamps_at_the_tracker_maximum():
    # SRD: "Stash & Retirement" - the tracker's best outcome is "Stash 40:
    # Fine."; there is nothing beyond the 40th box to mark.
    character = _character(stash=39)

    assert adjust_stash(character, 5).stash == 40


def test_set_load_level_declares_the_load_for_the_score():
    # SRD: "Loadout" - "For each operation, decide what your character's
    # load will be."
    character = set_load_level(_character(), LoadLevel.HEAVY)

    assert character.load_level is LoadLevel.HEAVY


def test_set_load_level_refuses_a_level_below_the_current_load():
    # SRD: "Loadout" - "1-3 load: Light"; four carried items cannot fit a
    # light load, and the engine refuses rather than dropping items.
    character = _character(
        load=4,
        items=[CharacterItem(item_id=f"item-{i}", carried=True) for i in range(4)],
    )

    with pytest.raises(EngineError):
        set_load_level(character, LoadLevel.LIGHT)


def test_set_item_carried_refuses_past_the_load_limit():
    # SRD: "Loadout" - "you may say that your character has an item on
    # hand... up to a number of items equal to your chosen load."
    character = _character(
        load_level=LoadLevel.LIGHT,
        load=3,
        items=[
            CharacterItem(item_id="lockpicks", carried=True),
            CharacterItem(item_id="pistol", carried=True),
            CharacterItem(item_id="rope", carried=True),
            CharacterItem(item_id="lantern"),
        ],
    )

    with pytest.raises(EngineError):
        set_item_carried(character, "lantern", True)


def test_adjust_crew_turf_caps_at_the_srd_maximum():
    # SRD: "Turf" - "You can hold a maximum of 6 turf."
    crew = _crew()

    assert adjust_crew_turf(crew, 8).rep.turf == 6
    assert adjust_crew_turf(crew, -1).rep.turf == 0


def test_set_claim_controlled_seizes_and_loses_an_existing_claim():
    # SRD: "Seizing a claim" / "Losing a claim".
    crew = _crew(claims=[Claim(id="docks", name="The Docks", is_turf=True)])

    seized = set_claim_controlled(crew, "docks", True)
    assert seized.claims[0].controlled
    assert seized.rep.turf == 1  # SRD: "Some claims count as turf."

    lost = set_claim_controlled(seized, "docks", False)
    assert not lost.claims[0].controlled
    assert lost.rep.turf == 0


def test_set_claim_controlled_adds_a_named_claim_not_on_the_map():
    # SRD: "Claims" - "you may... even seek out a special claim not on
    # your map"; recording it needs an explicit name, never a guess.
    crew = set_claim_controlled(_crew(), "vice-den", True, name="Undertow Vice Den", is_turf=False)

    assert crew.claims[0].name == "Undertow Vice Den"
    assert crew.rep.turf == 0


def test_set_claim_controlled_refuses_an_unknown_claim_without_a_name():
    with pytest.raises(EngineError):
        set_claim_controlled(_crew(), "nope", True)


def test_set_claim_controlled_refuses_a_no_op_toggle():
    crew = _crew(claims=[Claim(id="docks", name="The Docks")])

    with pytest.raises(EngineError):
        set_claim_controlled(crew, "docks", False)
