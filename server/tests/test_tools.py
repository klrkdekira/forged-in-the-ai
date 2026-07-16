import random
from datetime import UTC, datetime

import pytest

from ai.tools import (
    SHEET_OPERATIONS,
    AcquireAssetArgs,
    AddCanonFactArgs,
    AddCanonLocationArgs,
    AddCrewHeatArgs,
    AdjustCoinArgs,
    AdvanceActionRatingArgs,
    AdvanceCrewSpecialAbilityArgs,
    AdvanceCrewUpgradesArgs,
    AdvanceSpecialAbilityArgs,
    ApplyHarmArgs,
    CreateCharacterArgs,
    CreateClockArgs,
    CreateNpcArgs,
    CreateScoreArgs,
    FlashbackArgs,
    GameState,
    HealCharacterArgs,
    IndulgeViceArgs,
    InvokeXCardArgs,
    LongTermProjectArgs,
    MarkStressArgs,
    MarkXpArgs,
    RecoverArgs,
    ReduceHeatArgs,
    ResolvePayoffArgs,
    RollActionArgs,
    RollEngagementArgs,
    RollEntanglementArgs,
    RollFortuneArgs,
    RollResistanceArgs,
    SetCampaignCanonArgs,
    SetItemCarriedArgs,
    SetSessionZeroConfigArgs,
    TickClockArgs,
    ToolExecutor,
    TransitionPhaseArgs,
    UpdateFactionStatusArgs,
    UpdateRelationshipArgs,
    UpdateScoreArgs,
    tool_definitions,
)
from engine.campaign import CampaignCanon
from engine.character import Action, Attribute, Character, CharacterItem
from engine.clocks import ClockKind
from engine.crew import Crew
from engine.errors import EngineError
from engine.packs import EntanglementEntry
from engine.relationships import RelationshipKind
from engine.rolls import Effect, Position
from engine.session import CampaignPhase, Session

AT = datetime(2026, 1, 1, tzinfo=UTC)


def _state(character: Character | None = None) -> GameState:
    return GameState(
        character=character
        or Character(
            name="Test",
            playbook="Test Playbook",
            action_ratings={Action.PROWL: 2},
        ),
        crew=Crew(name="Test Crew", crew_type="Test Type"),
        session=Session(),
    )


def _executor(seed: int = 1, entanglements: list[EntanglementEntry] | None = None) -> ToolExecutor:
    return ToolExecutor(
        rng=random.Random(seed), clock=lambda: AT, entanglements=entanglements or []
    )


_ENTANGLEMENTS = [
    EntanglementEntry(heat_band="0-3", roll_result="1-3", entanglement="Gang Trouble"),
    EntanglementEntry(heat_band="0-3", roll_result="4/5", entanglement="Rivals"),
    EntanglementEntry(heat_band="0-3", roll_result="6", entanglement="Rough Trade"),
    EntanglementEntry(heat_band="4-5", roll_result="1-3", entanglement="Snitch"),
    EntanglementEntry(heat_band="4-5", roll_result="4/5", entanglement="Extradition"),
    EntanglementEntry(heat_band="4-5", roll_result="6", entanglement="Extortion"),
    EntanglementEntry(heat_band="6", roll_result="1-3", entanglement="Warrant"),
    EntanglementEntry(heat_band="6", roll_result="4/5", entanglement="Crackdown"),
    EntanglementEntry(heat_band="6", roll_result="6", entanglement="Unquiet Dead"),
]


def test_tool_definitions_cover_every_registered_tool():
    # FR-12: an OpenAI-compatible tools payload.
    definitions = tool_definitions()

    names = {d["function"]["name"] for d in definitions}
    assert names == {
        "roll_action",
        "roll_fortune",
        "roll_resistance",
        "create_clock",
        "tick_clock",
        "apply_harm",
        "mark_stress",
        "transition_phase",
        "create_score",
        "update_score",
        "create_npc",
        "create_character",
        "update_faction_status",
        "update_relationship",
        "add_canon_fact",
        "add_canon_location",
        "invoke_x_card",
        "set_session_zero_config",
        "set_campaign_canon",
        "roll_engagement",
        "resolve_payoff",
        "add_crew_heat",
        "roll_entanglement",
        "acquire_asset",
        "indulge_vice",
        "reduce_heat",
        "recover",
        "long_term_project",
        "flashback",
        "mark_xp",
        "advance_action_rating",
        "advance_special_ability",
        "advance_crew_special_ability",
        "advance_crew_upgrades",
    }
    assert all("parameters" in d["function"] for d in definitions)


