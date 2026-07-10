from ai.canon import render_canon
from ai.tools import GameState
from engine.character import Character
from engine.clocks import Clock, ClockKind
from engine.crew import Crew
from engine.entities import Npc
from engine.relationships import FactionStatus
from engine.session import Session


def _state(**overrides) -> GameState:
    return GameState(
        character=Character(name="Test Character", playbook="Test Playbook"),
        crew=Crew(name="Test Crew", crew_type="Test Type"),
        session=Session(),
        **overrides,
    )


def test_render_canon_always_includes_character_and_crew():
    sections = render_canon(_state())

    titles = {s.title for s in sections}
    assert {"Character", "Crew"} <= titles
    assert next(s for s in sections if s.title == "Character").priority == 2


def test_render_canon_includes_clocks_only_when_present():
    assert not any(s.title == "Active clocks" for s in render_canon(_state()))

    state = _state(clocks={"alert": Clock(name="Alert", kind=ClockKind.DANGER, segments=4)})
    clocks_section = next(s for s in render_canon(state) if s.title == "Active clocks")

    assert "Alert" in clocks_section.text
    assert clocks_section.priority < 2


def test_render_canon_includes_npcs_only_when_present():
    state = _state(npcs={"n1": Npc(id="n1", name="Test NPC", tags=["informant"])})

    npc_section = next(s for s in render_canon(state) if s.title == "Known NPCs")

    assert "Test NPC" in npc_section.text
    assert "informant" in npc_section.text


def test_render_canon_includes_faction_status_only_when_present():
    state = _state(
        faction_statuses={"f1": FactionStatus(crew_id="Test Crew", faction_id="f1", status=-2)}
    )

    status_section = next(s for s in render_canon(state) if s.title == "Faction status")

    assert "-2" in status_section.text
