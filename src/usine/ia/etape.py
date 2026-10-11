"""Étape `explications` de la Chaîne (Palier 2) : une Explication par Entité rouge ou orange."""

from usine.contrats.llm import SortieExplication
from usine.contrats.meteo import Couleur
from usine.contrats.passage import ContextePassage, ResultatEtape, StatutEtape
from usine.contrats.trace import EntreeTrace
from usine.ia.explication import ContexteExplication, expliquer, lire_prompt
from usine.ia.passerelle import Passerelle
from usine.ports.consultation import Consultation

COULEURS_EXPLIQUEES = frozenset({Couleur.rouge, Couleur.orange})
"""Météos expliquées par la tâche `explication` (FR-32)."""


class EtapeExplications:
    """Explique chaque Entité rouge ou orange à la Date d'arrêté ; n'écrit rien elle-même.

    `version_prompt` est calculée à partir des octets du gabarit qu'elle envoie (par défaut
    `ia/prompts/explication.md`).
    """

    def __init__(
        self,
        passerelle: Passerelle,
        version_donnees: str,
        gabarit: bytes | None = None,
    ) -> None:
        self._passerelle = passerelle
        self._version_donnees = version_donnees
        self._gabarit = gabarit if gabarit is not None else lire_prompt()

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Sortie `explications` et une trace par appel, lues via `ctx.consultation`."""
        contexte = ContexteExplication(
            passage_id=ctx.passage_id,
            version_donnees=self._version_donnees,
            gabarit=self._gabarit,
        )
        textes = ctx.consultation.textes_tickets()
        sorties: list[SortieExplication] = []
        traces: list[EntreeTrace] = []
        for meteo_entite in ctx.consultation.meteo(ctx.date_arrete):
            if meteo_entite.couleur not in COULEURS_EXPLIQUEES:
                continue
            sortie, traces_entite = expliquer(self._passerelle, meteo_entite, textes, contexte)
            sorties.append(sortie)
            traces.extend(traces_entite)
        return ResultatEtape(StatutEtape.reussie, {"explications": tuple(sorties)}, tuple(traces))
