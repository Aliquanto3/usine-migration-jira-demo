"""Écrans de la démo et navigation en étoile autour de la carte météo, sans Streamlit."""

from collections.abc import Mapping, MutableMapping
from enum import StrEnum
from types import MappingProxyType


class Ecran(StrEnum):
    """Écrans de la page, dans l'ordre de la navigation latérale ; la valeur est le libellé."""

    carte = "Carte météo"
    detail = "Détail d'une Entité"
    lancement = "Lancement de la Chaîne"
    avant_apres = "Avant / après"
    agent = "Agent"
    outillage = "Ce qu'il faut pour le faire en vrai"


ECRAN_PAR_DEFAUT = Ecran.carte
"""Écran affiché à l'ouverture de la page."""

STORY_A_VENIR: Mapping[Ecran, str] = MappingProxyType(
    {
        Ecran.detail: "7.2",
        Ecran.avant_apres: "7.4",
        Ecran.outillage: "7.5",
        Ecran.agent: "7.9",
    }
)
"""Story qui livre le contenu complet de chaque écran encore à l'état d'emplacement."""

CLE_ECRAN = "ecran"
"""Clé de `session_state` du sélecteur d'écran."""
CLE_ENTITE = "entite"
"""Clé de `session_state` du sélecteur d'Entité de l'écran Détail."""


def libelles_ecrans() -> list[str]:
    """Libellés de la navigation latérale ; le premier est l'écran par défaut."""
    ecrans = [ECRAN_PAR_DEFAUT, *(ecran for ecran in Ecran if ecran is not ECRAN_PAR_DEFAUT)]
    return [ecran.value for ecran in ecrans]


def ouvrir_detail(etat: MutableMapping[str, object], entite: str) -> None:
    """Rappel du bouton `Détail ENT-x` : écran Détail sur l'Entité, en un seul clic."""
    etat[CLE_ECRAN] = Ecran.detail.value
    etat[CLE_ENTITE] = entite