def test_roll_action_args_accepts_effect_by_name():
    # Effect is an IntEnum for its bumped() arithmetic, but a tool call
    # (human or model) should be able to pass "standard", not a raw 2.
    args = RollActionArgs(action=Action.PROWL, position=Position.RISKY, effect="standard")

    assert args.effect is Effect.STANDARD


def test_roll_action_args_still_accepts_the_effect_enum_directly():
    args = RollActionArgs(action=Action.PROWL, position=Position.RISKY, effect=Effect.GREAT)

    assert args.effect is Effect.GREAT


def test_roll_action_uses_the_character_action_rating_and_logs_it():
    result = _executor().roll_action(
        _state(),
        RollActionArgs(action=Action.PROWL, position=Position.RISKY, effect=Effect.STANDARD),
    )

    assert result.result["position"] == "risky"
    assert result.state.log.events[-1].event_type == "action_roll"
    assert result.state.log.events[-1].occurred_at == AT


def test_roll_fortune_logs_an_event():
    result = _executor().roll_fortune(_state(), RollFortuneArgs(pool_size=2))

    assert result.state.log.events[-1].event_type == "fortune_roll"


def test_roll_resistance_uses_the_character_attribute_rating():
    state = _state()
    result = _executor().roll_resistance(state, RollResistanceArgs(attribute=Attribute.PROWESS))

    assert "stress_delta" in result.result


def test_create_clock_then_tick_clock():
    state = (
        _executor()
        .create_clock(
            _state(),
            CreateClockArgs(clock_id="alert", name="Alert", kind=ClockKind.DANGER, segments=4),
        )
        .state
    )

    result = _executor(seed=2).tick_clock(state, TickClockArgs(clock_id="alert", amount=2))

    assert result.state.clocks["alert"].filled == 2
    assert result.state.log.events[-1].event_type == "clock_ticked"


def test_tick_clock_refuses_an_unknown_clock_id():
    with pytest.raises(EngineError, match="no clock"):
        _executor().tick_clock(_state(), TickClockArgs(clock_id="nope", amount=1))


def test_apply_harm_updates_the_character_and_reports_catastrophe():
    result = _executor().apply_harm(_state(), ApplyHarmArgs(level=4, name="Stabbed in the Heart"))

    assert result.result["catastrophic"]
    assert result.state.character.harm.entries == []


def test_mark_stress_updates_the_character():
    result = _executor().mark_stress(_state(), MarkStressArgs(amount=3))

    assert result.state.character.stress.marked == 3
    assert not result.result["triggered_trauma"]


def test_transition_phase_moves_the_session_forward():
    result = _executor().transition_phase(_state(), TransitionPhaseArgs(phase=CampaignPhase.SCORE))

    assert result.state.session.phase is CampaignPhase.SCORE


def test_transition_phase_refuses_an_illegal_transition():
    from engine.session import InvalidPhaseTransitionError

    with pytest.raises(InvalidPhaseTransitionError):
        _executor().transition_phase(_state(), TransitionPhaseArgs(phase=CampaignPhase.DOWNTIME))


def test_create_npc_adds_it_to_state():
    # SPECIFICATION.md §5: "NPC ... lightweight entities with tags"
    result = _executor().create_npc(
        _state(), CreateNpcArgs(npc_id="n1", name="Test NPC", tags=["informant"])
    )

    assert result.state.npcs["n1"].name == "Test NPC"
    assert result.state.log.events[-1].event_type == "npc_created"


def test_create_score_adds_it_to_state():
    # SPECIFICATION.md §5: "Score" - target and plan, set once
    result = _executor().create_score(
        _state(),
        CreateScoreArgs(
            score_id="s1", target="The Silver Vault", plan_type="Assault", plan_detail="Front door"
        ),
    )

    score = result.state.scores["s1"]
    assert score.target == "The Silver Vault"
    assert score.plan_type == "Assault"
    assert result.state.log.events[-1].event_type == "score_created"


