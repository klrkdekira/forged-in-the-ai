from ai.tools import GameState
from engine.campaign import CampaignCanon, SessionZeroConfig
from engine.character import Attribute
from engine.clocks import Clock, ClockKind
from engine.entities import Npc
from engine.events import Event, EventLog
from engine.operations import (
    adjust_coin,
    heal_character,
    mark_attribute_xp,
    mark_harm,
    mark_playbook_xp,
    mark_stress,
    set_item_carried,
)
from engine.relationships import FactionStatus, Relationship, RelationshipKind
from engine.session import CampaignPhase


def replay_state(base: GameState, events: list[Event]) -> GameState:
    """FR-19: reconstruct a campaign's state by folding events onto its
    original starting state - the mechanism undo/rewind
    (state/campaign_store.undo_to) is built on: truncate the log, then
    replay what survives. Reuses the exact same engine/operations.py
    functions ToolExecutor calls live, so replay and live play can never
    disagree about what an event means (NFR-1).

    Event types with no state to fold - action_roll, fortune_roll,
    resistance_roll (pure dice records), player_message/narration (FR-31's
    turn log), x_card_invoked (a safety-tool note, not a mutation) - are
    silently skipped."""
    character = base.character
    crew = base.crew
    session = base.session
    clocks = dict(base.clocks)
    npcs = dict(base.npcs)
    faction_statuses = dict(base.faction_statuses)
    relationships = dict(base.relationships)
    canon = base.canon
    session_zero = base.session_zero
    ordered = sorted(events, key=lambda e: e.sequence)

    for event in ordered:
        payload = event.payload
        if event.event_type == "stress_marked":
            character = mark_stress(character, payload["amount"]).character
        elif event.event_type == "harm_marked":
            character = mark_harm(character, payload["level"], payload["name"]).character
        elif event.event_type == "harm_healed":
            character = heal_character(character)
        elif event.event_type == "xp_marked":
            if payload["track"] == "playbook":
                character = mark_playbook_xp(character, payload["amount"])
            else:
                attribute = Attribute(payload["track"])
                character = mark_attribute_xp(character, attribute, payload["amount"])
        elif event.event_type == "coin_adjusted":
            character = adjust_coin(character, payload["amount"])
        elif event.event_type == "item_carried_set":
            character = set_item_carried(character, payload["item_id"], payload["carried"])
        elif event.event_type == "clock_created":
            clocks[event.entity_id] = Clock(
                name=payload["name"],
                kind=ClockKind(payload["kind"]),
                segments=payload["segments"],
            )
        elif event.event_type == "clock_ticked":
            clocks[event.entity_id] = clocks[event.entity_id].tick(payload["amount"])
        elif event.event_type == "phase_transitioned":
            session = session.transition_to(CampaignPhase(payload["phase"]))
        elif event.event_type == "npc_created":
            npcs[event.entity_id] = Npc.model_validate(payload)
        elif event.event_type == "faction_status_changed":
            current = faction_statuses.get(
                event.entity_id, FactionStatus(crew_id=crew.name, faction_id=event.entity_id)
            )
            faction_statuses[event.entity_id] = current.changed(payload["delta"], event.sequence)
        elif event.event_type == "canon_fact_added" and canon is not None:
            canon = canon.with_fact(payload["fact"])
        elif event.event_type == "canon_location_added" and canon is not None:
            canon = canon.with_location(payload["location"])
        elif event.event_type == "session_zero_configured":
            session_zero = SessionZeroConfig.model_validate(payload)
        elif event.event_type == "canon_set":
            canon = CampaignCanon.model_validate(payload)
        elif event.event_type == "relationship_updated":
            current = relationships.get(
                event.entity_id,
                Relationship(
                    subject_type=payload["subject_type"],
                    subject_id=payload["subject_id"],
                    object_type=payload["object_type"],
                    object_id=payload["object_id"],
                    kind=RelationshipKind(payload["kind"]),
                ),
            )
            relationships[event.entity_id] = current.updated(
                RelationshipKind(payload["kind"]), payload["status"], event.sequence
            )

    return base.model_copy(
        update={
            "character": character,
            "crew": crew,
            "session": session,
            "clocks": clocks,
            "npcs": npcs,
            "faction_statuses": faction_statuses,
            "relationships": relationships,
            "canon": canon,
            "session_zero": session_zero,
            "log": EventLog(events=ordered),
        }
    )
