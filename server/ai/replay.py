from ai.tools import GameState
from engine.advancement import (
    advance_action_rating,
    advance_crew_special_ability,
    advance_crew_upgrades,
    advance_special_ability,
)
from engine.campaign import CampaignCanon, SessionZeroConfig
from engine.character import Action, Attribute, Character, LoadLevel
from engine.clocks import Clock, ClockKind
from engine.controller import Controller
from engine.entities import Faction, Npc, Score
from engine.events import Event, EventLog
from engine.operations import (
    add_heat,
    adjust_coin,
    adjust_crew_coin,
    adjust_crew_rep,
    adjust_crew_turf,
    adjust_stash,
    adjust_wanted_level,
    develop_crew,
    flashback,
    heal_character,
    mark_attribute_xp,
    mark_crew_xp,
    mark_harm,
    mark_playbook_xp,
    mark_stress,
    mark_trauma,
    restore_armor,
    set_claim_controlled,
    set_item_carried,
    set_load_level,
    use_armor,
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

    Event types with no mechanical result to fold - action_roll, fortune_roll,
    resistance_roll, engagement_roll, entanglement_roll (pure dice/roll
    records) - are silently skipped. Asset, vice, and downtime activity events
    also fold the phase-scoped downtime allowance counters below, while their
    activity-specific mechanical state is folded by subsequent events.
    player_message/narration (FR-31's turn log), x_card_invoked (a
    safety-tool note, not a mutation), companion_roll_decision (FR-35's
    own record of what an AI companion chose - the roll it led to is
    already folded via action_roll/stress_marked) - are silently
    skipped."""
    characters = dict(base.characters)
    controllers = dict(base.controllers)
    crew = base.crew
    session = base.session
    clocks = dict(base.clocks)
    npcs = dict(base.npcs)
    scores = dict(base.scores)
    factions = dict(base.factions)
    faction_statuses = dict(base.faction_statuses)
    relationships = dict(base.relationships)
    canon = base.canon
    session_zero = base.session_zero
    ordered = sorted(events, key=lambda e: e.sequence)

    def replay_downtime_activity(character_id: str | None, track: str | None = None) -> None:
        nonlocal session
        if session.phase is not CampaignPhase.DOWNTIME or character_id not in characters:
            return
        session = session.begin_downtime_activity(character_id, track)

    for event in ordered:
        payload = event.payload
        if event.event_type == "character_created":
            characters[event.entity_id] = Character.model_validate(payload)
            seat_id = f"seat:{event.entity_id}"
            controllers[seat_id] = Controller(
                seat_id=seat_id,
                kind=payload.get("controller_kind", "human"),
                character_ids=[event.entity_id],
            )
        elif event.event_type == "controller_assigned":
            entity_type = payload.get("entity_type", "character")
            entity_id = payload.get("entity_id", payload.get("character_id"))
            for seat_id, seat in list(controllers.items()):
                controllers[seat_id] = seat.model_copy(
                    update={
                        "character_ids": [
                            cid for cid in seat.character_ids
                            if not (entity_type == "character" and cid == entity_id)
                        ],
                        "cohort_ids": [
                            cid for cid in seat.cohort_ids
                            if not (entity_type == "cohort" and cid == entity_id)
                        ]
                    }
                )
            seat_id = payload["seat_id"]
            seat = controllers.get(seat_id, Controller(seat_id=seat_id, kind=payload["kind"]))
            controllers[seat_id] = seat.model_copy(
                update={
                    "kind": payload["kind"],
                    "character_ids": [*seat.character_ids, entity_id]
                    if entity_type == "character" else seat.character_ids,
                    "cohort_ids": [*seat.cohort_ids, entity_id]
                    if entity_type == "cohort" else seat.cohort_ids,
                }
            )
        elif event.event_type == "stress_marked":
            character = mark_stress(
                characters[event.entity_id], payload["amount"]
            ).character
            characters[event.entity_id] = character.model_copy(
                update={"trauma_pending": payload.get("triggered_trauma", False)}
            )
        elif event.event_type == "harm_marked":
            characters[event.entity_id] = mark_harm(
                characters[event.entity_id], payload["level"], payload["name"]
            ).character
        elif event.event_type == "harm_healed":
            characters[event.entity_id] = heal_character(characters[event.entity_id])
        elif event.event_type == "healing_clock_ticked":
            character = characters[event.entity_id]
            characters[event.entity_id] = character.model_copy(
                update={
                    "healing_clock": character.healing_clock.tick(payload["amount"]),
                }
            )
        elif event.event_type == "healing_clock_reset":
            character = characters[event.entity_id]
            characters[event.entity_id] = character.model_copy(
                update={
                    "healing_clock": character.healing_clock.model_copy(update={"filled": 0}),
                }
            )
        elif event.event_type == "trauma_marked":
            character = mark_trauma(
                characters[event.entity_id], payload["condition"]
            )
            characters[event.entity_id] = character.model_copy(update={"trauma_pending": False})
        elif event.event_type == "armor_used":
            characters[event.entity_id] = use_armor(
                characters[event.entity_id], payload["armor_type"]
            )
        elif event.event_type == "armor_restored":
            characters[event.entity_id] = restore_armor(characters[event.entity_id])
        elif event.event_type == "stash_adjusted":
            characters[event.entity_id] = adjust_stash(
                characters[event.entity_id], payload["amount"]
            )
        elif event.event_type == "load_level_set":
            characters[event.entity_id] = set_load_level(
                characters[event.entity_id], LoadLevel(payload["level"])
            )
        elif event.event_type == "xp_marked":
            if payload["amount"] > 0:
                replay_downtime_activity(event.entity_id, payload["track"])
            if payload["track"] == "playbook":
                characters[event.entity_id] = mark_playbook_xp(
                    characters[event.entity_id], payload["amount"]
                )
            else:
                attribute = Attribute(payload["track"])
                characters[event.entity_id] = mark_attribute_xp(
                    characters[event.entity_id], attribute, payload["amount"]
                )
        elif event.event_type == "coin_adjusted":
            characters[event.entity_id] = adjust_coin(
                characters[event.entity_id], payload["amount"]
            )
        elif event.event_type == "item_carried_set":
            characters[event.entity_id] = set_item_carried(
                characters[event.entity_id], payload["item_id"], payload["carried"]
            )
        elif event.event_type == "clock_created":
            clocks[event.entity_id] = Clock(
                name=payload["name"],
                kind=ClockKind(payload["kind"]),
                segments=payload["segments"],
            )
            faction_id = payload.get("faction_id")
            if faction_id in factions:
                faction = factions[faction_id]
                factions[faction_id] = faction.model_copy(
                    update={"clock_ids": [*faction.clock_ids, event.entity_id]}
                )
        elif event.event_type == "clock_ticked":
            clocks[event.entity_id] = clocks[event.entity_id].tick(payload["amount"])
        elif event.event_type == "phase_transitioned":
            session = session.transition_to(CampaignPhase(payload["phase"]))
        elif event.event_type == "engagement_roll":
            session = session.model_copy(update={"score_engagement_completed": True})
        elif event.event_type == "action_roll":
            session = session.model_copy(update={"score_action_completed": True})
        elif event.event_type == "entanglement_roll":
            session = session.model_copy(update={"score_entanglement_completed": True})
        elif event.event_type == "asset_acquired":
            replay_downtime_activity(payload.get("character_id"))
        elif event.event_type == "vice_indulged":
            replay_downtime_activity(event.entity_id)
        elif event.event_type == "downtime_activity_rolled":
            replay_downtime_activity(payload.get("character_id"))
        elif event.event_type == "npc_created":
            npcs[event.entity_id] = Npc.model_validate(payload)
            faction_id = payload.get("faction_id")
            if faction_id in factions:
                faction = factions[faction_id]
                factions[faction_id] = faction.model_copy(
                    update={"notable_npc_ids": [*faction.notable_npc_ids, event.entity_id]}
                )
        elif event.event_type == "score_created":
            scores[event.entity_id] = Score.model_validate(payload)
        elif event.event_type == "score_updated":
            scores[event.entity_id] = scores[event.entity_id].model_copy(update=payload)
        elif event.event_type == "faction_status_changed":
            current = faction_statuses.get(
                event.entity_id, FactionStatus(crew_id=crew.name, faction_id=event.entity_id)
            )
            faction_statuses[event.entity_id] = current.changed(payload["delta"], event.sequence)
        elif event.event_type == "canon_fact_added" and canon is not None:
            canon = canon.with_fact(payload["fact"])
        elif event.event_type == "canon_location_added" and canon is not None:
            canon = canon.with_location(payload["location"])
        elif event.event_type == "canon_faction_added":
            factions[event.entity_id] = Faction.model_validate(payload)
            if canon is not None:
                canon = canon.with_faction(payload["name"])
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
        elif event.event_type == "heat_added":
            crew = add_heat(crew, payload["amount"]).crew
            if session.phase is CampaignPhase.DOWNTIME and session.score_payoff_completed:
                session = session.model_copy(update={"score_heat_completed": True})
        elif event.event_type == "wanted_level_adjusted":
            crew = adjust_wanted_level(crew, payload["amount"])
        elif event.event_type == "crew_rep_adjusted":
            crew = adjust_crew_rep(crew, payload["amount"])
        elif event.event_type == "crew_coin_adjusted":
            crew = adjust_crew_coin(crew, payload["amount"])
        elif event.event_type == "crew_turf_adjusted":
            crew = adjust_crew_turf(crew, payload["amount"])
        elif event.event_type == "claim_controlled_set":
            crew = set_claim_controlled(
                crew,
                payload["claim_id"],
                payload["controlled"],
                name=payload.get("name"),
                is_turf=payload.get("is_turf", False),
            )
        elif event.event_type == "crew_developed":
            crew = develop_crew(crew)
        elif event.event_type == "crew_xp_marked":
            crew = mark_crew_xp(crew, payload["amount"])
        elif event.event_type == "payoff":
            crew = crew.model_copy(
                update={
                    "rep": crew.rep.add_rep(payload["rep"]),
                    "coin": crew.coin + payload["coin"],
                }
            )
            session = session.model_copy(update={"score_payoff_completed": True})
        elif event.event_type == "flashback_taken":
            characters[event.entity_id] = flashback(
                characters[event.entity_id], payload["stress_cost"]
            ).character
        elif event.event_type == "action_advanced":
            characters[event.entity_id] = advance_action_rating(
                characters[event.entity_id], Action(payload["action"]), payload["cap"]
            )
        elif event.event_type == "special_ability_advanced":
            characters[event.entity_id] = advance_special_ability(
                characters[event.entity_id], payload["ability_id"]
            )
        elif event.event_type == "crew_special_ability_advanced":
            crew = advance_crew_special_ability(crew, payload["ability_id"])
        elif event.event_type == "crew_upgrades_advanced":
            crew = advance_crew_upgrades(crew, tuple(payload["upgrade_ids"]))

    return base.model_copy(
        update={
            "characters": characters,
            "controllers": controllers,
            "crew": crew,
            "session": session,
            "clocks": clocks,
            "npcs": npcs,
            "scores": scores,
            "factions": factions,
            "faction_statuses": faction_statuses,
            "relationships": relationships,
            "canon": canon,
            "session_zero": session_zero,
            "log": EventLog(events=ordered),
        }
    )
