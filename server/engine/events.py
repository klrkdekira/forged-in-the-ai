from datetime import datetime

from pydantic import BaseModel, Field


class Event(BaseModel):
    """FR-19/FR-31: an append-only, entity-tagged record of one state
    change. `occurred_at` is supplied by the caller (an injected clock) -
    the engine never calls datetime.now() itself (CLAUDE.md)."""

    sequence: int
    entity_type: str
    entity_id: str
    event_type: str
    payload: dict = Field(default_factory=dict)
    occurred_at: datetime


class EventLog(BaseModel):
    """SPECIFICATION.md §7 "Event-sourced state": append-only; snapshots
    are caches, not sources of truth. Immutable: `append` returns a new
    EventLog, so replaying the same sequence of appends is deterministic
    (NFR-1) rather than depending on mutation order."""

    events: list[Event] = Field(default_factory=list)

    def append(
        self,
        entity_type: str,
        entity_id: str,
        event_type: str,
        payload: dict,
        occurred_at: datetime,
    ) -> "EventLog":
        event = Event(
            sequence=len(self.events) + 1,
            entity_type=entity_type,
            entity_id=entity_id,
            event_type=event_type,
            payload=payload,
            occurred_at=occurred_at,
        )
        return EventLog(events=[*self.events, event])

    def for_entity(self, entity_type: str, entity_id: str) -> list[Event]:
        return [
            event
            for event in self.events
            if event.entity_type == entity_type and event.entity_id == entity_id
        ]

    def to_jsonl(self) -> str:
        """NFR-5 portability contract: one JSON object per line."""
        return "\n".join(event.model_dump_json() for event in self.events)

    @classmethod
    def from_jsonl(cls, text: str) -> "EventLog":
        events = [Event.model_validate_json(line) for line in text.splitlines() if line.strip()]
        return cls(events=events)
