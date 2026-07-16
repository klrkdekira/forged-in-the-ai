import random

from engine.dice import DiceResult
from engine.rolls import (
    ASSIST_BONUS_DICE,
    ASSIST_STRESS_COST,
    Effect,
    Position,
    RollBand,
    action_roll,
    band_for,
    fortune_roll,
    resistance_roll,
    step_position,
)


def test_assist_costs_one_stress_for_one_bonus_die():
    # SRD: "Teamwork" / "Assist" - "Take 1 stress and give them +1d to their roll."
    assert ASSIST_STRESS_COST == 1
    assert ASSIST_BONUS_DICE == 1


def test_band_for_critical_on_two_sixes():
    # SRD: "Rolling the Dice": "more than one 6... critical success"
    dice = DiceResult(rolls=[6, 6, 2], result=6, is_critical=True)
    assert band_for(dice) is RollBand.CRITICAL


def test_band_for_full_success_on_a_single_six():
    dice = DiceResult(rolls=[6, 2], result=6, is_critical=False)
    assert band_for(dice) is RollBand.FULL


def test_band_for_partial_on_four_or_five():
    # SRD: "Rolling the Dice": "4 or 5, that's a partial success"
    for value in (4, 5):
        dice = DiceResult(rolls=[value], result=value, is_critical=False)
        assert band_for(dice) is RollBand.PARTIAL


def test_band_for_bad_outcome_on_one_to_three():
    # SRD: "Rolling the Dice": "1-3, it's a bad outcome"
    for value in (1, 2, 3):
        dice = DiceResult(rolls=[value], result=value, is_critical=False)
        assert band_for(dice) is RollBand.BAD


def test_action_roll_bumps_effect_on_a_critical():
    # SRD: "ACTION ROLL" / CONTROLLED,RISKY,DESPERATE: "Critical: You do it
    # with increased effect."
    rng = random.Random(1)
    critical = next(
        r
        for r in (action_roll(6, Position.RISKY, Effect.STANDARD, rng) for _ in range(200))
        if r.band is RollBand.CRITICAL
    )

    assert critical.effect is Effect.GREAT


def test_action_roll_leaves_effect_unchanged_off_a_critical():
    rng = random.Random(1)
    non_critical = next(
        r
        for r in (action_roll(6, Position.RISKY, Effect.STANDARD, rng) for _ in range(200))
        if r.band is not RollBand.CRITICAL
    )

    assert non_critical.effect is Effect.STANDARD


def test_effect_bump_caps_at_extreme():
    assert Effect.GREAT.bumped(1) is Effect.EXTREME
    assert Effect.EXTREME.bumped(1) is Effect.EXTREME


def test_effect_bump_floors_at_zero():
    assert Effect.ZERO.bumped(-1) is Effect.ZERO


def test_step_position_moves_towards_desperate_and_clamps():
    # SRD: "Trading Position for Effect".
    assert step_position(Position.RISKY, 1) is Position.DESPERATE
    assert step_position(Position.DESPERATE, 1) is Position.DESPERATE


def test_step_position_moves_towards_controlled_and_clamps():
    assert step_position(Position.RISKY, -1) is Position.CONTROLLED
    assert step_position(Position.CONTROLLED, -1) is Position.CONTROLLED


def test_fortune_roll_uses_the_same_bands_as_an_action_roll():
    # SRD: "FORTUNE ROLL": "Critical / 6 / 4/5 / 1-3" - the same four bands.
    rng = random.Random(5)
    result = fortune_roll(2, rng)

    assert result.band in RollBand


def test_resistance_roll_costs_six_minus_the_highest_die():
    # SRD: "RESISTANCE ROLL": "Suffer 6 Stress minus the highest die result."
    rng = random.Random(6)
    result = next(
        r for r in (resistance_roll(3, rng) for _ in range(200)) if not r.dice.is_critical
    )

    assert result.stress_delta == max(0, 6 - result.dice.result)


def test_resistance_roll_critical_also_clears_one_stress():
    # SRD: "RESISTANCE ROLL": "Critical: Clear 1 stress."
    rng = random.Random(7)
    critical = next(r for r in (resistance_roll(4, rng) for _ in range(200)) if r.dice.is_critical)

    assert critical.stress_delta == -1


def test_resistance_roll_never_costs_negative_stress_off_a_non_critical():
    rng = random.Random(8)
    for _ in range(200):
        result = resistance_roll(4, rng)
        if not result.dice.is_critical:
            assert result.stress_delta >= 0
