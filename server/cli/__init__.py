import click

from cli import example_pack as example_pack_module
from cli import extract_srd as extract_srd_module
from cli import fetch_srd as fetch_srd_module
from cli import guided_entry as guided_entry_module
from cli import index_srd as index_srd_module
from cli import licensing_grep as licensing_grep_module
from cli import session as session_module


@click.group()
def cli() -> None:
    """Development tooling for forged-in-the-ai (SRD fetch/extract, licensing grep, etc.)."""


cli.add_command(fetch_srd_module.fetch_srd)
cli.add_command(extract_srd_module.extract_srd)
cli.add_command(licensing_grep_module.licensing_grep)
cli.add_command(example_pack_module.build_example_pack)
cli.add_command(guided_entry_module.guided_entry)
cli.add_command(index_srd_module.index_srd)
cli.add_command(session_module.dev_session)
