import rich_click as click
from twarc.command2 import twarc2


@click.group()
def cli():
    pass


cli.add_command(twarc2, name="api")
