import json
import random
from datetime import UTC, datetime
from pathlib import Path

import click

from ai.tools import TOOL_SPECS, GameState, ToolExecutor
from app.packs import load_entanglements
from app.settings import get_settings
from engine.character import Character
from engine.crew import Crew
from engine.session import Session


def _load_or_create_character(path: str | None) -> Character:
    if path:
        return Character.model_validate_json(Path(path).read_text(encoding="utf-8"))
    return Character(name=click.prompt("Character name"), playbook=click.prompt("Playbook name"))


def _load_or_create_crew(path: str | None) -> Crew:
    if path:
        return Crew.model_validate_json(Path(path).read_text(encoding="utf-8"))
    return Crew(name=click.prompt("Crew name"), crew_type=click.prompt("Crew type"))


@click.command("session")
@click.option(
    "--character",
    type=click.Path(exists=True),
    default=None,
    help="Load a character JSON file (e.g. from guided-entry).",
)
@click.option("--crew", type=click.Path(exists=True), default=None, help="Load a crew JSON file.")
@click.option("--seed", type=int, default=None, help="RNG seed, for deterministic rolls.")
def dev_session(character: str | None, crew: str | None, seed: int | None) -> None:
    """Dev CLI harness (kept from Phases 1-3): an interactive headless
    engine session using the same ToolExecutor the GM agent uses (FR-12),
    with no LLM or web client needed.

    Enter commands as `<tool_name> <json args>`, e.g.:

      roll_action {"action": "prowl", "position": "risky", "effect": "standard"}

    Type `tools` to list available tools, `quit` to end and save the log.
    """
    click.echo("Forged in the AI: dev session harness")
    state = GameState(
        character=_load_or_create_character(character),
        crew=_load_or_create_crew(crew),
        session=Session(),
    )
    executor = ToolExecutor(
        rng=random.Random(seed),
        clock=lambda: datetime.now(UTC),
        entanglements=load_entanglements(get_settings()),
    )

    while True:
        line = click.prompt(">", prompt_suffix=" ", default="", show_default=False).strip()
        if not line:
            continue
        if line in ("quit", "exit"):
            break
        if line == "tools":
            for name in TOOL_SPECS:
                click.echo(f"  {name}")
            continue

        tool_name, _, raw_args = line.partition(" ")
        spec = TOOL_SPECS.get(tool_name)
        if spec is None:
            click.echo(f"unknown tool {tool_name!r}; type 'tools' to list")
            continue

        args_model, _ = spec
        try:
            args = args_model.model_validate_json(raw_args or "{}")
            result = getattr(executor, tool_name)(state, args)
        except Exception as error:
            click.echo(f"error: {error}")
            continue
        state = result.state
        click.echo(json.dumps(result.result, indent=2))

    out_dir = get_settings().data_dir / "sessions"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{state.character.name.lower().replace(' ', '_')}-session.jsonl"
    out_path.write_text(state.log.to_jsonl(), encoding="utf-8")
    click.echo(f"Saved session log to {out_path}")
