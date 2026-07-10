import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from app.settings import get_settings
from cli import cli


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_dev_session_runs_a_tool_and_saves_the_log(data_dir: Path):
    script = "\n".join(
        [
            "Test Character",  # character name prompt
            "Test Playbook",  # playbook prompt
            "Test Crew",  # crew name prompt
            "Test Type",  # crew type prompt
            'roll_fortune {"pool_size": 2}',
            "quit",
        ]
    )

    result = CliRunner().invoke(cli, ["session", "--seed", "1"], input=script)

    assert result.exit_code == 0, result.output
    assert '"band"' in result.output

    saved = data_dir / "sessions" / "test_character-session.jsonl"
    events = [json.loads(line) for line in saved.read_text().splitlines()]
    assert events[0]["event_type"] == "fortune_roll"


def test_dev_session_reports_an_error_for_an_unknown_tool(data_dir: Path):
    script = "\n".join(
        ["Test Character", "Test Playbook", "Test Crew", "Test Type", "nope", "quit"]
    )

    result = CliRunner().invoke(cli, ["session"], input=script)

    assert result.exit_code == 0, result.output
    assert "unknown tool" in result.output


def test_dev_session_can_load_a_character_and_crew_from_files(data_dir: Path):
    character_path = data_dir / "character.json"
    character_path.write_text(
        json.dumps({"name": "Loaded Character", "playbook": "Test Playbook"}), encoding="utf-8"
    )
    crew_path = data_dir / "crew.json"
    crew_path.write_text(
        json.dumps({"name": "Loaded Crew", "crew_type": "Test Type"}), encoding="utf-8"
    )

    result = CliRunner().invoke(
        cli,
        ["session", "--character", str(character_path), "--crew", str(crew_path)],
        input="quit",
    )

    assert result.exit_code == 0, result.output
    assert (data_dir / "sessions" / "loaded_character-session.jsonl").exists()
