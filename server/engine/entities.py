from pydantic import BaseModel, Field

from engine.crew_mechanics import Hold


class Faction(BaseModel):
    """SPECIFICATION.md §5: "Faction". Status with the crew is a
    Relationship edge (FR-33), not a field here."""

    id: str
    name: str
    tier: int = 0
    hold: Hold = Hold.STRONG
    clock_ids: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)
    notable_npc_ids: list[str] = Field(default_factory=list)
    notes: str | None = None


class Npc(BaseModel):
    """SPECIFICATION.md §5: "NPC / Location / Item: lightweight entities
    with tags and the fiction established about them"."""

    id: str
    name: str
    tags: list[str] = Field(default_factory=list)
    faction_id: str | None = None
    notes: str | None = None


class Location(BaseModel):
    id: str
    name: str
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None


class ItemEntity(BaseModel):
    """A specific in-fiction item instance, distinct from `packs.Item`
    (a catalog entry describing an item type generically)."""

    id: str
    name: str
    tags: list[str] = Field(default_factory=list)
    owner_id: str | None = None
    notes: str | None = None


class Score(BaseModel):
    """SPECIFICATION.md §5: "Score" - FR-4's score loop fields."""

    id: str
    target: str
    plan_type: str | None = None
    plan_detail: str | None = None
    engagement_result: str | None = None
    payoff: int | None = None
    heat_gained: int | None = None
    entanglement: str | None = None
