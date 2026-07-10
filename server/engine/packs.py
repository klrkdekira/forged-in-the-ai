
from pydantic import BaseModel, Field


class SpecialAbility(BaseModel):
    id: str = Field(..., description="Unique identifier for the ability (e.g., 'battleborn')")
    name: str = Field(..., description="Display name")
    description: str = Field(..., description="Full rules text")
    tags: list[str] = Field(default_factory=list, description="Categories like 'combat', 'stealth'")

class Item(BaseModel):
    id: str = Field(..., description="Unique identifier for the item")
    name: str = Field(..., description="Display name")
    description: str | None = Field(None, description="Item rules or description")
    load: int = Field(default=1, description="Load cost. 0 means italicized/0 load.")
    tags: list[str] = Field(default_factory=list)

class Reputation(BaseModel):
    id: str
    name: str
    description: str | None = None

class Trauma(BaseModel):
    id: str
    name: str
    description: str

class Vice(BaseModel):
    id: str
    name: str
    description: str

class CrewUpgrade(BaseModel):
    id: str
    name: str
    description: str
    cost: int = Field(default=1, description="Number of upgrade boxes required")

class RollResult(BaseModel):
    level: str = Field(..., description="E.g., '1-3', '4/5', '6', 'critical'")
    description: str

class PositionRoll(BaseModel):
    position: str = Field(..., description="controlled, risky, desperate")
    results: list[RollResult]

class HeatPenalty(BaseModel):
    condition: str
    heat_added: int

class EntanglementEntry(BaseModel):
    heat_band: str = Field(..., description="'0-3', '4-5', '6'")
    roll_result: str = Field(..., description="'1-3', '4-5', '6'")
    entanglement: str

class ContentPack(BaseModel):
    id: str
    name: str
    description: str
    version: str
    special_abilities: list[SpecialAbility] = Field(default_factory=list)
    items: list[Item] = Field(default_factory=list)
    reputations: list[Reputation] = Field(default_factory=list)
    traumas: list[Trauma] = Field(default_factory=list)
    vices: list[Vice] = Field(default_factory=list)
    crew_upgrades: list[CrewUpgrade] = Field(default_factory=list)
    action_outcomes: list[PositionRoll] = Field(default_factory=list)
    heat_penalties: list[HeatPenalty] = Field(default_factory=list)
    entanglements: list[EntanglementEntry] = Field(default_factory=list)
