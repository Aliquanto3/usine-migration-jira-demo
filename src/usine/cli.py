"""Point d'entrée `usine` : enregistre une fois chaque sous-application de lane (AD-21)."""

import typer

from usine.adaptateurs.cli import app as app_extraction
from usine.chaine.cli import app as app_rapport
from usine.contrats.erreurs import UsineErreur
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


def main() -> None:
    """Point d'entrée du script `usine` : une `UsineErreur` devient un message et le code 1."""
    try:
        app()
    except UsineErreur as erreur:
        typer.echo(f"Erreur : {erreur}", err=True)
        raise SystemExit(1) from erreur
