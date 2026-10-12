"""`SchemaTable` et `valider` (AD-2)."""

from datetime import date

import polars as pl
import pytest

from usine.contrats import SchemaTable, UsineErreur, valider
from usine.contrats.calcul import (
    SCHEMA_INDICATEUR,
    SCHEMA_INSTANTANE,
    SCHEMA_KPI,
    StatutIndicateur,
)
from usine.contrats.llm import SCHEMA_REPARTITION_CAUSES
from usine.contrats.meteo import CodeIndicateur, Couleur
from usine.contrats.schemas import enum_polars
from usine.contrats.tickets import Gravite, StatutAnomalie, StatutCertification, StatutTest

SCHEMA_ESSAI = SchemaTable("SCHEMA_ESSAI", {"date": pl.Date(), "nombre": pl.Int64()})


def test_valide_et_reordonne() -> None:
    df = pl.DataFrame(
        {"nombre": [1], "date": [date(2026, 10, 12)]},
        schema={"nombre": pl.Int64, "date": pl.Date},
    )
    resultat = valider(df, SCHEMA_ESSAI)
    assert resultat.columns == ["date", "nombre"]


def test_table_vide_valide() -> None:
    df = pl.DataFrame(schema=dict(SCHEMA_ESSAI.colonnes))
    assert valider(df, SCHEMA_ESSAI).is_empty()


def test_colonne_absente() -> None:
    df = pl.DataFrame({"date": [date(2026, 10, 12)]})
    with pytest.raises(UsineErreur) as erreur:
        valider(df, SCHEMA_ESSAI)
    assert "SCHEMA_ESSAI" in str(erreur.value)
    assert "nombre" in str(erreur.value)


def test_mauvais_type() -> None:
    df = pl.DataFrame(
        {"date": [date(2026, 10, 12)], "nombre": [1]},
        schema={"date": pl.Date, "nombre": pl.Int32},
    )
    with pytest.raises(UsineErreur) as erreur:
        valider(df, SCHEMA_ESSAI)
    message = str(erreur.value)
    assert "SCHEMA_ESSAI" in message
    assert "nombre" in message
    assert "Int32" in message


def test_colonne_en_trop() -> None:
    df = pl.DataFrame(
        {"date": [date(2026, 10, 12)], "nombre": [1], "bruit": ["x"]},
        schema={"date": pl.Date, "nombre": pl.Int64, "bruit": pl.Utf8},
    )
    with pytest.raises(UsineErreur) as erreur:
        valider(df, SCHEMA_ESSAI)
    assert "SCHEMA_ESSAI" in str(erreur.value)
    assert "bruit" in str(erreur.value)


def test_fuseau_des_instants_controle() -> None:
    schema = SchemaTable("SCHEMA_INSTANT", {"h": pl.Datetime("us", "UTC")})
    df = pl.DataFrame({"h": []}, schema={"h": pl.Datetime("us")})
    with pytest.raises(UsineErreur, match="SCHEMA_INSTANT"):
        valider(df, schema)


def test_pas_un_dataframe() -> None:
    with pytest.raises(UsineErreur, match="SCHEMA_ESSAI"):
        valider({"date": []}, SCHEMA_ESSAI)  # type: ignore[arg-type]


def test_enum_polars() -> None:
    assert enum_polars(Gravite) == pl.Enum(["bloquante", "majeure", "mineure"])
    assert enum_polars(StatutTest, StatutCertification).categories.to_list() == [
        "ok",
        "ko",
        "non_execute",
        "accordee",
        "reservee",
        "refusee",
    ]
    with pytest.raises(UsineErreur, match="double"):
        enum_polars(Gravite, Gravite)


def test_colonne_d_enumeration_en_texte_refusee() -> None:
    schema = SchemaTable("SCHEMA_GRAVITE", {"gravite": enum_polars(Gravite)})
    df = pl.DataFrame({"gravite": ["bloquante"]})
    with pytest.raises(UsineErreur) as erreur:
        valider(df, schema)
    assert "SCHEMA_GRAVITE" in str(erreur.value)
    assert "gravite" in str(erreur.value)
    with pytest.raises(pl.exceptions.InvalidOperationError):
        df.with_columns(
            pl.col("gravite").replace("bloquante", "Bloquante").cast(enum_polars(Gravite))
        )


def test_colonnes_d_enumeration_des_schemas() -> None:
    assert SCHEMA_INDICATEUR.colonnes["couleur"] == enum_polars(Couleur)
    assert SCHEMA_INDICATEUR.colonnes["code"] == enum_polars(CodeIndicateur)
    assert SCHEMA_INDICATEUR.colonnes["statut"] == enum_polars(StatutIndicateur)
    assert SCHEMA_INSTANTANE.colonnes["statut"] == enum_polars(
        StatutAnomalie, StatutTest, StatutCertification
    )
    assert isinstance(SCHEMA_REPARTITION_CAUSES.colonnes["cause_racine"], pl.Enum)


def test_pire_couleur_par_gravite_dans_polars() -> None:
    couleurs = pl.Series(
        "couleur", ["rouge", "vert", "orange", "jaune"], dtype=enum_polars(Couleur)
    )
    assert couleurs.sort().to_list() == ["vert", "jaune", "orange", "rouge"]
    assert couleurs.max() == "rouge"
    assert pl.Series(["vert", "orange"], dtype=enum_polars(Couleur)).max() == "orange"


def test_schema_gele() -> None:
    with pytest.raises(TypeError):
        SCHEMA_ESSAI.colonnes["x"] = pl.Int64()  # type: ignore[index]


SCHEMA_NON_NUL = SchemaTable(
    "SCHEMA_NON_NUL", {"date": pl.Date(), "nombre": pl.Int64()}, frozenset({"nombre"})
)


def test_colonne_non_nulle_refusee() -> None:
    """D3 : une valeur nulle dans une colonne de `non_nulles` nomme schéma et colonne."""
    df = pl.DataFrame(
        {"date": [None, date(2026, 10, 12)], "nombre": [1, None]},
        schema={"date": pl.Date, "nombre": pl.Int64},
    )
    with pytest.raises(UsineErreur) as erreur:
        valider(df, SCHEMA_NON_NUL)
    message = str(erreur.value)
    assert "SCHEMA_NON_NUL" in message
    assert "« nombre »" in message
    sans_nul = df.with_columns(pl.col("nombre").fill_null(0))
    assert valider(sans_nul, SCHEMA_NON_NUL).height == 2  # `date` reste nullable


def test_ligne_nulle_refusee_par_le_kpi() -> None:
    df = pl.DataFrame([{c: None for c in SCHEMA_KPI.colonnes}], schema=dict(SCHEMA_KPI.colonnes))
    with pytest.raises(UsineErreur, match="SCHEMA_KPI"):
        valider(df, SCHEMA_KPI)


def test_non_nulles_inconnue_refusee() -> None:
    with pytest.raises(UsineErreur, match="inconnue"):
        SchemaTable("SCHEMA_X", {"a": pl.Utf8()}, frozenset({"b"}))
