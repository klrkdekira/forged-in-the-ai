import re
import subprocess

import click

from cli.paths import REPO_ROOT
from engine.pack_loader import FORBIDDEN_TERMS

# FORBIDDEN_TERMS lives in engine.pack_loader (NOTICE.md "Content
# policy"), the one runtime holder of the list; this is the commit-time
# check over the same terms, the loader is the runtime backstop for
# distribution-bound packs specifically.
FORBIDDEN_PATTERN = re.compile("|".join(re.escape(term) for term in FORBIDDEN_TERMS))

# Docs describing the content policy are allowed to name the forbidden
# terms, as is the one place that holds the term list as runtime data to
# enforce the firewall itself; code, packs, and fixtures otherwise are not.
ALLOWLIST = re.compile(
    r"^("
    r"NOTICE\.md|CLAUDE\.md|AGENTS\.md|README\.md|CONTRIBUTING\.md|"
    r"packs/README\.md|SPECIFICATION\.md|docs/.*\.md|"
    r"server/engine/pack_loader\.py"
    r")$"
)


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return result.stdout.splitlines()


def find_hits(relative_path: str) -> list[str]:
    """Lines matching a forbidden term, as "<lineno>:<line>" (like `grep -n`).
    Binary files are skipped, matching the original `grep -I`."""
    try:
        text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return [
        f"{lineno}:{line}"
        for lineno, line in enumerate(text.splitlines(), start=1)
        if FORBIDDEN_PATTERN.search(line)
    ]


@click.command("licensing-grep")
def licensing_grep() -> None:
    """Fail if a forbidden core-book term (NOTICE.md) appears in a tracked
    file outside the docs allowed to name it while describing the policy."""
    found_hits = False
    for path in tracked_files():
        if ALLOWLIST.match(path):
            continue
        hits = find_hits(path)
        if hits:
            found_hits = True
            click.echo(f"licensing-grep: forbidden term in {path}")
            for hit in hits:
                click.echo(f"  {hit}")

    if found_hits:
        raise click.ClickException("forbidden core-book content found, see NOTICE.md")

    click.echo("licensing-grep: clean")
