from pathlib import Path

import httpx2 as httpx
from click.testing import CliRunner

import cli.extract_srd as extract_srd_module
import cli.fetch_srd as fetch_srd_module
import cli.licensing_grep as licensing_grep_module
from cli import cli
from cli.fetch_srd import download_srd
from cli.licensing_grep import FORBIDDEN_TERMS

# A tiny SRD fixture covering both ability sections, so the extractor's
# start/end heading lookup (SRD: "Special abilities", "Crew special
# abilities") is exercised without needing the real SRD file.
_FIXTURE_SRD = """\
## Special abilities

### Battleborn

You may expend your special armor.

> Flavour text.

## Fortitude

### Bodyguard

When you protect a teammate, take +1d.

## Character items

Loadout text.

## Crew special abilities

### Ghost Contacts

Crew ability text.

# The Score

Score text.
"""


def test_extract_srd_writes_pack(tmp_path: Path, monkeypatch) -> None:
    srd_path = tmp_path / "srd.md"
    srd_path.write_text(_FIXTURE_SRD, encoding="utf-8")
    pack_path = tmp_path / "srd_base.json"
    monkeypatch.setattr(extract_srd_module, "SRD_PATH", srd_path)
    monkeypatch.setattr(extract_srd_module, "PACK_PATH", pack_path)

    result = CliRunner().invoke(cli, ["extract-srd"])

    assert result.exit_code == 0, result.output
    pack = extract_srd_module.ContentPack.model_validate_json(pack_path.read_text())
    assert {a.id for a in pack.special_abilities} == {"battleborn", "bodyguard", "ghost_contacts"}


def test_extract_srd_fails_without_srd_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(extract_srd_module, "SRD_PATH", tmp_path / "missing.md")

    result = CliRunner().invoke(cli, ["extract-srd"])

    assert result.exit_code != 0
    assert "fetch-srd" in result.output


def test_download_srd_returns_response_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == fetch_srd_module.SRD_URL
        return httpx.Response(200, text="# SRD text")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        content = download_srd(client)

    assert content == b"# SRD text"


def test_fetch_srd_writes_downloaded_content(tmp_path: Path, monkeypatch) -> None:
    srd_path = tmp_path / "srd.md"
    monkeypatch.setattr(fetch_srd_module, "SRD_PATH", srd_path)
    monkeypatch.setattr(fetch_srd_module, "download_srd", lambda client: b"downloaded")

    result = CliRunner().invoke(cli, ["fetch-srd"])

    assert result.exit_code == 0, result.output
    assert srd_path.read_bytes() == b"downloaded"


def test_licensing_grep_passes_on_a_clean_tree(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "README.md").write_text("clean content", encoding="utf-8")
    monkeypatch.setattr(licensing_grep_module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(licensing_grep_module, "tracked_files", lambda: ["README.md"])

    result = CliRunner().invoke(cli, ["licensing-grep"])

    assert result.exit_code == 0, result.output
    assert "clean" in result.output


def test_licensing_grep_fails_on_a_forbidden_term_outside_the_allowlist(
    tmp_path: Path, monkeypatch
) -> None:
    forbidden_term = FORBIDDEN_TERMS[0]
    (tmp_path / "fixture.json").write_text(f"a tale of {forbidden_term}", encoding="utf-8")
    monkeypatch.setattr(licensing_grep_module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(licensing_grep_module, "tracked_files", lambda: ["fixture.json"])

    result = CliRunner().invoke(cli, ["licensing-grep"])

    assert result.exit_code != 0
    assert "fixture.json" in result.output


def test_licensing_grep_allows_the_term_in_an_allowlisted_doc(
    tmp_path: Path, monkeypatch
) -> None:
    forbidden_term = FORBIDDEN_TERMS[0]
    (tmp_path / "NOTICE.md").write_text(f"policy names {forbidden_term}", encoding="utf-8")
    monkeypatch.setattr(licensing_grep_module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(licensing_grep_module, "tracked_files", lambda: ["NOTICE.md"])

    result = CliRunner().invoke(cli, ["licensing-grep"])

    assert result.exit_code == 0, result.output