def test_update_score_applies_only_provided_fields():
    state = _executor().create_score(_state(), CreateScoreArgs(score_id="s1", target="Vault")).state

    result = _executor().update_score(
        state, UpdateScoreArgs(score_id="s1", engagement_result="controlled")
    )

    score = result.state.scores["s1"]
    assert score.engagement_result == "controlled"
    assert score.payoff is None
    assert result.state.log.events[-1].event_type == "score_updated"

    result = _executor().update_score(result.state, UpdateScoreArgs(score_id="s1", payoff=6))
    assert result.state.scores["s1"].engagement_result == "controlled"
    assert result.state.scores["s1"].payoff == 6


def test_update_score_refuses_an_unknown_score_id():
    with pytest.raises(EngineError):
        _executor().update_score(_state(), UpdateScoreArgs(score_id="missing", payoff=6))


def test_create_character_adds_a_second_pc():
    # FR-25/FR-35: the only way a second PC comes into existence for now.
    result = _executor().create_character(
        _state(), CreateCharacterArgs(character_id="pc-2", name="Vex", playbook="Whisper")
    )

    assert result.state.characters["pc-2"].name == "Vex"
    assert "pc-1" in result.state.characters  # the original PC, untouched
    assert result.state.log.events[-1].event_type == "character_created"


def test_create_character_registers_an_ai_seat_by_default():
    # FR-35: a crewmate the GM introduces defaults to AI-controlled - no
    # separate wiring step needed before PlayerAgent picks it up.
    result = _executor().create_character(
        _state(), CreateCharacterArgs(character_id="pc-2", name="Vex", playbook="Whisper")
    )

    seat = result.state.controllers["seat:pc-2"]
    assert seat.kind == "ai"
    assert seat.character_ids == ["pc-2"]


def test_create_character_registers_a_human_seat_when_asked():
    result = _executor().create_character(
        _state(),
        CreateCharacterArgs(
            character_id="pc-2", name="Vex", playbook="Whisper", controller_kind="human"
        ),
    )

    assert result.state.controllers["seat:pc-2"].kind == "human"


def test_create_character_refuses_a_duplicate_id():
    executor = _executor()
    state = executor.create_character(
        _state(), CreateCharacterArgs(character_id="pc-2", name="Vex", playbook="Whisper")
    ).state

    with pytest.raises(EngineError, match="already exists"):
        executor.create_character(
            state, CreateCharacterArgs(character_id="pc-2", name="Someone Else", playbook="Cutter")
        )


def test_mark_stress_refuses_without_character_id_once_there_are_two_pcs():
    # CLAUDE.md: "the engine may refuse; it never guesses" - with two PCs,
    # an unspecified character_id is genuinely ambiguous.
    executor = _executor()
    state = executor.create_character(
        _state(), CreateCharacterArgs(character_id="pc-2", name="Vex", playbook="Whisper")
    ).state

    with pytest.raises(EngineError, match="character_id is required"):
        executor.mark_stress(state, MarkStressArgs(amount=1))


def test_mark_stress_with_an_explicit_character_id_affects_only_that_pc():
    executor = _executor()
    state = executor.create_character(
        _state(), CreateCharacterArgs(character_id="pc-2", name="Vex", playbook="Whisper")
    ).state

    result = executor.mark_stress(state, MarkStressArgs(amount=2, character_id="pc-2"))

    assert result.state.characters["pc-2"].stress.marked == 2
    assert result.state.characters["pc-1"].stress.marked == 0
    assert result.state.log.events[-1].entity_id == "pc-2"


def test_mark_stress_refuses_an_unknown_character_id():
    with pytest.raises(EngineError, match="no character"):
        _executor().mark_stress(_state(), MarkStressArgs(amount=1, character_id="nope"))


def test_update_faction_status_starts_from_neutral_and_applies_delta():
    # SRD: "Faction Status" - "zero (neutral) being the default"
    result = _executor().update_faction_status(
        _state(), UpdateFactionStatusArgs(faction_id="f1", delta=-2)
    )

    assert result.result["status"] == -2
    assert result.state.faction_statuses["f1"].history == [1]


