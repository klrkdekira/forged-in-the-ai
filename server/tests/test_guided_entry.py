import json
from pathlib import Path

from click.testing import CliRunner

from cli import cli

_HAPPY_PATH_INPUT = "\n".join(
    [
        "Test Character",  # name
        "Ghost",  # alias
        "Quiet, watchful",  # look
        "Test Playbook",  # playbook
        "Dockside",  # heritage
        "Fisher's kin",  # heritage detail
        "Smuggler",  # background
        "Ran the northern routes",  # background detail
        "2",  # hunt
        "2",  # study
        "1",  # survey
        "1",  # tinker
        "1",  # finesse
        "0",  # prowl
        "0",  # skirmish
        "0",  # wreck
        "0",  # attune
        "0",  # command
        "0",  # consort
        "0",  # sway
        "battleborn",  # special ability id
        "Old Rowan",  # friend
        "Captain Vess",  # rival
        "faith",  # vice
        "A forgotten god of the tides",  # vice detail
        "The Tideworn Shrine",  # vice purveyor
        "Traveler's Cloak, Worn Map",  # items
        "",
    ]
)


def test_guided_entry_saves_a_completed_character(tmp_path: Path):
    result = CliRunner().invoke(
        cli, ["guided-entry", "--output-dir", str(tmp_path)], input=_HAPPY_PATH_INPUT
    )

    assert result.exit_code == 0, result.output

    saved = json.loads((tmp_path / "test_character.json").read_text())
    assert saved["name"] == "Test Character"
    assert saved["playbook"] == "Test Playbook"
    assert saved["special_ability_ids"] == ["battleborn"]
    assert saved["vice"] == "faith"
    assert saved["friend"] == "Old Rowan"
    assert sum(saved["action_ratings"].values()) == 7
    assert [item["item_id"] for item in saved["items"]] == ["Traveler's Cloak", "Worn Map"]


def test_guided_entry_rejects_dots_that_do_not_total_seven(tmp_path: Path):
    lines = _HAPPY_PATH_INPUT.split("\n")
    lines[8] = "0"  # drop hunt from 2 to 0, so the total is short
    bad_input = "\n".join(lines)

    result = CliRunner().invoke(
        cli, ["guided-entry", "--output-dir", str(tmp_path)], input=bad_input
    )

    assert result.exit_code != 0
    assert "must total 7" in result.output
    assert not list(tmp_path.glob("*.json"))
