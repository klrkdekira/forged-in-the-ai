from engine.character import ATTRIBUTE_ACTIONS, Action, Attribute, Character
from engine.crew import Crew
from engine.errors import EngineError

# SRD: "PC Advancement" - "action ratings may advance up to 3. When you
# unlock the Mastery advance for your crew, you can advance actions up to
# rating 4." The engine doesn't check for the Mastery upgrade itself
# (that's cross-entity, a caller concern); pass cap=4 once it's confirmed.
POST_CREATION_ACTION_CAP = 3


class AdvancementError(EngineError):
    """Raised when advancing a track that isn't full, or an action rating
    already at its cap."""


def xp_attribute_for_action(action: Action) -> Attribute:
    return next(attr for attr, actions in ATTRIBUTE_ACTIONS.items() if action in actions)


def earns_desperate_roll_xp(is_desperate: bool) -> bool:
    """SRD: "PC Advancement" - "When you make a desperate action roll, mark
    1 xp in the attribute for the action you rolled."""
    return is_desperate


def advance_action_rating(
    character: Character, action: Action, cap: int = POST_CREATION_ACTION_CAP
) -> Character:
    """SRD: "PC Advancement" - filling an attribute's xp track adds a dot
    to one of its actions."""
    attribute = xp_attribute_for_action(action)
    track = character.attribute_xp[attribute]
    if not track.is_full:
        raise AdvancementError(f"{attribute.value} xp track is not full")

    current = character.action_ratings.get(action, 0)
    if current >= cap:
        raise AdvancementError(f"{action.value} is already at its cap of {cap}")

    return character.model_copy(
        update={
            "action_ratings": {**character.action_ratings, action: current + 1},
            "attribute_xp": {**character.attribute_xp, attribute: track.advanced()},
        }
    )


def advance_special_ability(character: Character, ability_id: str) -> Character:
    """SRD: "PC Advancement" - filling the playbook xp track grants a new
    special ability."""
    if not character.playbook_xp.is_full:
        raise AdvancementError("playbook xp track is not full")
    if ability_id in character.special_ability_ids:
        raise AdvancementError(f"{ability_id!r} is already known")

    return character.model_copy(
        update={
            "special_ability_ids": [*character.special_ability_ids, ability_id],
            "playbook_xp": character.playbook_xp.advanced(),
        }
    )


def crew_profit_share(crew_tier: int) -> int:
    """SRD: "Profits" - "each PC gets stash equal to the crew Tier+2"."""
    return crew_tier + 2


def advance_crew_special_ability(crew: Crew, ability_id: str) -> Crew:
    """SRD: "Crew Advancement" - filling the crew xp tracker grants a new
    special ability, or two crew upgrade boxes (`advance_crew_upgrades`)."""
    if not crew.xp.is_full:
        raise AdvancementError("crew xp track is not full")
    if ability_id in crew.special_ability_ids:
        raise AdvancementError(f"{ability_id!r} is already known")

    return crew.model_copy(
        update={
            "special_ability_ids": [*crew.special_ability_ids, ability_id],
            "xp": crew.xp.advanced(),
        }
    )


def advance_crew_upgrades(crew: Crew, upgrade_ids: tuple[str, str]) -> Crew:
    """SRD: "Crew Advancement" - the crew-xp alternative to a new special
    ability: "mark two crew upgrade boxes"."""
    if not crew.xp.is_full:
        raise AdvancementError("crew xp track is not full")

    return crew.model_copy(
        update={
            "upgrade_ids": [*crew.upgrade_ids, *upgrade_ids],
            "xp": crew.xp.advanced(),
        }
    )
