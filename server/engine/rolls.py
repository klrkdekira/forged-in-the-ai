import random
from enum import IntEnum, StrEnum

from pydantic import BaseModel

from engine.dice import DiceResult, roll_pool


class Position(StrEnum):
    """SRD: "Action Roll" - the three positions."""

    CONTROLLED = "controlled"
    RISKY = "risky"
    DESPERATE = "desperate"


class Effect(IntEnum):
    """SRD: "Effect" - zero and extreme are outside the three named levels,
    reached only by factors or a critical (zero) / by factors alone
    (extreme; a critical bump caps at GREAT, see `action_roll`)."""

    ZERO = 0
    LIMITED = 1
    STANDARD = 2
    GREAT = 3
    EXTREME = 4

    def bumped(self, delta: int) -> "Effect":
        return Effect(max(Effect.ZERO, min(Effect.EXTREME, self.value + delta)))


class RollBand(StrEnum):
    """SRD: "Rolling the Dice" outcome bands. Values match the `level`
    strings already used by `packs.RollResult` for the same four bands."""

    CRITICAL = "critical"
    FULL = "6"
    PARTIAL = "4/5"
    BAD = "1-3"


def band_for(dice: DiceResult) -> RollBand:
    if dice.is_critical:
        return RollBand.CRITICAL
    if dice.result == 6:
        return RollBand.FULL
    if dice.result in (4, 5):
        return RollBand.PARTIAL
    return RollBand.BAD


class ActionRollResult(BaseModel):
    dice: DiceResult
    position: Position
    band: RollBand
    effect: Effect


def action_roll(
    pool_size: int, position: Position, effect: Effect, rng: random.Random
) -> ActionRollResult:
    """SRD: "Action Roll" - position and effect are GM judgement calls made
    before the roll; only a critical changes effect after the fact ("you do
    it with increased effect")."""
    dice = roll_pool(pool_size, rng)
    band = band_for(dice)
    if band is RollBand.CRITICAL:
        effect = effect.bumped(1)
    return ActionRollResult(dice=dice, position=position, band=band, effect=effect)


class FortuneRollResult(BaseModel):
    dice: DiceResult
    band: RollBand


def fortune_roll(pool_size: int, rng: random.Random) -> FortuneRollResult:
    """SRD: "Fortune Roll" - same four outcome bands as an action roll, over
    any trait rating the GM assesses (Tier, quality, magnitude, and so on)."""
    dice = roll_pool(pool_size, rng)
    return FortuneRollResult(dice=dice, band=band_for(dice))


class ResistanceRollResult(BaseModel):
    dice: DiceResult
    stress_delta: int


def resistance_roll(attribute_rating: int, rng: random.Random) -> ResistanceRollResult:
    """SRD: "Resistance and Armor" / "RESISTANCE ROLL" - suffer 6 stress
    minus the highest die; a critical also clears 1 stress. Resistance
    rolls always succeed at reducing or avoiding the consequence; only the
    stress cost is uncertain."""
    dice = roll_pool(attribute_rating, rng)
    stress_delta = max(0, 6 - dice.result)
    if dice.is_critical:
        stress_delta -= 1
    return ResistanceRollResult(dice=dice, stress_delta=stress_delta)
