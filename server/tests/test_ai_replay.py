from datetime import UTC, datetime

from ai.replay import replay_state
from ai.tools import GameState
from engine.character import Character
from engine.crew import Crew
from engine.session import CampaignPhase, Session

AT = datetime(2026, 1, 1, tzinfo=UTC)


def _base_state() -> GameState:
    return GameState(
        character=Character(name="Scoundrel", playbook="Cutter"),
        crew=Crew(name="The Fifth Foxglove", crew_type="Assassins"),
        session=Session(),
    )


def test_replay_state_folds_stress_and_harm_onto_the_base_character():
    base = _base_state()
    log = base.log
    log = log.append("character", "Scoundrel", "stress_marked", {"amount": 3}, AT)
    log = log.append("character", "Scoundrel", "harm_marked", {"level": 2, "name": "Stabbed"}, AT)

    replayed = replay_state(base, log.events)

    assert replayed.character.stress.marked == 3
    assert replayed.character.harm.entries[-1].name == "Stabbed"


def test_replay_state_folds_clock_creation_and_ticks():
    base = _base_state()
    log = base.log
    log = log.append(
        "clock", "alert", "clock_created", {"name": "Alert", "kind": "danger", "segments": 4}, AT
    )
    log = log.append("clock", "alert", "clock_ticked", {"amount": 2}, AT)

    replayed = replay_state(base, log.events)

    assert replayed.clocks["alert"].filled == 2


def test_replay_state_folds_phase_transitions():
    base = _base_state()
    log = base.log.append("session", "current", "phase_transitioned", {"phase": "score"}, AT)

    replayed = replay_state(base, log.events)

    assert replayed.session.phase is CampaignPhase.SCORE


def test_replay_state_skips_pure_record_events():
    # action_roll/fortune_roll/resistance_roll/player_message/narration/
    # x_card_invoked carry no state to fold - only the log should reflect
    # them.
    base = _base_state()
    log = base.log.append("session", "current", "player_message", {"text": "I look around."}, AT)

    replayed = replay_state(base, log.events)

    assert replayed.character == base.character
    assert len(replayed.log.events) == 1


def test_replay_state_folds_session_zero_configuration_and_canon():
    # FR-17/FR-36: undo/rewind must not silently drop session-zero data
    # when replaying past it.
    base = _base_state()
    log = base.log
    log = log.append(
        "session",
        "current",
        "session_zero_configured",
        {"lines": ["no animal harm"], "veils": ["torture"], "tone": "pulpy noir"},
        AT,
    )
    log = log.append(
        "canon",
        "Harrow's Reach",
        "canon_set",
        {
            "setting_name": "Harrow's Reach",
            "tone": "rain-soaked industrial",
            "factions": ["The Rustworks Combine"],
            "locations": ["The Sunken Market"],
            "facts": [],
        },
        AT,
    )

    replayed = replay_state(base, log.events)

    assert replayed.session_zero.lines == ["no animal harm"]
    assert replayed.canon.setting_name == "Harrow's Reach"
    assert replayed.canon.factions == ["The Rustworks Combine"]


def test_replay_state_folds_newly_discovered_locations_onto_canon():
    # FR-15: the map grows during play - undo/rewind must not drop a
    # location discovered after session zero.
    base = _base_state()
    log = base.log
    log = log.append(
        "canon",
        "Harrow's Reach",
        "canon_set",
        {
            "setting_name": "Harrow's Reach",
            "tone": None,
            "factions": [],
            "locations": ["The Sunken Market"],
            "facts": [],
        },
        AT,
    )
    log = log.append(
        "canon", "Harrow's Reach", "canon_location_added", {"location": "The Old Quarter"}, AT
    )

    replayed = replay_state(base, log.events)

    assert replayed.canon.locations == ["The Sunken Market", "The Old Quarter"]


def test_replay_state_reproduces_a_truncated_prefix_of_the_log():
    # This is the mechanism undo/rewind is built on: replaying only a
    # prefix of the log reconstructs state as of that earlier point.
    base = _base_state()
    log = base.log
    log = log.append("character", "Scoundrel", "stress_marked", {"amount": 2}, AT)
    log = log.append("character", "Scoundrel", "coin_adjusted", {"amount": 5}, AT)

    prefix = [e for e in log.events if e.sequence == 1]
    replayed = replay_state(base, prefix)

    assert replayed.character.stress.marked == 2
    assert replayed.character.coin == 0
