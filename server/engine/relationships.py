from enum import StrEnum

from pydantic import BaseModel, Field


class RelationshipKind(StrEnum):
    """SPECIFICATION.md §5: "Relationship" - "a type (ally, rival, debt,
    romance, vendetta)"."""

    ALLY = "ally"
    RIVAL = "rival"
    DEBT = "debt"
    ROMANCE = "romance"
    VENDETTA = "vendetta"


class Relationship(BaseModel):
    """An edge between any two entities. `history` is a list of event
    sequence numbers (engine.events.Event.sequence) - "every change
    references the event that caused it"."""

    subject_type: str
    subject_id: str
    object_type: str
    object_id: str
    kind: RelationshipKind
    status: str | None = None
    history: list[int] = Field(default_factory=list)

    def with_event(self, sequence: int) -> "Relationship":
        return self.model_copy(update={"history": [*self.history, sequence]})

    def updated(
        self, kind: "RelationshipKind", status: str | None, sequence: int
    ) -> "Relationship":
        """FR-33: the AI records relationship changes as they happen in
        the fiction - a betrayal, a favour owed, a new contact - by
        setting kind/status again, same as `with_event` but for when the
        relationship itself changed, not just something referencing it."""
        return self.model_copy(
            update={"kind": kind, "status": status, "history": [*self.history, sequence]}
        )


class FactionStatus(BaseModel):
    """SPECIFICATION.md §5: "Faction status with the crew (-3 to +3) as a
    typed special case" of Relationship - a crew-to-faction edge with a
    bounded integer status rather than the free-form kind/status above."""

    crew_id: str
    faction_id: str
    status: int = Field(default=0, ge=-3, le=3)
    history: list[int] = Field(default_factory=list)

    def changed(self, delta: int, sequence: int) -> "FactionStatus":
        new_status = max(-3, min(3, self.status + delta))
        return self.model_copy(update={"status": new_status, "history": [*self.history, sequence]})
