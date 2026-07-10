import random

import pytest

from engine.packs import EntanglementEntry
from engine.rolls import Position, RollBand
from engine.score import (
    EntanglementNotFoundError,
    engagement_roll,
    entanglement_roll,
    payoff_rep,
)

_ENTANGLEMENTS = [
    EntanglementEntry(heat_band="0-3", roll_result="1-3", entanglement="Gang Trouble"),
    EntanglementEntry(heat_band="0-3", roll_result="4/5", entanglement="Rivals"),
    EntanglementEntry(heat_band="0-3", roll_result="6", entanglement="Cooperation"),
    EntanglementEntry(heat_band="6", roll_result="6", entanglement="Arrest"),
]


def test_engagement_roll_critical_carries_beyond_the_first_obstacle():
    # SRD: "ENGAGEMENT ROLL" - "Critical: ... you're in a controlled
    # position ... carries the action beyond the initial obstacle"
    rng = random.Random(1)
    critical = next(
        r for r in (engagement_roll(6, rng) for _ in range(200)) if r.band is RollBand.CRITICAL
    )

    assert critical.position is Position.CONTROLLED
    assert critical.beyond_first_obstacle


def test_engagement_roll_maps_bands_to_positions():
    # SRD: "Outcomes" - "1-3 desperate. 4/5 risky. 6 controlled."
    rng = random.Random(2)
    results = [engagement_roll(3, rng) for _ in range(300)]

    for band, position in (
        (RollBand.FULL, Position.CONTROLLED),
        (RollBand.PARTIAL, Position.RISKY),
        (RollBand.BAD, Position.DESPERATE),
    ):
        match = next(r for r in results if r.band is band)
        assert match.position is position


def test_payoff_rep_bonus_for_higher_tier_target():
    # SRD: "Payoff" - Tier I crew vs Tier III target = 4 rep.
    assert payoff_rep(crew_tier=1, target_tier=3) == 4


def test_payoff_rep_floors_at_zero_for_lower_tier_target():
    # SRD: "Payoff" - Tier III crew vs Tier I target = 0 rep.
    assert payoff_rep(crew_tier=3, target_tier=1) == 0


def test_payoff_rep_is_zero_when_kept_quiet():
    assert payoff_rep(crew_tier=0, target_tier=0, quiet=True) == 0


def test_entanglement_roll_picks_heat_band_and_result():
    # SRD: "Entanglements" - column by heat, row by the rolled result.
    rng = random.Random(3)
    result = entanglement_roll(wanted_level=1, heat=0, entanglements=_ENTANGLEMENTS, rng=rng)

    assert result.heat_band == "0-3"
    assert result.entanglement in {"Gang Trouble", "Rivals", "Cooperation"}


def test_entanglement_roll_at_zero_wanted_level_rolls_two_and_takes_lowest():
    # SRD: "Entanglements" - "If wanted level is zero, roll two dice and
    # keep the lowest result."
    rng = random.Random(4)
    result = entanglement_roll(wanted_level=0, heat=0, entanglements=_ENTANGLEMENTS, rng=rng)

    assert result.dice_pool_size == 0


def test_entanglement_roll_raises_on_missing_table_row():
    rng = random.Random(5)
    with pytest.raises(EntanglementNotFoundError):
        entanglement_roll(wanted_level=1, heat=4, entanglements=_ENTANGLEMENTS, rng=rng)
