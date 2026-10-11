"""Sous-application `usine agent` : Agent conversationnel en lecture seule."""

import typer

app = typer.Typer(help="Agent conversationnel en lecture seule.", no_args_is_help=True)


@app.callback()
def principal() -> None:
    """Agent conversationnel en lecture seule."""
