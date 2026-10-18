"""Écrans de la démo et navigation en étoile autour de la carte météo."""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType


class Ecran(StrEnum):
    """Écrans de la page, dans l'ordre de la navigation latérale ; la valeur est le libellé."""

    carte = "Carte météo"
    detail = "Détail d'une Entité"
    lancement = "Lancement de la Chaîne"
    avant_apres = "Avant / après"
    pseudonymisation = "Pseudonymisation"
    agent = "Agent"
    outillage = "Ce qu'il faut pour le faire en vrai"


ECRAN_PAR_DEFAUT = Ecran.carte
"""Écran affiché à l'ouverture de la page."""

STORY_A_VENIR: Mapping[Ecran, str] = MappingProxyType({})
"""Story qui livre le contenu complet de chaque écran encore à l'état d'emplacement (aucun :
l'écran Agent est livré par la Story 7.9)."""
