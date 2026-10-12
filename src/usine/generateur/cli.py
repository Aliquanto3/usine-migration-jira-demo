"""Sous-application `usine donnees` : Génération du Programme fictif et injection dans Jira."""

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated

import typer

from usine.config import charger_yaml
from usine.contrats.calendrier import analyser_date_iso, jour_local
from usine.contrats.config import ConfigProgramme
from usine.contrats.erreurs import UsineErreur
from usine.contrats.passage import CHEMIN_JOURNAL
from usine.generateur.journal import ecrire_journal
from usine.generateur.journal import generer as generer_journal

app = typer.Typer(
    help="Génération du Programme fictif et injection dans Jira.", no_args_is_help=True
)


@app.callback()
def principal() -> None:
    """Génération du Programme fictif et injection dans Jira."""


def _date(valeur: str) -> date:
    """Lit une date `AAAA-MM-JJ` ; toute autre forme devient une `UsineErreur`."""
    jour = analyser_date_iso(valeur)
    if jour is None:
        raise UsineErreur(f"date de génération invalide : {valeur!r} (attendu : AAAA-MM-JJ)")
    return jour


@app.command()
def generer(
    graine: Annotated[
        int | None, typer.Option(help="Graine du tirage (défaut : celle de la configuration).")
    ] = None,
    date_generation: Annotated[
        str | None,
        typer.Option(
            "--date-generation",
            metavar="AAAA-MM-JJ",
            help="Date de génération (défaut : aujourd'hui, heure de Paris).",
        ),
    ] = None,
    config: Annotated[Path, typer.Option(help="Configuration du Programme.")] = Path(
        "config/programme.yaml"
    ),
    sortie: Annotated[
        Path, typer.Option(help="Répertoire où écrire le Journal et la vérité terrain.")
    ] = CHEMIN_JOURNAL.parent,
) -> None:
    """Génère le Journal d'événements du Programme fictif réduit et sa vérité terrain."""
    jour = jour_local(datetime.now(UTC)) if date_generation is None else _date(date_generation)
    programme = charger_yaml(config, ConfigProgramme)
    generation = generer_journal(programme, programme.graine if graine is None else graine, jour)
    journal = ecrire_journal(generation, sortie)
    typer.echo(
        f"Journal écrit : {journal} ({len(generation.evenements)} événements,"
        f" graine {generation.entete.graine}, Date d'injection"
        f" {generation.entete.date_injection.isoformat()})"
    )
