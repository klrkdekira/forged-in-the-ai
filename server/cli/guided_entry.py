import click

from cli.paths import PACK_PATH, REPO_ROOT
from engine.character import Action, Character
from engine.errors import EngineError
from engine.pack_loader import load_pack

DEFAULT_OUTPUT_DIR = REPO_ROOT / "server" / "data" / "characters"

# SRD: "Assign four action dots" - 3 dots come pre-placed on a real
# playbook (which we don't have; it's the book owner's own), so this flow
# has the owner enter final totals directly instead of split. Same creation
# cap applies either way: no action above 2, 7 dots in total.
CREATION_TOTAL_DOTS = 7
CREATION_MAX_PER_ACTION = 2


class GuidedEntryError(EngineError):
    """The entered action dots don't satisfy the SRD's creation rules."""


def _validate_action_ratings(ratings: dict[Action, int]) -> None:
    over_cap = [a for a, dots in ratings.items() if dots > CREATION_MAX_PER_ACTION]
    if over_cap:
        raise GuidedEntryError(
            f"no action may start above {CREATION_MAX_PER_ACTION} dots: {over_cap}"
        )
    total = sum(ratings.values())
    if total != CREATION_TOTAL_DOTS:
        raise GuidedEntryError(f"action dots must total {CREATION_TOTAL_DOTS}, got {total}")


def _prompt_action_ratings() -> dict[Action, int]:
    click.echo(
        f"\nAssign {CREATION_TOTAL_DOTS} action dots total, max {CREATION_MAX_PER_ACTION} each."
    )
    ratings = {}
    for action in Action:
        ratings[action] = click.prompt(f"  {action.value.title()}", type=int, default=0)
    _validate_action_ratings(ratings)
    return ratings


def _prompt_special_ability(ability_ids: list[str], ability_names: dict[str, str]) -> str:
    click.echo("\nSpecial abilities (from the committed SRD bank):")
    for ability_id in ability_ids:
        click.echo(f"  {ability_id}: {ability_names[ability_id]}")
    chosen = click.prompt("Choose one by id")
    if chosen not in ability_ids:
        raise GuidedEntryError(f"{chosen!r} is not one of the listed ability ids")
    return chosen


def _prompt_vice(vice_ids: list[str]) -> str:
    click.echo(f"\nVices: {', '.join(vice_ids)}")
    chosen = click.prompt("Choose one")
    if chosen not in vice_ids:
        raise GuidedEntryError(f"{chosen!r} is not one of the listed vices")
    return chosen


@click.command("guided-entry")
@click.option(
    "--output-dir",
    type=click.Path(),
    default=None,
    help="Where to save the character (default: server/data/characters, gitignored).",
)
def guided_entry(output_dir: str | None) -> None:
    """FR-8/D6: build a private playbook assembly for an owner of the book.

    Walks the SRD's character-creation steps and saves the result as user
    data - never committed, exported, or shared by default (C6)."""
    click.echo("Forged in the AI: guided character entry")
    click.echo(
        "This builds your own character from your playbook. Nothing here is "
        "committed; it's saved to your local user-data directory.\n"
    )

    pack = load_pack(PACK_PATH)
    ability_names = {ability.id: ability.name for ability in pack.special_abilities}
    ability_ids = list(ability_names)
    vice_ids = [vice.id for vice in pack.vices]

    name = click.prompt("Character name")
    alias = click.prompt("Alias (blank for none)", default="", show_default=False) or None
    look = click.prompt("Look (a few evocative words)", default="", show_default=False) or None
    playbook = click.prompt("Playbook name (from your own book)")
    heritage = click.prompt("Heritage", default="", show_default=False) or None
    heritage_detail = click.prompt("Heritage detail", default="", show_default=False) or None
    background = click.prompt("Background", default="", show_default=False) or None
    background_detail = click.prompt("Background detail", default="", show_default=False) or None

    try:
        action_ratings = _prompt_action_ratings()
        special_ability_id = _prompt_special_ability(ability_ids, ability_names)
    except GuidedEntryError as error:
        raise click.ClickException(str(error)) from error

    friend = click.prompt("Close friend (name)", default="", show_default=False) or None
    rival = click.prompt("Rival (name)", default="", show_default=False) or None

    try:
        vice = _prompt_vice(vice_ids)
    except GuidedEntryError as error:
        raise click.ClickException(str(error)) from error
    vice_detail = click.prompt("Vice detail", default="", show_default=False) or None
    vice_purveyor = (
        click.prompt("Vice purveyor (name and location)", default="", show_default=False) or None
    )

    character = Character(
        name=name,
        alias=alias,
        look=look,
        playbook=playbook,
        heritage=heritage,
        heritage_detail=heritage_detail,
        background=background,
        background_detail=background_detail,
        action_ratings=action_ratings,
        special_ability_ids=[special_ability_id],
        friend=friend,
        rival=rival,
        vice=vice,
        vice_detail=vice_detail,
        vice_purveyor=vice_purveyor,
    )

    out_dir = REPO_ROOT / output_dir if output_dir else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{name.lower().replace(' ', '_')}.json"
    out_path.write_text(character.model_dump_json(indent=2), encoding="utf-8")

    click.echo(f"\nSaved {name} to {out_path}")