def test_update_faction_status_accumulates_across_calls():
    executor = _executor()
    state = executor.update_faction_status(
        _state(), UpdateFactionStatusArgs(faction_id="f1", delta=-1)
    ).state

    result = executor.update_faction_status(
        state, UpdateFactionStatusArgs(faction_id="f1", delta=-1)
    )

    assert result.result["status"] == -2
    assert result.state.faction_statuses["f1"].history == [1, 2]


def test_update_relationship_creates_a_new_edge():
    # FR-33: recorded the moment it happens in the fiction.
    result = _executor().update_relationship(
        _state(),
        UpdateRelationshipArgs(
            subject_type="character",
            subject_id="Test",
            object_type="npc",
            object_id="n1",
            kind=RelationshipKind.ALLY,
            status="owes a favour",
        ),
    )

    key = "character:Test:npc:n1"
    assert result.state.relationships[key].kind is RelationshipKind.ALLY
    assert result.state.relationships[key].status == "owes a favour"
    assert result.state.log.events[-1].event_type == "relationship_updated"


def test_update_relationship_changes_kind_on_the_same_edge():
    executor = _executor()
    args = UpdateRelationshipArgs(
        subject_type="character",
        subject_id="Test",
        object_type="npc",
        object_id="n1",
        kind=RelationshipKind.ALLY,
    )
    state = executor.update_relationship(_state(), args).state

    betrayed = executor.update_relationship(
        state,
        UpdateRelationshipArgs(
            subject_type="character",
            subject_id="Test",
            object_type="npc",
            object_id="n1",
            kind=RelationshipKind.RIVAL,
            status="betrayed the crew",
        ),
    )

    key = "character:Test:npc:n1"
    assert betrayed.state.relationships[key].kind is RelationshipKind.RIVAL
    assert betrayed.state.relationships[key].history == [1, 2]


def test_add_canon_fact_grows_the_campaign_canon():
    # FR-36: the session-zero-generated setting grows during play.
    state = _state().model_copy(update={"canon": CampaignCanon(setting_name="Test City")})

    result = _executor().add_canon_fact(state, AddCanonFactArgs(fact="The docks are haunted."))

    assert result.state.canon.facts == ["The docks are haunted."]


def test_add_canon_fact_refuses_without_canon_set():
    with pytest.raises(EngineError, match="no campaign canon"):
        _executor().add_canon_fact(_state(), AddCanonFactArgs(fact="anything"))


def test_add_canon_location_grows_the_map():
    # FR-15: the map grows as new locations are discovered during play.
    state = _state().model_copy(
        update={"canon": CampaignCanon(setting_name="Test City", locations=["The Docks"])}
    )

    result = _executor().add_canon_location(state, AddCanonLocationArgs(location="The Old Quarter"))

    assert result.state.canon.locations == ["The Docks", "The Old Quarter"]
    assert result.state.log.events[-1].event_type == "canon_location_added"


def test_add_canon_location_refuses_without_canon_set():
    with pytest.raises(EngineError, match="no campaign canon"):
        _executor().add_canon_location(_state(), AddCanonLocationArgs(location="anything"))


def test_set_session_zero_config_records_lines_veils_and_tone():
    # FR-17: session zero's safety agreements, generic tabletop safety
    # tools rather than an SRD mechanic.
    result = _executor().set_session_zero_config(
        _state(),
        SetSessionZeroConfigArgs(lines=["no animal harm"], veils=["torture"], tone="pulpy noir"),
    )

    assert result.state.session_zero.lines == ["no animal harm"]
    assert result.state.session_zero.veils == ["torture"]
    assert result.state.session_zero.tone == "pulpy noir"
    assert result.state.log.events[-1].event_type == "session_zero_configured"


def test_set_campaign_canon_creates_the_setting():
    # FR-36: session zero's one-time setting creation, distinct from
    # add_canon_fact which only grows canon that already exists.
    result = _executor().set_campaign_canon(
        _state(),
        SetCampaignCanonArgs(
            setting_name="Harrow's Reach",
            tone="rain-soaked industrial",
            factions=["The Rustworks Combine"],
            locations=["The Sunken Market"],
        ),
    )

    assert result.state.canon.setting_name == "Harrow's Reach"
    assert result.state.canon.factions == ["The Rustworks Combine"]
    assert result.state.canon.locations == ["The Sunken Market"]
    assert result.state.log.events[-1].event_type == "canon_set"
    assert result.result["setting_name"] == "Harrow's Reach"


