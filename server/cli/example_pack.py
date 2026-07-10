import click

from cli.paths import REPO_ROOT
from engine.packs import (
    ContentPack,
    CrewTypeTemplate,
    CrewUpgrade,
    Item,
    PlaybookTemplate,
    SpecialAbility,
)

EXAMPLE_PACK_PATH = REPO_ROOT / "packs" / "example_base.json"


def build_pack() -> ContentPack:
    """FR-9/C4: an entirely original playbook and crew type, proving the
    content-pack format without any real Blades in the Dark core-book
    content. Everything here - names, mechanics, prose - is invented for
    this project; none of it is drawn from the SRD or the core book."""
    special_abilities = [
        SpecialAbility(
            id="keen_eye",
            name="Keen Eye",
            description="When you Survey unfamiliar territory, take +1d.",
            tags=["playbook"],
        ),
        SpecialAbility(
            id="silver_tongue",
            name="Silver Tongue",
            description="When you Sway a stranger you've just met, take +1 effect.",
            tags=["playbook"],
        ),
        SpecialAbility(
            id="long_road",
            name="Long Road",
            description="You never suffer reduced effect from fatigue or bad weather.",
            tags=["playbook"],
        ),
        SpecialAbility(
            id="fleet_footed",
            name="Fleet-Footed",
            description="Your crew's couriers take +1d when racing against a deadline.",
            tags=["crew"],
        ),
    ]

    items = [
        Item(id="travelers_cloak", name="Traveler's Cloak", load=1),
        Item(id="worn_map", name="Worn Map", load=0),
        Item(id="signal_whistle", name="Signal Whistle", load=1),
    ]

    crew_upgrades = [
        CrewUpgrade(
            id="way_stations",
            name="Way-Stations",
            description="A network of safe houses along the routes your crew travels.",
            cost=2,
        )
    ]

    playbooks = [
        PlaybookTemplate(
            id="wayfarer",
            name="Wayfarer",
            starting_action_dots={"survey": 1, "prowl": 1, "sway": 1},
            special_ability_ids=["keen_eye", "silver_tongue", "long_road"],
            xp_trigger="Address a challenge by travelling into danger or the unknown.",
            item_ids=["travelers_cloak", "worn_map", "signal_whistle"],
            contact_names=["Old Rowan the Ferryman", "Captain Vess"],
        )
    ]

    crew_types = [
        CrewTypeTemplate(
            id="couriers",
            name="Couriers",
            starting_upgrade_ids=["way_stations"],
            special_ability_ids=["fleet_footed"],
            claim_names=["Waystation House", "River Ferry Dock"],
        )
    ]

    return ContentPack(
        id="example",
        name="Original Example Pack",
        description=(
            "An entirely original playbook (Wayfarer) and crew type "
            "(Couriers), proving the content-pack format without any "
            "core-book content."
        ),
        version="1.0.0",
        special_abilities=special_abilities,
        items=items,
        crew_upgrades=crew_upgrades,
        playbooks=playbooks,
        crew_types=crew_types,
    )


@click.command("build-example-pack")
def build_example_pack() -> None:
    """Regenerate packs/example_base.json, the original fixture pack (FR-9)."""
    pack = build_pack()
    EXAMPLE_PACK_PATH.write_text(pack.model_dump_json(indent=2), encoding="utf-8")
    click.echo(
        f"build-example-pack: wrote playbook {pack.playbooks[0].name!r} and "
        f"crew type {pack.crew_types[0].name!r} to {EXAMPLE_PACK_PATH}"
    )
