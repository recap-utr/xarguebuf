import typer

from . import convert, count

app = typer.Typer()

app.command()(convert.convert)
app.command()(count.count)

if __name__ == "__main__":
    app()
