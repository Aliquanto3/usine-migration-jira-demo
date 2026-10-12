"""Tables de calcul : Instantanés, KPI, Indicateurs, Tendances (AD-9, AD-10, FR-11, FR-12).

Comptes entiers ; tout taux ou ratio en `numerateur` / `denominateur` entiers, un compte valant
`n/1` ; `denominateur = 0` avec `numerateur > 0` vaut l'infini. KPI et Tendances sont en format
long : une ligne par (date, périmètre, code, dimension).
"""

from enum import StrEnum

import polars as pl

from usine.contrats.meteo import CodeIndicateur, Couleur
from usine.contrats.schemas import SchemaTable, enum_polars
from usine.contrats.tickets import (
    Gravite,
    Phase,
    StatutAnomalie,
    StatutCertification,
    StatutTest,
    TypeTicket,
)

PERIMETRE_PROGRAMME = "PROGRAMME"
"""Valeur de `perimetre` pour une mesure du Programme entier (sinon : code d'Entité)."""


class StatutIndicateur(StrEnum):
    """Un Indicateur est évalué, ou non évaluable avec un motif (jamais NaN ni `None`)."""

    evalue = "evalue"
    non_evaluable = "non_evaluable"


SCHEMA_INSTANTANE = SchemaTable(
    "SCHEMA_INSTANTANE",
    {
        "date": pl.Date(),
        "entite": pl.Utf8(),
        "type_ticket": enum_polars(TypeTicket),
        "vague": pl.Utf8(),
        "phase": enum_polars(Phase),
        "gravite": enum_polars(Gravite),
        "statut": enum_polars(StatutAnomalie, StatutTest, StatutCertification),
        "nombre": pl.Int64(),
    },
    non_nulles=frozenset({"date", "type_ticket", "nombre"}),
)
"""Instantané : nombre de tickets par Entité et par combinaison d'attributs, à chaque date.

`statut` porte la valeur canonique du statut propre au type de ticket (union des trois
énumérations de statut) ; `phase` et `gravite` sont nulles quand elles sont sans objet.
"""

_COLONNES_MESURE: dict[str, pl.DataType] = {
    "date": pl.Date(),
    "perimetre": pl.Utf8(),
    "code_kpi": pl.Utf8(),
    "dimension": pl.Utf8(),
    "numerateur": pl.Int64(),
    "denominateur": pl.Int64(),
}

SCHEMA_KPI = SchemaTable("SCHEMA_KPI", _COLONNES_MESURE, frozenset(_COLONNES_MESURE))
"""KPI quotidiens ; `dimension` vaut `""` quand le KPI n'est pas ventilé."""

SCHEMA_TENDANCE = SchemaTable("SCHEMA_TENDANCE", _COLONNES_MESURE, frozenset(_COLONNES_MESURE))
"""Tendances hebdomadaires ; `date` = dernier Jour ouvré de la semaine (partielle comprise)."""

SCHEMA_INDICATEUR = SchemaTable(
    "SCHEMA_INDICATEUR",
    {
        "date": pl.Date(),
        "entite": pl.Utf8(),
        "code": enum_polars(CodeIndicateur),
        "statut": enum_polars(StatutIndicateur),
        "motif": pl.Utf8(),
        "numerateur": pl.Int64(),
        "denominateur": pl.Int64(),
        "couleur": enum_polars(Couleur),
    },
    non_nulles=frozenset(
        {"date", "entite", "code", "statut", "motif", "numerateur", "denominateur", "couleur"}
    ),
)
"""Indicateurs de météo ; `motif` = `""` si évalué, valeur `0/0` si non évaluable.

`couleur` est un `pl.Enum` ordonné : la pire couleur se calcule par `max` dans Polars.
"""
