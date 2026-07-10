from ai.context import CanonSection
from ai.tools import GameState
from engine.character import render_markdown as render_character
from engine.crew import render_markdown as render_crew


def render_canon(state: GameState) -> list[CanonSection]:
    """FR-15: the campaign's established world state, as canon sections
    for `assemble_turn_context`. Character and crew are highest priority
    (always kept); clocks and NPCs are dropped first if the canon budget
    is tight."""
    sections = [
        CanonSection(title="Character", text=render_character(state.character), priority=2),
        CanonSection(title="Crew", text=render_crew(state.crew), priority=2),
    ]

    if state.clocks:
        clock_lines = [
            f"- {clock.name} ({clock.kind.value}): {clock.filled}/{clock.segments}"
            for clock in state.clocks.values()
        ]
        sections.append(
            CanonSection(title="Active clocks", text="\n".join(clock_lines), priority=1)
        )

    if state.npcs:
        npc_lines = [
            f"- {npc.name}: {', '.join(npc.tags) or 'no tags yet'}" for npc in state.npcs.values()
        ]
        sections.append(CanonSection(title="Known NPCs", text="\n".join(npc_lines), priority=1))

    if state.faction_statuses:
        status_lines = [
            f"- {faction_id}: {status.status:+d}"
            for faction_id, status in state.faction_statuses.items()
        ]
        sections.append(
            CanonSection(title="Faction status", text="\n".join(status_lines), priority=1)
        )

    return sections
