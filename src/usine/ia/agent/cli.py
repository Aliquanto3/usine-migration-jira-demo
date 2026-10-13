"""Sous-application `usine agent` : Agent conversationnel en lecture seule.

`usine agent --enregistrer` (Story 7.11) pose les questions de la démo à l'Agent réel
(`config/llm.yaml`, secrets) sur la copie `demo/repli/passage/` et écrit les réponses
enregistrées du Mode repli dans `demo/repli/agent/`.
"""

from datetime import UTC, datetime
from pathlib import Path

import typer

from usine import composition
from usine.contrats.erreurs import UsineErreur
from usine.contrats.passage import FICHIERS_PASSAGE
from usine.ia.agent.repli import REPERTOIRE_REPONSES, enregistrer_reponses

REPERTOIRE_PASSAGE_REPLI = Path("demo/repli/passage")
"""Copie du Passage interrogée à l'enregistrement, relative à la racine."""

app = typer.Typer(
    help="Agent conversationnel en lecture seule.",
    no_args_is_help=True,
    invoke_without_command=True,
)


@app.callback()
def principal(
    enregistrer: bool = typer.Option(
        False,
        "--enregistrer",
        help="Enregistre les réponses de l'Agent aux questions de la démo (Mode repli).",
    ),
) -> None:
    """Agent conversationnel en lecture seule."""
    if not enregistrer:
        return
    racine = Path.cwd()
    repertoire = racine / REPERTOIRE_PASSAGE_REPLI
    if not (repertoire / FICHIERS_PASSAGE["manifeste"]).exists():
        raise UsineErreur(f"{repertoire} : copie du Passage du Mode repli absente")
    session = composition.construire_session_agent(
        racine, composition.consultation_repertoire(repertoire)
    )
    try:
        chemins = enregistrer_reponses(
            session, racine / REPERTOIRE_REPONSES, lambda: datetime.now(UTC)
        )
    finally:
        session.fermer()
    for chemin in chemins:
        typer.echo(f"Réponse enregistrée : {chemin}")
