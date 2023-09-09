import rich_click as click

from . import hn, twitter

cli = click.Group(name="xarguebuf", commands=[hn.cli, twitter.cli])

if __name__ == "__main__":
    cli()
