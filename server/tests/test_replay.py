from datetime import UTC, datetime

from engine.events import EventLog
from engine.replay import replay_clocks

AT = datetime(2026, 1, 1, tzinfo=UTC)


def _sample_log() -> EventLog:
    log = EventLog()
    log = log.append(
        "clock", "alert", "clock_created", {"name": "Alert", "kind": "danger", "segments": 4}, AT
    )
    log = log.append("clock", "alert", "clock_ticked", {"amount": 2}, AT)
    log = log.append(
        "clock",
        "escape",
        "clock_created",
        {"name": "Escape", "kind": "racing", "segments": 6},
        AT,
    )
    log = log.append("clock", "alert", "clock_ticked", {"amount": 1}, AT)
    return log


def test_replay_clocks_reconstructs_state_from_events():
    # FR-19: state is reproducible by replaying the event log.
    clocks = replay_clocks(_sample_log().events)

    assert clocks["alert"].filled == 3
    assert clocks["alert"].segments == 4
    assert clocks["escape"].filled == 0
    assert clocks["escape"].segments == 6


def test_replay_is_deterministic_for_the_same_log():
    # NFR-1: the same event log yields the same state.
    events = _sample_log().events

    first = replay_clocks(events)
    second = replay_clocks(events)

    assert first == second


def test_replay_does_not_depend_on_event_order_in_the_input_list():
    # replay_clocks sorts by sequence, so passing events out of order still
    # replays correctly.
    events = list(reversed(_sample_log().events))

    clocks = replay_clocks(events)

    assert clocks["alert"].filled == 3
