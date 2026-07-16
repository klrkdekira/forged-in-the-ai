import random
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from engine.advancement import (
    POST_CREATION_ACTION_CAP,
    advance_action_rating,
    advance_crew_special_ability,
    advance_crew_upgrades,
    advance_special_ability,
)
from engine.campaign import CampaignCanon, SessionZeroConfig
from engine.character import Action, Attribute, Character
from engine.clocks import Clock, ClockKind
from engine.controller import Controller
from engine.crew import Crew
from engine.downtime import acquire_asset_roll, craft_roll, indulge_vice_roll
from engine.entities import Npc, Score
from engine.errors import EngineError
from engine.events import EventLog
from engine.operations import (
    add_heat,
    adjust_coin,
    adjust_crew_coin,
    adjust_crew_rep,
    adjust_wanted_level,
    flashback,
    heal_character,
    mark_attribute_xp,
    mark_harm,
    mark_playbook_xp,
    mark_stress,
    set_item_carried,
)
from engine.packs import EntanglementEntry
from engine.relationships import FactionStatus, Relationship, RelationshipKind
from engine.rolls import Effect, Position, action_roll, fortune_roll, resistance_roll
from engine.score import downtime_ticks, engagement_roll, entanglement_roll, payoff_rep
from engine.session import CampaignPhase, Session

_DEFAULT_CHARACTER_ID = "pc-1"


class GameState(BaseModel):
    """Everything one tool call can read or change (FR-25: "solo play is
    the whole crew under one seat" - one seat can control several PCs,
    via `characters`, keyed by a caller-supplied character_id the same
    way `clocks`/`npcs` are - not the character's own name)."""

    characters: dict[str, Character] = Field(
        ..., description="Keyed by a caller-supplied character_id"
    )
    crew: Crew
    session: Session
    canon: CampaignCanon | None = None
    session_zero: SessionZeroConfig | None = None
    controllers: dict[str, Controller] = Field(
        default_factory=dict,
        description="Keyed by seat_id; only AI seats need an entry (Controller.kind default "
        "'human' - see engine.controller.is_ai_controlled)",
    )
    clocks: dict[str, Clock] = Field(default_factory=dict)
    npcs: dict[str, Npc] = Field(default_factory=dict)
    scores: dict[str, Score] = Field(default_factory=dict)
    faction_statuses: dict[str, FactionStatus] = Field(
        default_factory=dict, description="Keyed by faction_id"
    )
    relationships: dict[str, Relationship] = Field(
        default_factory=dict,
        description="Keyed by '<subject_type>:<subject_id>:<object_type>:<object_id>'",
    )
    log: EventLog = Field(default_factory=EventLog)

    @model_validator(mode="before")
    @classmethod
    def _wrap_singular_character(cls, data: object) -> object:
        """Back-compat: every pre-multi-PC caller constructs
        `GameState(character=..., ...)` for the single-PC MVP (FR-25).
        Wraps it into `characters` under the reserved "pc-1" id rather
        than requiring every call site to migrate to the dict."""
        if isinstance(data, dict) and "characters" not in data and "character" in data:
            rest = {key: value for key, value in data.items() if key != "character"}
            data = {**rest, "characters": {_DEFAULT_CHARACTER_ID: data["character"]}}
        return data

    @computed_field  # type: ignore[prop-decorator]
    @property
    def character(self) -> Character:
        """The crew's primary PC, for single-PC contexts (canon/recap
        headers, the dev CLI) - never used to resolve a mutating tool
        call, which always names a specific character_id
        (`ToolExecutor.resolve_character_id`)."""
        return next(iter(self.characters.values()))


class ToolCallResult(BaseModel):
    state: GameState
    result: dict


class RollActionArgs(BaseModel):
    action: Action
    position: Position
    effect: Effect = Field(
        ..., description="limited, standard, great, zero, or extreme (name or Effect's int value)"
    )
    character_id: str | None = Field(
        None, description="Which PC is rolling; only needed once more than one PC exists"
    )

    @field_validator("effect", mode="before")
    @classmethod
    def _effect_by_name(cls, value: object) -> object:
        """`Effect` is an IntEnum (its ordering drives `bumped()`), but
        that means the raw tool-call value would otherwise have to be a
        magic number (0-4) instead of a name - awkward for a human typing
        JSON, and an easy mistake for a model reading the tool schema."""
        if isinstance(value, str) and value.upper() in Effect.__members__:
            return Effect[value.upper()]
        return value


class RollDecision(BaseModel):
    """SRD: "Add Bonus Dice" and "Trading Position for Effect" - the
    player's step-5 choices, applied to a GM-proposed `RollActionArgs`
    before the roll executes. Deliberately not part of `TOOL_SPECS`: this
    is never shown to the LLM as a tool schema, because the point of the
    negotiation dialog (FR-16) is that the player decides this, not the
    model that proposed the position/effect."""

    push_dice: bool = Field(False, description="Push yourself for +1d (2 stress)")
    push_effect: bool = Field(False, description="Push yourself for +1 effect level (2 stress)")
    devils_bargain: str | None = Field(
        None, description="Accepted Devil's Bargain price, if any (+1d, free)"
    )
    trade: Literal["worse_position_better_effect", "better_position_worse_effect"] | None = None
    assist_character_id: str | None = Field(
        None,
        description="SRD 'Teamwork'/'Assist': another PC helping this roll - they take 1 "
        "stress, this roll gets +1d",
    )


class RollFortuneArgs(BaseModel):
    pool_size: int = Field(..., description="Dice pool for the trait being assessed")


class RollResistanceArgs(BaseModel):
    attribute: Attribute
    character_id: str | None = Field(
        None, description="Which PC is resisting; only needed once more than one PC exists"
    )


class CreateClockArgs(BaseModel):
    clock_id: str
    name: str
    kind: ClockKind
    segments: int


class TickClockArgs(BaseModel):
    clock_id: str
    amount: int = Field(1, description="Positive to fill, negative to empty (tug-of-war)")


class ApplyHarmArgs(BaseModel):
    level: int = Field(..., description="1-3, or 4 for fatal harm")
    name: str
    character_id: str | None = Field(
        None, description="Which PC is harmed; only needed once more than one PC exists"
    )


class MarkStressArgs(BaseModel):
    amount: int = Field(..., description="Positive to mark, negative to clear")
    character_id: str | None = Field(
        None, description="Which PC marks stress; only needed once more than one PC exists"
    )


class TransitionPhaseArgs(BaseModel):
    phase: CampaignPhase


