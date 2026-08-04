from pydantic import BaseModel

from engine.character import LOAD_LIMITS, MAX_STASH, Attribute, Character, LoadLevel
from engine.consequences import TRAUMA_CONDITIONS
from engine.crew import Claim, Crew
from engine.crew_mechanics import MAX_WANTED_LEVEL, Hold
from engine.errors import EngineError


class InvalidTraumaConditionError(EngineError):
    """Raised when marking a trauma condition the SRD doesn't define."""


class InvalidArmorTypeError(EngineError):
    """Raised when using an armor box the SRD doesn't define."""


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


ARMOR_TYPES = ("standard", "heavy", "special")


def use_armor(character: Character, armor_type: str) -> Character:
    """SRD: "Armor" - "you can mark an armor box to reduce or avoid a
    consequence, instead of rolling to resist". `ArmorTrack` itself refuses
    a box that's unavailable or already marked."""
    if armor_type == "standard":
        armor = character.armor.use_armor()
    elif armor_type == "heavy":
        armor = character.armor.use_heavy_armor()
    elif armor_type == "special":
        armor = character.armor.use_special_armor()
    else:
        raise InvalidArmorTypeError(f"{armor_type!r} is not an SRD armor box")
    return character.model_copy(update={"armor": armor})


def restore_armor(character: Character) -> Character:
    """SRD: "Armor" - "All of your armor is restored when you choose your
    load for the next score"."""
    return character.model_copy(update={"armor": character.armor.restored()})


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
    if new_coin > 4:
        raise EngineError(
            f"character {character.name!r} can hold at most 4 coin; spend or stash the excess"
        )
    return character.model_copy(update={"coin": new_coin})


def adjust_stash(character: Character, amount: int) -> Character:
    """SRD: "Stash & Retirement" - stash is the retirement fund; the
    tracker tops out at 40. Refuses removing stash the character doesn't
    have (the 2-stash-for-1-coin conversion is the caller pairing this
    with `adjust_coin`, not a separate operation); gains clamp at the
    tracker's cap the same way rep and xp tracks do."""
    new_stash = character.stash + amount
    if new_stash < 0:
        raise EngineError(
            f"character {character.name!r} has {character.stash} stash, cannot remove {-amount}"
        )
    return character.model_copy(update={"stash": min(MAX_STASH, new_stash)})


def cash_out_stash(character: Character, stash_amount: int) -> Character:
    """SRD: "Removing coin from your stash" - remove two stash for each
    coin taken as cash. The conversion is deliberately atomic and refuses
    odd amounts or a coin-capacity overflow."""
    if stash_amount <= 0 or stash_amount % 2:
        raise EngineError("stash cash-out must remove a positive even amount")
    updated = adjust_stash(character, -stash_amount)
    return adjust_coin(updated, stash_amount // 2)


def set_load_level(character: Character, level: LoadLevel) -> Character:
    """SRD: "Loadout" - "For each operation, decide what your character's
    load will be." Refuses a level whose cap the currently carried items
    already exceed, rather than silently dropping items."""
    limit = LOAD_LIMITS[level]
    if character.load > limit:
        raise EngineError(
            f"character {character.name!r} carries {character.load} items, "
            f"over the {level.value} limit of {limit}"
        )
    return character.model_copy(update={"load_level": level})


def set_item_carried(character: Character, item_id: str, carried: bool) -> Character:
    """SRD: "Loadout" - checking an item's box selects it for the current
    load; load is the count of currently carried items, capped by the
    declared load level ("up to a number of items equal to your chosen
    load"). Refuses an unknown item id, or carrying past the cap, rather
    than silently ignoring or clamping."""
    if not any(item.item_id == item_id for item in character.items):
        raise EngineError(f"character {character.name!r} has no item {item_id!r}")
    items = [
        item.model_copy(update={"carried": carried}) if item.item_id == item_id else item
        for item in character.items
    ]
    load = sum(1 for item in items if item.carried)
    limit = LOAD_LIMITS[character.load_level]
    if load > limit:
        raise EngineError(
            f"character {character.name!r} is at their {character.load_level.value} "
            f"load limit of {limit}"
        )
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
    if new_coin > crew.coin_capacity:
        raise EngineError(
            f"crew {crew.name!r} can hold at most {crew.coin_capacity} coin in its vault"
        )
    return crew.model_copy(update={"coin": new_coin})


def mark_crew_xp(crew: Crew, amount: int) -> Crew:
    """SRD: "Crew Advancement" - the crew-xp equivalent of a character's
    own `mark_playbook_xp`; `XpTrack.mark` clamps to [0, segments]."""
    return crew.model_copy(update={"xp": crew.xp.mark(amount)})


def adjust_crew_turf(crew: Crew, amount: int) -> Crew:
    """SRD: "Turf" - "Each piece of turf you hold reduces the rep cost to
    develop by one... You can hold a maximum of 6 turf." For turf gained
    or lost outside the claim map; a claim marked `is_turf` manages its
    own turf mark through `set_claim_controlled` instead."""
    return crew.model_copy(update={"rep": crew.rep.add_turf(amount)})


def set_claim_controlled(
    crew: Crew,
    claim_id: str,
    controlled: bool,
    name: str | None = None,
    is_turf: bool = False,
) -> Crew:
    """SRD: "Seizing a claim" / "Losing a claim" - seizing marks the claim
    controlled (and its turf mark, if it's turf); losing it clears both.
    An unknown claim id is refused unless a `name` is supplied - the SRD
    lets a crew "seek out a special claim not on your map", so a named
    new claim is added rather than guessed at."""
    existing = next((claim for claim in crew.claims if claim.id == claim_id), None)
    if existing is None:
        if name is None:
            raise EngineError(f"crew {crew.name!r} has no claim {claim_id!r}")
        claim = Claim(id=claim_id, name=name, controlled=controlled, is_turf=is_turf)
        claims = [*crew.claims, claim]
    else:
        if existing.controlled == controlled:
            raise EngineError(
                f"claim {claim_id!r} is already {'controlled' if controlled else 'uncontrolled'}"
            )
        claim = existing.model_copy(update={"controlled": controlled})
        claims = [claim if c.id == claim_id else c for c in crew.claims]

    # SRD: "Turf" - turf marks track controlled turf claims; seizing adds
    # a mark, losing one removes it (a new claim recorded as uncontrolled
    # changes nothing yet).
    rep = crew.rep
    if claim.is_turf:
        if controlled:
            rep = rep.add_turf(1)
        elif existing is not None:
            rep = rep.add_turf(-1)
    return crew.model_copy(update={"claims": claims, "rep": rep})


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
