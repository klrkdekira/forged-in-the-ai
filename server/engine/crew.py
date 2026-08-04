from pydantic import BaseModel, Field, computed_field, model_validator

from engine.character import XpTrack
from engine.crew_mechanics import CohortHarmTrack, HeatTrack, Hold, RepTrack


class Cohort(BaseModel):
    """SRD: "Cohorts" - a gang or expert; up to two types, edges, and flaws."""

    cohort_id: str = Field(default="cohort-1", description="Stable id within the crew")
    types: list[str] = Field(default_factory=list, description="Up to two, e.g. 'Thugs'")
    is_expert: bool = False
    quality: int = 0
    scale: int = 0
    edges: list[str] = Field(default_factory=list)
    flaws: list[str] = Field(default_factory=list)
    harm: CohortHarmTrack = Field(default_factory=CohortHarmTrack)


class Claim(BaseModel):
    id: str
    name: str
    controlled: bool = False
    is_turf: bool = False


class Crew(BaseModel):
    """FR-7: crew sheet, field-for-field. `crew_type` and
    `special_ability_ids` are references, never a real BitD crew type's
    assembled upgrades/claim map (core-book content, NOTICE.md) - this
    schema holds a specific crew's own sheet."""

    name: str
    crew_type: str
    tier: int = 0
    hold: Hold = Hold.STRONG

    rep: RepTrack = Field(default_factory=RepTrack)
    heat: HeatTrack = Field(default_factory=HeatTrack)
    wanted_level: int = 0

    coin: int = 0
    vault_level: int = Field(default=0, ge=0, le=2)
    stash: int = 0

    claims: list[Claim] = Field(default_factory=list)
    upgrade_ids: list[str] = Field(default_factory=list)
    cohorts: list[Cohort] = Field(default_factory=list)
    special_ability_ids: list[str] = Field(default_factory=list)

    xp: XpTrack = Field(default_factory=XpTrack)

    @model_validator(mode="after")
    def ensure_cohort_ids(self) -> "Crew":
        """Give legacy and hand-entered cohorts deterministic unique ids."""
        used: set[str] = set()
        cohorts: list[Cohort] = []
        for index, cohort in enumerate(self.cohorts, start=1):
            cohort_id = cohort.cohort_id
            if cohort_id in used:
                cohort_id = f"cohort-{index}"
            used.add(cohort_id)
            cohorts.append(cohort.model_copy(update={"cohort_id": cohort_id}))
        self.cohorts = cohorts
        return self

    @computed_field
    @property
    def coin_capacity(self) -> int:
        """SRD: "Coin and Stash" - lair storage is 4, 8 with one vault
        upgrade, and 16 with the second."""
        return 4 * (2**self.vault_level)


def render_markdown(crew: Crew) -> str:
    """FR-8: human-readable markdown sheet render."""
    lines = [f"# {crew.name}", f"*{crew.crew_type}*", ""]
    lines.append(f"**Tier**: {crew.tier} ({crew.hold.value})")
    lines.append(f"**Rep**: {crew.rep.rep}/{crew.rep.threshold} (turf: {crew.rep.turf})")
    lines.append(f"**Heat**: {crew.heat.heat}/{HeatTrack.MAX}")
    lines.append(f"**Wanted level**: {crew.wanted_level}")
    lines.append(f"**Coin**: {crew.coin} (stash: {crew.stash})")
    lines.append("")

    if crew.claims:
        lines.append("## Claims")
        for claim in crew.claims:
            marker = "x" if claim.controlled else " "
            lines.append(f"- [{marker}] {claim.name}")
        lines.append("")

    if crew.cohorts:
        lines.append("## Cohorts")
        for cohort in crew.cohorts:
            kind = "Expert" if cohort.is_expert else "Gang"
            types = ", ".join(cohort.types) or "untyped"
            lines.append(f"- {kind} ({types}), quality {cohort.quality}: {cohort.harm.level.value}")
        lines.append("")

    return "\n".join(lines)
