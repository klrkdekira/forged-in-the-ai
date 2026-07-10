import random

from pydantic import BaseModel

from engine.dice import roll_pool
from engine.rolls import RollBand, band_for

# SRD: "Acquire asset" / "ACQUIRE ASSET" - quality relative to crew Tier.
_ACQUIRE_ASSET_QUALITY_DELTA = {
    RollBand.CRITICAL: 2,
    RollBand.FULL: 1,
    RollBand.PARTIAL: 0,
    RollBand.BAD: -1,
}


class AcquireAssetResult(BaseModel):
    band: RollBand
    quality: int


def acquire_asset_roll(crew_tier: int, rng: random.Random) -> AcquireAssetResult:
    """SRD: "Acquire asset" - roll the crew's Tier; the result sets the
    asset's quality relative to that Tier."""
    dice = roll_pool(crew_tier, rng)
    band = band_for(dice)
    quality = max(0, crew_tier + _ACQUIRE_ASSET_QUALITY_DELTA[band])
    return AcquireAssetResult(band=band, quality=quality)


class ViceRollResult(BaseModel):
    stress_cleared: int
    overindulged: bool


def indulge_vice_roll(
    lowest_attribute_rating: int, stress_marked: int, rng: random.Random
) -> ViceRollResult:
    """SRD: "VICE ROLL" - clear stress equal to the highest die of a pool
    sized by the character's lowest attribute; clearing more than was
    marked is an overindulgence."""
    dice = roll_pool(lowest_attribute_rating, rng)
    stress_cleared = min(dice.result, stress_marked)
    return ViceRollResult(stress_cleared=stress_cleared, overindulged=dice.result > stress_marked)
