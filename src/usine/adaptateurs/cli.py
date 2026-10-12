"""Sous-application `usine extraction` : Extraction Jira et sources d'événements."""

from pathlib import Path
from typing import Annotated

import typer

from usine.adaptateurs.jira_cloud import rafraichir_fixtures
from usine.adaptateurs.jira_http import construire_client_lecture
from usine.config import charger_secrets, charger_yaml
from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur

app = typer.Typer(help="Extraction Jira et sources d'événements.", no_args_is_help=True)


@app.callback()
def principal() -> None:
    """Extraction Jira et sources d'événements."""


def _rafraichir(racine: Path, sortie: Path, nb_tickets: int) -> Path:
    chemin_config = racine / "config" / "jira.yaml"
    config = charger_yaml(chemin_config, ConfigJira)
    if config.mode != "cloud":
        raise UsineErreur(
            f"{chemin_config} : mode : {config.mode!r} : le rafraîchissement des fixtures"
            " ne vise que Jira Cloud (mode: cloud)"
        )
    secrets_usine = charger_secrets(racine)
    with construire_client_lecture(
        config,
        email=secrets_usine.jira_email,
        jeton_lecture=secrets_usine.jira_token_lecture,
        pat=None,
    ) as client:
        return rafraichir_fixtures(client, config, sortie, nb_tickets)


@app.command("rafraichir-fixtures")
def rafraichir_fixtures_cli(
    racine: Annotated[
        Path, typer.Option(help="Racine portant config/jira.yaml et les secrets (.env).")
    ] = Path("."),
    sortie: Annotated[
        Path, typer.Option(help="Répertoire des fixtures écrites (direct_*).")
    ] = Path("tests/fixtures/jira_cloud"),
    nb_tickets: Annotated[int, typer.Option(help="Tickets de la page enregistrée.")] = 3,
) -> None:
    """Enregistre une page de recherche Jira Cloud anonymisée (lecture seule)."""
    try:
        chemin = _rafraichir(racine, sortie, nb_tickets)
    except UsineErreur as erreur:
        typer.echo(f"Erreur : {erreur}", err=True)
        raise typer.Exit(1) from erreur
    typer.echo(f"Fixture écrite : {chemin}")
