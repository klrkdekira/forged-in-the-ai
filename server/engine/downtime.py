import random

from pydantic import BaseModel

from engine.dice import roll_pool
from engine.rolls import RollBand, band_for

# SRD: "ACQUIRE ASSET"/"CRAFTING ROLL" - both roll a pool and set a result's
# quality relative to the crew's Tier with this same critical/6/4-5/1-3 delta.
_TIER_QUALITY_DELTA = {
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
    quality = max(0, crew_tier + _TIER_QUALITY_DELTA[band])
    return AcquireAssetResult(band=band, quality=quality)


class CraftResult(BaseModel):
    band: RollBand
    quality: int


def craft_roll(
    tinker_rating: int,
    crew_tier: int,
    rng: random.Random,
    has_workshop: bool = False,
    coin_spent: int = 0,
) -> CraftResult:
    """SRD: "Crafting"/"CRAFTING ROLL" - roll Tinker; the base quality is
    the crew's Tier, modified by the roll's result, +1 for the Workshop
    crew upgrade, and +1 per coin spent (unlike Acquire Asset's 2-coin
    rate, this one is explicitly "1-for-1... beyond Tier +2")."""
    dice = roll_pool(tinker_rating, rng)
    band = band_for(dice)
    quality = crew_tier + _TIER_QUALITY_DELTA[band] + int(has_workshop) + coin_spent
    return CraftResult(band=band, quality=max(0, quality))


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
