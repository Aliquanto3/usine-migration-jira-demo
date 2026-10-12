"""`SerieStock` d'Anomalies bloquantes par Entité, depuis l'état des tickets (FR-20, AD-18).

Fonction pure et déterministe. Le stock d'une Entité à un Jour ouvré est l'ensemble de ses
Anomalies bloquantes ouvertes ce jour-là (définition d'IND-1 : type anomalie, gravité
bloquante, statut renseigné hors `STATUTS_FERMES`). Les flux sont les transitions de cet
ensemble d'un Jour ouvré au précédent : une clé qui y entre est une Entrée (création,
réouverture, passage en bloquante, arrivée d'une autre Entité), une clé qui en sort est une
Sortie (fermeture, rejet, changement de gravité, départ vers une autre Entité). Le premier jour
est comparé à un ensemble vide. L'identité `stock(j) = stock(j−1) + entrées(j) − sorties(j)`
tient donc par construction.

Les KPI `entrees_jour` et `sorties_jour` ne conviennent pas : ils portent toutes les gravités
et ignorent les changements de gravité.
"""

from collections.abc import Sequence
from datetime import date

import polars as pl

from usine.contrats.calendrier import est_jour_ouvre, jour_ouvre_suivant
from usine.contrats.erreurs import UsineErreur
from usine.contrats.prevision import SCHEMA_SERIE_STOCK
from usine.contrats.schemas import valider
from usine.contrats.tickets import SCHEMA_TICKET_ETAT, STATUTS_FERMES, Gravite, TypeTicket

_FERMES = [statut.value for statut in STATUTS_FERMES]


def _verifier_jours(jours: Sequence[date]) -> None:
    """Refuse un jour non ouvré, ou des Jours ouvrés non consécutifs."""
    for rang, jour in enumerate(jours):
        if not est_jour_ouvre(jour):
            raise UsineErreur(f"SerieStock : {jour.isoformat()} n'est pas un Jour ouvré")
        if rang and jour_ouvre_suivant(jours[rang - 1]) != jour:
            raise UsineErreur(
                f"SerieStock : Jours ouvrés non consécutifs entre"
                f" {jours[rang - 1].isoformat()} et {jour.isoformat()}"
            )


def _verifier_entites(entites: Sequence[str]) -> None:
    doublons = sorted({e for e in entites if list(entites).count(e) > 1})
    if doublons:
        raise UsineErreur(f"SerieStock : Entités en double : {', '.join(doublons)}")


def series_stock(
    tickets_etats: pl.DataFrame, entites: Sequence[str], jours: Sequence[date]
) -> pl.DataFrame:
    """`SCHEMA_SERIE_STOCK` dense : une ligne par Entité (ordre de `entites`) et par jour.

    `tickets_etats` suit `SCHEMA_TICKET_ETAT` ; seules ses lignes datées d'un jour de `jours`
    et rattachées à une Entité de `entites` comptent. `jours` sont des Jours ouvrés consécutifs
    dans l'ordre ; un jour sans ligne d'état vaut un stock vide. `serie` porte le code de
    l'Entité. Lève une `UsineErreur` si la table, les jours ou les Entités sont invalides.
    """
    _verifier_entites(entites)
    _verifier_jours(jours)
    etats = valider(tickets_etats, SCHEMA_TICKET_ETAT)
    ouvertes = etats.filter(
        pl.col("date").is_in(list(jours))
        & pl.col("entite").is_in(list(entites))
        & (pl.col("type_ticket") == TypeTicket.anomalie.value)
        & (pl.col("gravite") == Gravite.bloquante.value)
        & pl.col("statut").is_not_null()
        & ~pl.col("statut").cast(pl.Utf8).is_in(_FERMES)
    )
    par_jour: dict[tuple[date, str], frozenset[str]] = {
        (jour, entite): frozenset(cles)
        for jour, entite, cles in ouvertes.group_by(["date", "entite"])
        .agg(pl.col("cle_ticket"))
        .iter_rows()
    }
    lignes: dict[str, list[object]] = {colonne: [] for colonne in SCHEMA_SERIE_STOCK.colonnes}
    for entite in entites:
        precedent: frozenset[str] = frozenset()
        for jour in jours:
            courant = par_jour.get((jour, entite), frozenset())
            lignes["serie"].append(entite)
            lignes["date"].append(jour)
            lignes["stock"].append(len(courant))
            lignes["entrees"].append(len(courant - precedent))
            lignes["sorties"].append(len(precedent - courant))
            precedent = courant
    table = pl.DataFrame(lignes, schema=dict(SCHEMA_SERIE_STOCK.colonnes))
    return valider(table, SCHEMA_SERIE_STOCK)
