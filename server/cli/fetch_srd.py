import click
import httpx2 as httpx

from cli.paths import SRD_PATH
from state.srd_bootstrap import SRD_URL


def download_srd(client: httpx.Client) -> bytes:
    response = client.get(SRD_URL)
    response.raise_for_status()
    return response.content


@click.command("fetch-srd")
def fetch_srd() -> None:
    """Download the SRD to the repo root as Blades-in-the-Dark-SRD.md (gitignored)."""
    with httpx.Client(follow_redirects=True) as client:
        content = download_srd(client)
    SRD_PATH.write_bytes(content)
    click.echo(f"fetch-srd: wrote {SRD_PATH}")
