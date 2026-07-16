from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, computed_field


class Hold(StrEnum):
    """SRD: "Hold" - W(eak) or S(trong); a crew begins strong at Tier 0."""

    WEAK = "weak"
    STRONG = "strong"


MAX_WANTED_LEVEL = 4
"""SRD: "Heat & Wanted Level" - "The maximum wanted level is 4"."""


class HeatMarkResult(BaseModel):
    track: "HeatTrack"
    wanted_level_increased: bool


class HeatTrack(BaseModel):
    """SRD: "Heat" - heat 0-9; reaching 9 gains a wanted level and clears
    heat, with any excess rolling over rather than being lost."""

    MAX: ClassVar[int] = 9
    heat: int = 0

    def add(self, amount: int) -> HeatMarkResult:
        new_heat = max(0, self.heat + amount)
        if new_heat < self.MAX:
            return HeatMarkResult(track=HeatTrack(heat=new_heat), wanted_level_increased=False)
        return HeatMarkResult(
            track=HeatTrack(heat=new_heat - self.MAX), wanted_level_increased=True
        )


class RepTrack(BaseModel):
    """SRD: "Development" / "Turf" - 12 rep develops the crew, reduced by
    1 per turf held (turf caps at 6, so the floor is 6 rep)."""

    MAX_TURF: ClassVar[int] = 6
    BASE_THRESHOLD: ClassVar[int] = 12
    rep: int = 0
    turf: int = 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def threshold(self) -> int:
        """Serialized (unlike a plain `@property`) so the web sheet panel's
        rep tick-boxes know their segment count without duplicating the
        SRD formula client-side."""
        return self.BASE_THRESHOLD - min(self.turf, self.MAX_TURF)

    @property
    def ready_to_develop(self) -> bool:
        return self.rep >= self.threshold

    def add_rep(self, amount: int) -> "RepTrack":
        capped = min(self.threshold, max(0, self.rep + amount))
        return self.model_copy(update={"rep": capped})

    def add_turf(self, amount: int) -> "RepTrack":
        turf = max(0, min(self.MAX_TURF, self.turf + amount))
        return self.model_copy(update={"turf": turf})

    def developed(self) -> "RepTrack":
        """SRD: "when you develop, you'll clear the Rep marks, but keep the
        turf marks."""
        return self.model_copy(update={"rep": 0})


class CohortHarmLevel(StrEnum):
    """SRD: "Cohort harm & Healing" - a cohort has one flat harm track,
    unlike a PC's per-level slots."""

    NONE = "none"
    WEAKENED = "weakened"
    IMPAIRED = "impaired"
    BROKEN = "broken"
    DEAD = "dead"


_COHORT_HARM_ORDER = list(CohortHarmLevel)


class CohortHarmTrack(BaseModel):
    level: CohortHarmLevel = CohortHarmLevel.NONE

    def mark(self, levels: int = 1) -> "CohortHarmTrack":
        index = _COHORT_HARM_ORDER.index(self.level)
        new_index = min(len(_COHORT_HARM_ORDER) - 1, index + levels)
        return CohortHarmTrack(level=_COHORT_HARM_ORDER[new_index])

    def heal(self, levels: int = 1) -> "CohortHarmTrack":
        index = _COHORT_HARM_ORDER.index(self.level)
        new_index = max(0, index - levels)
        return CohortHarmTrack(level=_COHORT_HARM_ORDER[new_index])
