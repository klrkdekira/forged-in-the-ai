import click

from cli.paths import PACK_PATH, SRD_PATH
from engine.packs import (
    ContentPack,
    CrewUpgrade,
    DowntimeActivity,
    EntanglementEntry,
    HeatPenalty,
    Item,
    MagnitudeLevel,
    PositionRoll,
    Reputation,
    RollResult,
    SpecialAbility,
    SrdSection,
    Trauma,
    Vice,
)


def _heading_level(line):
    """Number of leading '#' if line is a markdown heading, else None."""
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    return len(stripped) - len(stripped.lstrip("#"))


def _heading_text(line):
    return line.strip().lstrip("#").strip()


def _slugify(name):
    return name.lower().replace(" ", "_").replace("'", "")


def _section_index(lines):
    """Every markdown heading in the SRD, in document order (D3 groundwork
    for retrieval/chunking; not a substitute for the Phase 4 FTS5 index)."""
    return [
        SrdSection(heading=_heading_text(line), level=_heading_level(line), line=lineno)
        for lineno, line in enumerate(lines, start=1)
        if _heading_level(line) is not None
    ]


class SrdAbilityParser:
    """Reads special-ability "### Name" entries out of the SRD's playbook
    and crew sections. Bounded by an explicit start/end heading pair rather
    than a heading-level nesting rule: the SRD's markdown conversion has
    stray same-level headings (e.g. "## Fortitude") inside the ability
    list itself, so nesting depth alone can't mark a section's end."""

    # SRD headings "## Special abilities" and "## Crew special abilities"
    # (playbook and crew ability lists), each ending just before the named
    # heading that follows the last ability in that list.
    SECTIONS = (
        ("Special abilities", "Character items"),
        ("Crew special abilities", "The Score"),
    )

    def __init__(self, srd_text):
        self.lines = srd_text.splitlines()

    def parse(self):
        abilities = []
        for start_heading, end_heading in self.SECTIONS:
            for ability in self._parse_section(start_heading, end_heading):
                if not any(a.id == ability.id for a in abilities):
                    abilities.append(ability)
        return abilities

    def _parse_section(self, start_heading, end_heading):
        abilities = []
        name, desc = "", []

        def save():
            if name and desc:
                abilities.append(
                    SpecialAbility(
                        id=_slugify(name),
                        name=name.strip(),
                        description="\n".join(desc).strip(),
                        tags=[],
                    )
                )

        for line in self._section_lines(start_heading, end_heading):
            if line.startswith("### "):
                save()
                name, desc = line[4:].strip(), []
            elif _heading_level(line) is not None:
                save()
                name, desc = "", []
            elif name:
                desc.append(line)
        save()

        return abilities

    def _section_lines(self, start_heading, end_heading):
        """Lines strictly between the two named headings (exclusive)."""
        start = next(
            (
                i + 1
                for i, line in enumerate(self.lines)
                if _heading_level(line) and _heading_text(line) == start_heading
            ),
            None,
        )
        if start is None:
            raise ValueError(f"SRD section heading not found: {start_heading!r}")

        end = next(
            (
                j
                for j in range(start, len(self.lines))
                if _heading_level(self.lines[j]) and _heading_text(self.lines[j]) == end_heading
            ),
            len(self.lines),
        )
        return self.lines[start:end]


def _traumas():
    return [
        Trauma(
            id="cold", name="Cold", description="Not moved by emotional appeals or social bonds."
        ),
        Trauma(
            id="haunted",
            name="Haunted",
            description="Often lost in reverie, reliving past horrors, seeing things.",
        ),
        Trauma(
            id="obsessed",
            name="Obsessed",
            description="Enthralled by one thing: an activity, a person, an ideology.",
        ),
        Trauma(
            id="paranoid",
            name="Paranoid",
            description="Imagine danger everywhere; can't trust others.",
        ),
        Trauma(
            id="reckless",
            name="Reckless",
            description="Little regard for your own safety or best interests.",
        ),
        Trauma(
            id="soft",
            name="Soft",
            description="Lose your edge; become sentimental, passive, gentle.",
        ),
        Trauma(
            id="unstable",
            name="Unstable",
            description=(
                "Emotional state is volatile. Can instantly rage, or fall into "
                "despair, act impulsively, or freeze up."
            ),
        ),
        Trauma(
            id="vicious",
            name="Vicious",
            description="Seek out opportunities to hurt people, even for no good reason.",
        ),
    ]


