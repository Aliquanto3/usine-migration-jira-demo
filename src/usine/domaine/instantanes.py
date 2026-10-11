"""État des tickets et Instantanés, reconstitués depuis les événements (FR-10, AD-17).

Fonctions pures : la liste des dates arrive en paramètre. Un événement compte en D si son
Jour ouvré de rattachement (`calendrier.jour_ouvre_de`) est ≤ D.
"""

from collections.abc import Iterable, Sequence
from datetime import date

import polars as pl

from usine.contrats.calcul import SCHEMA_INSTANTANE
from usine.contrats.calendrier import jour_ouvre_de
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import Evenement, NatureEvenement, evenements_en_table
from usine.contrats.schemas import valider
from usine.contrats.tickets import (
    SCHEMA_TICKET_ETAT,
    SCHEMA_TICKET_TEXTE,
    STATUTS_FERMES,
    Champ,
    TypeTicket,
)

CHAMPS_ETAT: tuple[Champ, ...] = (
    Champ.entite,
    Champ.vague,
    Champ.domaine,
    Champ.gravite,
    Champ.phase,
    Champ.statut,
    Champ.statut_test,
    Champ.statut_certification,
)
"""Champs d'un ticket repris dans `SCHEMA_TICKET_ETAT` (ni titre, ni description)."""

_FERMES = [statut.value for statut in STATUTS_FERMES]


def _table_evenements(evenements: Iterable[Evenement]) -> pl.DataFrame:
    """Table `SCHEMA_EVENEMENT` + `jour` (Jour ouvré de rattachement) + `rang` (ordre reçu)."""
    liste = list(evenements)
    table = evenements_en_table(liste)
    return table.with_columns(
        pl.Series("jour", [jour_ouvre_de(e.horodatage) for e in liste], dtype=pl.Date()),
        pl.int_range(pl.len(), dtype=pl.Int64).alias("rang"),
    ).sort(["horodatage", "rang"])


def _etats_en(table: pl.DataFrame, jour: date) -> pl.DataFrame:
    """État de chaque ticket créé au plus tard en `jour`, colonnes de `SCHEMA_TICKET_ETAT`."""
    vus = table.filter(pl.col("jour") <= jour)
    creations = (
        vus.filter(pl.col("nature") == NatureEvenement.creation.value)
        .group_by("cle_ticket", maintain_order=True)
        .agg(pl.col("type_ticket").first(), pl.col("rang").first().alias("rang_creation"))
    )
    valeurs = (
        vus.filter(pl.col("champ").is_in([c.value for c in CHAMPS_ETAT]))
        .group_by(["cle_ticket", "champ"], maintain_order=True)
        .agg(pl.col("vers").last())
        .with_columns(pl.col("champ").cast(pl.Utf8))
    )
    if valeurs.height:
        valeurs = valeurs.pivot(on="champ", index="cle_ticket", values="vers")
    else:
        valeurs = pl.DataFrame(schema={"cle_ticket": pl.Utf8()})
    entrees = (
        vus.filter(
            (pl.col("nature") == NatureEvenement.creation.value)
            | (
                (pl.col("nature") == NatureEvenement.transition.value)
                & pl.col("de").is_in(_FERMES)
                & ~pl.col("vers").is_in(_FERMES)
            )
        )
        .group_by("cle_ticket")
        .agg(pl.col("jour").max().alias("date_derniere_entree"))
    )
    etats = creations.join(valeurs, on="cle_ticket", how="left").join(
        entrees, on="cle_ticket", how="left"
    )
    manquantes = [c.value for c in CHAMPS_ETAT if c.value not in etats.columns]
    etats = etats.with_columns(pl.lit(None, dtype=pl.Utf8).alias(c) for c in manquantes)
    est_anomalie = pl.col("type_ticket") == TypeTicket.anomalie.value
    return (
        etats.sort("rang_creation")
        .with_columns(
            pl.lit(jour, dtype=pl.Date()).alias("date"),
            pl.when(est_anomalie).then(pl.col("date_derniere_entree")),
        )
        .with_columns(
            pl.col(colonne).cast(SCHEMA_TICKET_ETAT.colonnes[colonne])
            for colonne in (c.value for c in CHAMPS_ETAT)
        )
        .select(list(SCHEMA_TICKET_ETAT.colonnes))
    )


