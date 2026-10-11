"""Étapes de la Chaîne du walking skeleton (Story 0.5).

Les étapes déterministes réelles enveloppent le domaine ; les autres sont des bouchons, et les
étapes LLM sont sautées en Palier 1. Aucune étape n'écrit : elle renvoie un `ResultatEtape`.
"""

from collections.abc import Sequence
from datetime import date

import polars as pl

from usine.contrats.calcul import SCHEMA_INDICATEUR
from usine.contrats.calendrier import jours_ouvres
from usine.contrats.config import GrilleMeteo
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import MeteoEntite
from usine.contrats.passage import ContextePassage, ResultatEtape, StatutEtape
from usine.domaine.instantanes import instantane, tickets_etats, tickets_textes
from usine.domaine.meteo import indicateurs, meteo
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
    """Indicateurs et Météo par Entité, pour chaque Jour ouvré de l'historique."""

    def __init__(
        self,
        grille: GrilleMeteo,
        version_grille: str,
        entites: Sequence[str],
        premier_jour: date,
    ) -> None:
        self._grille = grille
        self._version_grille = version_grille
        self._entites = tuple(entites)
        self._premier_jour = premier_jour

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Sorties `indicateurs` et `meteo`, lues depuis `tickets_etats` du Passage."""
        tables: list[pl.DataFrame] = []
        meteos: list[MeteoEntite] = []
        for jour in jours_du_passage(self._premier_jour, ctx.date_arrete):
            etats = ctx.consultation.tickets_etats(jour)
            tables.append(indicateurs(etats, jour, self._entites, self._grille))
            meteos.extend(meteo(etats, jour, self._entites, self._grille, self._version_grille))
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
