import rich_click as click

from . import convert, count

app = click.CommandCollection(sources=[convert.cli, count.cli])

if __name__ == "__main__":
    app()