def _vices():
    return [
        Vice(
            id="faith",
            name="Faith",
            description="Dedicated to an unseen power, forgotten god, ancestor, etc.",
        ),
        Vice(
            id="gambling",
            name="Gambling",
            description="Crave games of chance, betting on sporting events, etc.",
        ),
        Vice(
            id="luxury",
            name="Luxury",
            description="Expensive or ostentatious displays of opulence.",
        ),
        Vice(
            id="obligation",
            name="Obligation",
            description="Devoted to a family, a cause, an organization, a charity, etc.",
        ),
        Vice(
            id="pleasure",
            name="Pleasure",
            description="Gratification from lovers, food, drink, drugs, art, theater, etc.",
        ),
        Vice(
            id="stupor",
            name="Stupor",
            description=(
                "Seek oblivion in the abuse of drugs, drinking to excess, "
                "getting beaten to a pulp in fighting pits, etc."
            ),
        ),
        Vice(
            id="weird",
            name="Weird",
            description=(
                "Experiment with strange essences, consort with rogue spirits, "
                "observe bizarre rituals or taboos, etc."
            ),
        ),
    ]


def _reputations():
    return [
        Reputation(id="ambitious", name="Ambitious"),
        Reputation(id="brutal", name="Brutal"),
        Reputation(id="daring", name="Daring"),
        Reputation(id="honorable", name="Honorable"),
        Reputation(id="professional", name="Professional"),
        Reputation(id="savvy", name="Savvy"),
        Reputation(id="subtle", name="Subtle"),
        Reputation(id="strange", name="Strange"),
    ]


def _tables():
    outcomes = [
        PositionRoll(
            position="controlled",
            results=[
                RollResult(level="critical", description="You do it with increased effect."),
                RollResult(level="6", description="You do it."),
                RollResult(
                    level="4/5",
                    description=(
                        "You hesitate. Withdraw and try a different approach, or else "
                        "do it with a minor consequence: a minor complication occurs, "
                        "you have reduced effect, you suffer lesser harm, you end up "
                        "in a risky position."
                    ),
                ),
                RollResult(
                    level="1-3",
                    description=(
                        "You falter. Press on by seizing a risky opportunity, or "
                        "withdraw and try a different approach."
                    ),
                ),
            ],
        ),
        PositionRoll(
            position="risky",
            results=[
                RollResult(level="critical", description="You do it with increased effect."),
                RollResult(level="6", description="You do it."),
                RollResult(
                    level="4/5",
                    description=(
                        "You do it, but there's a consequence: you suffer harm, a "
                        "complication occurs, you have reduced effect, you end up "
                        "in a desperate position."
                    ),
                ),
                RollResult(
                    level="1-3",
                    description=(
                        "Things go badly. You suffer harm, a complication occurs, "
                        "you end up in a desperate position, you lose this "
                        "opportunity."
                    ),
                ),
            ],
        ),
        PositionRoll(
            position="desperate",
            results=[
                RollResult(level="critical", description="You do it with increased effect."),
                RollResult(level="6", description="You do it."),
                RollResult(
                    level="4/5",
                    description=(
                        "You do it, but there's a consequence: you suffer severe "
                        "harm, a serious complication occurs, you have reduced "
                        "effect."
                    ),
                ),
                RollResult(
                    level="1-3",
                    description=(
                        "It's the worst outcome. You suffer severe harm, a "
                        "serious complication occurs, you lose this opportunity "
                        "for action."
                    ),
                ),
            ],
        ),
    ]

    heat = [
        HeatPenalty(condition="0 heat", heat_added=0),
        HeatPenalty(condition="Smooth & quiet; low exposure", heat_added=0),
        HeatPenalty(condition="Contained; standard exposure", heat_added=2),
        HeatPenalty(condition="Loud & chaotic; high exposure", heat_added=4),
        HeatPenalty(condition="Wild; devastating exposure", heat_added=6),
        HeatPenalty(condition="High-profile or well-connected target", heat_added=1),
        HeatPenalty(condition="Situation happened on hostile turf", heat_added=1),
        HeatPenalty(condition="At war with another faction", heat_added=1),
        HeatPenalty(condition="Killing was involved", heat_added=2),
    ]

    entanglements = [
        EntanglementEntry(
            heat_band="0-3", roll_result="1-3", entanglement="Gang Trouble or The Usual Suspects"
        ),
        EntanglementEntry(
            heat_band="0-3", roll_result="4/5", entanglement="Rivals or Unquiet Dead"
        ),
        EntanglementEntry(heat_band="0-3", roll_result="6", entanglement="Cooperation"),
        EntanglementEntry(
            heat_band="4-5", roll_result="1-3", entanglement="Gang Trouble or Questioning"
        ),
        EntanglementEntry(
            heat_band="4-5", roll_result="4/5", entanglement="Reprisals or Unquiet Dead"
        ),
        EntanglementEntry(heat_band="4-5", roll_result="6", entanglement="Show of Force"),
        EntanglementEntry(
            heat_band="6", roll_result="1-3", entanglement="Flipped or Interrogation"
        ),
        EntanglementEntry(
            heat_band="6", roll_result="4/5", entanglement="Demonic Notice or Show of Force"
        ),
        EntanglementEntry(heat_band="6", roll_result="6", entanglement="Arrest"),
    ]

    return outcomes, heat, entanglements


