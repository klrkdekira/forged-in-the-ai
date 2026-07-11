from ai.tools import GameState


def render_recap(state: GameState) -> str:
    """FR-20: a human-readable session export ("the story so far"), built
    from the same player_message/narration events FR-18's resume context
    already relies on (ai/transcript.py) - the play-by-play text the GM
    actually narrated, not a mechanical audit log (that's the Journal
    view/FR-31's job, already covering rolls/clocks/harm in full detail)."""
    lines = [f"# {state.crew.name}", f"*{state.character.name}, {state.character.playbook}*", ""]

    turns = [
        event
        for event in sorted(state.log.events, key=lambda e: e.sequence)
        if event.event_type in ("player_message", "narration")
    ]
    if not turns:
        lines.append("*The story hasn't started yet.*")
        return "\n".join(lines)

    for event in turns:
        text = event.payload["text"]
        lines.append(f"> {text}" if event.event_type == "player_message" else text)
        lines.append("")

    return "\n".join(lines)
