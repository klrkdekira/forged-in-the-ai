from datetime import UTC, datetime

from ai.replay import replay_state
from ai.tools import GameState
from engine.campaign import CampaignCanon
from engine.character import Action, Attribute, Character
from engine.crew import Crew
from engine.entities import Faction
from engine.session import CampaignPhase, Session

AT = datetime(2026, 1, 1, tzinfo=UTC)


def _base_state() -> GameState:
    return GameState(
        character=Character(name="Scoundrel", playbook="Cutter"),
        crew=Crew(name="The Fifth Foxglove", crew_type="Assassins"),
        session=Session(),
    )


def test_replay_state_links_a_created_npc_to_its_faction():
    base = _base_state().model_copy(
        update={"factions": {"f1": Faction(id="f1", name="The Circle")}}
    )
    log = base.log.append(
        "npc",
        "n1",
        "npc_created",
        {"id": "n1", "name": "Informant", "tags": [], "faction_id": "f1", "notes": None},
        AT,
    )

    replayed = replay_state(base, log.events)

    assert replayed.factions["f1"].notable_npc_ids == ["n1"]


def test_replay_state_folds_stress_and_harm_onto_the_base_character():
    base = _base_state()
    log = base.log
    log = log.append("character", "pc-1", "stress_marked", {"amount": 3}, AT)
    log = log.append("character", "pc-1", "harm_marked", {"level": 2, "name": "Stabbed"}, AT)

    replayed = replay_state(base, log.events)

    assert replayed.character.stress.marked == 3
    assert replayed.character.harm.entries[-1].name == "Stabbed"


def test_replay_state_folds_a_second_character_and_its_own_stress():
    # FR-25/FR-35: undo/rewind must not drop a second PC, or fold its
    # stress onto the wrong character.
    base = _base_state()
    log = base.log
    log = log.append(
        "character",
        "pc-2",
        "character_created",
        {"name": "Vex", "playbook": "Whisper"},
        AT,
    )
    log = log.append("character", "pc-2", "stress_marked", {"amount": 2}, AT)

    replayed = replay_state(base, log.events)

    assert replayed.characters["pc-2"].name == "Vex"
    assert replayed.characters["pc-2"].stress.marked == 2
    assert replayed.characters["pc-1"].stress.marked == 0
    # No "controller_kind" in this (older-shaped) payload - defaults to
    # human, same as GameState.controllers having no entry at all.
    assert replayed.controllers["seat:pc-2"].kind == "human"


def test_replay_state_folds_a_created_characters_ai_controller_seat():
    # FR-35: undo/rewind must not drop which seat a companion belongs to.
    base = _base_state()
    log = base.log.append(
        "character",
        "pc-2",
        "character_created",
        {"name": "Vex", "playbook": "Whisper", "controller_kind": "ai"},
        AT,
    )

    replayed = replay_state(base, log.events)

    assert replayed.controllers["seat:pc-2"].kind == "ai"
    assert replayed.controllers["seat:pc-2"].character_ids == ["pc-2"]


def test_replay_state_folds_clock_creation_and_ticks():
    base = _base_state()
    log = base.log
    log = log.append(
        "clock", "alert", "clock_created", {"name": "Alert", "kind": "danger", "segments": 4}, AT
    )
    log = log.append("clock", "alert", "clock_ticked", {"amount": 2}, AT)

    replayed = replay_state(base, log.events)

    assert replayed.clocks["alert"].filled == 2


def test_replay_state_folds_phase_transitions():
    base = _base_state()
    log = base.log.append("session", "current", "phase_transitioned", {"phase": "score"}, AT)

    replayed = replay_state(base, log.events)

    assert replayed.session.phase is CampaignPhase.SCORE


def test_replay_state_skips_pure_record_events():
    # action_roll/fortune_roll/resistance_roll/player_message/narration/
    # x_card_invoked carry no state to fold - only the log should reflect
    # them.
    base = _base_state()
    log = base.log.append("session", "current", "player_message", {"text": "I look around."}, AT)

    replayed = replay_state(base, log.events)

    assert replayed.character == base.character
    assert len(replayed.log.events) == 1


