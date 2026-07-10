import click

from cli import example_pack as example_pack_module
from cli import extract_srd as extract_srd_module
from cli import fetch_srd as fetch_srd_module
from cli import licensing_grep as licensing_grep_module


@click.group()
def cli() -> None:
    """Development tooling for forged-in-the-ai (SRD fetch/extract, licensing grep, etc.)."""


cli.add_command(fetch_srd_module.fetch_srd)
cli.add_command(extract_srd_module.extract_srd)
cli.add_command(licensing_grep_module.licensing_grep)
cli.add_command(example_pack_module.build_example_pack)
