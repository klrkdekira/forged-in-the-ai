import random
from datetime import UTC, datetime

import pytest

from ai.tools import (
    AddCanonFactArgs,
    ApplyHarmArgs,
    CreateClockArgs,
    CreateNpcArgs,
    GameState,
    InvokeXCardArgs,
    MarkStressArgs,
    RollActionArgs,
    RollFortuneArgs,
    RollResistanceArgs,
    TickClockArgs,
    ToolExecutor,
    TransitionPhaseArgs,
    UpdateFactionStatusArgs,
    tool_definitions,
)
from engine.campaign import CampaignCanon
from engine.character import Action, Attribute, Character
from engine.clocks import ClockKind
from engine.crew import Crew
from engine.rolls import Effect, Position
from engine.session import CampaignPhase, Session

AT = datetime(2026, 1, 1, tzinfo=UTC)


def _state() -> GameState:
    return GameState(
        character=Character(
            name="Test",
            playbook="Test Playbook",
            action_ratings={Action.PROWL: 2},
        ),
        crew=Crew(name="Test Crew", crew_type="Test Type"),
        session=Session(),
    )


def _executor(seed: int = 1) -> ToolExecutor:
    return ToolExecutor(rng=random.Random(seed), clock=lambda: AT)


def test_tool_definitions_cover_every_registered_tool():
    # FR-12: an OpenAI-compatible tools payload.
    definitions = tool_definitions()

    names = {d["function"]["name"] for d in definitions}
    assert names == {
        "roll_action",
        "roll_fortune",
        "roll_resistance",
        "create_clock",
        "tick_clock",
        "apply_harm",
        "mark_stress",
        "transition_phase",
        "create_npc",
        "update_faction_status",
        "add_canon_fact",
        "invoke_x_card",
    }
    assert all("parameters" in d["function"] for d in definitions)


def test_roll_action_uses_the_character_action_rating_and_logs_it():
    result = _executor().roll_action(
        _state(),
        RollActionArgs(action=Action.PROWL, position=Position.RISKY, effect=Effect.STANDARD),
    )

    assert result.result["position"] == "risky"
    assert result.state.log.events[-1].event_type == "action_roll"
    assert result.state.log.events[-1].occurred_at == AT


def test_roll_fortune_logs_an_event():
    result = _executor().roll_fortune(_state(), RollFortuneArgs(pool_size=2))

    assert result.state.log.events[-1].event_type == "fortune_roll"


def test_roll_resistance_uses_the_character_attribute_rating():
    state = _state()
    result = _executor().roll_resistance(state, RollResistanceArgs(attribute=Attribute.PROWESS))

    assert "stress_delta" in result.result


def test_create_clock_then_tick_clock():
    state = (
        _executor()
        .create_clock(
            _state(),
            CreateClockArgs(clock_id="alert", name="Alert", kind=ClockKind.DANGER, segments=4),
        )
        .state
    )

    result = _executor(seed=2).tick_clock(state, TickClockArgs(clock_id="alert", amount=2))

    assert result.state.clocks["alert"].filled == 2
    assert result.state.log.events[-1].event_type == "clock_ticked"


def test_apply_harm_updates_the_character_and_reports_catastrophe():
    result = _executor().apply_harm(_state(), ApplyHarmArgs(level=4, name="Stabbed in the Heart"))

    assert result.result["catastrophic"]
    assert result.state.character.harm.entries == []


def test_mark_stress_updates_the_character():
    result = _executor().mark_stress(_state(), MarkStressArgs(amount=3))

    assert result.state.character.stress.marked == 3
    assert not result.result["triggered_trauma"]


def test_transition_phase_moves_the_session_forward():
    result = _executor().transition_phase(_state(), TransitionPhaseArgs(phase=CampaignPhase.SCORE))

    assert result.state.session.phase is CampaignPhase.SCORE


def test_transition_phase_refuses_an_illegal_transition():
    from engine.session import InvalidPhaseTransitionError

    with pytest.raises(InvalidPhaseTransitionError):
        _executor().transition_phase(_state(), TransitionPhaseArgs(phase=CampaignPhase.DOWNTIME))


def test_create_npc_adds_it_to_state():
    # SPECIFICATION.md §5: "NPC ... lightweight entities with tags"
    result = _executor().create_npc(
        _state(), CreateNpcArgs(npc_id="n1", name="Test NPC", tags=["informant"])
    )

    assert result.state.npcs["n1"].name == "Test NPC"
    assert result.state.log.events[-1].event_type == "npc_created"


def test_update_faction_status_starts_from_neutral_and_applies_delta():
    # SRD: "Faction Status" - "zero (neutral) being the default"
    result = _executor().update_faction_status(
        _state(), UpdateFactionStatusArgs(faction_id="f1", delta=-2)
    )

    assert result.result["status"] == -2
    assert result.state.faction_statuses["f1"].history == [1]


def test_update_faction_status_accumulates_across_calls():
    executor = _executor()
    state = executor.update_faction_status(
        _state(), UpdateFactionStatusArgs(faction_id="f1", delta=-1)
    ).state

    result = executor.update_faction_status(
        state, UpdateFactionStatusArgs(faction_id="f1", delta=-1)
    )

    assert result.result["status"] == -2
    assert result.state.faction_statuses["f1"].history == [1, 2]


def test_add_canon_fact_grows_the_campaign_canon():
    # FR-36: the session-zero-generated setting grows during play.
    state = _state().model_copy(update={"canon": CampaignCanon(setting_name="Test City")})

    result = _executor().add_canon_fact(state, AddCanonFactArgs(fact="The docks are haunted."))

    assert result.state.canon.facts == ["The docks are haunted."]


def test_add_canon_fact_refuses_without_canon_set():
    with pytest.raises(ValueError, match="no campaign canon"):
        _executor().add_canon_fact(_state(), AddCanonFactArgs(fact="anything"))


def test_invoke_x_card_logs_an_event():
    # FR-17: safety-tool command, logged but not narratively resolved here.
    result = _executor().invoke_x_card(_state(), InvokeXCardArgs(note="pacing check"))

    assert result.result["acknowledged"]
    assert result.state.log.events[-1].event_type == "x_card_invoked"
    assert result.state.log.events[-1].payload["note"] == "pacing check"


def test_tool_calls_are_deterministic_for_the_same_seed():
    args = RollActionArgs(action=Action.PROWL, position=Position.RISKY, effect=Effect.STANDARD)

    first = _executor(seed=9).roll_action(_state(), args)
    second = _executor(seed=9).roll_action(_state(), args)

    assert first.result == second.result