def test_replay_state_folds_session_zero_configuration_and_canon():
    # FR-17/FR-36: undo/rewind must not silently drop session-zero data
    # when replaying past it.
    base = _base_state()
    log = base.log
    log = log.append(
        "session",
        "current",
        "session_zero_configured",
        {"lines": ["no animal harm"], "veils": ["torture"], "tone": "pulpy noir"},
        AT,
    )
    log = log.append(
        "canon",
        "Harrow's Reach",
        "canon_set",
        {
            "setting_name": "Harrow's Reach",
            "tone": "rain-soaked industrial",
            "factions": ["The Rustworks Combine"],
            "locations": ["The Sunken Market"],
            "facts": [],
        },
        AT,
    )

    replayed = replay_state(base, log.events)

    assert replayed.session_zero.lines == ["no animal harm"]
    assert replayed.canon.setting_name == "Harrow's Reach"
    assert replayed.canon.factions == ["The Rustworks Combine"]


def test_replay_state_folds_newly_discovered_locations_onto_canon():
    # FR-15: the map grows during play - undo/rewind must not drop a
    # location discovered after session zero.
    base = _base_state()
    log = base.log
    log = log.append(
        "canon",
        "Harrow's Reach",
        "canon_set",
        {
            "setting_name": "Harrow's Reach",
            "tone": None,
            "factions": [],
            "locations": ["The Sunken Market"],
            "facts": [],
        },
        AT,
    )
    log = log.append(
        "canon", "Harrow's Reach", "canon_location_added", {"location": "The Old Quarter"}, AT
    )

    replayed = replay_state(base, log.events)

    assert replayed.canon.locations == ["The Sunken Market", "The Old Quarter"]


def test_replay_state_folds_relationship_updates_and_accumulates_history():
    # FR-33/FR-34: undo/rewind must not drop a relationship, and a second
    # update to the same edge must extend its history, not replace it.
    base = _base_state()
    log = base.log
    log = log.append(
        "relationship",
        "character:Scoundrel:npc:n1",
        "relationship_updated",
        {
            "subject_type": "character",
            "subject_id": "Scoundrel",
            "object_type": "npc",
            "object_id": "n1",
            "kind": "ally",
            "status": "owes a favour",
        },
        AT,
    )
    log = log.append(
        "relationship",
        "character:Scoundrel:npc:n1",
        "relationship_updated",
        {
            "subject_type": "character",
            "subject_id": "Scoundrel",
            "object_type": "npc",
            "object_id": "n1",
            "kind": "rival",
            "status": "betrayed the crew",
        },
        AT,
    )

    replayed = replay_state(base, log.events)

    edge = replayed.relationships["character:Scoundrel:npc:n1"]
    assert edge.kind.value == "rival"
    assert edge.status == "betrayed the crew"
    assert edge.history == [1, 2]


def test_replay_state_folds_crew_heat_and_payoff():
    base = _base_state()
    log = base.log
    log = log.append("crew", "The Fifth Foxglove", "heat_added", {"amount": 4}, AT)
    log = log.append(
        "crew",
        "The Fifth Foxglove",
        "payoff",
        {"rep": 3, "coin": 4, "target_tier": 2, "quiet": False},
        AT,
    )

    replayed = replay_state(base, log.events)

    assert replayed.crew.heat.heat == 4
    assert replayed.crew.rep.rep == 3
    assert replayed.crew.coin == 4


def test_replay_state_folds_score_creation_and_updates():
    base = _base_state()
    log = base.log
    log = log.append(
        "score",
        "s1",
        "score_created",
        {
            "id": "s1",
            "target": "The Silver Vault",
            "plan_type": "Assault",
            "plan_detail": None,
            "engagement_result": None,
            "payoff": None,
            "heat_gained": None,
            "entanglement": None,
        },
        AT,
    )
    log = log.append("score", "s1", "score_updated", {"engagement_result": "controlled"}, AT)
    log = log.append("score", "s1", "score_updated", {"payoff": 6, "heat_gained": 2}, AT)

    replayed = replay_state(base, log.events)

    score = replayed.scores["s1"]
    assert score.target == "The Silver Vault"
    assert score.engagement_result == "controlled"
    assert score.payoff == 6
    assert score.heat_gained == 2


