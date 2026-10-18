"""Écran Pseudonymisation, sans Streamlit : descriptions à comparer et messages (FR-31, AD-15).

La page montre côte à côte une description de ticket et sa version pseudonymisée par
`Pseudonymiseur.apercu`, que la composition expose seul (`ui/cli.apercu_pseudonymisation`) :
l'aperçu est local, sans fournisseur LLM ni écriture de la table de correspondance.
"""

from collections.abc import Mapping
from typing import Protocol

import polars as pl

AUCUNE_DESCRIPTION = "Aucune description de ticket non vide dans ce Passage : rien à comparer."
LEGENDE = (
    "Aperçu local : la description choisie est pseudonymisée sur ce poste, sans appel LLM ni"
    " écriture de la table de correspondance (donnees/pseudonymes.sqlite)."
)
TITRE_ORIGINAL = "Original"
TITRE_PSEUDONYMISE = "Version pseudonymisée"


class LecturePseudonymisation(Protocol):
    """Lecture de la `Consultation` dont l'écran a besoin (alignée sur elle par un test)."""

    def textes_tickets(self) -> pl.DataFrame:
        """Table `SCHEMA_TICKET_TEXTE` à la Date d'arrêté du Passage."""
        ...


def descriptions(table: pl.DataFrame) -> Mapping[str, str]:
    """Description de chaque ticket qui en a une non vide, par clé, dans l'ordre de la table."""
    return {
        rangee["cle_ticket"]: rangee["description"]
        for rangee in table.select("cle_ticket", "description").iter_rows(named=True)
        if rangee["description"] is not None and rangee["description"].strip()
    }


def moteur_indisponible(exc: Exception) -> str:
    """Message d'une ligne qui nomme la cause : moteur Presidio ou modèle spaCy introuvable
    ou en échec (première ligne du message seulement)."""
    lignes = str(exc).strip().splitlines()
    cause = f"{type(exc).__name__} : {lignes[0]}" if lignes else type(exc).__name__
    return f"Moteur de Pseudonymisation indisponible (Presidio ou modèle spaCy) : {cause}"
