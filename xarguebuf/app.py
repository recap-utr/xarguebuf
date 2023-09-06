import rich_click as click

from . import api, convert, count

app = click.CommandCollection(sources=[convert.cli, count.cli, api.cli])

if __name__ == "__main__":
    app()