def test_replay_state_folds_wanted_level_and_crew_rep_and_coin_adjustments():
    base = _base_state()
    log = base.log
    log = log.append("crew", "The Fifth Foxglove", "wanted_level_adjusted", {"amount": 2}, AT)
    log = log.append("crew", "The Fifth Foxglove", "crew_rep_adjusted", {"amount": 3}, AT)
    log = log.append("crew", "The Fifth Foxglove", "crew_coin_adjusted", {"amount": 4}, AT)

    replayed = replay_state(base, log.events)

    assert replayed.crew.wanted_level == 2
    assert replayed.crew.rep.rep == 3
    assert replayed.crew.coin == 4


def test_replay_state_folds_crew_xp_marks():
    # SRD: "Crew Advancement" - end-of-session crew trigger review.
    base = _base_state()
    log = base.log.append(
        "crew", "The Fifth Foxglove", "crew_xp_marked", {"amount": 2, "reason": "bolstered rep"}, AT
    )

    replayed = replay_state(base, log.events)

    assert replayed.crew.xp.marked == 2


def test_replay_state_folds_flashbacks():
    base = _base_state()
    log = base.log.append(
        "character", "pc-1", "flashback_taken", {"stress_cost": 2, "triggered_trauma": False}, AT
    )

    replayed = replay_state(base, log.events)

    assert replayed.character.stress.marked == 2


def test_replay_state_folds_action_and_ability_advancement():
    base = _base_state().model_copy(
        update={
            "characters": {
                "pc-1": Character(
                    name="Scoundrel",
                    playbook="Cutter",
                    action_ratings={Action.PROWL: 1},
                    attribute_xp={Attribute.PROWESS: {"marked": 6, "segments": 6}},
                    playbook_xp={"marked": 8, "segments": 8},
                )
            }
        }
    )
    log = base.log
    log = log.append(
        "character",
        "pc-1",
        "action_advanced",
        {"action": "prowl", "new_rating": 2, "cap": 3},
        AT,
    )
    log = log.append("character", "pc-1", "special_ability_advanced", {"ability_id": "veteran"}, AT)

    replayed = replay_state(base, log.events)

    assert replayed.character.action_ratings[Action.PROWL] == 2
    assert "veteran" in replayed.character.special_ability_ids


def test_replay_state_folds_crew_advancement():
    base = _base_state().model_copy(
        update={
            "crew": Crew(
                name="The Fifth Foxglove",
                crew_type="Assassins",
                xp={"marked": 8, "segments": 8},
            )
        }
    )
    log = base.log
    log = log.append(
        "crew", "The Fifth Foxglove", "crew_special_ability_advanced", {"ability_id": "vice"}, AT
    )

    replayed = replay_state(base, log.events)

    assert "vice" in replayed.crew.special_ability_ids


def test_replay_state_folds_crew_upgrades():
    base = _base_state().model_copy(
        update={
            "crew": Crew(
                name="The Fifth Foxglove",
                crew_type="Assassins",
                xp={"marked": 8, "segments": 8},
            )
        }
    )
    log = base.log.append(
        "crew",
        "The Fifth Foxglove",
        "crew_upgrades_advanced",
        {"upgrade_ids": ["quality", "quality"]},
        AT,
    )

    replayed = replay_state(base, log.events)

    assert replayed.crew.upgrade_ids == ["quality", "quality"]


def test_replay_state_skips_downtime_and_score_roll_records():
    # engagement_roll/entanglement_roll/asset_acquired/downtime_activity_rolled/
    # vice_indulged are pure records - only the log should reflect them.
    base = _base_state()
    log = base.log.append(
        "score", "current", "engagement_roll", {"band": "6", "position": "controlled"}, AT
    )

    replayed = replay_state(base, log.events)

    assert replayed.crew == base.crew
    assert len(replayed.log.events) == 1


def test_replay_state_folds_downtime_activity_allowances():
    # SRD: "Downtime Activities" - replay must preserve the two-free-
    # activity counter used to refuse an unpaid third activity.
    base = _base_state()
    log = base.log
    log = log.append("session", "current", "phase_transitioned", {"phase": "score"}, AT)
    log = log.append("session", "current", "phase_transitioned", {"phase": "downtime"}, AT)
    log = log.append(
        "character",
        "pc-1",
        "downtime_activity_rolled",
        {"activity": "craft", "character_id": "pc-1"},
        AT,
    )

    replayed = replay_state(base, log.events)

    assert replayed.session.downtime_activity_counts == {"pc-1": 1}


