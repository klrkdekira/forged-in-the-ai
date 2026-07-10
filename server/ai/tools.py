import random
from collections.abc import Callable
from datetime import datetime

from pydantic import BaseModel, Field

from engine.character import Action, Attribute, Character
from engine.clocks import Clock, ClockKind
from engine.crew import Crew
from engine.entities import Npc
from engine.events import EventLog
from engine.operations import mark_harm, mark_stress
from engine.relationships import FactionStatus
from engine.rolls import Effect, Position, action_roll, fortune_roll, resistance_roll
from engine.session import CampaignPhase, Session


class GameState(BaseModel):
    """Everything one tool call can read or change, for a single-PC MVP
    session (FR-25: "solo play is the whole crew under one seat" - one
    character for now; multi-PC control is a later Phase 4/7 concern)."""

    character: Character
    crew: Crew
    session: Session
    clocks: dict[str, Clock] = Field(default_factory=dict)
    npcs: dict[str, Npc] = Field(default_factory=dict)
    faction_statuses: dict[str, FactionStatus] = Field(
        default_factory=dict, description="Keyed by faction_id"
    )
    log: EventLog = Field(default_factory=EventLog)


class ToolCallResult(BaseModel):
    state: GameState
    result: dict


class RollActionArgs(BaseModel):
    action: Action
    position: Position
    effect: Effect


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


class ToolExecutor:
    """Executes GM-agent tool calls against a `GameState` (FR-12): the AI
    never edits state directly, only through these methods. Holds the
    injected RNG and clock so no method call needs to pass them - the same
    "no datetime.now()/random() inside deterministic logic" rule the engine
    follows (CLAUDE.md), applied one layer up."""

    def __init__(self, rng: random.Random, clock: Callable[[], datetime]):
        self._rng = rng
        self._clock = clock

    def roll_action(self, state: GameState, args: RollActionArgs) -> ToolCallResult:
        """SRD: "Action Roll"."""
        pool_size = state.character.action_ratings.get(args.action, 0)
        roll = action_roll(pool_size, args.position, args.effect, self._rng)
        log = state.log.append(
            "character",
            state.character.name,
            "action_roll",
            {"action": args.action.value, **roll.model_dump(mode="json")},
            self._clock(),
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
