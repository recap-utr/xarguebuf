import rich_click as click

from . import api, convert, count

cli = click.CommandCollection(name="twitter", sources=[convert.cli, count.cli, api.cli])
