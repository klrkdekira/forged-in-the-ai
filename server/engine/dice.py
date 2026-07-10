import random

from pydantic import BaseModel, Field


class DiceResult(BaseModel):
    """The outcome of one dice-pool roll (SRD: "Rolling the Dice")."""

    rolls: list[int]
    result: int = Field(..., description="The single die result read to judge the outcome")
    is_critical: bool


def roll_pool(size: int, rng: random.Random) -> DiceResult:
    """SRD: "Rolling the Dice" - roll dice equal to the pool size and read
    the single highest result. 6 = full success, two or more 6s = critical.
    Zero (or negative) dice: roll two and take the lowest; this can never
    be a critical."""
    if size <= 0:
        rolls = [rng.randint(1, 6), rng.randint(1, 6)]
        return DiceResult(rolls=rolls, result=min(rolls), is_critical=False)

    rolls = [rng.randint(1, 6) for _ in range(size)]
    return DiceResult(rolls=rolls, result=max(rolls), is_critical=rolls.count(6) >= 2)