class CreateNpcArgs(BaseModel):
    npc_id: str
    name: str
    tags: list[str] = Field(default_factory=list)
    faction_id: str | None = None


class CreateScoreArgs(BaseModel):
    score_id: str
    target: str = Field(..., description="What the crew is after and where")
    plan_type: str | None = None
    plan_detail: str | None = None


class UpdateScoreArgs(BaseModel):
    score_id: str
    engagement_result: str | None = Field(
        None, description="The engagement roll's outcome, e.g. 'controlled'"
    )
    payoff: int | None = Field(None, description="Coin the score earned")
    heat_gained: int | None = Field(None, description="Heat the crew took for this score")
    entanglement: str | None = Field(None, description="The entanglement rolled, if any")


class CreateCharacterArgs(BaseModel):
    character_id: str = Field(..., description="A stable id for this PC, e.g. 'pc-2'")
    name: str
    playbook: str
    controller_kind: Literal["human", "ai"] = Field(
        "ai",
        description="'ai' for a crewmate the AI player agent runs (FR-35); 'human' for another "
        "player's seat. The primary PC from campaign creation is always human and unaffected.",
    )


class UpdateFactionStatusArgs(BaseModel):
    faction_id: str
    delta: int = Field(..., description="Change to apply, e.g. -1 or -2 after a hostile score")


class UpdateRelationshipArgs(BaseModel):
    subject_type: str = Field(..., description="e.g. 'character', 'crew', 'npc'")
    subject_id: str
    object_type: str = Field(..., description="e.g. 'npc', 'faction', 'crew'")
    object_id: str
    kind: RelationshipKind
    status: str | None = Field(
        None, description="Free-form detail, e.g. 'owes a favour after the Docks job'"
    )


class AddCanonFactArgs(BaseModel):
    fact: str = Field(..., description="A new established fact about the setting")


class AddCanonLocationArgs(BaseModel):
    location: str = Field(..., description="A new location the fiction has just introduced")


class SetSessionZeroConfigArgs(BaseModel):
    lines: list[str] = Field(default_factory=list, description="Hard limits: never in the fiction")
    veils: list[str] = Field(
        default_factory=list, description="Fade-to-black topics: implied, not detailed"
    )
    tone: str | None = None


class SetCampaignCanonArgs(BaseModel):
    setting_name: str = Field(
        ..., description="An original city/setting name - never a core-book setting"
    )
    tone: str | None = None
    factions: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)


class InvokeXCardArgs(BaseModel):
    note: str | None = Field(None, description="Optional context for the campaign log")


class HealCharacterArgs(BaseModel):
    """SRD: "Recover" - no other fields; healing one level of harm needs
    no further input from whoever clicks it."""

    character_id: str | None = Field(
        None, description="Which PC heals; only needed once more than one PC exists"
    )


class MarkXpArgs(BaseModel):
    track: Literal["playbook", "insight", "prowess", "resolve"]
    amount: int = Field(..., description="Positive to mark, negative to clear")
    character_id: str | None = Field(
        None, description="Which PC marks XP; only needed once more than one PC exists"
    )


class AdjustCoinArgs(BaseModel):
    amount: int = Field(..., description="Positive to gain, negative to spend")
    character_id: str | None = Field(
        None, description="Which PC's coin; only needed once more than one PC exists"
    )


class SetItemCarriedArgs(BaseModel):
    item_id: str
    carried: bool
    character_id: str | None = Field(
        None, description="Which PC's loadout; only needed once more than one PC exists"
    )


class RollEngagementArgs(BaseModel):
    pool_size: int = Field(
        ...,
        description="Fortune-roll pool: 1d for sheer luck, +-1d per major advantage/disadvantage",
    )


class ResolvePayoffArgs(BaseModel):
    target_tier: int = Field(..., description="The target's Tier, for the rep formula")
    coin: int = Field(0, description="Coin the crew earned from the score")
    quiet: bool = Field(
        False, description="No rep is gained if the operation was kept completely quiet"
    )


class AddCrewHeatArgs(BaseModel):
    amount: int = Field(
        ..., description="Positive to add heat, negative to clear it (e.g. from Reduce Heat)"
    )


class AdjustWantedLevelArgs(BaseModel):
    amount: int = Field(
        ..., description="Positive to raise the crew's wanted level, negative to lower it"
    )


class AdjustCrewRepArgs(BaseModel):
    amount: int = Field(..., description="Rep gained, outside of a score's payoff")


class AdjustCrewCoinArgs(BaseModel):
    amount: int = Field(..., description="Positive to gain crew coin, negative to spend it")


class RollEntanglementArgs(BaseModel):
    """SRD: "Entanglements" - no fields; the roll is entirely determined by
    the crew's current wanted level and heat."""


class AcquireAssetArgs(BaseModel):
    """SRD: "Acquire Asset" - no fields; rolls the crew's Tier."""


class IndulgeViceArgs(BaseModel):
    character_id: str | None = Field(
        None, description="Which PC indulges; only needed once more than one PC exists"
    )


class CraftArgs(BaseModel):
    coin_spent: int = Field(0, description="Coin spent 1-for-1 to raise the result's quality level")
    character_id: str | None = Field(
        None, description="Which PC crafts; only needed once more than one PC exists"
    )


class ReduceHeatArgs(BaseModel):
    pool_size: int = Field(..., description="Dice pool for the action rolled to reduce heat")


class RecoverArgs(BaseModel):
    clock_id: str = Field(..., description="The character's healing clock")
    pool_size: int = Field(..., description="Dice pool for the action rolled to get treatment")
    character_id: str | None = Field(
        None, description="Which PC recovers; only needed once more than one PC exists"
    )


class LongTermProjectArgs(BaseModel):
    clock_id: str = Field(..., description="The long-term project's clock")
    pool_size: int = Field(..., description="Dice pool for the action rolled to work the project")


class FlashbackArgs(BaseModel):
    stress_cost: int = Field(
        ..., description="0, 1, 2, or more - the GM's judged cost for this flashback"
    )
    character_id: str | None = Field(
        None, description="Which PC flashes back; only needed once more than one PC exists"
    )


class AdvanceActionRatingArgs(BaseModel):
    action: Action
    character_id: str | None = Field(
        None, description="Which PC advances; only needed once more than one PC exists"
    )
    cap: int = Field(
        POST_CREATION_ACTION_CAP, description="Action rating cap - 4 once the crew has Mastery"
    )


class AdvanceSpecialAbilityArgs(BaseModel):
    ability_id: str
    character_id: str | None = Field(
        None, description="Which PC advances; only needed once more than one PC exists"
    )


