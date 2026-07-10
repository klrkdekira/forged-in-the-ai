import random
from enum import StrEnum

from pydantic import BaseModel

from engine.errors import EngineError
from engine.packs import EntanglementEntry
from engine.rolls import Position, RollBand, fortune_roll


class Plan(StrEnum):
    """SRD: "Planning & engagement" - the six plan types."""

    ASSAULT = "assault"
    DECEPTION = "deception"
    STEALTH = "stealth"
    OCCULT = "occult"
    SOCIAL = "social"
    TRANSPORT = "transport"


class EngagementRollResult(BaseModel):
    dice_pool_size: int
    band: RollBand
    position: Position
    beyond_first_obstacle: bool


# SRD: "ENGAGEMENT ROLL" / "Outcomes" - 1-3 desperate, 4/5 risky, 6
# controlled, critical carries the action beyond the first obstacle.
_ENGAGEMENT_POSITION = {
    RollBand.CRITICAL: Position.CONTROLLED,
    RollBand.FULL: Position.CONTROLLED,
    RollBand.PARTIAL: Position.RISKY,
    RollBand.BAD: Position.DESPERATE,
}


def engagement_roll(pool_size: int, rng: random.Random) -> EngagementRollResult:
    """SRD: "Engagement Roll" - a fortune roll (1d for sheer luck, +-1d per
    major advantage/disadvantage) that sets the crew's starting position."""
    result = fortune_roll(pool_size, rng)
    return EngagementRollResult(
        dice_pool_size=pool_size,
        band=result.band,
        position=_ENGAGEMENT_POSITION[result.band],
        beyond_first_obstacle=result.band is RollBand.CRITICAL,
    )


def payoff_rep(crew_tier: int, target_tier: int, quiet: bool = False) -> int:
    """SRD: "Payoff" - 2 rep, +-1 per Tier difference, floored at zero;
    zero if the operation was kept completely quiet."""
    if quiet:
        return 0
    return max(0, 2 + (target_tier - crew_tier))


# SRD: "RECOVER"/"REDUCE HEAT"/"LONG-TERM PROJECT" downtime rolls all use
# this same critical:5, 6:3, 4/5:2, 1-3:1 result-band table.
_DOWNTIME_TICKS = {
    RollBand.CRITICAL: 5,
    RollBand.FULL: 3,
    RollBand.PARTIAL: 2,
    RollBand.BAD: 1,
}


def downtime_ticks(band: RollBand) -> int:
    return _DOWNTIME_TICKS[band]


class EntanglementRollResult(BaseModel):
    dice_pool_size: int
    heat_band: str
    roll_result: str
    entanglement: str


class EntanglementNotFoundError(EngineError):
    """Raised when the given entanglement table has no row for the rolled
    heat band/result - a malformed or incomplete content pack."""


def _heat_band(heat: int) -> str:
    if heat >= 6:
        return "6"
    if heat >= 4:
        return "4-5"
    return "0-3"


def _roll_result_band(die: int) -> str:
    if die == 6:
        return "6"
    if die in (4, 5):
        return "4/5"
    return "1-3"


def entanglement_roll(
    wanted_level: int, heat: int, entanglements: list[EntanglementEntry], rng: random.Random
) -> EntanglementRollResult:
    """SRD: "Entanglements" - roll dice equal to wanted level (0 rolls two,
    takes the lowest, same as any 0d roll); the heat band picks the column,
    the die result picks the row."""
    dice = fortune_roll(wanted_level, rng).dice
    heat_band = _heat_band(heat)
    roll_result = _roll_result_band(dice.result)

    entry = next(
        (e for e in entanglements if e.heat_band == heat_band and e.roll_result == roll_result),
        None,
    )
    if entry is None:
        raise EntanglementNotFoundError(
            f"no entanglement for heat band {heat_band!r}, roll result {roll_result!r}"
        )

    return EntanglementRollResult(
        dice_pool_size=wanted_level,
        heat_band=heat_band,
        roll_result=roll_result,
        entanglement=entry.entanglement,
    )
