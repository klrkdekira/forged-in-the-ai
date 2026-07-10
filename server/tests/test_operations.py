import pytest

from engine.character import Character
from engine.crew import Crew
from engine.crew_mechanics import Hold, RepTrack
from engine.errors import EngineError
from engine.operations import (
    InvalidTraumaConditionError,
    add_heat,
    develop_crew,
    flashback,
    heal_character,
    mark_harm,
    mark_stress,
    mark_trauma,
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
