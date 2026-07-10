import random

from engine.dice import roll_pool


def test_roll_pool_reads_the_highest_die():
    # SRD: "Rolling the Dice": "you roll several at once and read the
    # single highest result"
    rng = random.Random(1)
    result = roll_pool(4, rng)

    assert result.result == max(result.rolls)
    assert len(result.rolls) == 4


def test_roll_pool_of_one_can_still_be_a_full_success():
    # SRD: "Rolling the Dice": "If the highest die is a 6, it's a full
    # success"
    rng = random.Random(0)
    six_seen = any(roll_pool(1, rng).result == 6 for _ in range(200))

    assert six_seen


def test_roll_pool_is_critical_on_two_or_more_sixes():
    # SRD: "Rolling the Dice": "If you roll more than one 6, it's a
    # critical success"
    rng = random.Random(2)
    results = [roll_pool(6, rng) for _ in range(200)]

    critical = next(r for r in results if r.rolls.count(6) >= 2)
    non_critical = next(r for r in results if r.rolls.count(6) < 2)
    assert critical.is_critical
    assert not non_critical.is_critical


def test_roll_pool_of_zero_rolls_two_and_takes_the_lowest():
    # SRD: "Rolling the Dice": "If you ever need to roll but you have zero
    # (or negative) dice, roll two dice and take the single lowest result.
    # You can't roll a critical when you have zero dice."
    rng = random.Random(3)
    for _ in range(200):
        result = roll_pool(0, rng)
        assert len(result.rolls) == 2
        assert result.result == min(result.rolls)
        assert not result.is_critical


def test_roll_pool_of_negative_size_behaves_like_zero():
    rng = random.Random(4)
    result = roll_pool(-2, rng)

    assert len(result.rolls) == 2
    assert result.result == min(result.rolls)
    assert not result.is_critical


def test_roll_pool_is_deterministic_for_a_given_seed():
    # NFR-1: the same seed yields the same result.
    first = roll_pool(4, random.Random(42))
    second = roll_pool(4, random.Random(42))

    assert first == second
