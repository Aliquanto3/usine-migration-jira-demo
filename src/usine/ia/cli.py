"""Sous-application `usine ia` : Couche LLM : passerelle, classification, explications."""

import typer

app = typer.Typer(
    help="Couche LLM : passerelle, classification, explications.", no_args_is_help=True
)


@app.callback()
def principal() -> None:
    """Couche LLM : passerelle, classification, explications."""
