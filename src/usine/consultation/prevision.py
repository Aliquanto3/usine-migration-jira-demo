"""État de la Prévision d'une Entité, lu via `Consultation` (FR-20, FR-21, FR-26 onglet 1).

Le port gelé rend `()` aussi bien pour « Prévision non calculée » que pour « aucun Risque ».
Depuis le câblage de l'étape `prevision` (Story 5.3), toute étape `prevision` réussie écrit
`previsions.json` ; son échec arrête le Passage. Le manifeste distingue donc une Prévision
calculée (étape réussie) d'une Prévision non calculée (étape sautée ou absente) :
`previsions_calculees`. Pendant la construction du Passage, sans manifeste, le lecteur reçoit
cette information de l'appelant (le rendu suit l'étape `prevision`, AD-8).

Restent indiscernables sans changer les contrats : un Passage publié avec l'ancien bouchon
(étape « réussie », sans `previsions.json`), lu comme « aucun Risque » pour une Entité non
rouge ; une Entité non rouge dont tous les indicateurs projetés sont écartés
(`ResultatRisque.exclus` n'a pas de place dans `ContenuPrevisions`), lue comme « aucun Risque ».
"""

from datetime import date
from enum import StrEnum

from usine.contrats.meteo import Couleur
from usine.contrats.passage import Etape, ManifestePassage, StatutEtape
from usine.ports.consultation import Consultation


class EtatPrevision(StrEnum):
    """Ce que le Rapport affiche dans la colonne « Prévision ou Risque » d'une Entité."""

    prevision = "prevision"
    """Entité rouge : sa Prévision de sortie du rouge."""
    risque = "risque"
    """Entité non rouge : ses Risques d'entrée en rouge."""
    aucun_risque = "aucun_risque"
    """Entité non rouge, Prévision calculée, sans Risque."""
    non_calculee = "non_calculee"
    """Étape `prevision` non réussie, Entité inconnue de la Météo, ou rouge sans Prévision."""


def previsions_calculees(manifeste: ManifestePassage) -> bool:
    """Vrai si l'étape `prevision` du Passage a réussi."""
    return any(
        execution.etape is Etape.prevision and execution.statut is StatutEtape.reussie
        for execution in manifeste.etapes
    )


def etat_prevision(
    consultation: Consultation, entite: str, date_arrete: date | None, calculees: bool
) -> EtatPrevision:
    """État de la Prévision de `entite` à la date (`None` : Date d'arrêté du Passage).

    `calculees` dit si l'étape `prevision` a réussi (`previsions_calculees` sur un Passage
    publié, `True` pendant le rendu).
    """
    if not calculees:
        return EtatPrevision.non_calculee
    meteos = consultation.meteo(date_arrete, entite)
    if not meteos:
        return EtatPrevision.non_calculee
    if meteos[0].couleur is Couleur.rouge:
        if consultation.previsions(date_arrete, entite):
            return EtatPrevision.prevision
        return EtatPrevision.non_calculee
    if consultation.risques(date_arrete, entite):
        return EtatPrevision.risque
    return EtatPrevision.aucun_risque
