import typer

from . import convert, download, parse_annotations

app = typer.Typer()

app.add_typer(convert.app, name="convert")
app.add_typer(download.app, name="download")
app.add_typer(parse_annotations.app, name="parse-annotations")

if __name__ == "__main__":
    app()
