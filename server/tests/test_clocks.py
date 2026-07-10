import pytest

from engine.clocks import Clock, ClockKind
from engine.errors import ClockEmptyError, ClockFullError


def test_clock_ticks_up_and_reports_completion():
    # SRD: "Progress clocks": "a circle divided into segments"
    clock = Clock(name="Alert", kind=ClockKind.DANGER, segments=4)

    ticked = clock.tick(2)

    assert ticked.filled == 2
    assert not ticked.is_complete
    assert ticked.tick(2).is_complete


def test_clock_tick_is_immutable():
    clock = Clock(name="Alert", kind=ClockKind.DANGER, segments=4)

    clock.tick(1)

    assert clock.filled == 0


def test_ticking_a_full_clock_raises():
    # CLAUDE.md's own example of an illegal engine operation.
    clock = Clock(name="Alert", kind=ClockKind.DANGER, segments=4, filled=4)

    with pytest.raises(ClockFullError):
        clock.tick(1)


def test_tug_of_war_clock_can_tick_down():
    # SRD: "Tug-of-war Clocks": "can be filled and emptied by events"
    clock = Clock(name="Revolution", kind=ClockKind.TUG_OF_WAR, segments=6, filled=3)

    assert clock.tick(-2).filled == 1


def test_emptying_an_already_empty_clock_raises():
    clock = Clock(name="Revolution", kind=ClockKind.TUG_OF_WAR, segments=6, filled=0)

    with pytest.raises(ClockEmptyError):
        clock.tick(-1)


def test_tick_clamps_to_segments_when_overshooting():
    clock = Clock(name="Alert", kind=ClockKind.DANGER, segments=4, filled=3)

    assert clock.tick(3).filled == 4
