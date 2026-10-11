"""Sous-application `usine donnees` : Génération du Programme fictif et injection dans Jira."""

import typer

app = typer.Typer(
    help="Génération du Programme fictif et injection dans Jira.", no_args_is_help=True
)


@app.callback()
def principal() -> None:
    """Génération du Programme fictif et injection dans Jira."""
