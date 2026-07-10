from engine.clocks import Clock, ClockKind
from engine.events import Event

# Event types this module knows how to fold into state. Other phases add
# their own entity types and event types here as those entities exist.
CLOCK_CREATED = "clock_created"
CLOCK_TICKED = "clock_ticked"


def replay_clocks(events: list[Event]) -> dict[str, Clock]:
    """FR-19: reconstruct every clock's current state by folding its
    "clock_created"/"clock_ticked" events in sequence order. The same
    event log always replays to the same state (NFR-1)."""
    clocks: dict[str, Clock] = {}
    for event in sorted(events, key=lambda e: e.sequence):
        if event.event_type == CLOCK_CREATED:
            clocks[event.entity_id] = Clock(
                name=event.payload["name"],
                kind=ClockKind(event.payload["kind"]),
                segments=event.payload["segments"],
            )
        elif event.event_type == CLOCK_TICKED:
            clocks[event.entity_id] = clocks[event.entity_id].tick(event.payload["amount"])
    return clocks
