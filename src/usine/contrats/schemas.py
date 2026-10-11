"""Schémas des tables Polars et leur validation aux frontières (AD-2)."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

import polars as pl

from usine.contrats.erreurs import UsineErreur


@dataclass(frozen=True)
class SchemaTable:
    """Schéma nommé d'une table : colonnes ordonnées et type Polars attendu de chacune."""

    nom: str
    colonnes: Mapping[str, pl.DataType]

    def __post_init__(self) -> None:
        object.__setattr__(self, "colonnes", MappingProxyType(dict(self.colonnes)))

    def __hash__(self) -> int:
        return hash((self.nom, tuple(self.colonnes)))


def enum_polars(*enumerations: type[StrEnum]) -> pl.Enum:
    """Type `pl.Enum` dont les catégories sont les valeurs des énumérations, dans leur ordre.

    Une colonne de ce type refuse toute valeur hors domaine et se trie dans l'ordre de
    définition (`Couleur` : `vert < jaune < orange < rouge`).
    """
    valeurs = [membre.value for enumeration in enumerations for membre in enumeration]
    if len(set(valeurs)) != len(valeurs):
        raise UsineErreur(f"valeurs en double dans les énumérations : {valeurs}")
    return pl.Enum(valeurs)


def valider(df: pl.DataFrame, schema: SchemaTable) -> pl.DataFrame:
    """Vérifie que `df` suit `schema` et le renvoie, colonnes dans l'ordre du schéma.

    Lève une `UsineErreur` qui nomme le schéma et la colonne absente, en trop ou mal typée.
    """
    if not isinstance(df, pl.DataFrame):
        raise UsineErreur(f"{schema.nom} : polars.DataFrame attendu, pas {type(df).__name__}")
    presentes = df.schema
    for colonne, attendu in schema.colonnes.items():
        if colonne not in presentes:
            raise UsineErreur(f"{schema.nom} : colonne « {colonne} » absente")
        if presentes[colonne] != attendu:
            raise UsineErreur(
                f"{schema.nom} : colonne « {colonne} » de type {presentes[colonne]},"
                f" attendu {attendu}"
            )
    en_trop = [colonne for colonne in presentes if colonne not in schema.colonnes]
    if en_trop:
        raise UsineErreur(f"{schema.nom} : colonne « {en_trop[0]} » inattendue")
    return df.select(list(schema.colonnes))
