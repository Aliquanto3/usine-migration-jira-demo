"""Point d'entrée `usine` : enregistre une fois chaque sous-application de lane (AD-21)."""

import logging
import sys
from datetime import UTC, datetime

import typer

from usine.adaptateurs.cli import app as app_extraction
from usine.chaine.cli import app as app_rapport
from usine.contrats.erreurs import UsineErreur
from usine.contrats.format import formater_horodatage
from usine.generateur.cli import app as app_donnees
from usine.ia.agent.cli import app as app_agent
from usine.ia.cli import app as app_ia
from usine.ui.cli import app as app_ui

app = typer.Typer(name="usine", help="Copilote de pilotage d'une usine de migration.")
app.add_typer(app_donnees, name="donnees")
app.add_typer(app_extraction, name="extraction")
app.add_typer(app_rapport, name="rapport")
app.add_typer(app_ia, name="ia")
app.add_typer(app_agent, name="agent")
app.add_typer(app_ui, name="ui")


FORMAT_JOURNAL = "%(asctime)s %(levelname)s %(name)s : %(message)s"
"""Format sobre des journaux de la CLI (stderr, niveau INFO)."""


class FormateurJournal(logging.Formatter):
    """Journaux horodatés en heure de Paris (`contrats.format`), quel que soit le poste."""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return formater_horodatage(datetime.fromtimestamp(record.created, UTC))


def configurer_console() -> None:
    """Sorties standard en UTF-8 (console Windows en cp1252) et journaux sur stderr.

    Journaux de l'usine en INFO ; bibliothèques tierces (httpx…) en WARNING, pour ne pas noyer
    la progression sous une ligne par requête. Un caractère que le flux ne sait toujours pas
    écrire est remplacé, jamais une `UnicodeEncodeError`.
    """
    for flux in (sys.stdout, sys.stderr):
        reconfigurer = getattr(flux, "reconfigure", None)
        if reconfigurer is not None:
            reconfigurer(encoding="utf-8", errors="replace")
    gestionnaire = logging.StreamHandler(sys.stderr)
    gestionnaire.setFormatter(FormateurJournal(FORMAT_JOURNAL))
    logging.basicConfig(level=logging.WARNING, handlers=[gestionnaire])
    logging.getLogger("usine").setLevel(logging.INFO)


def main() -> None:
    """Point d'entrée du script `usine` : une `UsineErreur` devient un message et le code 1."""
    configurer_console()
    try:
        app()
    except UsineErreur as erreur:
        typer.echo(f"Erreur : {erreur}", err=True)
        raise SystemExit(1) from erreur
