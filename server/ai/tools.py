import random
from collections.abc import Callable
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from engine.campaign import CampaignCanon, SessionZeroConfig
from engine.character import Action, Attribute, Character
from engine.clocks import Clock, ClockKind
from engine.crew import Crew
from engine.entities import Npc
from engine.errors import EngineError
from engine.events import EventLog
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
from engine.rolls import Effect, Position, action_roll, fortune_roll, resistance_roll
from engine.session import CampaignPhase, Session


class GameState(BaseModel):
    """Everything one tool call can read or change, for a single-PC MVP
    session (FR-25: "solo play is the whole crew under one seat" - one
    character for now; multi-PC control is a later Phase 4/7 concern)."""

    character: Character
    crew: Crew
    session: Session
    canon: CampaignCanon | None = None
    session_zero: SessionZeroConfig | None = None
    clocks: dict[str, Clock] = Field(default_factory=dict)
    npcs: dict[str, Npc] = Field(default_factory=dict)
    faction_statuses: dict[str, FactionStatus] = Field(
        default_factory=dict, description="Keyed by faction_id"
    )
    relationships: dict[str, Relationship] = Field(
        default_factory=dict,
        description="Keyed by '<subject_type>:<subject_id>:<object_type>:<object_id>'",
    )
    log: EventLog = Field(default_factory=EventLog)


class ToolCallResult(BaseModel):
    state: GameState
    result: dict


