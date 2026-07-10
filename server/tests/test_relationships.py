from engine.relationships import FactionStatus, Relationship, RelationshipKind


def test_relationship_tracks_the_event_that_caused_a_change():
    # SPECIFICATION.md §5: "every change references the event that caused it"
    relationship = Relationship(
        subject_type="npc",
        subject_id="n1",
        object_type="npc",
        object_id="n2",
        kind=RelationshipKind.RIVAL,
    )

    updated = relationship.with_event(3)

    assert updated.history == [3]
    assert relationship.history == []


def test_faction_status_defaults_to_neutral():
    # SRD: "Faction Status" - "zero (neutral) being the default"
    status = FactionStatus(crew_id="c1", faction_id="f1")

    assert status.status == 0


def test_faction_status_clamps_to_plus_or_minus_three():
    # SRD: "Faction Status" - "rated from -3 to +3"
    status = FactionStatus(crew_id="c1", faction_id="f1", status=3)

    maxed = status.changed(+1, sequence=1)
    assert maxed.status == 3

    minned = FactionStatus(crew_id="c1", faction_id="f1", status=-3).changed(-1, sequence=2)
    assert minned.status == -3


def test_faction_status_records_history():
    status = FactionStatus(crew_id="c1", faction_id="f1").changed(-2, sequence=5)

    assert status.status == -2
    assert status.history == [5]
