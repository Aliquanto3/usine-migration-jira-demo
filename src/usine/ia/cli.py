"""Sous-application `usine ia` : Couche LLM : passerelle, classification, explications."""

from pathlib import Path
from typing import Annotated

import typer

from usine import composition
from usine.ia.doublons import LIMITE_DEFAUT, SEUIL_DEFAUT

app = typer.Typer(
    help="Couche LLM : passerelle, classification, explications, doublons.", no_args_is_help=True
)


@app.callback()
def principal() -> None:
    """Couche LLM : passerelle, classification, explications, doublons."""


@app.command()
def doublons(
    repertoire: Annotated[Path, typer.Argument(help="Répertoire d'un Passage publié.")],
    seuil: Annotated[
        float, typer.Option(min=0, max=1, help="Score minimal d'une paire (0 à 1).")
    ] = SEUIL_DEFAUT,
    limite: Annotated[
        int, typer.Option(min=1, help="Nombre maximal de paires affichées.")
    ] = LIMITE_DEFAUT,
) -> None:
    """Liste les paires d'Anomalies ouvertes probablement en doublon (FR-36, bonus).

    Suggestions à revoir par le Pilote : aucune fusion, aucune écriture dans Jira.
    """
    sortie = composition.doublons_passage(Path.cwd(), repertoire, seuil, limite)
    typer.echo(f"Doublons probables au {sortie.date_arrete} (seuil {sortie.seuil}) :")
    for paire in sortie.paires:
        typer.echo(f"{paire.cle_a}  {paire.cle_b}  {paire.score:.2f}")
    typer.echo(f"{len(sortie.paires)} paire(s) à revoir ; rien n'est fusionné ni écrit dans Jira.")
