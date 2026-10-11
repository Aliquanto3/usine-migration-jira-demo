"""`ConsultationPassage` minimal (Story 0.5) : lecture validée de `tickets_etats`."""

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from usine.consultation.passage import MESSAGE_STORY_0_6, ConsultationPassage
from usine.contrats.erreurs import UsineErreur
from usine.contrats.tickets import SCHEMA_TICKET_ETAT
from usine.contrats.versions import CLE_VERSION, CONTRATS_VERSION
from usine.ports.consultation import Consultation

LUNDI = date(2026, 10, 5)
MARDI = date(2026, 10, 6)


def _etats() -> pl.DataFrame:
    lignes = {
        "date": [LUNDI, MARDI, MARDI],
        "cle_ticket": ["DEMO-1", "DEMO-1", "DEMO-2"],
        "type_ticket": ["anomalie"] * 3,
        "entite": ["ENT-A"] * 3,
        "vague": ["V1"] * 3,
        "domaine": ["paie"] * 3,
        "gravite": ["bloquante"] * 3,
        "phase": ["recette"] * 3,
        "statut": ["nouvelle"] * 3,
        "statut_test": [None] * 3,
        "statut_certification": [None] * 3,
        "date_derniere_entree": [LUNDI, LUNDI, MARDI],
    }
    return pl.DataFrame(lignes, schema=dict(SCHEMA_TICKET_ETAT.colonnes))


def _ecrire(repertoire: Path, table: pl.DataFrame, version: str | None = CONTRATS_VERSION) -> None:
    metadonnees = {} if version is None else {CLE_VERSION: version}
    table.write_parquet(repertoire / "tickets_etats.parquet", metadata=metadonnees)


def test_lecture_par_date(tmp_path: Path) -> None:
    _ecrire(tmp_path, _etats())
    consultation = ConsultationPassage(tmp_path)
    assert isinstance(consultation, Consultation)
    assert consultation.tickets_etats(LUNDI)["cle_ticket"].to_list() == ["DEMO-1"]
    assert consultation.tickets_etats()["cle_ticket"].to_list() == ["DEMO-1", "DEMO-2"]
    assert consultation.tickets_etats(date(2026, 10, 2)).is_empty()


def test_table_vide(tmp_path: Path) -> None:
    _ecrire(tmp_path, _etats().clear())
    assert ConsultationPassage(tmp_path).tickets_etats().is_empty()


def test_fichier_absent(tmp_path: Path) -> None:
    with pytest.raises(UsineErreur, match=r"tickets_etats.parquet"):
        ConsultationPassage(tmp_path).tickets_etats()


@pytest.mark.parametrize(("version", "motif"), [(None, "absente"), ("2.0.0", "incompatible")])
def test_version_refusee(tmp_path: Path, version: str | None, motif: str) -> None:
    _ecrire(tmp_path, _etats(), version)
    with pytest.raises(UsineErreur, match=motif):
        ConsultationPassage(tmp_path).tickets_etats()


def test_schema_refuse(tmp_path: Path) -> None:
    _ecrire(tmp_path, _etats().drop("domaine"))
    with pytest.raises(UsineErreur, match="SCHEMA_TICKET_ETAT"):
        ConsultationPassage(tmp_path).tickets_etats()


def test_lectures_de_la_story_0_6(tmp_path: Path) -> None:
    consultation = ConsultationPassage(tmp_path)
    for lecture in (
        consultation.dernier_passage,
        consultation.manifeste,
        consultation.dates_disponibles,
        consultation.meteo,
        consultation.evolution_meteo,
        consultation.instantanes,
        consultation.indicateurs,
        consultation.kpi,
        consultation.tendances,
        consultation.textes_tickets,
        consultation.anomalies,
        consultation.previsions,
        consultation.risques,
        consultation.classification,
        consultation.repartition_causes,
        consultation.explications,
        consultation.narrations,
        consultation.traces,
    ):
        with pytest.raises(UsineErreur, match=MESSAGE_STORY_0_6):
            lecture()
    with pytest.raises(UsineErreur, match=MESSAGE_STORY_0_6):
        consultation.url_ticket("DEMO-1")