class AdvanceCrewSpecialAbilityArgs(BaseModel):
    ability_id: str


class AdvanceCrewUpgradesArgs(BaseModel):
    upgrade_ids: tuple[str, str] = Field(
        ..., description="Two crew upgrade boxes to mark - the crew-xp alternative to a new ability"
    )


class ToolExecutor:
    """Executes GM-agent tool calls against a `GameState` (FR-12): the AI
    never edits state directly, only through these methods. Holds the
    injected RNG and clock so no method call needs to pass them - the same
    "no datetime.now()/random() inside deterministic logic" rule the engine
    follows (CLAUDE.md), applied one layer up."""

    def __init__(
        self,
        rng: random.Random,
        clock: Callable[[], datetime],
        entanglements: Sequence[EntanglementEntry] = (),
    ):
        self._rng = rng
        self._clock = clock
        self._entanglements = entanglements

    def log_event(
        self, state: GameState, entity_type: str, entity_id: str, event_type: str, payload: dict
    ) -> GameState:
        """FR-31: lets the GM agent record player input and narration as
        structured events too, not just mechanical tool calls - the
        journal, and FR-18's resume recap, need the whole turn, not just
        its dice."""
        log = state.log.append(entity_type, entity_id, event_type, payload, self._clock())
        return state.model_copy(update={"log": log})

    def resolve_character_id(self, state: GameState, character_id: str | None) -> str:
        """FR-25: resolves which PC a tool call affects. Refuses rather
        than guessing (CLAUDE.md) once there's more than one - an
        unspecified `character_id` is only unambiguous while there's
        exactly one PC."""
        if character_id is not None:
            if character_id not in state.characters:
                raise EngineError(f"no character {character_id!r} in this session")
            return character_id
        if len(state.characters) != 1:
            raise EngineError("character_id is required once a session has more than one character")
        return next(iter(state.characters))

    def create_character(self, state: GameState, args: CreateCharacterArgs) -> ToolCallResult:
        """FR-25/FR-35: the only way a second PC comes into existence for
        now - session zero, or a crewmate introduced mid-campaign. Also
        registers the new PC's seat (`controller_kind`) - a companion
        defaults to AI-controlled, so PlayerAgent picks it up as soon as
        it exists, with no separate wiring step required."""
        if args.character_id in state.characters:
            raise EngineError(f"character {args.character_id!r} already exists in this session")
        character = Character(name=args.name, playbook=args.playbook)
        event_payload = {
            **character.model_dump(mode="json"),
            "controller_kind": args.controller_kind,
        }
        log = state.log.append(
            "character", args.character_id, "character_created", event_payload, self._clock()
        )
        characters = {**state.characters, args.character_id: character}
        seat_id = f"seat:{args.character_id}"
        controllers = {
            **state.controllers,
            seat_id: Controller(
                seat_id=seat_id, kind=args.controller_kind, character_ids=[args.character_id]
            ),
        }
        return ToolCallResult(
            state=state.model_copy(
                update={"characters": characters, "controllers": controllers, "log": log}
            ),
            result={"character_id": args.character_id},
        )

    def roll_action(
        self,
        state: GameState,
        args: RollActionArgs,
        bonus_dice: int = 0,
        devils_bargain: str | None = None,
        assisted_by: str | None = None,
    ) -> ToolCallResult:
        """SRD: "Action Roll". `bonus_dice`/`devils_bargain`/`assisted_by`
        are Python-only parameters, not fields on `RollActionArgs` - they
        come from the player's post-negotiation `RollDecision` (FR-16),
        applied by the GM agent's `_resolve_roll` before this call, never
        from the LLM's own tool-call arguments (`tool_definitions()` only
        ever introspects `RollActionArgs`, so the model never sees these as
        choices it makes)."""
        character_id = self.resolve_character_id(state, args.character_id)
        pool_size = state.characters[character_id].action_ratings.get(args.action, 0) + bonus_dice
        roll = action_roll(pool_size, args.position, args.effect, self._rng)
        payload = {
            "action": args.action.value,
            "bonus_dice": bonus_dice,
            **roll.model_dump(mode="json"),
        }
        if devils_bargain:
            payload["devils_bargain"] = devils_bargain
        if assisted_by:
            payload["assisted_by"] = assisted_by
        log = state.log.append("character", character_id, "action_roll", payload, self._clock())
        return ToolCallResult(
            state=state.model_copy(update={"log": log}), result=roll.model_dump(mode="json")
        )

    def roll_fortune(self, state: GameState, args: RollFortuneArgs) -> ToolCallResult:
        """SRD: "Fortune Roll". Logged under the session, not a PC: the
        mechanic is trait-agnostic (a faction's quality, weather, an
        offscreen outcome), so it belongs to no character."""
        roll = fortune_roll(args.pool_size, self._rng)
        log = state.log.append(
            "session",
            "current",
            "fortune_roll",
            roll.model_dump(mode="json"),
            self._clock(),
        )
        return ToolCallResult(
            state=state.model_copy(update={"log": log}), result=roll.model_dump(mode="json")
        )

    def roll_resistance(self, state: GameState, args: RollResistanceArgs) -> ToolCallResult:
        """SRD: "Resistance and Armor"."""
        character_id = self.resolve_character_id(state, args.character_id)
        rating = state.characters[character_id].attribute_rating(args.attribute)
        roll = resistance_roll(rating, self._rng)
        log = state.log.append(
            "character",
            character_id,
            "resistance_roll",
            {"attribute": args.attribute.value, **roll.model_dump(mode="json")},
            self._clock(),
        )
        return ToolCallResult(
            state=state.model_copy(update={"log": log}), result=roll.model_dump(mode="json")
        )

    def create_clock(self, state: GameState, args: CreateClockArgs) -> ToolCallResult:
        """SRD: "Progress clocks"."""
        clock = Clock(name=args.name, kind=args.kind, segments=args.segments)
        log = state.log.append(
            "clock",
            args.clock_id,
            "clock_created",
            {"name": args.name, "kind": args.kind.value, "segments": args.segments},
            self._clock(),
        )
        clocks = {**state.clocks, args.clock_id: clock}
        return ToolCallResult(
            state=state.model_copy(update={"clocks": clocks, "log": log}),
            result=clock.model_dump(mode="json"),
        )

    def tick_clock(self, state: GameState, args: TickClockArgs) -> ToolCallResult:
        if args.clock_id not in state.clocks:
            raise EngineError(f"no clock {args.clock_id!r} in this session")
        clock = state.clocks[args.clock_id].tick(args.amount)
        log = state.log.append(
            "clock", args.clock_id, "clock_ticked", {"amount": args.amount}, self._clock()
        )
        clocks = {**state.clocks, args.clock_id: clock}
        return ToolCallResult(
            state=state.model_copy(update={"clocks": clocks, "log": log}),
            result=clock.model_dump(mode="json"),
        )

    def apply_harm(self, state: GameState, args: ApplyHarmArgs) -> ToolCallResult:
        """SRD: "Consequences and Harm"."""
        character_id = self.resolve_character_id(state, args.character_id)
        mutation = mark_harm(state.characters[character_id], args.level, args.name)
        log = state.log.append(
            "character",
            character_id,
            "harm_marked",
            {"level": args.level, "name": args.name, "catastrophic": mutation.catastrophic_harm},
            self._clock(),
        )
        characters = {**state.characters, character_id: mutation.character}
        state = state.model_copy(update={"characters": characters, "log": log})
        return ToolCallResult(state=state, result={"catastrophic": mutation.catastrophic_harm})

    def mark_stress(self, state: GameState, args: MarkStressArgs) -> ToolCallResult:
        character_id = self.resolve_character_id(state, args.character_id)
        mutation = mark_stress(state.characters[character_id], args.amount)
        log = state.log.append(
            "character",
            character_id,
            "stress_marked",
            {"amount": args.amount, "triggered_trauma": mutation.triggered_trauma},
            self._clock(),
        )
        characters = {**state.characters, character_id: mutation.character}
        state = state.model_copy(update={"characters": characters, "log": log})
        return ToolCallResult(state=state, result={"triggered_trauma": mutation.triggered_trauma})

    def heal_character(self, state: GameState, args: HealCharacterArgs) -> ToolCallResult:
        """SRD: "Recover". Part of `SHEET_OPERATIONS` (FR-28), not
        `TOOL_SPECS`: the player heals directly, the GM/model doesn't call
        this on their behalf."""
        character_id = self.resolve_character_id(state, args.character_id)
        character = heal_character(state.characters[character_id])
        log = state.log.append("character", character_id, "harm_healed", {}, self._clock())
        characters = {**state.characters, character_id: character}
        return ToolCallResult(
            state=state.model_copy(update={"characters": characters, "log": log}), result={}
        )

    def mark_xp(self, state: GameState, args: MarkXpArgs) -> ToolCallResult:
        """SRD: "PC Advancement". `SHEET_OPERATIONS` only (FR-28) - marking
        xp is the player's own bookkeeping, not a GM/model tool call."""
        character_id = self.resolve_character_id(state, args.character_id)
        base = state.characters[character_id]
        if args.track == "playbook":
            character = mark_playbook_xp(base, args.amount)
        else:
            character = mark_attribute_xp(base, Attribute(args.track), args.amount)
        log = state.log.append(
            "character",
            character_id,
            "xp_marked",
            {"track": args.track, "amount": args.amount},
            self._clock(),
        )
        characters = {**state.characters, character_id: character}
        return ToolCallResult(
            state=state.model_copy(update={"characters": characters, "log": log}),
            result={"track": args.track},
        )

    def adjust_coin(self, state: GameState, args: AdjustCoinArgs) -> ToolCallResult:
        """SRD: "Coin and Stash". `SHEET_OPERATIONS` only (FR-28)."""
        character_id = self.resolve_character_id(state, args.character_id)
        character = adjust_coin(state.characters[character_id], args.amount)
        log = state.log.append(
            "character",
            character_id,
            "coin_adjusted",
            {"amount": args.amount},
            self._clock(),
        )
        characters = {**state.characters, character_id: character}
        return ToolCallResult(
            state=state.model_copy(update={"characters": characters, "log": log}),
            result={"coin": character.coin},
        )

    def set_item_carried(self, state: GameState, args: SetItemCarriedArgs) -> ToolCallResult:
        """SRD: "Loadout". `SHEET_OPERATIONS` only (FR-28) - toggling
        carried items is the player choosing their loadout, not a GM call."""
        character_id = self.resolve_character_id(state, args.character_id)
        character = set_item_carried(state.characters[character_id], args.item_id, args.carried)
        log = state.log.append(
            "character",
            character_id,
            "item_carried_set",
            {"item_id": args.item_id, "carried": args.carried},
            self._clock(),
        )
        characters = {**state.characters, character_id: character}
        return ToolCallResult(
            state=state.model_copy(update={"characters": characters, "log": log}),
            result={"load": character.load},
        )

    def roll_engagement(self, state: GameState, args: RollEngagementArgs) -> ToolCallResult:
        """SRD: "Engagement Roll" - sets the crew's starting position for the score."""
        roll = engagement_roll(args.pool_size, self._rng)
        log = state.log.append(
            "score", "current", "engagement_roll", roll.model_dump(mode="json"), self._clock()
        )
        return ToolCallResult(
            state=state.model_copy(update={"log": log}), result=roll.model_dump(mode="json")
        )

    def resolve_payoff(self, state: GameState, args: ResolvePayoffArgs) -> ToolCallResult:
        """SRD: "Payoff" - rep (+-1 per Tier difference from the target, zero if kept quiet)
        plus whatever coin the score earned."""
        rep = payoff_rep(state.crew.tier, args.target_tier, args.quiet)
        crew = state.crew.model_copy(
            update={"rep": state.crew.rep.add_rep(rep), "coin": state.crew.coin + args.coin}
        )
        log = state.log.append(
            "crew",
            crew.name,
            "payoff",
            {"rep": rep, "coin": args.coin, "target_tier": args.target_tier, "quiet": args.quiet},
            self._clock(),
        )
        return ToolCallResult(
            state=state.model_copy(update={"crew": crew, "log": log}),
            result={"rep": rep, "coin": args.coin},
        )

    def add_crew_heat(self, state: GameState, args: AddCrewHeatArgs) -> ToolCallResult:
        """SRD: "Heat" - heat 0-9; reaching 9 gains a wanted level and rolls the excess over."""
        mutation = add_heat(state.crew, args.amount)
        log = state.log.append(
            "crew", mutation.crew.name, "heat_added", {"amount": args.amount}, self._clock()
        )
        return ToolCallResult(
            state=state.model_copy(update={"crew": mutation.crew, "log": log}),
            result={
                "heat": mutation.crew.heat.heat,
                "wanted_level": mutation.crew.wanted_level,
                "wanted_level_increased": mutation.wanted_level_increased,
            },
        )

    def adjust_wanted_level(self, state: GameState, args: AdjustWantedLevelArgs) -> ToolCallResult:
        """SRD: "Heat & Wanted Level" - direct adjustment (e.g.
        incarceration lowering it by 1), outside of heat overflow."""
        crew = adjust_wanted_level(state.crew, args.amount)
        log = state.log.append(
            "crew", crew.name, "wanted_level_adjusted", {"amount": args.amount}, self._clock()
        )
        return ToolCallResult(
            state=state.model_copy(update={"crew": crew, "log": log}),
            result={"wanted_level": crew.wanted_level},
        )

    def adjust_crew_rep(self, state: GameState, args: AdjustCrewRepArgs) -> ToolCallResult:
        """SRD: "Development" - rep gained outside of a score's payoff."""
        crew = adjust_crew_rep(state.crew, args.amount)
        log = state.log.append(
            "crew", crew.name, "crew_rep_adjusted", {"amount": args.amount}, self._clock()
        )
        return ToolCallResult(
            state=state.model_copy(update={"crew": crew, "log": log}),
            result={"rep": crew.rep.rep},
        )

    def adjust_crew_coin(self, state: GameState, args: AdjustCrewCoinArgs) -> ToolCallResult:
        """SRD: "Coin and Stash" - the crew's own coin, spent on crew
        upgrades and assets."""
        crew = adjust_crew_coin(state.crew, args.amount)
        log = state.log.append(
            "crew", crew.name, "crew_coin_adjusted", {"amount": args.amount}, self._clock()
        )
        return ToolCallResult(
            state=state.model_copy(update={"crew": crew, "log": log}),
            result={"coin": crew.coin},
        )

    def roll_entanglement(self, state: GameState, args: RollEntanglementArgs) -> ToolCallResult:
        """SRD: "Entanglements" - heat band picks the column, wanted-level dice pick the row."""
        if not self._entanglements:
            raise EngineError("no entanglement table loaded for this session")
        roll = entanglement_roll(
            state.crew.wanted_level, state.crew.heat.heat, self._entanglements, self._rng
        )
        log = state.log.append(
            "crew",
            state.crew.name,
            "entanglement_roll",
            roll.model_dump(mode="json"),
            self._clock(),
        )
        return ToolCallResult(
            state=state.model_copy(update={"log": log}), result=roll.model_dump(mode="json")
        )

    def acquire_asset(self, state: GameState, args: AcquireAssetArgs) -> ToolCallResult:
        """SRD: "Acquire Asset" - roll the crew's Tier; the result sets the asset's quality."""
        roll = acquire_asset_roll(state.crew.tier, self._rng)
        log = state.log.append(
            "crew", state.crew.name, "asset_acquired", roll.model_dump(mode="json"), self._clock()
        )
        return ToolCallResult(
            state=state.model_copy(update={"log": log}), result=roll.model_dump(mode="json")
        )

    def indulge_vice(self, state: GameState, args: IndulgeViceArgs) -> ToolCallResult:
        """SRD: "Vice" - clear stress equal to the highest die of a pool sized by the
        character's lowest attribute; clearing more than was marked overindulges."""
        character_id = self.resolve_character_id(state, args.character_id)
        character = state.characters[character_id]
        lowest = min(character.attribute_rating(attribute) for attribute in Attribute)
        roll = indulge_vice_roll(lowest, character.stress.marked, self._rng)
        log = state.log.append(
            "character", character_id, "vice_indulged", roll.model_dump(mode="json"), self._clock()
        )
        state = state.model_copy(update={"log": log})
        state = self.mark_stress(
            state, MarkStressArgs(amount=-roll.stress_cleared, character_id=character_id)
        ).state
        return ToolCallResult(state=state, result=roll.model_dump(mode="json"))

    def craft(self, state: GameState, args: CraftArgs) -> ToolCallResult:
        """SRD: "Crafting"/"CRAFTING ROLL" - roll Tinker; quality is the
        crew's Tier plus the result, +1 for the Workshop crew upgrade
        (`"workshop"`, the SRD base pack's own id for it), and +1 per coin
        spent."""
        character_id = self.resolve_character_id(state, args.character_id)
        character = state.characters[character_id]
        tinker_rating = character.action_ratings.get(Action.TINKER, 0)
        has_workshop = "workshop" in state.crew.upgrade_ids
        roll = craft_roll(
            tinker_rating,
            state.crew.tier,
            self._rng,
            has_workshop=has_workshop,
            coin_spent=args.coin_spent,
        )
        log = state.log.append(
            "character",
            character_id,
            "downtime_activity_rolled",
            {
                "activity": "craft",
                "pool_size": tinker_rating,
                "band": roll.band.value,
                "quality": roll.quality,
                "coin_spent": args.coin_spent,
            },
            self._clock(),
        )
        state = state.model_copy(update={"log": log})
        if args.coin_spent:
            state = self.adjust_coin(
                state, AdjustCoinArgs(amount=-args.coin_spent, character_id=character_id)
            ).state
        return ToolCallResult(state=state, result=roll.model_dump(mode="json"))

    def reduce_heat(self, state: GameState, args: ReduceHeatArgs) -> ToolCallResult:
        """SRD: "Reduce Heat" - roll your action; the result clears that much heat."""
        roll = fortune_roll(args.pool_size, self._rng)
        ticks = downtime_ticks(roll.band)
        log = state.log.append(
            "crew",
            state.crew.name,
            "downtime_activity_rolled",
            {
                "activity": "reduce_heat",
                "pool_size": args.pool_size,
                "band": roll.band.value,
                "amount": ticks,
            },
            self._clock(),
        )
        state = state.model_copy(update={"log": log})
        state = self.add_crew_heat(state, AddCrewHeatArgs(amount=-ticks)).state
        return ToolCallResult(state=state, result={"band": roll.band.value, "heat_cleared": ticks})

    def recover(self, state: GameState, args: RecoverArgs) -> ToolCallResult:
        """SRD: "Recover" - tick the healing clock like a long-term project; filling it
        heals one level of harm."""
        character_id = self.resolve_character_id(state, args.character_id)
        if args.clock_id not in state.clocks:
            raise EngineError(f"no clock {args.clock_id!r} in this session")
        roll = fortune_roll(args.pool_size, self._rng)
        ticks = downtime_ticks(roll.band)
        log = state.log.append(
            "character",
            character_id,
            "downtime_activity_rolled",
            {
                "activity": "recover",
                "pool_size": args.pool_size,
                "band": roll.band.value,
                "amount": ticks,
            },
            self._clock(),
        )
        state = state.model_copy(update={"log": log})
        state = self.tick_clock(state, TickClockArgs(clock_id=args.clock_id, amount=ticks)).state
        healed = False
        if state.clocks[args.clock_id].is_complete:
            state = self.heal_character(state, HealCharacterArgs(character_id=character_id)).state
            healed = True
        return ToolCallResult(
            state=state, result={"band": roll.band.value, "ticks": ticks, "healed": healed}
        )

    def long_term_project(self, state: GameState, args: LongTermProjectArgs) -> ToolCallResult:
        """SRD: "Long-Term Project" - roll your action; the result ticks that many segments."""
        if args.clock_id not in state.clocks:
            raise EngineError(f"no clock {args.clock_id!r} in this session")
        roll = fortune_roll(args.pool_size, self._rng)
        ticks = downtime_ticks(roll.band)
        log = state.log.append(
            "clock",
            args.clock_id,
            "downtime_activity_rolled",
            {
                "activity": "long_term_project",
                "pool_size": args.pool_size,
                "band": roll.band.value,
                "amount": ticks,
            },
            self._clock(),
        )
        state = state.model_copy(update={"log": log})
        state = self.tick_clock(state, TickClockArgs(clock_id=args.clock_id, amount=ticks)).state
        return ToolCallResult(state=state, result={"band": roll.band.value, "ticks": ticks})

    def flashback(self, state: GameState, args: FlashbackArgs) -> ToolCallResult:
        """SRD: "Flashbacks" - a stress cost the GM sets, paid the same way any other
        stress is marked."""
        character_id = self.resolve_character_id(state, args.character_id)
        mutation = flashback(state.characters[character_id], args.stress_cost)
        log = state.log.append(
            "character",
            character_id,
            "flashback_taken",
            {"stress_cost": args.stress_cost, "triggered_trauma": mutation.triggered_trauma},
            self._clock(),
        )
        characters = {**state.characters, character_id: mutation.character}
        return ToolCallResult(
            state=state.model_copy(update={"characters": characters, "log": log}),
            result={"triggered_trauma": mutation.triggered_trauma},
        )

    def advance_action_rating(
        self, state: GameState, args: AdvanceActionRatingArgs
    ) -> ToolCallResult:
        """SRD: "PC Advancement" - filling an attribute's xp track adds a dot to one
        of its actions."""
        character_id = self.resolve_character_id(state, args.character_id)
        character = advance_action_rating(state.characters[character_id], args.action, args.cap)
        new_rating = character.action_ratings[args.action]
        log = state.log.append(
            "character",
            character_id,
            "action_advanced",
            {"action": args.action.value, "new_rating": new_rating, "cap": args.cap},
            self._clock(),
        )
        characters = {**state.characters, character_id: character}
        return ToolCallResult(
            state=state.model_copy(update={"characters": characters, "log": log}),
            result={"action": args.action.value, "new_rating": new_rating},
        )

    def advance_special_ability(
        self, state: GameState, args: AdvanceSpecialAbilityArgs
    ) -> ToolCallResult:
        """SRD: "PC Advancement" - filling the playbook xp track grants a new special
        ability."""
        character_id = self.resolve_character_id(state, args.character_id)
        character = advance_special_ability(state.characters[character_id], args.ability_id)
        log = state.log.append(
            "character",
            character_id,
            "special_ability_advanced",
            {"ability_id": args.ability_id},
            self._clock(),
        )
        characters = {**state.characters, character_id: character}
        return ToolCallResult(
            state=state.model_copy(update={"characters": characters, "log": log}),
            result={"ability_id": args.ability_id},
        )

    def advance_crew_special_ability(
        self, state: GameState, args: AdvanceCrewSpecialAbilityArgs
    ) -> ToolCallResult:
        """SRD: "Crew Advancement" - filling the crew xp tracker grants a new special
        ability."""
        crew = advance_crew_special_ability(state.crew, args.ability_id)
        log = state.log.append(
            "crew",
            crew.name,
            "crew_special_ability_advanced",
            {"ability_id": args.ability_id},
            self._clock(),
        )
        return ToolCallResult(
            state=state.model_copy(update={"crew": crew, "log": log}),
            result={"ability_id": args.ability_id},
        )

    def advance_crew_upgrades(
        self, state: GameState, args: AdvanceCrewUpgradesArgs
    ) -> ToolCallResult:
        """SRD: "Crew Advancement" - the crew-xp alternative to a new special ability:
        mark two crew upgrade boxes."""
        crew = advance_crew_upgrades(state.crew, args.upgrade_ids)
        log = state.log.append(
            "crew",
            crew.name,
            "crew_upgrades_advanced",
            {"upgrade_ids": list(args.upgrade_ids)},
            self._clock(),
        )
        return ToolCallResult(
            state=state.model_copy(update={"crew": crew, "log": log}),
            result={"upgrade_ids": list(args.upgrade_ids)},
        )

    def transition_phase(self, state: GameState, args: TransitionPhaseArgs) -> ToolCallResult:
        """SRD: "The Game Structure"."""
        session = state.session.transition_to(args.phase)
        log = state.log.append(
            "session", "current", "phase_transitioned", {"phase": args.phase.value}, self._clock()
        )
        state = state.model_copy(update={"session": session, "log": log})
        return ToolCallResult(state=state, result={"phase": args.phase.value})

    def create_score(self, state: GameState, args: CreateScoreArgs) -> ToolCallResult:
        """SPECIFICATION.md §5: "Score" - the target and plan, set once
        the crew commits to a job (SRD: "The Score")."""
        score = Score(
            id=args.score_id,
            target=args.target,
            plan_type=args.plan_type,
            plan_detail=args.plan_detail,
        )
        log = state.log.append(
            "score", args.score_id, "score_created", score.model_dump(mode="json"), self._clock()
        )
        scores = {**state.scores, args.score_id: score}
        return ToolCallResult(
            state=state.model_copy(update={"scores": scores, "log": log}),
            result=score.model_dump(mode="json"),
        )

    def update_score(self, state: GameState, args: UpdateScoreArgs) -> ToolCallResult:
        """SPECIFICATION.md §5: "Score" - records this score's engagement
        result, payoff, heat, and entanglement as they're resolved."""
        if args.score_id not in state.scores:
            raise EngineError(f"no score {args.score_id!r} in this session")
        updates = {
            field: value
            for field, value in (
                ("engagement_result", args.engagement_result),
                ("payoff", args.payoff),
                ("heat_gained", args.heat_gained),
                ("entanglement", args.entanglement),
            )
            if value is not None
        }
        score = state.scores[args.score_id].model_copy(update=updates)
        log = state.log.append("score", args.score_id, "score_updated", updates, self._clock())
        scores = {**state.scores, args.score_id: score}
        return ToolCallResult(
            state=state.model_copy(update={"scores": scores, "log": log}),
            result=score.model_dump(mode="json"),
        )

    def create_npc(self, state: GameState, args: CreateNpcArgs) -> ToolCallResult:
        """SPECIFICATION.md §5: "NPC ... lightweight entities with tags and
        the fiction established about them"."""
        npc = Npc(id=args.npc_id, name=args.name, tags=args.tags, faction_id=args.faction_id)
        log = state.log.append(
            "npc", args.npc_id, "npc_created", npc.model_dump(mode="json"), self._clock()
        )
        npcs = {**state.npcs, args.npc_id: npc}
        return ToolCallResult(
            state=state.model_copy(update={"npcs": npcs, "log": log}),
            result=npc.model_dump(mode="json"),
        )

    def update_faction_status(
        self, state: GameState, args: UpdateFactionStatusArgs
    ) -> ToolCallResult:
        """SRD: "Faction Status" (-3 to +3); FR-33's typed Relationship
        special case (engine.relationships.FactionStatus)."""
        current = state.faction_statuses.get(
            args.faction_id, FactionStatus(crew_id=state.crew.name, faction_id=args.faction_id)
        )
        log = state.log.append(
            "faction_status",
            args.faction_id,
            "faction_status_changed",
            {"delta": args.delta},
            self._clock(),
        )
        updated = current.changed(args.delta, log.events[-1].sequence)
        statuses = {**state.faction_statuses, args.faction_id: updated}
        return ToolCallResult(
            state=state.model_copy(update={"faction_statuses": statuses, "log": log}),
            result={"status": updated.status},
        )

    def update_relationship(self, state: GameState, args: UpdateRelationshipArgs) -> ToolCallResult:
        """FR-33/FR-34: a typed edge between any two entities - a
        betrayal, a favour owed, a new contact - recorded the moment it
        happens in the fiction, not guessed at from narration later."""
        key = f"{args.subject_type}:{args.subject_id}:{args.object_type}:{args.object_id}"
        current = state.relationships.get(
            key,
            Relationship(
                subject_type=args.subject_type,
                subject_id=args.subject_id,
                object_type=args.object_type,
                object_id=args.object_id,
                kind=args.kind,
            ),
        )
        log = state.log.append(
            "relationship",
            key,
            "relationship_updated",
            {
                "subject_type": args.subject_type,
                "subject_id": args.subject_id,
                "object_type": args.object_type,
                "object_id": args.object_id,
                "kind": args.kind.value,
                "status": args.status,
            },
            self._clock(),
        )
        updated = current.updated(args.kind, args.status, log.events[-1].sequence)
        relationships = {**state.relationships, key: updated}
        return ToolCallResult(
            state=state.model_copy(update={"relationships": relationships, "log": log}),
            result={"kind": updated.kind.value, "status": updated.status},
        )

    def set_session_zero_config(
        self, state: GameState, args: SetSessionZeroConfigArgs
    ) -> ToolCallResult:
        """FR-17: session zero's safety-tool agreements (lines, veils,
        tone) - generic tabletop safety tools, not an SRD mechanic."""
        session_zero = SessionZeroConfig(lines=args.lines, veils=args.veils, tone=args.tone)
        log = state.log.append(
            "session",
            "current",
            "session_zero_configured",
            session_zero.model_dump(mode="json"),
            self._clock(),
        )
        return ToolCallResult(
            state=state.model_copy(update={"session_zero": session_zero, "log": log}),
            result={"acknowledged": True},
        )

    def set_campaign_canon(self, state: GameState, args: SetCampaignCanonArgs) -> ToolCallResult:
        """FR-36: session zero's setting generation - an original city
        sketch (never a core-book setting, C3), the one-time creation of
        canon. `add_canon_fact` is for growing it afterwards, not this."""
        canon = CampaignCanon(
            setting_name=args.setting_name,
            tone=args.tone,
            factions=args.factions,
            locations=args.locations,
        )
        log = state.log.append(
            "canon", args.setting_name, "canon_set", canon.model_dump(mode="json"), self._clock()
        )
        return ToolCallResult(
            state=state.model_copy(update={"canon": canon, "log": log}),
            result={"setting_name": args.setting_name},
        )

    def add_canon_fact(self, state: GameState, args: AddCanonFactArgs) -> ToolCallResult:
        """FR-36: the session-zero-generated setting grows as new facts
        are established during play."""
        if state.canon is None:
            raise EngineError("no campaign canon set for this session")
        canon = state.canon.with_fact(args.fact)
        log = state.log.append(
            "canon",
            state.canon.setting_name,
            "canon_fact_added",
            {"fact": args.fact},
            self._clock(),
        )
        return ToolCallResult(
            state=state.model_copy(update={"canon": canon, "log": log}), result={"fact": args.fact}
        )

    def add_canon_location(self, state: GameState, args: AddCanonLocationArgs) -> ToolCallResult:
        """FR-15: the map (Table view's district map) grows as the fiction
        introduces new locations during play, not just at session zero."""
        if state.canon is None:
            raise EngineError("no campaign canon set for this session")
        canon = state.canon.with_location(args.location)
        log = state.log.append(
            "canon",
            state.canon.setting_name,
            "canon_location_added",
            {"location": args.location},
            self._clock(),
        )
        return ToolCallResult(
            state=state.model_copy(update={"canon": canon, "log": log}),
            result={"location": args.location},
        )

    def invoke_x_card(self, state: GameState, args: InvokeXCardArgs) -> ToolCallResult:
        """FR-17: a safety-tool command that rewinds/redirects the fiction
        without argument - not an SRD mechanic. Logging the event is the
        engine's part; stopping and redirecting the scene is the GM
        agent's (system-prompt-level) responsibility, not something this
        tool decides on the model's behalf."""
        log = state.log.append(
            "session", "current", "x_card_invoked", {"note": args.note}, self._clock()
        )
        return ToolCallResult(
            state=state.model_copy(update={"log": log}), result={"acknowledged": True}
        )


