import pytest

from engine.advancement import (
    AdvancementError,
    advance_action_rating,
    advance_crew_special_ability,
    advance_crew_upgrades,
    advance_special_ability,
    crew_profit_share,
    earns_desperate_roll_xp,
    xp_attribute_for_action,
)
from engine.character import Action, Attribute, Character, XpTrack
from engine.crew import Crew
from engine.rolls import Position


def _character(**overrides) -> Character:
    return Character(name="Test", playbook="Test Playbook", **overrides)


def test_xp_attribute_for_action_matches_the_srd_grouping():
    # SRD: "roll a desperate Skirmish action, you mark xp in Prowess"
    assert xp_attribute_for_action(Action.SKIRMISH) is Attribute.PROWESS


def test_earns_desperate_roll_xp_only_on_desperate():
    # SRD: "PC Advancement" - "When you make a desperate action roll, mark
    # 1 xp in the attribute for the action you rolled."
    for position in Position:
        assert earns_desperate_roll_xp(position is Position.DESPERATE) == (
            position is Position.DESPERATE
        )


def test_advance_action_rating_requires_a_full_track():
    character = _character()

    with pytest.raises(AdvancementError):
        advance_action_rating(character, Action.SKIRMISH)


def test_advance_action_rating_adds_a_dot_and_resets_the_track():
    # SRD: "PC Advancement" - "When you fill an xp track... take an
    # advance... add an additional action dot."
    character = _character(
        action_ratings={Action.SKIRMISH: 1},
        attribute_xp={Attribute.PROWESS: XpTrack(marked=6, segments=6)},
    )

    advanced = advance_action_rating(character, Action.SKIRMISH)

    assert advanced.action_ratings[Action.SKIRMISH] == 2
    assert advanced.attribute_xp[Attribute.PROWESS].marked == 0


def test_advance_action_rating_refuses_past_the_cap():
    character = _character(
        action_ratings={Action.SKIRMISH: 3},
        attribute_xp={Attribute.PROWESS: XpTrack(marked=6, segments=6)},
    )

    with pytest.raises(AdvancementError):
        advance_action_rating(character, Action.SKIRMISH, cap=3)


def test_advance_special_ability_requires_a_full_playbook_track():
    with pytest.raises(AdvancementError):
        advance_special_ability(_character(), "battleborn")


def test_advance_special_ability_adds_it_and_resets_the_track():
    character = _character(playbook_xp=XpTrack(marked=8, segments=8))

    advanced = advance_special_ability(character, "battleborn")

    assert advanced.special_ability_ids == ["battleborn"]
    assert advanced.playbook_xp.marked == 0


def test_crew_profit_share_is_tier_plus_two():
    # SRD: "Profits" - "each PC gets stash equal to the crew Tier+2"
    assert crew_profit_share(crew_tier=1) == 3


def test_advance_crew_special_ability_requires_full_crew_xp():
    crew = Crew(name="Test Crew", crew_type="Test Type")

    with pytest.raises(AdvancementError):
        advance_crew_special_ability(crew, "fleet_footed")


def test_advance_crew_upgrades_marks_two_boxes():
    # SRD: "Crew Advancement" - "mark two crew upgrade boxes"
    crew = Crew(name="Test Crew", crew_type="Test Type", xp=XpTrack(marked=8, segments=8))

    advanced = advance_crew_upgrades(crew, ("way_stations", "quality"))

    assert advanced.upgrade_ids == ["way_stations", "quality"]
    assert advanced.xp.marked == 0