def _items():
    return [
        Item(
            id="blade_or_two",
            name="A Blade or Two",
            load=1,
            description="A fighting knife, switchblade, or other small weapon.",
        ),
        Item(
            id="throwing_knives",
            name="Throwing Knives",
            load=1,
            description="Six small, balanced throwing blades.",
        ),
        Item(id="pistol", name="A Pistol", load=1, description="A heavy, single-shot pistol."),
        Item(
            id="large_weapon",
            name="A Large Weapon",
            load=2,
            description="A weapon requiring two hands (sword, pole-arm, rifle).",
        ),
        Item(
            id="unusual_weapon",
            name="An Unusual Weapon",
            load=1,
            description="A whip, dart-thrower, trick-blade, etc.",
        ),
        Item(id="armor", name="Armor", load=2, description="Thick leather tunic and high boots."),
        Item(
            id="heavy_armor",
            name="Heavy Armor",
            load=3,
            description="Plate and chainmail (requires Armor).",
        ),
        Item(
            id="burglary_gear",
            name="Burglary Gear",
            load=1,
            description="Lockpicks, prybar, wire-snippers, etc.",
        ),
        Item(
            id="climbing_gear",
            name="Climbing Gear",
            load=2,
            description="Rope, grappling hook, pitons.",
        ),
        Item(
            id="arcane_implements",
            name="Arcane Implements",
            load=1,
            description="Vials of blood, bone-dust, spirit-incense.",
        ),
        Item(
            id="documents",
            name="Documents",
            load=1,
            description="Forged papers, ledgers, blueprints.",
        ),
        Item(
            id="subterfuge_supplies",
            name="Subterfuge Supplies",
            load=1,
            description="Makeup, fake mustaches, disguises.",
        ),
        Item(
            id="demolition_tools",
            name="Demolition Tools",
            load=2,
            description="Sledgehammer, heavy prybar, etc.",
        ),
        Item(
            id="tinkering_tools",
            name="Tinkering Tools",
            load=1,
            description="Fine hand tools and supplies.",
        ),
        Item(id="lantern", name="Lantern", load=1, description="Oil or electroplasmic lamp."),
    ]


