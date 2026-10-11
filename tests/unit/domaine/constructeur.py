"""Construction à la main de flux d'`Evenement` pour les tests du domaine."""

from datetime import datetime

from usine.contrats.evenements import Evenement, NatureEvenement, SourceEvenement
from usine.contrats.tickets import Champ, TypeTicket


class Flux:
    """Accumule des événements numérotés `J-<rang>` dans l'ordre des appels."""

    def __init__(self) -> None:
        self.evenements: list[Evenement] = []

    def _ajouter(
        self,
        cle: str,
        type_ticket: TypeTicket,
        horodatage: datetime,
        nature: NatureEvenement,
        champ: Champ | None = None,
        de: str | None = None,
        vers: str | None = None,
    ) -> None:
        self.evenements.append(
            Evenement(
                id_evenement=f"J-{len(self.evenements) + 1}",
                cle_ticket=cle,
                type_ticket=type_ticket,
                horodatage=horodatage,
                nature=nature,
                champ=champ,
                de=de,
                vers=vers,
                source=SourceEvenement.journal,
            )
        )

    def creer(
        self, cle: str, type_ticket: TypeTicket, horodatage: datetime, attributs: dict[Champ, str]
    ) -> None:
        """Création suivie d'un `modification_champ` par attribut initial."""
        self._ajouter(cle, type_ticket, horodatage, NatureEvenement.creation)
        for champ, valeur in attributs.items():
            self._ajouter(
                cle,
                type_ticket,
                horodatage,
                NatureEvenement.modification_champ,
                champ,
                None,
                valeur,
            )

    def anomalie(
        self,
        cle: str,
        horodatage: datetime,
        *,
        entite: str = "ENT-A",
        gravite: str = "bloquante",
        statut: str = "nouvelle",
    ) -> None:
        """Anomalie de la Vague V1, Phase recette, Domaine paie."""
        self.creer(
            cle,
            TypeTicket.anomalie,
            horodatage,
            {
                Champ.statut: statut,
                Champ.entite: entite,
                Champ.vague: "V1",
                Champ.domaine: "paie",
                Champ.gravite: gravite,
                Champ.phase: "recette",
            },
        )

    def transition(self, cle: str, horodatage: datetime, de: str, vers: str) -> None:
        """Transition de statut d'une Anomalie."""
        self._ajouter(
            cle,
            TypeTicket.anomalie,
            horodatage,
            NatureEvenement.transition,
            Champ.statut,
            de,
            vers,
        )

    def modifier(
        self,
        cle: str,
        type_ticket: TypeTicket,
        horodatage: datetime,
        champ: Champ,
        de: str,
        vers: str,
    ) -> None:
        """Modification d'un champ après la création."""
        self._ajouter(
            cle, type_ticket, horodatage, NatureEvenement.modification_champ, champ, de, vers
        )
