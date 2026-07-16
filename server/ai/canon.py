from ai.context import CanonSection
from ai.tools import GameState
from engine.character import render_markdown as render_character
from engine.crew import render_markdown as render_crew


def render_canon(state: GameState) -> list[CanonSection]:
    """FR-15: the campaign's established world state, as canon sections
    for `assemble_turn_context`. Character and crew are highest priority
    (always kept); clocks and NPCs are dropped first if the canon budget
    is tight."""
    sections = []

    if state.session_zero is not None:
        lines = [
            f"Lines: {', '.join(state.session_zero.lines) or 'none stated'}",
            f"Veils: {', '.join(state.session_zero.veils) or 'none stated'}",
        ]
        if state.session_zero.tone:
            lines.append(f"Tone: {state.session_zero.tone}")
        sections.append(CanonSection(title="Safety agreements", text="\n".join(lines), priority=2))

    if state.canon is not None:
        canon_lines = [f"**{state.canon.setting_name}**"]
        if state.canon.tone:
            canon_lines.append(f"*{state.canon.tone}*")
        canon_lines.append(f"Factions: {', '.join(state.canon.factions) or 'none yet'}")
        canon_lines.append(f"Locations: {', '.join(state.canon.locations) or 'none yet'}")
        if state.canon.facts:
            canon_lines.append("Established facts:")
            canon_lines.extend(f"- {fact}" for fact in state.canon.facts)
        sections.append(CanonSection(title="Setting", text="\n".join(canon_lines), priority=2))

    sections.append(
        CanonSection(title="Character", text=render_character(state.character), priority=2)
    )
    sections.append(CanonSection(title="Crew", text=render_crew(state.crew), priority=2))

    if state.scores:
        score_lines = []
        for score in state.scores.values():
            line = f"- {score.target}"
            if score.plan_type:
                line += f" ({score.plan_type})"
            details = []
            if score.engagement_result:
                details.append(f"engagement: {score.engagement_result}")
            if score.payoff is not None:
                details.append(f"payoff: {score.payoff} coin")
            if score.heat_gained is not None:
                details.append(f"heat: {score.heat_gained}")
            if score.entanglement:
                details.append(f"entanglement: {score.entanglement}")
            if details:
                line += " - " + ", ".join(details)
            score_lines.append(line)
        sections.append(CanonSection(title="Active score", text="\n".join(score_lines), priority=1))

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

    if state.relationships:
        relationship_lines = [
            f"- {r.subject_id} -> {r.object_id}: {r.kind.value}"
            + (f" ({r.status})" if r.status else "")
            for r in state.relationships.values()
        ]
        sections.append(
            CanonSection(title="Relationships", text="\n".join(relationship_lines), priority=1)
        )

    return sections
