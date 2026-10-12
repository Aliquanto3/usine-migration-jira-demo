"""Étapes de la Chaîne du walking skeleton (Story 0.5).

Les étapes déterministes réelles enveloppent le domaine ; les autres sont des bouchons, et les
étapes LLM sont sautées en Palier 1. Aucune étape n'écrit : elle renvoie un `ResultatEtape`.
"""

from collections import deque
from collections.abc import Sequence
from datetime import date

import polars as pl

from usine.contrats.calcul import SCHEMA_INDICATEUR
from usine.contrats.calendrier import TAILLE_FENETRE_GLISSANTE, jours_ouvres
from usine.contrats.config import ConfigProgramme, GrilleMeteo
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import MeteoEntite
from usine.contrats.passage import ContextePassage, ResultatEtape, StatutEtape
from usine.domaine.instantanes import instantane, tickets_etats, tickets_textes
from usine.domaine.meteo import DECALAGE_IND8, indicateurs, meteo
from usine.ports.consultation import Consultation
from usine.ports.source_tickets import SourceTickets


def jours_du_passage(premier_jour: date, date_arrete: date) -> tuple[date, ...]:
    """Jours ouvrés de `premier_jour` à la Date d'arrêté ; refuse une date antérieure."""
    if date_arrete < premier_jour:
        raise UsineErreur(
            f"Date d'arrêté {date_arrete.isoformat()} antérieure au premier jour de"
            f" l'historique {premier_jour.isoformat()}"
        )
    return jours_ouvres(premier_jour, date_arrete)


class EtapeInstantanes:
    """États des tickets et Instantanés, pour chaque Jour ouvré de l'historique."""

    def __init__(self, source: SourceTickets, premier_jour: date) -> None:
        self._source = source
        self._premier_jour = premier_jour

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Sorties `tickets_etats`, `instantanes` et `tickets_textes` (à la Date d'arrêté)."""
        dates = jours_du_passage(self._premier_jour, ctx.date_arrete)
        evenements = list(self._source.evenements())
        etats = tickets_etats(evenements, dates)
        return ResultatEtape(
            StatutEtape.reussie,
            {
                "tickets_etats": etats,
                "instantanes": instantane(etats),
                "tickets_textes": tickets_textes(evenements, ctx.date_arrete),
            },
        )


class EtapeMeteo:
    """Indicateurs et Météo par Entité, pour chaque Jour ouvré de l'historique.

    `premier_jour` est aussi l'ancrage des semaines du Programme (Phase en cours, IND-8).
    """

    def __init__(
        self,
        grille: GrilleMeteo,
        version_grille: str,
        entites: Sequence[str],
        premier_jour: date,
        programme: ConfigProgramme,
    ) -> None:
        self._grille = grille
        self._version_grille = version_grille
        self._entites = tuple(entites)
        self._premier_jour = premier_jour
        self._programme = programme

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Sorties `indicateurs` et `meteo`, lues depuis `tickets_etats` du Passage.

        Chaque jour reçoit l'état des tickets de J-5 au jour (Fenêtre glissante d'IND-7,
        comparaison d'IND-8 à J-5).
        """
        tables: list[pl.DataFrame] = []
        meteos: list[MeteoEntite] = []
        historique: deque[pl.DataFrame] = deque(
            maxlen=max(DECALAGE_IND8, TAILLE_FENETRE_GLISSANTE) + 1
        )
        for jour in jours_du_passage(self._premier_jour, ctx.date_arrete):
            historique.append(ctx.consultation.tickets_etats(jour))
            etats = pl.concat(historique, how="vertical")
            tables.append(
                indicateurs(
                    etats,
                    jour,
                    self._entites,
                    self._grille,
                    programme=self._programme,
                    ancrage=self._premier_jour,
                )
            )
            meteos.extend(
                meteo(
                    etats,
                    jour,
                    self._entites,
                    self._grille,
                    self._version_grille,
                    programme=self._programme,
                    ancrage=self._premier_jour,
                )
            )
        table = (
            pl.concat(tables, how="vertical")
            if tables
            else pl.DataFrame(schema=dict(SCHEMA_INDICATEUR.colonnes))
        )
        return ResultatEtape(StatutEtape.reussie, {"indicateurs": table, "meteo": tuple(meteos)})


class EtapeBouchon:
    """Étape pas encore implémentée : réussie, sans sortie."""

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Rend une étape réussie sans sortie."""
        return ResultatEtape(StatutEtape.reussie)


class EtapeSautee:
    """Étape sautée (étapes LLM en Palier 1)."""

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Rend une étape sautée."""
        return ResultatEtape(StatutEtape.sautee)
