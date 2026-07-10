import random

from engine.downtime import acquire_asset_roll, indulge_vice_roll
from engine.rolls import RollBand
from engine.score import downtime_ticks


def test_downtime_ticks_matches_the_shared_result_band_table():
    # SRD: "RECOVER"/"REDUCE HEAT"/"LONG-TERM PROJECT" - critical 5, 6
    # three, 4/5 two, 1-3 one.
    assert downtime_ticks(RollBand.CRITICAL) == 5
    assert downtime_ticks(RollBand.FULL) == 3
    assert downtime_ticks(RollBand.PARTIAL) == 2
    assert downtime_ticks(RollBand.BAD) == 1


def test_acquire_asset_roll_sets_quality_relative_to_tier():
    # SRD: "ACQUIRE ASSET" - "6: Tier +1."
    rng = random.Random(1)
    result = next(
        r for r in (acquire_asset_roll(2, rng) for _ in range(200)) if r.band is RollBand.FULL
    )

    assert result.quality == 3


def test_acquire_asset_roll_never_goes_below_zero_quality():
    rng = random.Random(2)
    result = next(
        r for r in (acquire_asset_roll(0, rng) for _ in range(200)) if r.band is RollBand.BAD
    )

    assert result.quality == 0


def test_indulge_vice_roll_clears_stress_up_to_what_was_marked():
    # SRD: "VICE ROLL" - "Clear stress equal to your highest die result."
    rng = random.Random(3)
    result = indulge_vice_roll(lowest_attribute_rating=3, stress_marked=2, rng=rng)

    assert result.stress_cleared <= 2


def test_indulge_vice_roll_flags_overindulgence():
    # SRD: "Overindulgence" - "If your vice roll clears more stress levels
    # than you had marked, you overindulge."
    rng = random.Random(4)
    overindulged = next(
        r
        for r in (indulge_vice_roll(4, stress_marked=1, rng=rng) for _ in range(200))
        if r.overindulged
    )

    assert overindulged.stress_cleared == 1
