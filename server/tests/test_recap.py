from datetime import UTC, datetime

from ai.recap import render_recap
from ai.tools import GameState
from engine.character import Character
from engine.crew import Crew
from engine.session import Session

AT = datetime(2026, 1, 1, tzinfo=UTC)


def _state() -> GameState:
    return GameState(
        character=Character(name="Scoundrel", playbook="Cutter"),
        crew=Crew(name="The Fifth Foxglove", crew_type="Assassins"),
        session=Session(),
    )


def test_render_recap_notes_the_story_has_not_started_yet_for_an_empty_log():
    recap = render_recap(_state())
    assert "The Fifth Foxglove" in recap
    assert "hasn't started yet" in recap


def test_render_recap_renders_player_and_gm_turns_in_order():
    state = _state()
    log = state.log
    log = log.append("session", "current", "player_message", {"text": "I pick the lock."}, AT)
    log = log.append("character", "Scoundrel", "action_roll", {"band": "success"}, AT)
    log = log.append("session", "current", "narration", {"text": "The door swings open."}, AT)
    state = state.model_copy(update={"log": log})

    recap = render_recap(state)

    assert "> I pick the lock." in recap
    assert "The door swings open." in recap
    assert "action_roll" not in recap  # mechanical events aren't part of the story text
    assert recap.index("I pick the lock.") < recap.index("The door swings open.")
