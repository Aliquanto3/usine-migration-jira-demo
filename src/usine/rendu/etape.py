"""Étape `rendu` de la Chaîne : renvoie les octets du Rapport, sans rien écrire (AD-22)."""

from usine.contrats.passage import ContextePassage, ResultatEtape, StatutEtape
from usine.ports.consultation import Consultation
from usine.rendu.excel import rendre_excel
from usine.rendu.powerpoint import rendre_powerpoint


class EtapeRendu:
    """Rend l'Excel et le PowerPoint du Passage ; seule la Chaîne les écrit."""

    def __init__(self, gabarit: bytes) -> None:
        self._gabarit = gabarit

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Sorties `rapport_xlsx` et `rapport_pptx`, lues via `ctx.consultation` seulement."""
        return ResultatEtape(
            StatutEtape.reussie,
            {
                "rapport_xlsx": rendre_excel(ctx.consultation, ctx.date_arrete),
                "rapport_pptx": rendre_powerpoint(ctx.consultation, self._gabarit, ctx.date_arrete),
            },
        )
