from pydantic import BaseModel

from engine.character import Attribute, Character
from engine.consequences import TRAUMA_CONDITIONS
from engine.crew import Crew
from engine.crew_mechanics import MAX_WANTED_LEVEL, Hold
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


def mark_playbook_xp(character: Character, amount: int) -> Character:
    """SRD: "PC Advancement" - marking the playbook xp track (FR-28's
    clickable sheet boxes); `XpTrack.mark` clamps to [0, segments]."""
    return character.model_copy(update={"playbook_xp": character.playbook_xp.mark(amount)})


def mark_attribute_xp(character: Character, attribute: Attribute, amount: int) -> Character:
    """SRD: "PC Advancement" - marking one of the three attribute xp tracks."""
    tracks = {**character.attribute_xp, attribute: character.attribute_xp[attribute].mark(amount)}
    return character.model_copy(update={"attribute_xp": tracks})


def adjust_coin(character: Character, amount: int) -> Character:
    """SRD: "Coin and Stash" - spend (negative) or gain (positive) coin;
    refuses rather than letting a character spend coin they don't have."""
    new_coin = character.coin + amount
    if new_coin < 0:
        raise EngineError(
            f"character {character.name!r} has {character.coin} coin, cannot spend {-amount}"
        )
    return character.model_copy(update={"coin": new_coin})


def set_item_carried(character: Character, item_id: str, carried: bool) -> Character:
    """SRD: "Loadout" - checking an item's box selects it for the current
    load; load is the count of currently carried items. Refuses an
    unknown item id rather than silently ignoring it."""
    if not any(item.item_id == item_id for item in character.items):
        raise EngineError(f"character {character.name!r} has no item {item_id!r}")
    items = [
        item.model_copy(update={"carried": carried}) if item.item_id == item_id else item
        for item in character.items
    ]
    load = sum(1 for item in items if item.carried)
    return character.model_copy(update={"items": items, "load": load})


class CrewMutation(BaseModel):
    crew: Crew
    wanted_level_increased: bool = False


def add_heat(crew: Crew, amount: int) -> CrewMutation:
    """FR-10: the engine is the only writer of a crew's heat/wanted level."""
    result = crew.heat.add(amount)
    crew = crew.model_copy(update={"heat": result.track})
    if result.wanted_level_increased:
        crew = crew.model_copy(
            update={"wanted_level": min(MAX_WANTED_LEVEL, crew.wanted_level + 1)}
        )
    return CrewMutation(crew=crew, wanted_level_increased=result.wanted_level_increased)


def adjust_wanted_level(crew: Crew, amount: int) -> Crew:
    """SRD: "Heat & Wanted Level" - direct adjustment, clamped to [0, 4]
    (e.g. incarceration reducing it by 1, outside of heat overflow)."""
    new_level = max(0, min(MAX_WANTED_LEVEL, crew.wanted_level + amount))
    return crew.model_copy(update={"wanted_level": new_level})


def adjust_crew_rep(crew: Crew, amount: int) -> Crew:
    """SRD: "Development" - rep gained outside of a score's payoff (e.g. a
    GM-awarded bonus); `RepTrack.add_rep` clamps to [0, threshold]."""
    return crew.model_copy(update={"rep": crew.rep.add_rep(amount)})


def adjust_crew_coin(crew: Crew, amount: int) -> Crew:
    """SRD: "Coin and Stash" - the crew's own coin, spent on crew upgrades
    and assets; refuses rather than letting the crew spend coin they
    don't have, same as a character's own `adjust_coin`."""
    new_coin = crew.coin + amount
    if new_coin < 0:
        raise EngineError(f"crew {crew.name!r} has {crew.coin} coin, cannot spend {-amount}")
    return crew.model_copy(update={"coin": new_coin})


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
