from engine.entities import Faction, ItemEntity, Location, Npc, Score


def test_entities_round_trip_through_json():
    # FR-8-style JSON round-trip for the lightweight world entities
    # (SPECIFICATION.md §5).
    faction = Faction(id="f1", name="Test Faction", tier=2)
    npc = Npc(id="n1", name="Test NPC", faction_id="f1")
    location = Location(id="l1", name="Test Location")
    item = ItemEntity(id="i1", name="Test Item", owner_id="n1")
    score = Score(id="s1", target="f1", plan_type="Assault")

    for entity in (faction, npc, location, item, score):
        assert type(entity).model_validate_json(entity.model_dump_json()) == entity
