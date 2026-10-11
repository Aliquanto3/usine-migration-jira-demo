"""Sous-application `usine donnees` : Génération du Programme fictif et injection dans Jira."""

import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated

import typer

from usine.config import charger_yaml
from usine.contrats.calendrier import jour_local
from usine.contrats.config import ConfigProgramme
from usine.contrats.erreurs import UsineErreur
from usine.generateur.journal import generer as generer_journal
from usine.generateur.journal import serialiser_journal, serialiser_verite

_MOTIF_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

NOM_JOURNAL = "journal.jsonl"
"""Nom du Journal d'événements écrit dans le répertoire de sortie."""

NOM_VERITE = "verite_terrain.json"
"""Nom du fichier de vérité terrain des Causes racines."""

app = typer.Typer(
    help="Génération du Programme fictif et injection dans Jira.", no_args_is_help=True
)


@app.callback()
def principal() -> None:
    """Génération du Programme fictif et injection dans Jira."""


def _date(valeur: str) -> date:
    """Lit une date `AAAA-MM-JJ` ; toute autre forme devient une `UsineErreur`."""
    erreur = UsineErreur(f"date de génération invalide : {valeur!r} (attendu : AAAA-MM-JJ)")
    if not _MOTIF_DATE.fullmatch(valeur):
        raise erreur
    try:
        return date.fromisoformat(valeur)
    except ValueError as exc:
        raise erreur from exc


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
    ] = Path("donnees"),
) -> None:
    """Génère le Journal d'événements du Programme fictif réduit et sa vérité terrain."""
    jour = jour_local(datetime.now(UTC)) if date_generation is None else _date(date_generation)
    programme = charger_yaml(config, ConfigProgramme)
    generation = generer_journal(programme, programme.graine if graine is None else graine, jour)
    try:
        sortie.mkdir(parents=True, exist_ok=True)
        (sortie / NOM_JOURNAL).write_bytes(serialiser_journal(generation))
        (sortie / NOM_VERITE).write_bytes(serialiser_verite(generation))
    except OSError as exc:
        raise UsineErreur(f"{sortie} : écriture impossible ({exc.strerror or exc})") from exc
    typer.echo(
        f"Journal écrit : {sortie / NOM_JOURNAL} ({len(generation.evenements)} événements,"
        f" graine {generation.entete.graine}, Date d'injection"
        f" {generation.entete.date_injection.isoformat()})"
    )
