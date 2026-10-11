"""Sous-application `usine extraction` : Extraction Jira et sources d'événements."""

import typer

app = typer.Typer(help="Extraction Jira et sources d'événements.", no_args_is_help=True)


@app.callback()
def principal() -> None:
    """Extraction Jira et sources d'événements."""
