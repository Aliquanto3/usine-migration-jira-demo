"""Primitives partagées de la Prévision (AD-18 : une seule implémentation par calcul).

Avance en Jours ouvrés (par `contrats.calendrier`) et test de déclenchement d'un seuil de la
Grille en nombres exacts ; la Baseline (`baseline`) et le Risque d'entrée en rouge (`risque`)
les utilisent sans les redéfinir.
"""

from datetime import date
from fractions import Fraction

from usine.contrats.calendrier import jour_ouvre_suivant
from usine.contrats.meteo import Operateur


def avancer(jour: date, n: int) -> date:
    """`jour` avancé de `n` Jours ouvrés (`n` ≥ 0)."""
    for _ in range(n):
        jour = jour_ouvre_suivant(jour)
    return jour


def declenche(valeur: Fraction, operateur: Operateur, seuil: Fraction) -> bool:
    """Vrai si `valeur <operateur> seuil` : la règle de la Grille se déclenche."""
    if operateur is Operateur.superieur_ou_egal:
        return valeur >= seuil
    return valeur > seuil