def test_replay_state_skips_companion_roll_decision_records():
    # FR-35: a pure record of what an AI companion chose - the roll it
    # led to is already folded via action_roll/stress_marked.
    base = _base_state()
    log = base.log.append("character", "pc-1", "companion_roll_decision", {"push_dice": True}, AT)

    replayed = replay_state(base, log.events)

    assert replayed.character == base.character
    assert len(replayed.log.events) == 1


def test_replay_state_reproduces_a_truncated_prefix_of_the_log():
    # This is the mechanism undo/rewind is built on: replaying only a
    # prefix of the log reconstructs state as of that earlier point.
    base = _base_state()
    log = base.log
    log = log.append("character", "pc-1", "stress_marked", {"amount": 2}, AT)
    log = log.append("character", "pc-1", "coin_adjusted", {"amount": 5}, AT)

    prefix = [e for e in log.events if e.sequence == 1]
    replayed = replay_state(base, prefix)

    assert replayed.character.stress.marked == 2
    assert replayed.character.coin == 0


def test_replay_state_folds_trauma_and_armor_events():
    # SRD: "Trauma" - conditions are permanent; SRD: "Armor" - a marked
    # box stays marked until restored. Undo/rewind must keep both.
    base = _base_state().model_copy(
        update={
            "characters": {
                "pc-1": Character(name="Scoundrel", playbook="Cutter", armor={"has_armor": True})
            }
        }
    )
    log = base.log
    log = log.append(
        "character", "pc-1", "trauma_marked", {"condition": "haunted", "retired": False}, AT
    )
    log = log.append("character", "pc-1", "armor_used", {"armor_type": "standard"}, AT)

    replayed = replay_state(base, log.events)

    assert replayed.character.trauma.conditions == ["haunted"]
    assert replayed.character.armor.armor_used

    restored_log = log.append("character", "pc-1", "armor_restored", {}, AT)
    restored = replay_state(base, restored_log.events)

    assert not restored.character.armor.armor_used


def test_replay_state_folds_stash_and_load_level():
    base = _base_state()
    log = base.log
    log = log.append("character", "pc-1", "stash_adjusted", {"amount": 3}, AT)
    log = log.append("character", "pc-1", "load_level_set", {"level": "light"}, AT)

    replayed = replay_state(base, log.events)

    assert replayed.character.stash == 3
    assert replayed.character.load_level.value == "light"


def test_replay_state_folds_crew_development_turf_and_claims():
    # SRD: "Development" / "Turf" / "Seizing a claim".
    base = _base_state().model_copy(
        update={
            "crew": Crew(
                name="The Fifth Foxglove",
                crew_type="Assassins",
                hold="weak",
                rep={"rep": 12},
            )
        }
    )
    log = base.log
    log = log.append(
        "crew", "The Fifth Foxglove", "crew_developed", {"tier": 0, "hold": "strong"}, AT
    )
    log = log.append("crew", "The Fifth Foxglove", "crew_turf_adjusted", {"amount": 1}, AT)
    log = log.append(
        "crew",
        "The Fifth Foxglove",
        "claim_controlled_set",
        {"claim_id": "docks", "controlled": True, "name": "The Docks", "is_turf": True},
        AT,
    )

    replayed = replay_state(base, log.events)

    assert replayed.crew.hold.value == "strong"
    assert replayed.crew.rep.rep == 0
    assert replayed.crew.rep.turf == 2  # 1 direct + 1 from the turf claim
    assert replayed.crew.claims[0].controlled


def test_replay_state_folds_canon_factions_and_their_clocks():
    # FR-14/FR-15: undo/rewind must not drop a faction or unlink its clock.
    base = _base_state().model_copy(
        update={
            "canon": CampaignCanon(setting_name="Harrow's Reach"),
        }
    )
    log = base.log
    log = log.append(
        "faction",
        "red-circle",
        "canon_faction_added",
        {"id": "red-circle", "name": "The Red Circle", "tier": 2},
        AT,
    )
    log = log.append(
        "clock",
        "rc-plot",
        "clock_created",
        {"name": "Seize the docks", "kind": "faction", "segments": 6, "faction_id": "red-circle"},
        AT,
    )

    replayed = replay_state(base, log.events)

    assert replayed.factions["red-circle"].name == "The Red Circle"
    assert replayed.factions["red-circle"].clock_ids == ["rc-plot"]
    assert replayed.canon.factions == ["The Red Circle"]
