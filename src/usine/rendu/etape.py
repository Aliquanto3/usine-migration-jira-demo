"""Étape `rendu` de la Chaîne : renvoie les octets du Rapport, sans rien écrire (AD-22)."""

from datetime import datetime

from usine.contrats.passage import ContextePassage, DonneesPassage, ResultatEtape, StatutEtape
from usine.ports.consultation import Consultation
from usine.rendu.commun import ContexteRendu
from usine.rendu.excel import rendre_excel
from usine.rendu.powerpoint import rendre_powerpoint


class EtapeRendu:
    """Rend l'Excel et le PowerPoint du Passage ; seule la Chaîne les écrit.

    `donnees` (source, versions de Grille et de données) et `horodatage_extraction` viennent de
    la composition : le manifeste n'existe pas encore pendant le Passage.
    """

    def __init__(
        self,
        gabarit: bytes,
        donnees: DonneesPassage,
        horodatage_extraction: datetime | None = None,
    ) -> None:
        self._gabarit = gabarit
        self._donnees = donnees
        self._horodatage_extraction = horodatage_extraction

    def contexte(self, ctx: ContextePassage[Consultation]) -> ContexteRendu:
        """Contexte du rendu : Palier et Grille du Passage, identité des données.

        `previsions_calculees` est vrai : l'étape `prevision` précède le rendu et son échec
        arrête le Passage (AD-8).
        """
        return ContexteRendu(
            palier=ctx.palier,
            source=self._donnees.source,
            version_grille=self._donnees.version_grille,
            version_donnees=self._donnees.version_donnees,
            horodatage_extraction=self._horodatage_extraction,
            grille=ctx.configuration.grille_meteo,
            previsions_calculees=True,
        )

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Sorties `rapport_xlsx` et `rapport_pptx`, lues via `ctx.consultation` seulement."""
        return ResultatEtape(
            StatutEtape.reussie,
            {
                "rapport_xlsx": rendre_excel(ctx.consultation, ctx.date_arrete, self.contexte(ctx)),
                "rapport_pptx": rendre_powerpoint(ctx.consultation, self._gabarit, ctx.date_arrete),
            },
        )
