import pytest

from engine.controller import (
    Controller,
    ControllerError,
    assert_controls,
    assert_no_double_assignment,
    is_ai_controlled,
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


def test_controller_defaults_to_human():
    # FR-25/FR-35: a character with no seat at all is human-controlled,
    # same as an explicit human seat - unassigned never means "AI".
    assert Controller(seat_id="seat-1", character_ids=["pc-1"]).kind == "human"


def test_is_ai_controlled_true_for_an_ai_seat():
    controllers = {"seat:pc-2": Controller(seat_id="seat:pc-2", kind="ai", character_ids=["pc-2"])}

    assert is_ai_controlled(controllers, "pc-2")


def test_is_ai_controlled_false_for_a_human_seat():
    controllers = {"seat-1": Controller(seat_id="seat-1", character_ids=["pc-1"])}

    assert not is_ai_controlled(controllers, "pc-1")


def test_is_ai_controlled_false_when_the_character_has_no_seat_at_all():
    assert not is_ai_controlled({}, "pc-1")
