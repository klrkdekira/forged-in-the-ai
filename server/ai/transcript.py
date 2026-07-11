from engine.events import EventLog

_SPEAKER_BY_EVENT_TYPE = {"player_message": "Player", "narration": "GM"}


def render_transcript(log: EventLog) -> list[str]:
    """FR-15/FR-18: the conversation so far, derived from the persisted
    event log rather than held in memory on the agent instance - so a
    resumed campaign's GM turn is assembled exactly the same way a live
    one's is, with no separate recap step needed. Still budgeted, not a
    full replay: `assemble_turn_context`'s transcript budget applies to
    the result the same as it always did (NFR-4).

    A `player_message` event's payload may carry a `speaker` override
    (FR-35: an AI companion's roleplay line, logged under its own
    character rather than "Player") - falls back to the human/GM default
    when absent, so every pre-existing event still renders unchanged."""
    lines = []
    for event in sorted(log.events, key=lambda e: e.sequence):
        default_speaker = _SPEAKER_BY_EVENT_TYPE.get(event.event_type)
        if default_speaker is None:
            continue
        speaker = event.payload.get("speaker", default_speaker)
        lines.append(f"{speaker}: {event.payload['text']}")
    return lines
