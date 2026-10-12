"""Répartition des Causes racines proposées par Entité à la Date d'arrêté (FR-35, AD-9).

Fonction pure et déterministe, sans E/S : compte, pour chaque Entité, les Anomalies ouvertes
classées par Cause racine proposée, et la part de chaque Cause parmi ces Anomalies classées.
Une Anomalie ouverte non encore classée (part du plafond de coût atteinte) n'entre pas dans le
calcul ; une classification sans Anomalie ouverte à la date, ou une Anomalie sans Entité, non
plus. La somme des parts vaut donc 1 pour chaque Entité présente.
"""

from collections import Counter
from collections.abc import Sequence
from datetime import date

import polars as pl

from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import SCHEMA_REPARTITION_CAUSES, SortieClassification
from usine.contrats.tickets import CauseRacine

COLONNES_ANOMALIES = ("cle_ticket", "entite")
"""Colonnes attendues de la table des Anomalies ouvertes à la Date d'arrêté."""


def repartition(
    date_arrete: date,
    classification: Sequence[SortieClassification],
    anomalies: pl.DataFrame,
) -> pl.DataFrame:
    """Table `SCHEMA_REPARTITION_CAUSES` des Anomalies ouvertes classées à `date_arrete`.

    `anomalies` porte `cle_ticket` et `entite` des Anomalies ouvertes à la Date d'arrêté.
    Tri : `entite`, `nombre` décroissant, puis `cause_racine` (ordre alphabétique) ; la sortie
    ne dépend pas de l'ordre des entrées, qui ne sont pas modifiées.
    """
    manquantes = [c for c in COLONNES_ANOMALIES if c not in anomalies.columns]
    if manquantes:
        raise UsineErreur(f"répartition des Causes racines : colonnes absentes {manquantes}")
    entites: dict[str, str] = {}
    for cle, entite in anomalies.select(COLONNES_ANOMALIES).iter_rows():
        if cle and entite:
            entites[cle] = entite
    causes: dict[str, CauseRacine] = {}
    for sortie in classification:
        if sortie.cle_ticket in entites:
            # Une clé classée deux fois n'est pas attendue ; la plus grande Cause (ordre
            # alphabétique) est retenue pour que la sortie ne dépende pas de l'ordre.
            precedente = causes.get(sortie.cle_ticket)
            if precedente is None or sortie.cause_racine.value > precedente.value:
                causes[sortie.cle_ticket] = sortie.cause_racine
    comptes = Counter((entites[cle], cause) for cle, cause in causes.items())
    totaux = Counter(entites[cle] for cle in causes)
    lignes = sorted(
        ((entite, cause, nombre) for (entite, cause), nombre in comptes.items()),
        key=lambda ligne: (ligne[0], -ligne[2], ligne[1].value),
    )
    return pl.DataFrame(
        {
            "date": [date_arrete] * len(lignes),
            "entite": [entite for entite, _, _ in lignes],
            "cause_racine": [cause.value for _, cause, _ in lignes],
            "nombre": [nombre for _, _, nombre in lignes],
            "part": [nombre / totaux[entite] for entite, _, nombre in lignes],
        },
        schema=dict(SCHEMA_REPARTITION_CAUSES.colonnes),
    )
