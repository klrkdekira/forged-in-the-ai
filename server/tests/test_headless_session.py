import random
from datetime import UTC, datetime
from pathlib import Path

from engine.character import Action, Attribute, Character
from engine.crew import Crew
from engine.downtime import indulge_vice_roll
from engine.events import EventLog
from engine.operations import add_heat, heal_character, mark_harm, mark_stress
from engine.pack_loader import load_pack
from engine.rolls import Effect, RollBand, action_roll, resistance_roll
from engine.score import engagement_roll, entanglement_roll, payoff_rep
from engine.session import CampaignPhase, Session

AT = datetime(2026, 1, 1, tzinfo=UTC)
PACK_PATH = Path(__file__).parents[2] / "packs" / "srd_base.json"


def _run_session(seed: int) -> tuple[Character, Crew, EventLog, Session]:
    """One full score-and-downtime loop (FR-4), engine-only, no AI: plan,
    engagement, an action roll and its consequence, payoff, heat and
    entanglement, then downtime (recover, indulge vice). Every step is
    logged, so the whole session replays deterministically (NFR-1)."""
    rng = random.Random(seed)
    pack = load_pack(PACK_PATH)
    log = EventLog()
    session = Session()

    character = Character(
        name="Test Character",
        playbook="Test Playbook",
        action_ratings={Action.PROWL: 2, Action.SKIRMISH: 1},
    )
    crew = Crew(name="Test Crew", crew_type="Test Type", tier=1)

    session = session.transition_to(CampaignPhase.SCORE)
    engagement = engagement_roll(pool_size=1, rng=rng)
    log = log.append("score", "s1", "engagement_roll", engagement.model_dump(mode="json"), AT)

    roll = action_roll(
        character.action_ratings[Action.PROWL], engagement.position, Effect.STANDARD, rng
    )
    log = log.append("character", character.name, "action_roll", roll.model_dump(mode="json"), AT)

    if roll.band is RollBand.BAD:
        mutation = mark_harm(character, 2, "Winded")
        character = mutation.character
        log = log.append(
            "character", character.name, "harm_marked", {"level": 2, "name": "Winded"}, AT
        )

        resistance = resistance_roll(character.attribute_rating(Attribute.PROWESS), rng)
        stress_result = mark_stress(character, resistance.stress_delta)
        character = stress_result.character
        log = log.append(
            "character",
            character.name,
            "stress_marked",
            {"amount": resistance.stress_delta},
            AT,
        )

    session = session.transition_to(CampaignPhase.DOWNTIME)
    rep = payoff_rep(crew_tier=crew.tier, target_tier=crew.tier + 1)
    crew = crew.model_copy(update={"rep": crew.rep.add_rep(rep), "coin": crew.coin + 4})
    log = log.append("crew", crew.name, "payoff", {"rep": rep, "coin": 4}, AT)

    heat_result = add_heat(crew, 4)
    crew = heat_result.crew
    log = log.append("crew", crew.name, "heat_added", {"amount": 4}, AT)

    entanglement = entanglement_roll(crew.wanted_level, crew.heat.heat, pack.entanglements, rng)
    log = log.append(
        "crew", crew.name, "entanglement_roll", entanglement.model_dump(mode="json"), AT
    )

    if character.harm.entries:
        character = heal_character(character)
        log = log.append("character", character.name, "healed", {}, AT)

    vice = indulge_vice_roll(
        character.attribute_rating(Attribute.INSIGHT), character.stress.marked, rng
    )
    stress_result = mark_stress(character, -vice.stress_cleared)
    character = stress_result.character
    log = log.append("character", character.name, "vice_indulged", vice.model_dump(mode="json"), AT)
    session = session.transition_to(CampaignPhase.FREE_PLAY)

    return character, crew, log, session


def test_headless_session_runs_the_full_score_loop():
    character, crew, log, session = _run_session(seed=1)

    event_types = [event.event_type for event in log.events]
    assert "engagement_roll" in event_types
    assert "payoff" in event_types
    assert "entanglement_roll" in event_types
    assert "vice_indulged" in event_types
    assert [event.sequence for event in log.events] == list(range(1, len(log.events) + 1))
    assert crew.coin == 4
    assert session.phase is CampaignPhase.FREE_PLAY


def test_headless_session_is_deterministic_for_the_same_seed():
    # NFR-1: the same seed (and so the same event log) yields the same state.
    first_character, first_crew, first_log, first_session = _run_session(seed=7)
    second_character, second_crew, second_log, second_session = _run_session(seed=7)

    assert first_character == second_character
    assert first_crew == second_crew
    assert first_log == second_log
    assert first_session == second_session


def test_headless_session_can_diverge_on_a_different_seed():
    _, _, log_a, _ = _run_session(seed=1)
    _, _, log_b, _ = _run_session(seed=2)

    assert log_a != log_b


def test_headless_session_log_round_trips_through_jsonl():
    # NFR-5: portability contract for the whole session's log.
    _, _, log, _ = _run_session(seed=3)

    assert EventLog.from_jsonl(log.to_jsonl()) == log