def _crew_upgrades():
    return [
        CrewUpgrade(
            id="boat_house", name="Boat House", description="A boat, a dock, and a shack.", cost=1
        ),
        CrewUpgrade(
            id="carriage_house",
            name="Carriage House",
            description="A carriage, two draft animals, and a stable.",
            cost=1,
        ),
        CrewUpgrade(id="cohort", name="Cohort", description="A gang or expert NPC.", cost=2),
        CrewUpgrade(id="hidden_lair", name="Hidden Lair", description="Secret location.", cost=1),
        CrewUpgrade(
            id="mastery", name="Mastery", description="PC action ratings can reach 4.", cost=4
        ),
        CrewUpgrade(
            id="quality", name="Quality", description="+1 quality for one gear type.", cost=1
        ),
        CrewUpgrade(id="quarters", name="Quarters", description="Living space in lair.", cost=1),
        CrewUpgrade(
            id="secure_lair", name="Secure Lair", description="Locks, alarms, traps.", cost=1
        ),
        CrewUpgrade(
            id="training",
            name="Training",
            description="2 xp instead of 1 when training a specific track.",
            cost=1,
        ),
        CrewUpgrade(id="vault", name="Vault", description="Secure storage for 8 coin.", cost=1),
        CrewUpgrade(
            id="workshop", name="Workshop", description="Tools for tinkering/alchemy.", cost=1
        ),
    ]


_MAGNITUDE_COLUMNS = (
    "level",
    "area",
    "scale",
    "duration",
    "range",
    "quality_tier",
    "force",
    "quality_example",
    "force_example",
)


def _magnitude_levels():
    # SRD: "Magnitude" - AREA/SCALE, DURATION/RANGE, and TIER & QUALITY/FORCE
    # tables, plus the QUALITY EXAMPLES and FORCE EXAMPLES tables, combined
    # one row per level (see _MAGNITUDE_COLUMNS for column order). The
    # source table's level-6 "area" cell is blank.
    rows = [
        (
            0,
            "A closet",
            "1 or 2 people",
            "A few moments",
            "Within reach",
            "Poor",
            "Weak",
            "A rusty knife, worn & tattered clothing, rickety shack on the street",
            "A firm shove, a candle flame, breeze, tiny spark",
        ),
        (
            1,
            "A small room",
            "A small gang (3-6)",
            "A few minutes",
            "A dozen paces",
            "Adequate",
            "Moderate",
            "A fighting blade, ordinary clothing, shared apartment, cheap food or drugs",
            "A solid punch, steady wind, torch flame, electrical shock",
        ),
        (
            2,
            "A large room& Several rooms",
            "A medium gang (12)",
            "An hour",
            "A stone's throw",
            "Good",
            "Strong",
            "A pistol, respectable clothing, private rented room, typical ghost",
            "A powerful blow, howling wind, burning brand",
        ),
        (
            3,
            "A small building",
            "A large gang (20)",
            "A few hours",
            "Down the road",
            "Excellent",
            "Serious",
            "A coach, boat, military rifle, fashionable clothing, small home",
            "A crushing blow, staggering wind, grenade, searing fire, electrical surge",
        ),
        (
            4,
            "A large building",
            "A huge gang (40)",
            "A day",
            "Several blocks away",
            "Superior",
            "Powerful",
            "A luxury vehicle, townhouse, typical demon or powerful ghost",
            "A charging horse, burning forge, bomb, whirlwind, electrocution",
        ),
        (
            5,
            "A city block",
            "A massive gang (80)",
            "Several days",
            "Across the district",
            "Impeccable",
            "Overwhelming",
            "A large townhouse, small ship, custom-tailored clothing, lightning barrier",
            "A ship's cannon, raging thunder-storm, massive fire, lightning strike",
        ),
        (
            6,
            "",
            "A colossal gang (160)",
            "A week",
            "Across the city",
            "Legendary",
            "Devastating",
            "A mansion, large ship, rare essences or arcane artifacts, powerful demon",
            "Hurricane wind, molten lava, tidal wave, electrical maelstrom",
        ),
    ]
    return [MagnitudeLevel(**dict(zip(_MAGNITUDE_COLUMNS, row, strict=True))) for row in rows]


