import rich_click as click

from . import api

cli = click.CommandCollection(name="hn", sources=[api.cli])