def test_invoke_x_card_logs_an_event():
    # FR-17: safety-tool command, logged but not narratively resolved here.
    result = _executor().invoke_x_card(_state(), InvokeXCardArgs(note="pacing check"))

    assert result.result["acknowledged"]
    assert result.state.log.events[-1].event_type == "x_card_invoked"
    assert result.state.log.events[-1].payload["note"] == "pacing check"


def test_tool_calls_are_deterministic_for_the_same_seed():
    args = RollActionArgs(action=Action.PROWL, position=Position.RISKY, effect=Effect.STANDARD)

    first = _executor(seed=9).roll_action(_state(), args)
    second = _executor(seed=9).roll_action(_state(), args)

    assert first.result == second.result


def test_sheet_operations_are_never_exposed_to_the_llm():
    # FR-28/FR-16: the sheet panel's own engine-operation surface is
    # distinct from the LLM's tool surface (CLAUDE.md: "the engine
    # adjudicates, the model narrates"), except mark_xp - the GM also
    # needs it for the TRAIN downtime activity.
    tool_names = {d["function"]["name"] for d in tool_definitions()}

    assert "adjust_coin" not in tool_names
    assert "set_item_carried" not in tool_names
    assert "heal_character" not in tool_names
    # mark_stress/apply_harm/tick_clock/mark_xp are shared with TOOL_SPECS.
    assert SHEET_OPERATIONS["mark_stress"] is MarkStressArgs
    assert SHEET_OPERATIONS["apply_harm"] is ApplyHarmArgs
    assert SHEET_OPERATIONS["tick_clock"] is TickClockArgs
    assert SHEET_OPERATIONS["mark_xp"] is MarkXpArgs


def test_heal_character_heals_one_level_and_logs_it():
    # SRD: "Recover" - every harm entry is reduced by one level.
    character = Character(
        name="Test",
        playbook="Test Playbook",
        harm={"entries": [{"level": 2, "name": "Twisted Ankle"}]},
    )
    result = _executor().heal_character(_state(character), HealCharacterArgs())

    assert result.state.log.events[-1].event_type == "harm_healed"
    assert result.state.character.harm.entries[0].level == 1


def test_mark_xp_marks_the_playbook_track():
    result = _executor().mark_xp(_state(), MarkXpArgs(track="playbook", amount=2))

    assert result.state.character.playbook_xp.marked == 2
    assert result.state.log.events[-1].event_type == "xp_marked"


def test_mark_xp_marks_an_attribute_track():
    result = _executor().mark_xp(_state(), MarkXpArgs(track="prowess", amount=1))

    assert result.state.character.attribute_xp[Attribute.PROWESS].marked == 1


def test_adjust_coin_updates_the_character_and_logs_it():
    character = Character(name="Test", playbook="Test Playbook", coin=2)

    result = _executor().adjust_coin(_state(character), AdjustCoinArgs(amount=-2))

    assert result.result["coin"] == 0
    assert result.state.log.events[-1].event_type == "coin_adjusted"


def test_adjust_coin_refuses_to_go_negative():
    with pytest.raises(EngineError, match="cannot spend"):
        _executor().adjust_coin(_state(), AdjustCoinArgs(amount=-1))


def test_set_item_carried_toggles_and_recomputes_load():
    character = Character(
        name="Test", playbook="Test Playbook", items=[CharacterItem(item_id="lockpicks")]
    )

    result = _executor().set_item_carried(
        _state(character), SetItemCarriedArgs(item_id="lockpicks", carried=True)
    )

    assert result.result["load"] == 1
    assert result.state.log.events[-1].event_type == "item_carried_set"


def _state_with_crew_tier(tier: int) -> GameState:
    return _state().model_copy(
        update={"crew": Crew(name="Test Crew", crew_type="Test Type", tier=tier)}
    )


def test_roll_engagement_sets_a_starting_position():
    # SRD: "Engagement Roll" - a fortune roll setting the crew's position.
    result = _executor().roll_engagement(_state(), RollEngagementArgs(pool_size=1))

    assert result.state.log.events[-1].event_type == "engagement_roll"
    assert result.state.log.events[-1].entity_type == "score"
    assert "position" in result.result


