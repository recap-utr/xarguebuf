import typer

from . import convert, download, parse_annotations

app = typer.Typer()

app.command()(convert.convert)
app.command()(download.download)
app.add_typer(parse_annotations.app, name="parse-annotations")

if __name__ == "__main__":
    app()
