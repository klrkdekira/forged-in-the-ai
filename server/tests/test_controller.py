import pytest

from engine.controller import (
    Controller,
    ControllerError,
    assert_controls,
    assert_no_double_assignment,
    solo_controller,
)


def test_solo_controller_covers_the_whole_crew():
    # FR-25: "solo play is the whole crew under one seat"
    controller = solo_controller("seat-1", character_ids=["pc-1", "pc-2"], cohort_ids=["cohort-1"])

    assert controller.controls("pc-1")
    assert controller.controls("pc-2")
    assert not controller.controls("pc-3")


def test_assert_controls_passes_for_the_owning_seat():
    controllers = [Controller(seat_id="seat-1", character_ids=["pc-1"])]

    assert_controls(controllers, "seat-1", "pc-1")


def test_assert_controls_refuses_an_unowned_character():
    controllers = [Controller(seat_id="seat-1", character_ids=["pc-1"])]

    with pytest.raises(ControllerError):
        assert_controls(controllers, "seat-1", "pc-2")


def test_assert_controls_refuses_an_unknown_seat():
    with pytest.raises(ControllerError):
        assert_controls([], "seat-1", "pc-1")


def test_assert_no_double_assignment_passes_for_disjoint_seats():
    controllers = [
        Controller(seat_id="seat-1", character_ids=["pc-1"]),
        Controller(seat_id="seat-2", character_ids=["pc-2"]),
    ]

    assert_no_double_assignment(controllers)


def test_assert_no_double_assignment_refuses_a_shared_character():
    controllers = [
        Controller(seat_id="seat-1", character_ids=["pc-1"]),
        Controller(seat_id="seat-2", character_ids=["pc-1"]),
    ]

    with pytest.raises(ControllerError):
        assert_no_double_assignment(controllers)