def test_resolve_payoff_applies_rep_and_coin_to_the_crew():
    # SRD: "Payoff" - 2 rep, +-1 per Tier difference from the target.
    state = _state_with_crew_tier(1)

    result = _executor().resolve_payoff(state, ResolvePayoffArgs(target_tier=2, coin=4))

    assert result.result["rep"] == 3
    assert result.state.crew.rep.rep == 3
    assert result.state.crew.coin == 4
    assert result.state.log.events[-1].event_type == "payoff"


def test_resolve_payoff_is_zero_rep_when_kept_quiet():
    state = _state_with_crew_tier(1)

    result = _executor().resolve_payoff(state, ResolvePayoffArgs(target_tier=2, coin=0, quiet=True))

    assert result.result["rep"] == 0
    assert result.state.crew.rep.rep == 0


def test_add_crew_heat_increases_heat_and_reports_wanted_level():
    state = _state_with_crew_tier(1)

    result = _executor().add_crew_heat(state, AddCrewHeatArgs(amount=9))

    assert result.result["wanted_level_increased"]
    assert result.state.log.events[-1].event_type == "heat_added"


def test_add_crew_heat_can_clear_heat():
    state = _state_with_crew_tier(1).model_copy(
        update={"crew": Crew(name="Test Crew", crew_type="Test Type", tier=1, heat={"heat": 3})}
    )

    result = _executor().add_crew_heat(state, AddCrewHeatArgs(amount=-2))

    assert result.state.crew.heat.heat == 1


def test_roll_entanglement_refuses_without_a_table_loaded():
    with pytest.raises(EngineError, match="no entanglement table"):
        _executor().roll_entanglement(_state_with_crew_tier(1), RollEntanglementArgs())


def test_roll_entanglement_uses_the_crews_wanted_level_and_heat():
    # SRD: "Entanglements" - heat band picks the column, wanted-level dice
    # pick the row.
    state = _state_with_crew_tier(1).model_copy(
        update={
            "crew": Crew(
                name="Test Crew", crew_type="Test Type", tier=1, wanted_level=1, heat={"heat": 4}
            )
        }
    )

    result = _executor(entanglements=_ENTANGLEMENTS).roll_entanglement(
        state, RollEntanglementArgs()
    )

    assert result.state.log.events[-1].event_type == "entanglement_roll"
    assert result.result["heat_band"] == "4-5"


def test_acquire_asset_rolls_the_crews_tier():
    result = _executor().acquire_asset(_state_with_crew_tier(2), AcquireAssetArgs())

    assert result.state.log.events[-1].event_type == "asset_acquired"
    assert "quality" in result.result


def test_indulge_vice_clears_stress_and_logs_it():
    character = Character(
        name="Test",
        playbook="Test Playbook",
        action_ratings={Action.PROWL: 2},
        stress={"marked": 2},
    )

    result = _executor().indulge_vice(_state(character), IndulgeViceArgs())

    assert result.state.log.events[-2].event_type == "vice_indulged"
    assert result.state.log.events[-1].event_type == "stress_marked"
    assert result.state.character.stress.marked <= 2


def test_reduce_heat_clears_heat_by_the_downtime_ticks_table():
    state = _state_with_crew_tier(1).model_copy(
        update={"crew": Crew(name="Test Crew", crew_type="Test Type", tier=1, heat={"heat": 5})}
    )

    result = _executor().reduce_heat(state, ReduceHeatArgs(pool_size=2))

    assert result.state.log.events[-2].event_type == "downtime_activity_rolled"
    assert result.state.log.events[-1].event_type == "heat_added"
    assert result.state.crew.heat.heat == max(0, 5 - result.result["heat_cleared"])


def test_recover_ticks_the_healing_clock():
    executor = _executor()
    state = executor.create_clock(
        _state(),
        CreateClockArgs(clock_id="heal-1", name="Healing", kind=ClockKind.HEALING, segments=8),
    ).state

    result = executor.recover(state, RecoverArgs(clock_id="heal-1", pool_size=2))

    assert result.state.log.events[-2].event_type == "downtime_activity_rolled"
    assert result.state.log.events[-1].event_type == "clock_ticked"
    assert result.state.clocks["heal-1"].filled == result.result["ticks"]
    assert not result.result["healed"]


