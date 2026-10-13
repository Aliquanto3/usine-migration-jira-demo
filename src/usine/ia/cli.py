"""Sous-application `usine ia` : Couche LLM : passerelle, classification, explications.

`usine ia doublons --passage <répertoire>` (Story 6.11, bonus) liste les paires d'Anomalies
ouvertes probablement en doublon, avec un score, dans `sorties/doublons/<passage_id>.json` ;
la trace des appels les accompagne (`.trace.jsonl`). Aucune fusion, aucune écriture dans Jira.
"""

import json
from pathlib import Path
from typing import Annotated

import typer

from usine import composition
from usine.contrats.erreurs import UsineErreur
from usine.contrats.passage import FICHIERS_PASSAGE

REPERTOIRE_DOUBLONS = Path("sorties") / "doublons"
"""Résultats de la détection de doublons, relatifs à la racine."""

app = typer.Typer(
    help="Couche LLM : passerelle, classification, explications.", no_args_is_help=True
)


@app.callback()
def principal() -> None:
    """Couche LLM : passerelle, classification, explications."""


@app.command("doublons")
def doublons(
    passage: Annotated[
        Path,
        typer.Option(
            "--passage",
            help="Répertoire d'un Passage publié de Palier 2 (ou 1) dont lire les Anomalies.",
        ),
    ],
) -> None:
    """[BONUS] Paires d'Anomalies ouvertes probablement en doublon, avec un score (FR-36)."""
    racine = Path.cwd()
    if not (passage / FICHIERS_PASSAGE["manifeste"]).exists():
        raise UsineErreur(f"{passage} : Passage publié introuvable (manifeste absent)")
    consultation = composition.consultation_repertoire(passage)
    detection = composition.construire_doublons(racine)
    try:
        sorties, traces = detection(consultation)
    finally:
        detection.fermer()
    passage_id = consultation.manifeste().passage_id
    repertoire = racine / REPERTOIRE_DOUBLONS
    repertoire.mkdir(parents=True, exist_ok=True)
    resultat = repertoire / f"{passage_id}.json"
    resultat.write_text(
        json.dumps([s.model_dump(mode="json") for s in sorties], ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (repertoire / f"{passage_id}.trace.jsonl").write_text(
        "".join(t.model_dump_json() + "\n" for t in traces), encoding="utf-8"
    )
    for sortie in sorties:
        typer.echo(f"{sortie.score:.2f}  {sortie.cle_a}  {sortie.cle_b}  {sortie.justification}")
    typer.echo(f"{len(sorties)} paire(s) à revoir : {resultat}")
