from engine.events import EventLog

_SPEAKER_BY_EVENT_TYPE = {"player_message": "Player", "narration": "GM"}


def render_transcript(log: EventLog) -> list[str]:
    """FR-15/FR-18: the conversation so far, derived from the persisted
    event log rather than held in memory on the agent instance - so a
    resumed campaign's GM turn is assembled exactly the same way a live
    one's is, with no separate recap step needed. Still budgeted, not a
    full replay: `assemble_turn_context`'s transcript budget applies to
    the result the same as it always did (NFR-4)."""
    lines = []
    for event in sorted(log.events, key=lambda e: e.sequence):
        speaker = _SPEAKER_BY_EVENT_TYPE.get(event.event_type)
        if speaker is not None:
            lines.append(f"{speaker}: {event.payload['text']}")
    return lines
