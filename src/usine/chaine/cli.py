"""Commande `usine rapport [--date-arrete AAAA-MM-JJ]` : Chaîne de reporting de bout en bout."""

import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated

import typer

from usine import composition
from usine.contrats.calendrier import dernier_jour_ouvre_ecoule, jour_local
from usine.contrats.erreurs import UsineErreur

_MOTIF_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

app = typer.Typer(help="Rapport quotidien : Chaîne de reporting de bout en bout.")


def lire_date_arrete(valeur: str | None, maintenant: datetime) -> date:
    """Date d'arrêté demandée, ou dernier Jour ouvré écoulé ; refuse un jour non ouvré."""
    if valeur is None:
        return dernier_jour_ouvre_ecoule(jour_local(maintenant))
    erreur = UsineErreur(f"Date d'arrêté invalide : {valeur!r} (attendu : AAAA-MM-JJ)")
    if not _MOTIF_DATE.fullmatch(valeur):
        raise erreur
    try:
        jour = date.fromisoformat(valeur)
    except ValueError as exc:
        raise erreur from exc
    return composition.verifier_date_arrete(jour)


@app.callback(invoke_without_command=True)
def rapport(
    date_arrete: Annotated[
        str | None,
        typer.Option(
            "--date-arrete",
            metavar="AAAA-MM-JJ",
            help="Date d'arrêté du Rapport (défaut : dernier Jour ouvré écoulé, heure de Paris).",
        ),
    ] = None,
) -> None:
    """Exécute la Chaîne et publie un Passage complet, ou rien."""
    jour = lire_date_arrete(date_arrete, datetime.now(UTC))
    lance = composition.lancer_rapport(Path("."), jour)
    typer.echo(f"Passage publié : {lance.repertoire}")
