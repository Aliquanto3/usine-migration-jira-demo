"""`domaine.causes.repartition` : répartition des Causes racines par Entité (Story 6.5)."""

from datetime import date

import polars as pl
import pytest

from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import SCHEMA_REPARTITION_CAUSES, SortieClassification
from usine.contrats.schemas import valider
from usine.contrats.tickets import CauseRacine
from usine.domaine.causes.repartition import repartition

D = date(2026, 10, 9)


def _anomalies(lignes: list[tuple[str, str | None]]) -> pl.DataFrame:
    return pl.DataFrame(
        {"cle_ticket": [c for c, _ in lignes], "entite": [e for _, e in lignes]},
        schema={"cle_ticket": pl.Utf8(), "entite": pl.Utf8()},
    )


def _classe(cle: str, cause: CauseRacine) -> SortieClassification:
    return SortieClassification(cle_ticket=cle, cause_racine=cause)


CLASSIFICATION = (
    _classe("DEMO-1", CauseRacine.parametrage),
    _classe("DEMO-2", CauseRacine.reprise_donnees),
    _classe("DEMO-3", CauseRacine.parametrage),
    _classe("DEMO-4", CauseRacine.environnement),
)
ANOMALIES = _anomalies(
    [("DEMO-1", "ENT-A"), ("DEMO-2", "ENT-A"), ("DEMO-3", "ENT-A"), ("DEMO-4", "ENT-B")]
)


def test_nominal() -> None:
    table = repartition(D, CLASSIFICATION, ANOMALIES)
    valider(table, SCHEMA_REPARTITION_CAUSES)
    assert table.rows() == [
        (D, "ENT-A", "parametrage", 2, pytest.approx(2 / 3)),
        (D, "ENT-A", "reprise_donnees", 1, pytest.approx(1 / 3)),
        (D, "ENT-B", "environnement", 1, 1.0),
    ]
    sommes = table.group_by("entite").agg(pl.col("part").sum())
    assert all(s == pytest.approx(1.0) for s in sommes["part"])


def test_anomalie_ouverte_non_classee_ignoree() -> None:
    anomalies = _anomalies([("DEMO-1", "ENT-A"), ("DEMO-9", "ENT-A")])
    table = repartition(D, CLASSIFICATION[:1], anomalies)
    assert table.rows() == [(D, "ENT-A", "parametrage", 1, 1.0)]


def test_classification_sans_anomalie_ouverte_ignoree() -> None:
    anomalies = _anomalies([("DEMO-1", "ENT-A")])
    table = repartition(D, CLASSIFICATION, anomalies)
    assert table.rows() == [(D, "ENT-A", "parametrage", 1, 1.0)]


def test_anomalie_sans_entite_ignoree() -> None:
    anomalies = _anomalies([("DEMO-1", ""), ("DEMO-2", None), ("DEMO-3", "ENT-A")])
    table = repartition(D, CLASSIFICATION, anomalies)
    assert table.rows() == [(D, "ENT-A", "parametrage", 1, 1.0)]


def test_aucune_classification() -> None:
    table = repartition(D, (), ANOMALIES)
    assert table.is_empty()
    assert table.schema == pl.Schema(SCHEMA_REPARTITION_CAUSES.colonnes)


def test_tri_et_permutation() -> None:
    classification = (
        _classe("DEMO-1", CauseRacine.reprise_donnees),
        _classe("DEMO-2", CauseRacine.environnement),
        _classe("DEMO-3", CauseRacine.parametrage),
        _classe("DEMO-4", CauseRacine.parametrage),
        _classe("DEMO-5", CauseRacine.donnee_test),
    )
    anomalies = _anomalies(
        [
            ("DEMO-1", "ENT-B"),
            ("DEMO-2", "ENT-B"),
            ("DEMO-3", "ENT-B"),
            ("DEMO-4", "ENT-B"),
            ("DEMO-5", "ENT-A"),
        ]
    )
    table = repartition(D, classification, anomalies)
    assert [(e, c, n) for _, e, c, n, _ in table.rows()] == [
        ("ENT-A", "donnee_test", 1),
        ("ENT-B", "parametrage", 2),
        ("ENT-B", "environnement", 1),
        ("ENT-B", "reprise_donnees", 1),
    ]
    permutee = repartition(D, classification[::-1], anomalies.reverse())
    assert permutee.equals(table)


def test_purete() -> None:
    anomalies = ANOMALIES.clone()
    classification = tuple(CLASSIFICATION)
    premiere = repartition(D, classification, anomalies)
    seconde = repartition(D, classification, anomalies)
    assert premiere.equals(seconde)
    assert anomalies.equals(ANOMALIES)
    assert classification == CLASSIFICATION


def test_colonnes_manquantes() -> None:
    with pytest.raises(UsineErreur, match="entite"):
        repartition(D, CLASSIFICATION, pl.DataFrame({"cle_ticket": ["DEMO-1"]}))