def tickets_etats(evenements: Iterable[Evenement], dates: Sequence[date]) -> pl.DataFrame:
    """`TicketEtat` : une ligne par ticket créé au plus tard en D, pour chaque D de `dates`.

    Chaque champ prend la dernière valeur `vers` reçue en D (ordre : horodatage, puis rang
    dans le flux). `date_derniere_entree` = Jour ouvré de la création, ou de la dernière
    transition qui sort de `STATUTS_FERMES` ; nulle hors Anomalies (l'Entrée est un concept
    d'Anomalie). Les colonnes sans objet pour le type restent nulles.
    """
    doublons = sorted({jour for jour in dates if list(dates).count(jour) > 1})
    if doublons:
        raise UsineErreur(f"dates en double : {', '.join(jour.isoformat() for jour in doublons)}")
    table = _table_evenements(evenements)
    morceaux = [_etats_en(table, jour) for jour in dates]
    if not morceaux:
        return valider(pl.DataFrame(schema=dict(SCHEMA_TICKET_ETAT.colonnes)), SCHEMA_TICKET_ETAT)
    return valider(pl.concat(morceaux, how="vertical"), SCHEMA_TICKET_ETAT)


CHAMPS_TEXTE: tuple[Champ, ...] = (Champ.entite, Champ.titre, Champ.description)
"""Champs d'un ticket repris dans `SCHEMA_TICKET_TEXTE`."""


def tickets_textes(evenements: Iterable[Evenement], date_arrete: date) -> pl.DataFrame:
    """`TicketTexte` : titre et description de chaque ticket créé au plus tard en D.

    Chaque champ prend la dernière valeur `vers` rattachée au plus tard à la Date d'arrêté
    (ordre : horodatage, puis rang dans le flux) ; un champ jamais renseigné reste nul.
    """
    table = _table_evenements(evenements)
    vus = table.filter(pl.col("jour") <= date_arrete)
    creations = (
        vus.filter(pl.col("nature") == NatureEvenement.creation.value)
        .group_by("cle_ticket", maintain_order=True)
        .agg(pl.col("type_ticket").first(), pl.col("rang").first().alias("rang_creation"))
    )
    valeurs = (
        vus.filter(pl.col("champ").is_in([c.value for c in CHAMPS_TEXTE]))
        .group_by(["cle_ticket", "champ"], maintain_order=True)
        .agg(pl.col("vers").last())
        .with_columns(pl.col("champ").cast(pl.Utf8))
    )
    if valeurs.height:
        valeurs = valeurs.pivot(on="champ", index="cle_ticket", values="vers")
    else:
        valeurs = pl.DataFrame(schema={"cle_ticket": pl.Utf8()})
    textes = creations.join(valeurs, on="cle_ticket", how="left")
    manquantes = [c.value for c in CHAMPS_TEXTE if c.value not in textes.columns]
    textes = textes.with_columns(pl.lit(None, dtype=pl.Utf8).alias(c) for c in manquantes)
    textes = (
        textes.sort("rang_creation")
        .with_columns(pl.col(c.value).cast(pl.Utf8) for c in CHAMPS_TEXTE)
        .select(list(SCHEMA_TICKET_TEXTE.colonnes))
    )
    return valider(textes, SCHEMA_TICKET_TEXTE)


def instantane(etats: pl.DataFrame) -> pl.DataFrame:
    """Instantané : nombre de tickets par date, Entité et combinaison d'attributs.

    `statut` porte le statut propre au type de ticket (`statut`, `statut_test` ou
    `statut_certification`).
    """
    etats = valider(etats, SCHEMA_TICKET_ETAT)
    type_statut = SCHEMA_INSTANTANE.colonnes["statut"]
    cles = ["date", "entite", "type_ticket", "vague", "phase", "gravite", "statut"]
    table = (
        etats.with_columns(
            pl.coalesce(
                pl.col("statut").cast(pl.Utf8),
                pl.col("statut_test").cast(pl.Utf8),
                pl.col("statut_certification").cast(pl.Utf8),
            )
            .cast(type_statut)
            .alias("statut")
        )
        .group_by(cles)
        .agg(pl.len().cast(pl.Int64).alias("nombre"))
        .sort(cles, nulls_last=True)
    )
    return valider(table, SCHEMA_INSTANTANE)
