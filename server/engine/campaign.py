from pydantic import BaseModel, Field


class SessionZeroConfig(BaseModel):
    """FR-17: safety tools agreed before play starts. Not SRD content -
    lines/veils/X-card are generic tabletop safety tools, not specific to
    Blades in the Dark."""

    lines: list[str] = Field(default_factory=list, description="Hard limits: never in the fiction")
    veils: list[str] = Field(
        default_factory=list, description="Fade-to-black topics: implied, not detailed"
    )
    tone: str | None = None


class CampaignCanon(BaseModel):
    """FR-36: an original setting, generated at session zero and grown
    during play - never a core-book setting (C3). Persisted as
    campaign-local content, not shipped with the product."""

    setting_name: str
    tone: str | None = None
    factions: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    facts: list[str] = Field(
        default_factory=list, description="Established facts, in the order they entered play"
    )

    def with_fact(self, fact: str) -> "CampaignCanon":
        return self.model_copy(update={"facts": [*self.facts, fact]})

    def with_location(self, location: str) -> "CampaignCanon":
        """FR-15: the map grows as new locations are discovered during
        play, the same way facts do."""
        return self.model_copy(update={"locations": [*self.locations, location]})