class RollActionArgs(BaseModel):
    action: Action
    position: Position
    effect: Effect = Field(
        ..., description="limited, standard, great, zero, or extreme (name or Effect's int value)"
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


class RollFortuneArgs(BaseModel):
    pool_size: int = Field(..., description="Dice pool for the trait being assessed")


class RollResistanceArgs(BaseModel):
    attribute: Attribute


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


class MarkStressArgs(BaseModel):
    amount: int = Field(..., description="Positive to mark, negative to clear")


class TransitionPhaseArgs(BaseModel):
    phase: CampaignPhase


class CreateNpcArgs(BaseModel):
    npc_id: str
    name: str
    tags: list[str] = Field(default_factory=list)
    faction_id: str | None = None


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
    """SRD: "Recover" - no fields; healing one level of harm needs no
    further input from whoever clicks it."""


class MarkXpArgs(BaseModel):
    track: Literal["playbook", "insight", "prowess", "resolve"]
    amount: int = Field(..., description="Positive to mark, negative to clear")


class AdjustCoinArgs(BaseModel):
    amount: int = Field(..., description="Positive to gain, negative to spend")


class SetItemCarriedArgs(BaseModel):
    item_id: str
    carried: bool


class ToolExecutor:
    """Executes GM-agent tool calls against a `GameState` (FR-12): the AI
    never edits state directly, only through these methods. Holds the
    injected RNG and clock so no method call needs to pass them - the same
    "no datetime.now()/random() inside deterministic logic" rule the engine
    follows (CLAUDE.md), applied one layer up."""

    def __init__(self, rng: random.Random, clock: Callable[[], datetime]):
        self._rng = rng
        self._clock = clock

    def log_event(
        self, state: GameState, entity_type: str, entity_id: str, event_type: str, payload: dict
    ) -> GameState:
        """FR-31: lets the GM agent record player input and narration as
        structured events too, not just mechanical tool calls - the
        journal, and FR-18's resume recap, need the whole turn, not just
        its dice."""
        log = state.log.append(entity_type, entity_id, event_type, payload, self._clock())
        return state.model_copy(update={"log": log})

    def roll_action(
        self,
        state: GameState,
        args: RollActionArgs,
        bonus_dice: int = 0,
        devils_bargain: str | None = None,
    ) -> ToolCallResult:
        """SRD: "Action Roll". `bonus_dice`/`devils_bargain` are Python-only
        parameters, not fields on `RollActionArgs` - they come from the
        player's post-negotiation `RollDecision` (FR-16), applied by the GM
        agent's `_resolve_roll` before this call, never from the LLM's own
        tool-call arguments (`tool_definitions()` only ever introspects
        `RollActionArgs`, so the model never sees these as choices it makes)."""
        pool_size = state.character.action_ratings.get(args.action, 0) + bonus_dice
        roll = action_roll(pool_size, args.position, args.effect, self._rng)
        payload = {
            "action": args.action.value,
            "bonus_dice": bonus_dice,
            **roll.model_dump(mode="json"),
        }
        if devils_bargain:
            payload["devils_bargain"] = devils_bargain
        log = state.log.append(
            "character", state.character.name, "action_roll", payload, self._clock()
        )
        return ToolCallResult(
            state=state.model_copy(update={"log": log}), result=roll.model_dump(mode="json")
        )

    def roll_fortune(self, state: GameState, args: RollFortuneArgs) -> ToolCallResult:
        """SRD: "Fortune Roll"."""
        roll = fortune_roll(args.pool_size, self._rng)
        log = state.log.append(
            "character",
            state.character.name,
            "fortune_roll",
            roll.model_dump(mode="json"),
            self._clock(),
        )
        return ToolCallResult(
            state=state.model_copy(update={"log": log}), result=roll.model_dump(mode="json")
        )

    def roll_resistance(self, state: GameState, args: RollResistanceArgs) -> ToolCallResult:
        """SRD: "Resistance and Armor"."""
        rating = state.character.attribute_rating(args.attribute)
        roll = resistance_roll(rating, self._rng)
        log = state.log.append(
            "character",
            state.character.name,
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
        mutation = mark_harm(state.character, args.level, args.name)
        log = state.log.append(
            "character",
            state.character.name,
            "harm_marked",
            {"level": args.level, "name": args.name, "catastrophic": mutation.catastrophic_harm},
            self._clock(),
        )
        state = state.model_copy(update={"character": mutation.character, "log": log})
        return ToolCallResult(state=state, result={"catastrophic": mutation.catastrophic_harm})

    def mark_stress(self, state: GameState, args: MarkStressArgs) -> ToolCallResult:
        mutation = mark_stress(state.character, args.amount)
        log = state.log.append(
            "character",
            state.character.name,
            "stress_marked",
            {"amount": args.amount, "triggered_trauma": mutation.triggered_trauma},
            self._clock(),
        )
        state = state.model_copy(update={"character": mutation.character, "log": log})
        return ToolCallResult(state=state, result={"triggered_trauma": mutation.triggered_trauma})

    def heal_character(self, state: GameState, args: HealCharacterArgs) -> ToolCallResult:
        """SRD: "Recover". Part of `SHEET_OPERATIONS` (FR-28), not
        `TOOL_SPECS`: the player heals directly, the GM/model doesn't call
        this on their behalf."""
        character = heal_character(state.character)
        log = state.log.append("character", state.character.name, "harm_healed", {}, self._clock())
        return ToolCallResult(
            state=state.model_copy(update={"character": character, "log": log}), result={}
        )

    def mark_xp(self, state: GameState, args: MarkXpArgs) -> ToolCallResult:
        """SRD: "PC Advancement". `SHEET_OPERATIONS` only (FR-28) - marking
        xp is the player's own bookkeeping, not a GM/model tool call."""
        if args.track == "playbook":
            character = mark_playbook_xp(state.character, args.amount)
        else:
            character = mark_attribute_xp(state.character, Attribute(args.track), args.amount)
        log = state.log.append(
            "character",
            state.character.name,
            "xp_marked",
            {"track": args.track, "amount": args.amount},
            self._clock(),
        )
        return ToolCallResult(
            state=state.model_copy(update={"character": character, "log": log}),
            result={"track": args.track},
        )

    def adjust_coin(self, state: GameState, args: AdjustCoinArgs) -> ToolCallResult:
        """SRD: "Coin and Stash". `SHEET_OPERATIONS` only (FR-28)."""
        character = adjust_coin(state.character, args.amount)
        log = state.log.append(
            "character",
            state.character.name,
            "coin_adjusted",
            {"amount": args.amount},
            self._clock(),
        )
        return ToolCallResult(
            state=state.model_copy(update={"character": character, "log": log}),
            result={"coin": character.coin},
        )

    def set_item_carried(self, state: GameState, args: SetItemCarriedArgs) -> ToolCallResult:
        """SRD: "Loadout". `SHEET_OPERATIONS` only (FR-28) - toggling
        carried items is the player choosing their loadout, not a GM call."""
        character = set_item_carried(state.character, args.item_id, args.carried)
        log = state.log.append(
            "character",
            state.character.name,
            "item_carried_set",
            {"item_id": args.item_id, "carried": args.carried},
            self._clock(),
        )
        return ToolCallResult(
            state=state.model_copy(update={"character": character, "log": log}),
            result={"load": character.load},
        )

    def transition_phase(self, state: GameState, args: TransitionPhaseArgs) -> ToolCallResult:
        """SRD: "The Game Structure"."""
        session = state.session.transition_to(args.phase)
        log = state.log.append(
            "session", "current", "phase_transitioned", {"phase": args.phase.value}, self._clock()
        )
        state = state.model_copy(update={"session": session, "log": log})
        return ToolCallResult(state=state, result={"phase": args.phase.value})

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
            raise ValueError("no campaign canon set for this session")
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
            raise ValueError("no campaign canon set for this session")
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
    "create_npc": (CreateNpcArgs, "Introduce a new NPC as campaign canon."),
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
# for the LLM to invoke on the player's behalf. mark_stress/apply_harm/
# tick_clock are shared with TOOL_SPECS - the same ToolExecutor method,
# reachable from either surface.
SHEET_OPERATIONS: dict[str, type[BaseModel]] = {
    "mark_stress": MarkStressArgs,
    "apply_harm": ApplyHarmArgs,
    "heal_character": HealCharacterArgs,
    "mark_xp": MarkXpArgs,
    "adjust_coin": AdjustCoinArgs,
    "set_item_carried": SetItemCarriedArgs,
    "tick_clock": TickClockArgs,
}
