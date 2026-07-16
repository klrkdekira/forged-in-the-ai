import pytest

from engine.character import Attribute, Character, CharacterItem, XpTrack
from engine.crew import Crew
from engine.crew_mechanics import Hold, RepTrack
from engine.errors import EngineError
from engine.operations import (
    InvalidTraumaConditionError,
    add_heat,
    adjust_coin,
    adjust_crew_coin,
    adjust_crew_rep,
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
    set_item_carried,
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
    crew = _crew(coin=2)

    crew = adjust_crew_coin(crew, 3)
    assert crew.coin == 5

    crew = adjust_crew_coin(crew, -4)
    assert crew.coin == 1


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
