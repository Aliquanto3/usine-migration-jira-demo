"""Source composite et alignements « Jira fait foi » (AD-4, H-27, FR-49).

- `source` : `SourceComposite` (port `SourceTickets`), tout le Journal aux clés Jira puis les
  seuls événements Jira postérieurs à `horodatage_fin_injection` ;
- `alignements` : rejeu d'état, `Evenement` `alignement` quand l'état rejoué diffère de l'état
  Jira, conversion de l'état Jira (FR-49) et `DetecteurAlignements` pour l'étape `extraction`.

N'importe ni `usine.domaine` ni l'entrepôt : le rejeu d'état est fait ici, en Python.
"""

from usine.adaptateurs.composite.alignements import (
    CHAMPS_ETAT,
    DetecteurAlignements,
    EtatTicket,
    alignements,
    convertir_etat_jira,
    etats_tickets,
    id_alignement,
)
from usine.adaptateurs.composite.source import SourceComposite

__all__ = [
    "CHAMPS_ETAT",
    "DetecteurAlignements",
    "EtatTicket",
    "SourceComposite",
    "alignements",
    "convertir_etat_jira",
    "etats_tickets",
    "id_alignement",
]
