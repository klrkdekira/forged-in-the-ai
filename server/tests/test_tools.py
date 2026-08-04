import random
from datetime import UTC, datetime

import pytest

from ai.tools import (
    SHEET_OPERATIONS,
    AcquireAssetArgs,
    AddCanonFactArgs,
    AddCanonFactionArgs,
    AddCanonLocationArgs,
    AddCrewHeatArgs,
    AdjustCoinArgs,
    AdjustCrewCoinArgs,
    AdjustCrewRepArgs,
    AdjustCrewTurfArgs,
    AdjustStashArgs,
    AdjustWantedLevelArgs,
    AdvanceActionRatingArgs,
    AdvanceCrewSpecialAbilityArgs,
    AdvanceCrewUpgradesArgs,
    AdvanceSpecialAbilityArgs,
    ApplyHarmArgs,
    CashOutStashArgs,
    CraftArgs,
    CreateCharacterArgs,
    CreateClockArgs,
    CreateNpcArgs,
    CreateScoreArgs,
    DevelopCrewArgs,
    FlashbackArgs,
    GameState,
    HealCharacterArgs,
    IndulgeViceArgs,
    InvokeXCardArgs,
    LongTermProjectArgs,
    MarkCrewXpArgs,
    MarkStressArgs,
    MarkTraumaArgs,
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
    SetClaimControlledArgs,
    SetItemCarriedArgs,
    SetLoadLevelArgs,
    SetSessionZeroConfigArgs,
    TickClockArgs,
    ToolExecutor,
    TransitionPhaseArgs,
    UpdateFactionStatusArgs,
    UpdateRelationshipArgs,
    UpdateScoreArgs,
    UseArmorArgs,
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


def _downtime_state(state: GameState) -> GameState:
    """Put a focused downtime-tool fixture through the real phase cycle."""
    session = state.session.transition_to(CampaignPhase.SCORE).transition_to(
        CampaignPhase.DOWNTIME
    )
    return state.model_copy(update={"session": session})


def test_resolve_character_id_matches_by_name_or_alias():
    state = GameState(
        characters={
            "pc-1": Character(name="Corvo Attano", alias="The Blade", playbook="Cutter"),
            "pc-2": Character(name="Valeria", alias="Ghost", playbook="Lurk"),
        },
        crew=Crew(name="Test Crew", crew_type="Test Type"),
        session=Session(),
    )
    executor = _executor()
    assert executor.resolve_character_id(state, "pc-1") == "pc-1"
    assert executor.resolve_character_id(state, "Corvo Attano") == "pc-1"
    assert executor.resolve_character_id(state, "corvo attano") == "pc-1"
    assert executor.resolve_character_id(state, "The Blade") == "pc-1"
    assert executor.resolve_character_id(state, "ghost") == "pc-2"


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
        "mark_trauma",
        "use_armor",
        "transition_phase",
        "create_score",
        "update_score",
        "create_npc",
        "create_character",
        "update_faction_status",
        "update_relationship",
        "add_canon_fact",
        "add_canon_location",
        "add_canon_faction",
        "invoke_x_card",
        "set_session_zero_config",
        "set_campaign_canon",
        "roll_engagement",
        "resolve_payoff",
        "add_crew_heat",
        "adjust_wanted_level",
        "adjust_crew_rep",
        "adjust_crew_coin",
        "adjust_crew_turf",
        "set_claim_controlled",
        "develop_crew",
        "roll_entanglement",
        "acquire_asset",
        "indulge_vice",
        "craft",
        "reduce_heat",
        "recover",
        "long_term_project",
        "flashback",
        "mark_xp",
        "mark_crew_xp",
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
    state = _executor().roll_engagement(
        _state().model_copy(update={"session": Session().transition_to(CampaignPhase.SCORE)}),
        RollEngagementArgs(pool_size=1),
    ).state
    result = _executor().roll_action(
        state,
        RollActionArgs(action=Action.PROWL, position=Position.RISKY, effect=Effect.STANDARD),
    )

    assert result.result["position"] == "risky"
    assert result.state.log.events[-1].event_type == "action_roll"
    assert result.state.log.events[-1].occurred_at == AT


def test_roll_action_marks_xp_automatically_on_a_desperate_roll():
    # SRD: "PC Advancement" - "When you make a desperate action roll, mark
    # 1 xp in the attribute for the action you rolled."
    state = _executor().roll_engagement(
        _state().model_copy(update={"session": Session().transition_to(CampaignPhase.SCORE)}),
        RollEngagementArgs(pool_size=1),
    ).state
    result = _executor().roll_action(
        state,
        RollActionArgs(action=Action.PROWL, position=Position.DESPERATE, effect=Effect.STANDARD),
    )

    xp_event = result.state.log.events[-1]
    assert xp_event.event_type == "xp_marked"
    assert xp_event.payload == {"track": "prowess", "amount": 1, "reason": "desperate roll"}
    assert result.state.character.attribute_xp[Attribute.PROWESS].marked == 1


def test_roll_action_does_not_mark_xp_on_a_non_desperate_roll():
    state = _executor().roll_engagement(
        _state().model_copy(update={"session": Session().transition_to(CampaignPhase.SCORE)}),
        RollEngagementArgs(pool_size=1),
    ).state
    result = _executor().roll_action(
        state,
        RollActionArgs(action=Action.PROWL, position=Position.RISKY, effect=Effect.STANDARD),
    )

    assert result.state.log.events[-1].event_type == "action_roll"
    assert result.state.character.attribute_xp[Attribute.PROWESS].marked == 0


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


def test_mark_stress_exposes_a_pending_trauma_choice_after_overflow():
    character = Character(name="Test", playbook="Test Playbook", stress={"marked": 8})
    result = _executor().mark_stress(_state(character), MarkStressArgs(amount=1))

    assert result.result["triggered_trauma"]
    assert result.state.character.stress.marked == 0
    assert result.state.character.trauma_pending
    chosen = _executor().mark_trauma(
        result.state, MarkTraumaArgs(condition="haunted")
    )
    assert not chosen.state.character.trauma_pending


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


def test_create_npc_links_it_to_an_existing_faction():
    result = _executor().create_npc(
        _state_with_faction(), CreateNpcArgs(npc_id="n1", name="Test NPC", faction_id="f1")
    )

    assert result.state.npcs["n1"].faction_id == "f1"
    assert result.state.factions["f1"].notable_npc_ids == ["n1"]


def test_create_npc_refuses_an_unknown_faction_id():
    with pytest.raises(EngineError, match="no canon faction"):
        _executor().create_npc(
            _state(), CreateNpcArgs(npc_id="n1", name="Test NPC", faction_id="missing")
        )


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


def _state_with_faction(faction_id: str = "f1", name: str = "The Circle") -> GameState:
    state = _state().model_copy(update={"canon": CampaignCanon(setting_name="Test City")})
    return (
        _executor()
        .add_canon_faction(state, AddCanonFactionArgs(faction_id=faction_id, name=name))
        .state
    )


def test_update_faction_status_starts_from_neutral_and_applies_delta():
    # SRD: "Faction Status" - "zero (neutral) being the default"
    result = _executor().update_faction_status(
        _state_with_faction(), UpdateFactionStatusArgs(faction_id="f1", delta=-2)
    )

    assert result.result["status"] == -2
    # history holds the faction_status_changed event's own sequence; the
    # canon_faction_added event that introduced "f1" is sequence 1.
    assert result.state.faction_statuses["f1"].history == [2]


def test_update_faction_status_accumulates_across_calls():
    executor = _executor()
    state = executor.update_faction_status(
        _state_with_faction(), UpdateFactionStatusArgs(faction_id="f1", delta=-1)
    ).state

    result = executor.update_faction_status(
        state, UpdateFactionStatusArgs(faction_id="f1", delta=-1)
    )

    assert result.result["status"] == -2
    assert result.state.faction_statuses["f1"].history == [2, 3]


def test_update_faction_status_refuses_an_unknown_faction():
    # FR-12: status with a faction nobody introduced is a free-form edit.
    with pytest.raises(EngineError, match="no faction"):
        _executor().update_faction_status(
            _state(), UpdateFactionStatusArgs(faction_id="nope", delta=-1)
        )


def _state_with_npc(state: GameState | None = None) -> GameState:
    return (
        _executor().create_npc(state or _state(), CreateNpcArgs(npc_id="n1", name="Test NPC")).state
    )


def test_update_relationship_creates_a_new_edge():
    # FR-33: recorded the moment it happens in the fiction. Characters are
    # referenced by their character_id key ("pc-1"), the same id every
    # character-tagged event uses - not their display name.
    result = _executor().update_relationship(
        _state_with_npc(),
        UpdateRelationshipArgs(
            subject_type="character",
            subject_id="pc-1",
            object_type="npc",
            object_id="n1",
            kind=RelationshipKind.ALLY,
            status="owes a favour",
        ),
    )

    key = "character:pc-1:npc:n1"
    assert result.state.relationships[key].kind is RelationshipKind.ALLY
    assert result.state.relationships[key].status == "owes a favour"
    assert result.state.log.events[-1].event_type == "relationship_updated"


def test_update_relationship_changes_kind_on_the_same_edge():
    executor = _executor()
    args = UpdateRelationshipArgs(
        subject_type="character",
        subject_id="pc-1",
        object_type="npc",
        object_id="n1",
        kind=RelationshipKind.ALLY,
    )
    state = executor.update_relationship(_state_with_npc(), args).state

    betrayed = executor.update_relationship(
        state,
        UpdateRelationshipArgs(
            subject_type="character",
            subject_id="pc-1",
            object_type="npc",
            object_id="n1",
            kind=RelationshipKind.RIVAL,
            status="betrayed the crew",
        ),
    )

    key = "character:pc-1:npc:n1"
    assert betrayed.state.relationships[key].kind is RelationshipKind.RIVAL
    # npc_created is sequence 1, so the two edge updates are 2 and 3.
    assert betrayed.state.relationships[key].history == [2, 3]


def test_update_relationship_refuses_a_missing_entity_on_either_end():
    # FR-12: both ends must exist - an edge to an entity nobody created
    # would dangle in the relationship map.
    with pytest.raises(EngineError, match="no npc"):
        _executor().update_relationship(
            _state(),
            UpdateRelationshipArgs(
                subject_type="character",
                subject_id="pc-1",
                object_type="npc",
                object_id="never-created",
                kind=RelationshipKind.ALLY,
            ),
        )

    with pytest.raises(EngineError, match="no character"):
        _executor().update_relationship(
            _state_with_npc(),
            UpdateRelationshipArgs(
                subject_type="character",
                subject_id="Test",  # the display name, not the "pc-1" id
                object_type="npc",
                object_id="n1",
                kind=RelationshipKind.ALLY,
            ),
        )


def test_update_relationship_refuses_an_unknown_entity_type():
    with pytest.raises(EngineError, match="unknown entity type"):
        _executor().update_relationship(
            _state(),
            UpdateRelationshipArgs(
                subject_type="ghost",
                subject_id="pc-1",
                object_type="npc",
                object_id="n1",
                kind=RelationshipKind.ALLY,
            ),
        )


def test_update_relationship_accepts_the_crew_by_name_and_a_canon_location():
    state = _state_with_npc().model_copy(
        update={"canon": CampaignCanon(setting_name="Test City", locations=["The Docks"])}
    )

    result = _executor().update_relationship(
        state,
        UpdateRelationshipArgs(
            subject_type="crew",
            subject_id="Test Crew",
            object_type="location",
            object_id="The Docks",
            kind=RelationshipKind.ALLY,
            status="operates from here",
        ),
    )

    assert "crew:Test Crew:location:The Docks" in result.state.relationships


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
    assert [e.event_type for e in result.state.log.events] == [
        "canon_set",
        "canon_faction_added",
    ]
    assert result.result["setting_name"] == "Harrow's Reach"


def test_set_campaign_canon_makes_session_zero_factions_first_class():
    # FR-15: a session-zero faction is a Faction entity from the start
    # (deterministic slug id), so update_faction_status and faction clocks
    # can reference it without a separate introduction step.
    result = _executor().set_campaign_canon(
        _state(),
        SetCampaignCanonArgs(setting_name="Harrow's Reach", factions=["The Rustworks Combine"]),
    )

    assert result.result["faction_ids"] == ["the-rustworks-combine"]
    assert result.state.factions["the-rustworks-combine"].name == "The Rustworks Combine"


def test_invoke_x_card_logs_an_event():
    # FR-17: safety-tool command, logged but not narratively resolved here.
    result = _executor().invoke_x_card(_state(), InvokeXCardArgs(note="pacing check"))

    assert result.result["acknowledged"]
    assert result.state.log.events[-1].event_type == "x_card_invoked"
    assert result.state.log.events[-1].payload["note"] == "pacing check"


def test_tool_calls_are_deterministic_for_the_same_seed():
    args = RollActionArgs(action=Action.PROWL, position=Position.RISKY, effect=Effect.STANDARD)

    first_state = _executor(seed=9).roll_engagement(
        _state().model_copy(update={"session": Session().transition_to(CampaignPhase.SCORE)}),
        RollEngagementArgs(pool_size=1),
    ).state
    second_state = _executor(seed=9).roll_engagement(
        _state().model_copy(update={"session": Session().transition_to(CampaignPhase.SCORE)}),
        RollEngagementArgs(pool_size=1),
    ).state
    first = _executor(seed=9).roll_action(first_state, args)
    second = _executor(seed=9).roll_action(second_state, args)

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


def test_mark_xp_records_a_reason_when_given():
    result = _executor().mark_xp(
        _state(), MarkXpArgs(track="playbook", amount=1, reason="expressed beliefs")
    )

    assert result.state.log.events[-1].payload["reason"] == "expressed beliefs"


def test_mark_crew_xp_updates_the_crew_and_logs_the_reason():
    # SRD: "Crew Advancement" - end-of-session crew trigger review.
    result = _executor().mark_crew_xp(
        _state(), MarkCrewXpArgs(amount=2, reason="bolstered reputation")
    )

    assert result.result["xp"] == 2
    assert result.state.crew.xp.marked == 2
    event = result.state.log.events[-1]
    assert event.event_type == "crew_xp_marked"
    assert event.payload["reason"] == "bolstered reputation"


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
    result = _executor().roll_engagement(
        _state().model_copy(update={"session": Session().transition_to(CampaignPhase.SCORE)}),
        RollEngagementArgs(pool_size=1),
    )

    assert result.state.log.events[-1].event_type == "engagement_roll"
    assert result.state.log.events[-1].entity_type == "score"
    assert "position" in result.result


def test_score_procedure_refuses_repeated_engagement_and_unordered_entanglement():
    # SRD: "Engagement Roll" and "Entanglements" - one engagement starts the
    # score, and entanglements are resolved after payoff during downtime.
    executor = _executor(entanglements=_ENTANGLEMENTS)
    score_state = _state().model_copy(
        update={"session": Session().transition_to(CampaignPhase.SCORE)}
    )
    rolled = executor.roll_engagement(score_state, RollEngagementArgs(pool_size=1)).state
    with pytest.raises(EngineError, match="already been rolled"):
        executor.roll_engagement(rolled, RollEngagementArgs(pool_size=1))

    downtime = rolled.model_copy(
        update={"session": rolled.session.transition_to(CampaignPhase.DOWNTIME)}
    )
    with pytest.raises(EngineError, match="resolve payoff"):
        executor.roll_entanglement(downtime, RollEntanglementArgs())


def test_resolve_payoff_applies_rep_and_coin_to_the_crew():
    # SRD: "Payoff" - 2 rep, +-1 per Tier difference from the target.
    state = _downtime_state(_state_with_crew_tier(1))

    result = _executor().resolve_payoff(state, ResolvePayoffArgs(target_tier=2, coin=4))

    assert result.result["rep"] == 3
    assert result.state.crew.rep.rep == 3
    assert result.state.crew.coin == 4
    assert result.state.log.events[-1].event_type == "payoff"


def test_resolve_payoff_is_zero_rep_when_kept_quiet():
    state = _downtime_state(_state_with_crew_tier(1))

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


def test_adjust_wanted_level_updates_the_crew():
    # SRD: "Heat & Wanted Level".
    state = _state_with_crew_tier(1)

    result = _executor().adjust_wanted_level(state, AdjustWantedLevelArgs(amount=1))

    assert result.result["wanted_level"] == 1
    assert result.state.crew.wanted_level == 1
    assert result.state.log.events[-1].event_type == "wanted_level_adjusted"


def test_adjust_crew_rep_updates_the_crew():
    # SRD: "Development".
    state = _state_with_crew_tier(1)

    result = _executor().adjust_crew_rep(state, AdjustCrewRepArgs(amount=3))

    assert result.result["rep"] == 3
    assert result.state.crew.rep.rep == 3
    assert result.state.log.events[-1].event_type == "crew_rep_adjusted"


def test_adjust_crew_coin_updates_the_crew():
    # SRD: "Coin and Stash".
    state = _state_with_crew_tier(1)

    result = _executor().adjust_crew_coin(state, AdjustCrewCoinArgs(amount=4))

    assert result.result["coin"] == 4
    assert result.state.crew.coin == 4
    assert result.state.log.events[-1].event_type == "crew_coin_adjusted"


def test_adjust_crew_coin_refuses_to_go_negative():
    state = _state_with_crew_tier(1)

    with pytest.raises(EngineError):
        _executor().adjust_crew_coin(state, AdjustCrewCoinArgs(amount=-1))


def test_roll_entanglement_refuses_without_a_table_loaded():
    with pytest.raises(EngineError, match="no entanglement table"):
        _executor().roll_entanglement(
            _downtime_state(_state_with_crew_tier(1)), RollEntanglementArgs()
        )


def test_roll_entanglement_uses_the_crews_wanted_level_and_heat():
    # SRD: "Entanglements" - heat band picks the column, wanted-level dice
    # pick the row.
    state = _downtime_state(_state_with_crew_tier(1)).model_copy(
        update={
            "crew": Crew(
                name="Test Crew", crew_type="Test Type", tier=1, wanted_level=1, heat={"heat": 4}
            )
        }
    )

    state = _executor().resolve_payoff(state, ResolvePayoffArgs(target_tier=1)).state
    state = _executor().add_crew_heat(state, AddCrewHeatArgs(amount=1)).state
    result = _executor(entanglements=_ENTANGLEMENTS).roll_entanglement(
        state, RollEntanglementArgs()
    )

    assert result.state.log.events[-1].event_type == "entanglement_roll"
    assert result.result["heat_band"] == "4-5"


def test_acquire_asset_rolls_the_crews_tier():
    result = _executor().acquire_asset(
        _downtime_state(_state_with_crew_tier(2)), AcquireAssetArgs()
    )

    assert result.state.log.events[-1].event_type == "asset_acquired"
    assert "quality" in result.result


def test_indulge_vice_clears_stress_and_logs_it():
    character = Character(
        name="Test",
        playbook="Test Playbook",
        action_ratings={Action.PROWL: 2},
        stress={"marked": 2},
    )

    result = _executor().indulge_vice(_downtime_state(_state(character)), IndulgeViceArgs())

    assert result.state.log.events[-2].event_type == "vice_indulged"
    assert result.state.log.events[-1].event_type == "stress_marked"
    assert result.state.character.stress.marked <= 2


def _state_for_craft(tier: int, tinker: int, coin: int = 0, upgrade_ids: tuple = ()) -> GameState:
    character = Character(
        name="Test", playbook="Test Playbook", action_ratings={Action.TINKER: tinker}, coin=coin
    )
    return _state(character).model_copy(
        update={
            "crew": Crew(
                name="Test Crew", crew_type="Test Type", tier=tier, upgrade_ids=list(upgrade_ids)
            )
        }
    )


def test_craft_logs_a_downtime_activity_with_quality():
    # SRD: "Crafting"/"CRAFTING ROLL".
    result = _executor().craft(
        _downtime_state(_state_for_craft(tier=1, tinker=2)), CraftArgs()
    )

    event = result.state.log.events[-1]
    assert event.event_type == "downtime_activity_rolled"
    assert event.payload["activity"] == "craft"
    assert result.result["quality"] == event.payload["quality"]


def test_craft_adds_one_for_the_workshop_upgrade():
    # SRD: "CRAFTING ROLL" - "+1 quality for Workshop crew upgrade."
    without_workshop = _executor(seed=9).craft(
        _downtime_state(_state_for_craft(tier=1, tinker=2)), CraftArgs()
    )
    with_workshop = _executor(seed=9).craft(
        _downtime_state(_state_for_craft(tier=1, tinker=2, upgrade_ids=("workshop",))), CraftArgs()
    )

    assert with_workshop.result["quality"] == without_workshop.result["quality"] + 1


def test_craft_spends_coin_and_raises_quality():
    # SRD: "Crafting" - "spend coin 1-for-1 to increase the final quality level."
    no_spend = _executor(seed=9).craft(
        _downtime_state(_state_for_craft(tier=1, tinker=2, coin=3)), CraftArgs(coin_spent=0)
    )
    spend = _executor(seed=9).craft(
        _downtime_state(_state_for_craft(tier=1, tinker=2, coin=3)), CraftArgs(coin_spent=2)
    )

    assert spend.result["quality"] == no_spend.result["quality"] + 2
    assert spend.state.character.coin == 1
    assert any(e.event_type == "coin_adjusted" for e in spend.state.log.events)


def test_craft_refuses_when_coin_spent_exceeds_available_coin():
    with pytest.raises(EngineError):
        _executor().craft(
            _downtime_state(_state_for_craft(tier=1, tinker=2, coin=1)), CraftArgs(coin_spent=2)
        )


def test_reduce_heat_clears_heat_by_the_downtime_ticks_table():
    state = _downtime_state(_state_with_crew_tier(1)).model_copy(
        update={"crew": Crew(name="Test Crew", crew_type="Test Type", tier=1, heat={"heat": 5})}
    )

    result = _executor().reduce_heat(state, ReduceHeatArgs(pool_size=2))

    assert result.state.log.events[-2].event_type == "downtime_activity_rolled"
    assert result.state.log.events[-1].event_type == "heat_added"
    assert result.state.crew.heat.heat == max(0, 5 - result.result["heat_cleared"])


def test_recover_ticks_the_healing_clock():
    executor = _executor()
    state = _downtime_state(_state())

    result = executor.recover(state, RecoverArgs(pool_size=2))

    assert result.state.log.events[-2].event_type == "downtime_activity_rolled"
    assert result.state.log.events[-1].event_type == "healing_clock_ticked"
    assert result.state.character.healing_clock.filled == result.result["ticks"]
    assert not result.result["healed"]


def test_recover_heals_once_the_clock_fills():
    character = Character(
        name="Test",
        playbook="Test Playbook",
        harm={"entries": [{"level": 2, "name": "Twisted Ankle"}]},
    )
    executor = _executor(seed=9)
    character = character.model_copy(
        update={"healing_clock": character.healing_clock.model_copy(update={"segments": 1})}
    )
    state = _downtime_state(_state(character))

    result = executor.recover(state, RecoverArgs(pool_size=1))

    assert result.result["healed"]
    assert result.state.character.harm.entries[0].level == 1
    assert result.state.character.healing_clock.filled == 0


def test_recover_uses_the_character_owned_healing_clock():
    result = _executor(seed=9).recover(_downtime_state(_state()), RecoverArgs(pool_size=1))
    assert result.state.character.healing_clock.kind is ClockKind.HEALING


def test_downtime_allows_two_free_activities_then_requires_payment():
    # SRD: "Downtime Activities" - each PC gets two free activities; each
    # additional activity costs 1 coin or 1 rep.
    state = _downtime_state(_state_for_craft(tier=1, tinker=2, coin=1))
    executor = _executor(seed=9)
    first = executor.craft(state, CraftArgs()).state
    second = executor.craft(first, CraftArgs()).state

    with pytest.raises(EngineError, match="two free downtime activities"):
        executor.craft(second, CraftArgs())

    third = executor.craft(second, CraftArgs(extra_cost="coin"))
    assert third.state.character.coin == 0
    assert third.state.session.downtime_activity_counts["pc-1"] == 3


def test_downtime_training_track_can_only_be_used_once():
    # SRD: "Training" - train one attribute or playbook track once per downtime.
    state = _downtime_state(_state())
    executor = _executor()
    executor.mark_xp(state, MarkXpArgs(track="playbook", amount=1))
    with pytest.raises(EngineError, match="already trained"):
        executor.mark_xp(
            executor.mark_xp(state, MarkXpArgs(track="playbook", amount=1)).state,
            MarkXpArgs(track="playbook", amount=1),
        )


def test_long_term_project_ticks_the_projects_clock():
    executor = _executor()
    state = executor.create_clock(
        _downtime_state(_state()),
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


def test_mark_trauma_records_the_players_chosen_condition():
    # SRD: "Trauma" - "When you take trauma, circle one of your trauma
    # conditions like Cold, Reckless, Unstable".
    result = _executor().mark_trauma(_state(), MarkTraumaArgs(condition="haunted"))

    assert result.state.character.trauma.conditions == ["haunted"]
    assert not result.result["retired"]
    event = result.state.log.events[-1]
    assert event.event_type == "trauma_marked"
    assert event.payload == {"condition": "haunted", "retired": False}


def test_mark_trauma_reports_retirement_on_the_fourth_condition():
    # SRD: "Trauma" - "When you mark your fourth trauma condition, your
    # character cannot continue... You must retire them".
    character = Character(
        name="Test",
        playbook="Test Playbook",
        trauma={"conditions": ["cold", "reckless", "unstable"]},
    )

    result = _executor().mark_trauma(_state(character), MarkTraumaArgs(condition="haunted"))

    assert result.result["retired"]
    assert result.state.log.events[-1].payload["retired"]


def test_mark_trauma_refuses_a_condition_the_srd_does_not_define():
    with pytest.raises(EngineError):
        _executor().mark_trauma(_state(), MarkTraumaArgs(condition="brave"))


def _state_with_armor(**armor_fields) -> GameState:
    character = Character(
        name="Test", playbook="Test Playbook", armor={"has_armor": True, **armor_fields}
    )
    return _state(character)


def test_use_armor_marks_the_box_and_logs_it():
    # SRD: "Armor" - "you can mark an armor box to reduce or avoid a
    # consequence, instead of rolling to resist".
    result = _executor().use_armor(_state_with_armor(), UseArmorArgs(armor_type="standard"))

    assert result.state.character.armor.armor_used
    event = result.state.log.events[-1]
    assert event.event_type == "armor_used"
    assert event.payload == {"armor_type": "standard"}


def test_use_armor_refuses_a_box_already_marked():
    # SRD: "Armor" - "When an armor box is marked, it can't be used again
    # until it's restored."
    state = _state_with_armor(armor_used=True)

    with pytest.raises(EngineError):
        _executor().use_armor(state, UseArmorArgs(armor_type="standard"))


def test_transition_into_a_score_restores_used_armor():
    # SRD: "Armor" - "All of your armor is restored when you choose your
    # load for the next score" - hooked to the transition into the score
    # phase, the engine-visible moment closest to choosing load.
    state = _state_with_armor(armor_used=True)

    result = _executor().transition_phase(state, TransitionPhaseArgs(phase=CampaignPhase.SCORE))

    assert not result.state.character.armor.armor_used
    assert result.state.log.events[-1].event_type == "armor_restored"


def test_transition_into_a_score_logs_no_restore_when_no_armor_was_used():
    result = _executor().transition_phase(_state(), TransitionPhaseArgs(phase=CampaignPhase.SCORE))

    assert result.state.log.events[-1].event_type == "phase_transitioned"


def test_transition_into_downtime_enumerates_canon_factions_and_their_clocks():
    # FR-14: faction downtime works from an engine-enumerated list, not
    # model memory - the transition's own tool result carries it.
    executor = _executor()
    state = _state_with_faction(faction_id="red-circle", name="The Red Circle")
    state = executor.transition_phase(state, TransitionPhaseArgs(phase=CampaignPhase.SCORE)).state
    state = executor.create_clock(
        state,
        CreateClockArgs(
            clock_id="rc-plot",
            name="Seize the docks",
            kind=ClockKind.FACTION,
            segments=6,
            faction_id="red-circle",
        ),
    ).state
    state = executor.tick_clock(state, TickClockArgs(clock_id="rc-plot", amount=2)).state
    state = executor.update_faction_status(
        state, UpdateFactionStatusArgs(faction_id="red-circle", delta=-1)
    ).state
    state = executor.roll_engagement(state, RollEngagementArgs(pool_size=1)).state
    state = executor.roll_action(
        state,
        RollActionArgs(action=Action.PROWL, position=Position.RISKY, effect=Effect.STANDARD),
    ).state

    result = executor.transition_phase(state, TransitionPhaseArgs(phase=CampaignPhase.DOWNTIME))

    assert result.result["phase"] == "downtime"
    (faction,) = result.result["factions"]
    assert faction["faction_id"] == "red-circle"
    assert faction["name"] == "The Red Circle"
    assert faction["status"] == -1
    (clock,) = faction["clocks"]
    assert clock["clock_id"] == "rc-plot"
    assert clock["filled"] == 2
    assert "NPC & faction downtime" in result.result["faction_downtime_reminder"]


def test_create_clock_refuses_an_unknown_faction_id():
    with pytest.raises(EngineError, match="no canon faction"):
        _executor().create_clock(
            _state(),
            CreateClockArgs(
                clock_id="c1", name="Plot", kind=ClockKind.FACTION, segments=6, faction_id="nope"
            ),
        )


def test_adjust_stash_updates_the_character_and_logs_it():
    # SRD: "Stash & Retirement" - the retirement fund on the sheet.
    character = Character(name="Test", playbook="Test Playbook", stash=3)

    result = _executor().adjust_stash(_state(character), AdjustStashArgs(amount=2))

    assert result.result["stash"] == 5
    assert result.state.log.events[-1].event_type == "stash_adjusted"


def test_adjust_stash_refuses_to_go_negative():
    with pytest.raises(EngineError, match="cannot remove"):
        _executor().adjust_stash(_state(), AdjustStashArgs(amount=-1))


def test_cash_out_stash_converts_two_stash_to_one_coin():
    character = Character(name="Test", playbook="Test Playbook", stash=4)
    result = _executor().cash_out_stash(
        _state(character), CashOutStashArgs(stash_amount=2)
    )
    assert result.result == {"stash": 2, "coin": 1}
    assert [event.event_type for event in result.state.log.events[-2:]] == [
        "stash_adjusted",
        "coin_adjusted",
    ]


def test_cash_out_stash_refuses_odd_amount_or_coin_overflow():
    with pytest.raises(EngineError, match="positive even"):
        _executor().cash_out_stash(
            _state(Character(name="Test", playbook="Test Playbook", stash=3)),
            CashOutStashArgs(stash_amount=1),
        )
    with pytest.raises(EngineError, match="at most 4 coin"):
        _executor().cash_out_stash(
            _state(Character(name="Test", playbook="Test Playbook", stash=2, coin=4)),
            CashOutStashArgs(stash_amount=2),
        )


def test_set_load_level_records_the_declared_load():
    # SRD: "Loadout" - "For each operation, decide what your character's
    # load will be... 1-3 load: Light."
    result = _executor().set_load_level(_state(), SetLoadLevelArgs(level="light"))

    assert result.result == {"level": "light", "limit": 3}
    assert result.state.character.load_level.value == "light"
    assert result.state.log.events[-1].event_type == "load_level_set"


def test_set_item_carried_refuses_past_the_declared_load_limit():
    # SRD: "Loadout" - "up to a number of items equal to your chosen load".
    character = Character(
        name="Test",
        playbook="Test Playbook",
        load_level="light",
        load=3,
        items=[
            CharacterItem(item_id="lockpicks", carried=True),
            CharacterItem(item_id="pistol", carried=True),
            CharacterItem(item_id="rope", carried=True),
            CharacterItem(item_id="lantern"),
        ],
    )

    with pytest.raises(EngineError, match="load limit"):
        _executor().set_item_carried(
            _state(character), SetItemCarriedArgs(item_id="lantern", carried=True)
        )


def test_develop_crew_strengthens_hold_and_pays_the_profit_share():
    # SRD: "Development" - filling the tracker with weak hold makes it
    # strong; "Profits" - "Every time the crew advances, each PC gets
    # stash equal to the crew Tier+2".
    state = _state().model_copy(
        update={
            "crew": Crew(
                name="Test Crew", crew_type="Test Type", tier=1, hold="weak", rep={"rep": 12}
            )
        }
    )

    result = _executor().develop_crew(state, DevelopCrewArgs())

    assert result.result == {"tier": 1, "hold": "strong", "profit_share_per_pc": 3}
    assert result.state.crew.hold.value == "strong"
    assert result.state.crew.rep.rep == 0
    assert result.state.character.stash == 3
    types = [e.event_type for e in result.state.log.events]
    assert types == ["crew_developed", "stash_adjusted"]


def test_develop_crew_refuses_below_the_rep_threshold():
    # SRD: "Development" - "You need 12 rep to fill the rep tracker".
    with pytest.raises(EngineError, match="rep threshold"):
        _executor().develop_crew(_state(), DevelopCrewArgs())


def test_adjust_crew_turf_lowers_the_rep_threshold():
    # SRD: "Turf" - "Each piece of turf you hold reduces the rep cost to
    # develop by one."
    result = _executor().adjust_crew_turf(_state(), AdjustCrewTurfArgs(amount=2))

    assert result.result == {"turf": 2, "threshold": 10}
    assert result.state.log.events[-1].event_type == "crew_turf_adjusted"


def test_set_claim_controlled_seizes_a_new_named_claim_with_turf():
    # SRD: "Seizing a claim" - "if you succeed, you seize the claim";
    # "Some claims count as turf."
    result = _executor().set_claim_controlled(
        _state(),
        SetClaimControlledArgs(claim_id="docks", controlled=True, name="The Docks", is_turf=True),
    )

    claim = result.state.crew.claims[0]
    assert claim.controlled and claim.is_turf
    assert result.result["turf"] == 1
    assert result.state.log.events[-1].event_type == "claim_controlled_set"


def test_set_claim_controlled_refuses_an_unknown_claim_without_a_name():
    with pytest.raises(EngineError, match="no claim"):
        _executor().set_claim_controlled(
            _state(), SetClaimControlledArgs(claim_id="nope", controlled=True)
        )


def test_add_canon_faction_grows_canon_and_creates_the_entity():
    # FR-15: a faction introduced mid-play joins canon like a location does.
    state = _state().model_copy(update={"canon": CampaignCanon(setting_name="Test City")})

    result = _executor().add_canon_faction(
        state, AddCanonFactionArgs(faction_id="red-circle", name="The Red Circle", tier=2)
    )

    assert result.state.canon.factions == ["The Red Circle"]
    assert result.state.factions["red-circle"].tier == 2
    assert result.state.log.events[-1].event_type == "canon_faction_added"


def test_add_canon_faction_refuses_without_canon_set():
    with pytest.raises(EngineError, match="no campaign canon"):
        _executor().add_canon_faction(_state(), AddCanonFactionArgs(faction_id="f1", name="Anyone"))


def test_add_canon_faction_refuses_a_duplicate_id():
    with pytest.raises(EngineError, match="already exists"):
        _executor().add_canon_faction(
            _state_with_faction(), AddCanonFactionArgs(faction_id="f1", name="Someone Else")
        )


def test_create_npc_refuses_a_duplicate_id():
    # FR-12: overwriting an existing NPC would be a free-form edit in
    # disguise, same reasoning as create_character's duplicate refusal.
    state = _state_with_npc()

    with pytest.raises(EngineError, match="already exists"):
        _executor().create_npc(state, CreateNpcArgs(npc_id="n1", name="Someone Else"))
