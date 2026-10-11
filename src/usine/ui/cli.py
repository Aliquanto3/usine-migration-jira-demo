"""Sous-application `usine ui` : Interface de démo Streamlit."""

import typer

app = typer.Typer(help="Interface de démo Streamlit.", no_args_is_help=True)


@app.callback()
def principal() -> None:
    """Interface de démo Streamlit."""
