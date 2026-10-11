"""Sous-application `usine rapport` : Rapport quotidien : Chaîne de reporting de bout en bout."""

import typer

app = typer.Typer(
    help="Rapport quotidien : Chaîne de reporting de bout en bout.", no_args_is_help=True
)


@app.callback()
def principal() -> None:
    """Rapport quotidien : Chaîne de reporting de bout en bout."""
