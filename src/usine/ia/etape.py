"""Étapes LLM de la Chaîne (Palier 2).

`explications` : une Explication par Entité rouge ou orange ; `narration` : une narration de
la Prévision par Entité ayant une Prévision ou des Risques d'entrée en rouge.
"""

from collections import defaultdict

from usine.contrats.llm import SortieExplication, SortieNarration
from usine.contrats.meteo import Couleur
from usine.contrats.passage import ContextePassage, ResultatEtape, StatutEtape
from usine.contrats.prevision import RisqueEntreeRouge
from usine.contrats.trace import EntreeTrace
from usine.ia.explication import ContexteExplication, expliquer, lire_prompt
from usine.ia.narration import ContexteNarration, narrer
from usine.ia.narration import lire_prompt as lire_prompt_narration
from usine.ia.passerelle import Passerelle
from usine.ports.consultation import Consultation

COULEURS_EXPLIQUEES = frozenset({Couleur.rouge, Couleur.orange})
"""Météos expliquées par la tâche `explication` (FR-32)."""


class EtapeExplications:
    """Explique chaque Entité rouge ou orange à la Date d'arrêté ; n'écrit rien elle-même.

    Lit via la Consultation la Météo, les textes des tickets, et pour chaque Entité expliquée
    ses KPI à la Date d'arrêté et sa répartition des Causes racines (vide sans étape
    `repartition_causes`).

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
            entite = meteo_entite.entite
            sortie, traces_entite = expliquer(
                self._passerelle,
                meteo_entite,
                textes,
                contexte,
                kpi=ctx.consultation.kpi(ctx.date_arrete, entite),
                repartition=ctx.consultation.repartition_causes(entite),
            )
            sorties.append(sortie)
            traces.extend(traces_entite)
        return ResultatEtape(StatutEtape.reussie, {"explications": tuple(sorties)}, tuple(traces))


class EtapeNarration:
    """Narre la Prévision de chaque Entité ayant une Prévision ou des Risques (FR-24).

    Lit via la Consultation les Prévisions et les Risques d'entrée en rouge à la Date
    d'arrêté, groupés par Entité ; une `SortieNarration` par Entité, triée par Entité. N'écrit
    rien elle-même. `version_prompt` est calculée à partir des octets du gabarit qu'elle envoie
    (par défaut `ia/prompts/narration.md`).
    """

    def __init__(
        self,
        passerelle: Passerelle,
        version_donnees: str,
        gabarit: bytes | None = None,
    ) -> None:
        self._passerelle = passerelle
        self._version_donnees = version_donnees
        self._gabarit = gabarit if gabarit is not None else lire_prompt_narration()

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Sortie `narrations` et une trace par appel, lues via `ctx.consultation`."""
        contexte = ContexteNarration(
            passage_id=ctx.passage_id,
            version_donnees=self._version_donnees,
            gabarit=self._gabarit,
        )
        previsions = {p.entite: p for p in ctx.consultation.previsions(ctx.date_arrete)}
        risques: dict[str, list[RisqueEntreeRouge]] = defaultdict(list)
        for risque in ctx.consultation.risques(ctx.date_arrete):
            risques[risque.entite].append(risque)
        sorties: list[SortieNarration] = []
        traces: list[EntreeTrace] = []
        for entite in sorted(previsions.keys() | risques.keys()):
            prevision = previsions.get(entite)
            risques_entite = tuple(risques.get(entite, ()))
            version_grille = (
                prevision.version_grille
                if prevision is not None
                else risques_entite[0].version_grille
            )
            sortie, traces_entite = narrer(
                self._passerelle,
                entite,
                ctx.date_arrete,
                version_grille,
                prevision,
                risques_entite,
                contexte,
            )
            sorties.append(sortie)
            traces.extend(traces_entite)
        return ResultatEtape(StatutEtape.reussie, {"narrations": tuple(sorties)}, tuple(traces))
