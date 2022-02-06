import typer

from . import api, convert, parse_annotations

app = typer.Typer()

app.command()(convert.convert)
app.add_typer(api.app, name="api")
app.add_typer(parse_annotations.app, name="parse-annotations")

if __name__ == "__main__":
    app()