# FR-12: the tool surface exposed to the GM agent - name, argument schema,
# and the ToolExecutor method that handles it. Used both to build
# OpenAI-style tool definitions (via each Args model's model_json_schema())
# and to dispatch a parsed tool call to its handler.
TOOL_SPECS: dict[str, tuple[type[BaseModel], str]] = {
    "roll_action": (RollActionArgs, "Make an action roll for the current character."),
    "roll_fortune": (RollFortuneArgs, "Make a fortune roll for an uncertain outcome."),
    "roll_resistance": (RollResistanceArgs, "Resist a consequence, at a stress cost."),
    "create_clock": (CreateClockArgs, "Create a new progress clock."),
    "tick_clock": (TickClockArgs, "Tick an existing progress clock."),
    "apply_harm": (ApplyHarmArgs, "Record harm on the current character."),
    "mark_stress": (MarkStressArgs, "Mark or clear stress on the current character."),
    "transition_phase": (TransitionPhaseArgs, "Move the campaign to its next phase."),
    "create_score": (CreateScoreArgs, "Start a new score: the target and plan."),
    "update_score": (
        UpdateScoreArgs,
        "Record a score's engagement result, payoff, heat gained, or entanglement.",
    ),
    "create_npc": (CreateNpcArgs, "Introduce a new NPC as campaign canon."),
    "create_character": (
        CreateCharacterArgs,
        "Add a new PC to the crew - a crewmate joining the session.",
    ),
    "update_faction_status": (
        UpdateFactionStatusArgs,
        "Change the crew's status with a faction (-3 to +3).",
    ),
    "update_relationship": (
        UpdateRelationshipArgs,
        "Record or change a relationship between two entities (ally, rival, debt, "
        "romance, vendetta).",
    ),
    "add_canon_fact": (AddCanonFactArgs, "Record a new established fact about the setting."),
    "add_canon_location": (
        AddCanonLocationArgs,
        "Add a newly-introduced location to the setting's map.",
    ),
    "invoke_x_card": (InvokeXCardArgs, "Safety tool: stop and redirect the current scene."),
    "set_session_zero_config": (
        SetSessionZeroConfigArgs,
        "Session zero: record agreed lines, veils, and tone before play starts.",
    ),
    "set_campaign_canon": (
        SetCampaignCanonArgs,
        "Session zero: create the original campaign setting (never a core-book setting).",
    ),
    "roll_engagement": (
        RollEngagementArgs,
        "Roll the engagement roll that sets the crew's starting position for a score.",
    ),
    "resolve_payoff": (ResolvePayoffArgs, "Resolve the score's payoff: rep and coin earned."),
    "add_crew_heat": (AddCrewHeatArgs, "Add (or clear) heat on the crew."),
    "adjust_wanted_level": (
        AdjustWantedLevelArgs,
        "Directly raise or lower the crew's wanted level (e.g. incarceration).",
    ),
    "adjust_crew_rep": (
        AdjustCrewRepArgs,
        "Add rep to the crew, outside of a score's payoff.",
    ),
    "adjust_crew_coin": (AdjustCrewCoinArgs, "Add or spend the crew's own coin."),
    "roll_entanglement": (
        RollEntanglementArgs,
        "Roll for an entanglement from the crew's current wanted level and heat.",
    ),
    "acquire_asset": (
        AcquireAssetArgs,
        "Downtime: acquire an asset, quality set by the crew's Tier.",
    ),
    "indulge_vice": (
        IndulgeViceArgs,
        "Downtime: indulge a PC's vice to clear stress, at the risk of overindulging.",
    ),
    "craft": (
        CraftArgs,
        "Downtime: Tinker to craft or modify an item; quality is set by the roll.",
    ),
    "reduce_heat": (ReduceHeatArgs, "Downtime: roll to reduce the crew's heat."),
    "recover": (RecoverArgs, "Downtime: tick a PC's healing clock; heals harm once it fills."),
    "long_term_project": (LongTermProjectArgs, "Downtime: work a long-term project's clock."),
    "flashback": (FlashbackArgs, "Take a flashback at a GM-set stress cost."),
    "mark_xp": (MarkXpArgs, "Downtime: train - mark 1 xp in an attribute or the playbook."),
    "advance_action_rating": (
        AdvanceActionRatingArgs,
        "Advance a PC's action rating once its attribute xp track is full.",
    ),
    "advance_special_ability": (
        AdvanceSpecialAbilityArgs,
        "Grant a PC a new special ability once their playbook xp track is full.",
    ),
    "advance_crew_special_ability": (
        AdvanceCrewSpecialAbilityArgs,
        "Grant the crew a new special ability once their xp track is full.",
    ),
    "advance_crew_upgrades": (
        AdvanceCrewUpgradesArgs,
        "Mark two crew upgrade boxes once the crew's xp track is full.",
    ),
}


