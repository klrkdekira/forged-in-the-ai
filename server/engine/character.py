from enum import StrEnum

from pydantic import BaseModel, Field

from engine.consequences import ArmorTrack, HarmTrack, StressTrack, TraumaTrack


class Attribute(StrEnum):
    """SRD: "Attribute Ratings" - Insight, Prowess, Resolve."""

    INSIGHT = "insight"
    PROWESS = "prowess"
    RESOLVE = "resolve"


class Action(StrEnum):
    """SRD: "Action Ratings" - the 12 actions, grouped under an attribute."""

    HUNT = "hunt"
    STUDY = "study"
    SURVEY = "survey"
    TINKER = "tinker"
    FINESSE = "finesse"
    PROWL = "prowl"
    SKIRMISH = "skirmish"
    WRECK = "wreck"
    ATTUNE = "attune"
    COMMAND = "command"
    CONSORT = "consort"
    SWAY = "sway"


# SRD: "EXAMPLE ACTION & ATTRIBUTE RATINGS" - each attribute's four actions.
ATTRIBUTE_ACTIONS: dict[Attribute, tuple[Action, ...]] = {
    Attribute.INSIGHT: (Action.HUNT, Action.STUDY, Action.SURVEY, Action.TINKER),
    Attribute.PROWESS: (Action.FINESSE, Action.PROWL, Action.SKIRMISH, Action.WRECK),
    Attribute.RESOLVE: (Action.ATTUNE, Action.COMMAND, Action.CONSORT, Action.SWAY),
}


def attribute_rating(action_ratings: dict[Action, int], attribute: Attribute) -> int:
    """SRD: "Attribute Ratings" - "equal to the number of dots in the first
    column under that attribute", i.e. how many of its four actions have at
    least one dot, not the sum of their ratings."""
    return sum(1 for action in ATTRIBUTE_ACTIONS[attribute] if action_ratings.get(action, 0) >= 1)


class XpTrack(BaseModel):
    """SRD: "Advancement" - playbook and attribute xp tracks; FR-5's
    trigger detection is Phase 3 scope, this is just the counter."""

    marked: int = 0
    segments: int = 8

    @property
    def is_full(self) -> bool:
        return self.marked >= self.segments

    def mark(self, amount: int = 1) -> "XpTrack":
        return self.model_copy(update={"marked": max(0, min(self.segments, self.marked + amount))})

    def advanced(self) -> "XpTrack":
        return self.model_copy(update={"marked": 0})


class CharacterItem(BaseModel):
    item_id: str
    carried: bool = Field(default=False, description="Selected in the current load")


class Character(BaseModel):
    """FR-7: field-for-field with the official sheet. `playbook` and
    `special_ability_ids` are references (a name, and ids into the SRD/pack
    ability bank) - never an assembled playbook's specific dots/friends/
    items, which is core-book content (NOTICE.md) when it's a real BitD
    playbook; this schema only holds a specific player's own character."""

    name: str
    alias: str | None = None
    look: str | None = None
    heritage: str | None = None
    heritage_detail: str | None = None
    background: str | None = None
    background_detail: str | None = None

    playbook: str
    action_ratings: dict[Action, int] = Field(default_factory=dict)
    special_ability_ids: list[str] = Field(default_factory=list)

    stress: StressTrack = Field(default_factory=StressTrack)
    trauma: TraumaTrack = Field(default_factory=TraumaTrack)
    harm: HarmTrack = Field(default_factory=HarmTrack)
    armor: ArmorTrack = Field(default_factory=ArmorTrack)

    vice: str | None = None
    vice_detail: str | None = None
    vice_purveyor: str | None = None

    coin: int = 0
    stash: int = 0
    load: int = 0
    items: list[CharacterItem] = Field(default_factory=list)

    friend: str | None = None
    rival: str | None = None

    playbook_xp: XpTrack = Field(default_factory=XpTrack)
    attribute_xp: dict[Attribute, XpTrack] = Field(
        default_factory=lambda: {attribute: XpTrack(segments=6) for attribute in Attribute}
    )

    def attribute_rating(self, attribute: Attribute) -> int:
        return attribute_rating(self.action_ratings, attribute)


def render_markdown(character: Character) -> str:
    """FR-8: human-readable markdown sheet render."""
    lines = [f"# {character.name}" + (f' "{character.alias}"' if character.alias else "")]
    if character.look:
        lines.append(f"*{character.look}*")
    lines.append("")
    lines.append(f"**Playbook**: {character.playbook}")
    if character.heritage:
        lines.append(f"**Heritage**: {character.heritage} - {character.heritage_detail or ''}")
    if character.background:
        lines.append(
            f"**Background**: {character.background} - {character.background_detail or ''}"
        )
    lines.append("")

    lines.append("## Actions")
    for attribute in Attribute:
        rating = character.attribute_rating(attribute)
        lines.append(f"**{attribute.value.title()}** ({rating})")
        for action in ATTRIBUTE_ACTIONS[attribute]:
            lines.append(f"- {action.value.title()}: {character.action_ratings.get(action, 0)}")
    lines.append("")

    lines.append("## Condition")
    lines.append(f"- Stress: {character.stress.marked}/{StressTrack.MAX}")
    lines.append(f"- Trauma: {', '.join(character.trauma.conditions) or 'none'}")
    for entry in character.harm.entries:
        lines.append(f"- Harm (level {entry.level}): {entry.name}")
    lines.append("")

    if character.vice:
        lines.append("## Vice")
        lines.append(f"{character.vice}: {character.vice_detail or ''}")
        if character.vice_purveyor:
            lines.append(f"Purveyor: {character.vice_purveyor}")
        lines.append("")

    lines.append("## Contacts")
    lines.append(f"- Friend: {character.friend or 'none'}")
    lines.append(f"- Rival: {character.rival or 'none'}")

    return "\n".join(lines)
