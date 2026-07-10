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


class MagnitudeLevel(BaseModel):
    """One row (0-6) of the SRD "Magnitude" master table."""

    level: int = Field(..., description="0-6")
    area: str = Field(..., description="Physical space at this level, e.g. 'A city block'")
    scale: str = Field(..., description="Group size at this level, e.g. 'A large gang (20)'")
    duration: str = Field(..., description="Time span at this level, e.g. 'A day'")
    range: str = Field(..., description="Distance at this level, e.g. 'Down the road'")
    quality_tier: str = Field(..., description="Quality/Tier adjective, e.g. 'Superior'")
    force: str = Field(..., description="Force adjective, e.g. 'Powerful'")
    quality_example: str = Field(..., description="Example item/entity at this quality")
    force_example: str = Field(..., description="Example force/effect at this level")


class DowntimeActivity(BaseModel):
    id: str
    name: str
    summary: str = Field(..., description="What the activity does and how to resolve it")
    results: list[RollResult] = Field(
        default_factory=list, description="Roll-result bands, if the activity has one"
    )


class SrdSection(BaseModel):
    heading: str
    level: int = Field(..., description="Markdown heading depth (1 = '#', 2 = '##', ...)")
    line: int = Field(..., description="1-indexed line number in the source SRD file")


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
    magnitude_levels: list[MagnitudeLevel] = Field(default_factory=list)
    downtime_activities: list[DowntimeActivity] = Field(default_factory=list)
    srd_sections: list[SrdSection] = Field(
        default_factory=list, description="Section index of the source SRD file"
    )
