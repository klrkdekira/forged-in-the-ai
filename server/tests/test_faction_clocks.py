from datetime import UTC, datetime

from engine.entities import Faction
from engine.events import EventLog
from engine.replay import replay_clocks

AT = datetime(2026, 1, 1, tzinfo=UTC)


def test_faction_downtime_progression_ticks_its_own_clocks():
    # SRD: "Faction Clocks" - "When the PCs have downtime, the GM ticks
    # forward the faction clocks that they're interested in." A faction's
    # clocks are ordinary clocks (engine.clocks.Clock); FR-14's engine side
    # is just ticking the ones a faction references, replayed like any
    # other clock (engine.replay.replay_clocks).
    faction = Faction(id="f1", name="Test Faction", tier=2, clock_ids=["f1-goal"])

    log = EventLog()
    log = log.append(
        "clock",
        "f1-goal",
        "clock_created",
        {"name": "Seize the Docks", "kind": "faction", "segments": 8},
        AT,
    )
    log = log.append("clock", "f1-goal", "clock_ticked", {"amount": 2}, AT)

    clocks = replay_clocks(log.events)

    assert clocks[faction.clock_ids[0]].filled == 2
    assert clocks[faction.clock_ids[0]].segments == 8
