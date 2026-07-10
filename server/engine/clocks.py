from enum import StrEnum

from pydantic import BaseModel

from engine.errors import ClockEmptyError, ClockFullError


class ClockKind(StrEnum):
    """SRD: "Progress clocks" - every flavour is the same segments-and-fill
    structure; kind is a label for how the engine/GM uses it, not a
    different data shape."""

    DANGER = "danger"
    RACING = "racing"
    LINKED = "linked"
    MISSION = "mission"
    TUG_OF_WAR = "tug_of_war"
    LONG_TERM_PROJECT = "long_term_project"
    FACTION = "faction"
    HEALING = "healing"


class Clock(BaseModel):
    """SRD: "Progress clocks". Immutable: `tick` returns a new Clock rather
    than mutating, so a sequence of clock events replays deterministically."""

    name: str
    kind: ClockKind
    segments: int
    filled: int = 0

    @property
    def is_complete(self) -> bool:
        return self.filled >= self.segments

    def tick(self, amount: int = 1) -> "Clock":
        """Fill (or, for a tug-of-war clock, empty) segments. Ticking a
        clock that's already full (CLAUDE.md's canonical example of an
        illegal engine operation) or emptying one that's already at zero
        raises rather than silently clamping."""
        if amount > 0 and self.is_complete:
            raise ClockFullError(f"clock {self.name!r} is already full")
        if amount < 0 and self.filled <= 0:
            raise ClockEmptyError(f"clock {self.name!r} is already empty")

        filled = max(0, min(self.segments, self.filled + amount))
        return self.model_copy(update={"filled": filled})
