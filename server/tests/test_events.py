from datetime import UTC, datetime

from engine.events import EventLog

AT = datetime(2026, 1, 1, tzinfo=UTC)


def test_append_assigns_increasing_sequence_numbers():
    # FR-19/FR-31: an append-only, entity-tagged event log.
    log = EventLog()
    log = log.append("clock", "alert", "clock_created", {"segments": 4}, AT)
    log = log.append("clock", "alert", "clock_ticked", {"amount": 1}, AT)

    assert [event.sequence for event in log.events] == [1, 2]


def test_append_does_not_mutate_the_original_log():
    # SPECIFICATION.md §7 "Event-sourced state": append-only.
    log = EventLog()
    appended = log.append("clock", "alert", "clock_created", {"segments": 4}, AT)

    assert log.events == []
    assert len(appended.events) == 1


def test_for_entity_filters_by_entity_type_and_id():
    log = EventLog()
    log = log.append("clock", "alert", "clock_created", {"segments": 4}, AT)
    log = log.append("clock", "escape", "clock_created", {"segments": 6}, AT)
    log = log.append("clock", "alert", "clock_ticked", {"amount": 1}, AT)

    alert_events = log.for_entity("clock", "alert")

    assert [event.event_type for event in alert_events] == ["clock_created", "clock_ticked"]


def test_jsonl_round_trip():
    # NFR-5: portability of saves via a canonical JSONL event-log export
    # that round-trips through import.
    log = EventLog()
    log = log.append("clock", "alert", "clock_created", {"segments": 4}, AT)
    log = log.append("clock", "alert", "clock_ticked", {"amount": 2}, AT)

    restored = EventLog.from_jsonl(log.to_jsonl())

    assert restored == log


def test_jsonl_export_is_one_json_object_per_line():
    log = EventLog()
    log = log.append("clock", "alert", "clock_created", {"segments": 4}, AT)
    log = log.append("clock", "alert", "clock_ticked", {"amount": 2}, AT)

    lines = log.to_jsonl().splitlines()

    assert len(lines) == 2


def test_empty_log_round_trips():
    assert EventLog.from_jsonl(EventLog().to_jsonl()) == EventLog()