def tool_definitions() -> list[dict]:
    """OpenAI-compatible `tools` payload (ADR-0001) for every tool in
    TOOL_SPECS."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": args_model.model_json_schema(),
            },
        }
        for name, (args_model, description) in TOOL_SPECS.items()
    ]


# FR-28/FR-29: engine operations the web UI (sheet panel, table view)
# calls directly - stress, harm, XP, coin, load, and clock ticks.
# Deliberately separate from TOOL_SPECS: CLAUDE.md's "the engine
# adjudicates, the model narrates" splits the AI's tool surface from the
# UI's own engine-operation calls, so none of this is in tool_definitions()
# for the LLM to invoke on the player's behalf, except where the SRD gives
# the GM a hand in it too: mark_stress/apply_harm/tick_clock/mark_xp (the
# TRAIN downtime activity) are shared with TOOL_SPECS - the same
# ToolExecutor method, reachable from either surface. add_crew_heat/
# adjust_wanted_level/adjust_crew_rep/adjust_crew_coin are the crew-sheet
# equivalent of adjust_coin - direct bookkeeping a player can tick on the
# crew half of the sheet, same shared-method shape.
SHEET_OPERATIONS: dict[str, type[BaseModel]] = {
    "mark_stress": MarkStressArgs,
    "apply_harm": ApplyHarmArgs,
    "heal_character": HealCharacterArgs,
    "mark_xp": MarkXpArgs,
    "adjust_coin": AdjustCoinArgs,
    "set_item_carried": SetItemCarriedArgs,
    "tick_clock": TickClockArgs,
    "add_crew_heat": AddCrewHeatArgs,
    "adjust_wanted_level": AdjustWantedLevelArgs,
    "adjust_crew_rep": AdjustCrewRepArgs,
    "adjust_crew_coin": AdjustCrewCoinArgs,
}
