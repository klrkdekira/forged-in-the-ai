from pydantic import BaseModel

from engine.character import Character
from engine.consequences import TRAUMA_CONDITIONS
from engine.crew import Crew
from engine.crew_mechanics import Hold
from engine.errors import EngineError


class InvalidTraumaConditionError(EngineError):
    """Raised when marking a trauma condition the SRD doesn't define."""


class CharacterMutation(BaseModel):
    character: Character
    triggered_trauma: bool = False
    catastrophic_harm: bool = False


def mark_stress(character: Character, amount: int) -> CharacterMutation:
    """FR-10: the engine is the only writer of a character's stress track."""
    result = character.stress.mark(amount)
    return CharacterMutation(
        character=character.model_copy(update={"stress": result.track}),
        triggered_trauma=result.triggered_trauma,
    )


def mark_trauma(character: Character, condition: str) -> Character:
    """The engine refuses a condition the SRD doesn't define rather than
    guessing one (CLAUDE.md); which condition to circle is a player choice
    made outside the engine."""
    if condition not in TRAUMA_CONDITIONS:
        raise InvalidTraumaConditionError(f"{condition!r} is not an SRD trauma condition")
    return character.model_copy(update={"trauma": character.trauma.add(condition)})


def mark_harm(character: Character, level: int, name: str) -> CharacterMutation:
    result = character.harm.mark(level, name)
    return CharacterMutation(
        character=character.model_copy(update={"harm": result.track}),
        catastrophic_harm=result.catastrophic,
    )


def heal_character(character: Character) -> Character:
    """SRD: "Recover" - applied when a healing clock fills."""
    return character.model_copy(update={"harm": character.harm.heal_one_level()})


def flashback(character: Character, stress_cost: int) -> CharacterMutation:
    """SRD: "Flashbacks" - the GM sets a stress cost (0, 1, 2, or more)
    for a flashback action; paying it is the same operation as any other
    stress mark. A downtime-flavoured flashback pays 1 coin or 1 rep
    instead - spend those directly, there's no separate operation for it."""
    return mark_stress(character, stress_cost)


class CrewMutation(BaseModel):
    crew: Crew
    wanted_level_increased: bool = False


def add_heat(crew: Crew, amount: int) -> CrewMutation:
    """FR-10: the engine is the only writer of a crew's heat/wanted level."""
    result = crew.heat.add(amount)
    crew = crew.model_copy(update={"heat": result.track})
    if result.wanted_level_increased:
        crew = crew.model_copy(update={"wanted_level": min(4, crew.wanted_level + 1)})
    return CrewMutation(crew=crew, wanted_level_increased=result.wanted_level_increased)


def develop_crew(crew: Crew) -> Crew:
    """SRD: "Development" - weak hold becomes strong; strong hold instead
    pays coin (new Tier x 8) to raise Tier. Either way rep resets to zero,
    keeping turf marks. Refuses rather than guessing if the crew hasn't
    reached its rep threshold, or can't afford the Tier cost."""
    if not crew.rep.ready_to_develop:
        raise EngineError(f"crew {crew.name!r} has not reached its rep threshold")

    if crew.hold is Hold.WEAK:
        return crew.model_copy(update={"hold": Hold.STRONG, "rep": crew.rep.developed()})

    new_tier = crew.tier + 1
    cost = new_tier * 8
    if crew.coin < cost:
        raise EngineError(f"crew {crew.name!r} has {crew.coin} coin, needs {cost} to advance Tier")
    return crew.model_copy(
        update={
            "tier": new_tier,
            "hold": Hold.WEAK,
            "coin": crew.coin - cost,
            "rep": crew.rep.developed(),
        }
    )