def _downtime_activities():
    # SRD: "Downtime activities" > "DOWNTIME ACTIVITIES SUMMARY"
    return [
        DowntimeActivity(
            id="acquire_asset",
            name="Acquire Asset",
            summary=(
                "Roll the crew's Tier. The result indicates the quality of the "
                "asset. Some items require a minimum quality result to acquire; "
                "to raise the result beyond critical, you may spend 2 coin per "
                "+1 Tier bonus."
            ),
            results=[
                RollResult(level="critical", description="Tier +2."),
                RollResult(level="6", description="Tier +1."),
                RollResult(level="4/5", description="Tier."),
                RollResult(level="1-3", description="Tier -1."),
            ],
        ),
        DowntimeActivity(
            id="long_term_project",
            name="Long-Term Project",
            summary=(
                "Work on a long-term project, if you have the means. Mark "
                "segments on the clock according to your result."
            ),
            results=[
                RollResult(level="critical", description="Five ticks."),
                RollResult(level="6", description="Three ticks."),
                RollResult(level="4/5", description="Two ticks."),
                RollResult(level="1-3", description="One tick."),
            ],
        ),
        DowntimeActivity(
            id="recover",
            name="Recover",
            summary=(
                "Get treatment to tick your healing clock (like a long-term "
                "project). When you fill a clock, each harm is reduced by one "
                "level."
            ),
        ),
        DowntimeActivity(
            id="reduce_heat",
            name="Reduce Heat",
            summary=(
                "Say how you reduce heat on the crew and roll your action. "
                "Reduce heat according to the result level."
            ),
            results=[
                RollResult(level="critical", description="Clear five heat."),
                RollResult(level="6", description="Clear three heat."),
                RollResult(level="4/5", description="Clear two heat."),
                RollResult(level="1-3", description="Clear one heat."),
            ],
        ),
        DowntimeActivity(
            id="train",
            name="Train",
            summary=(
                "Mark 1 xp (in an attribute or your playbook). Add +1 xp if "
                "you have the appropriate crew upgrade. You may train a given "
                "xp track once per downtime."
            ),
        ),
        DowntimeActivity(
            id="indulge_vice",
            name="Indulge Vice",
            summary=(
                "Visit your vice purveyor to relieve stress. Roll dice equal "
                "to your lowest attribute. Clear stress equal to your highest "
                "die result. If you clear more stress levels than you had "
                "marked, you overindulge. If you do not or cannot indulge your "
                "vice during downtime, you take stress equal to your trauma."
            ),
        ),
    ]


def build_pack(srd_text):
    outcomes, heat, entanglements = _tables()
    return ContentPack(
        id="srd",
        name="Blades in the Dark SRD Base Pack",
        description="Core mechanics and abilities extracted from the SRD.",
        version="1.0.0",
        special_abilities=SrdAbilityParser(srd_text).parse(),
        traumas=_traumas(),
        vices=_vices(),
        reputations=_reputations(),
        items=_items(),
        crew_upgrades=_crew_upgrades(),
        action_outcomes=outcomes,
        heat_penalties=heat,
        entanglements=entanglements,
        magnitude_levels=_magnitude_levels(),
        downtime_activities=_downtime_activities(),
        srd_sections=_section_index(srd_text.splitlines()),
    )


@click.command("extract-srd")
def extract_srd() -> None:
    """Regenerate packs/srd_base.json from the local SRD copy (FR-9, C3a)."""
    if not SRD_PATH.exists():
        raise click.ClickException(f"SRD file not found at {SRD_PATH}; run `fid fetch-srd` first")

    pack = build_pack(SRD_PATH.read_text(encoding="utf-8"))
    PACK_PATH.write_text(pack.model_dump_json(indent=2), encoding="utf-8")
    click.echo(
        f"extract-srd: wrote {len(pack.special_abilities)} abilities, "
        f"{len(pack.items)} items, and tables to {PACK_PATH}"
    )
