import click

from cli import extract_srd as extract_srd_module
from cli import fetch_srd as fetch_srd_module


@click.group()
def cli() -> None:
    """Development tooling for forged-in-the-ai (SRD fetch/extract, etc.)."""


cli.add_command(fetch_srd_module.fetch_srd)
cli.add_command(extract_srd_module.extract_srd)