def test_recover_heals_once_the_clock_fills():
    character = Character(
        name="Test",
        playbook="Test Playbook",
        harm={"entries": [{"level": 2, "name": "Twisted Ankle"}]},
    )
    executor = _executor(seed=9)
    state = executor.create_clock(
        _state(character),
        CreateClockArgs(clock_id="heal-1", name="Healing", kind=ClockKind.HEALING, segments=1),
    ).state

    result = executor.recover(state, RecoverArgs(clock_id="heal-1", pool_size=1))

    assert result.result["healed"]
    assert result.state.character.harm.entries[0].level == 1


def test_recover_refuses_an_unknown_clock():
    with pytest.raises(EngineError, match="no clock"):
        _executor().recover(_state(), RecoverArgs(clock_id="nope", pool_size=1))


def test_long_term_project_ticks_the_projects_clock():
    executor = _executor()
    state = executor.create_clock(
        _state(),
        CreateClockArgs(
            clock_id="vault", name="Crack the Vault", kind=ClockKind.LONG_TERM_PROJECT, segments=8
        ),
    ).state

    result = executor.long_term_project(state, LongTermProjectArgs(clock_id="vault", pool_size=2))

    assert result.state.log.events[-1].event_type == "clock_ticked"
    assert result.state.clocks["vault"].filled == result.result["ticks"]


def test_flashback_marks_stress_at_the_gm_set_cost():
    # SRD: "Flashbacks" - the GM sets the stress cost.
    result = _executor().flashback(_state(), FlashbackArgs(stress_cost=2))

    assert result.state.character.stress.marked == 2
    assert result.state.log.events[-1].event_type == "flashback_taken"


def test_advance_action_rating_requires_a_full_xp_track():
    from engine.advancement import AdvancementError

    with pytest.raises(AdvancementError, match="not full"):
        _executor().advance_action_rating(_state(), AdvanceActionRatingArgs(action=Action.PROWL))


def test_advance_action_rating_adds_a_dot_once_the_track_is_full():
    character = Character(
        name="Test",
        playbook="Test Playbook",
        action_ratings={Action.PROWL: 1},
        attribute_xp={Attribute.PROWESS: {"marked": 6, "segments": 6}},
    )

    result = _executor().advance_action_rating(
        _state(character), AdvanceActionRatingArgs(action=Action.PROWL)
    )

    assert result.state.character.action_ratings[Action.PROWL] == 2
    assert result.state.log.events[-1].event_type == "action_advanced"
    assert result.state.log.events[-1].payload["cap"] == 3


def test_advance_special_ability_requires_a_full_playbook_track():
    from engine.advancement import AdvancementError

    with pytest.raises(AdvancementError, match="not full"):
        _executor().advance_special_ability(
            _state(), AdvanceSpecialAbilityArgs(ability_id="veteran")
        )


def test_advance_special_ability_grants_it_once_full():
    character = Character(
        name="Test", playbook="Test Playbook", playbook_xp={"marked": 8, "segments": 8}
    )

    result = _executor().advance_special_ability(
        _state(character), AdvanceSpecialAbilityArgs(ability_id="veteran")
    )

    assert "veteran" in result.state.character.special_ability_ids
    assert result.state.log.events[-1].event_type == "special_ability_advanced"


def test_advance_crew_special_ability_grants_it_once_full():
    state = _state().model_copy(
        update={
            "crew": Crew(name="Test Crew", crew_type="Test Type", xp={"marked": 8, "segments": 8})
        }
    )

    result = _executor().advance_crew_special_ability(
        state, AdvanceCrewSpecialAbilityArgs(ability_id="crew-veteran")
    )

    assert "crew-veteran" in result.state.crew.special_ability_ids
    assert result.state.log.events[-1].event_type == "crew_special_ability_advanced"


def test_advance_crew_upgrades_marks_two_boxes():
    state = _state().model_copy(
        update={
            "crew": Crew(name="Test Crew", crew_type="Test Type", xp={"marked": 8, "segments": 8})
        }
    )

    result = _executor().advance_crew_upgrades(
        state, AdvanceCrewUpgradesArgs(upgrade_ids=("quality", "quality"))
    )

    assert result.state.crew.upgrade_ids == ["quality", "quality"]
    assert result.state.log.events[-1].event_type == "crew_upgrades_advanced"
