"""`ConsultationPassage` : lectures du port `Consultation` sur un Passage (Stories 0.5, 0.6)."""

import json
import logging
import shutil
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from tests.unit.chaine.environnement import DATE_ARRETE, horloge_figee, preparer_racine
from usine.composition import PassageLance, lancer_rapport
from usine.consultation.passage import ConsultationPassage
from usine.contrats.agent import AnomalieResume
from usine.contrats.calcul import SCHEMA_KPI
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import SortieExplication
from usine.contrats.meteo import Couleur
from usine.contrats.passage import EnveloppeFichier
from usine.contrats.tickets import SCHEMA_TICKET_ETAT, StatutAnomalie
from usine.contrats.trace import EntreeTrace, TypeTrace
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


# --- tickets_etats (Story 0.5) ---


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


def test_fichier_absent_table_vide(tmp_path: Path) -> None:
    table = ConsultationPassage(tmp_path).tickets_etats(LUNDI)
    assert table.is_empty()
    assert table.schema == dict(SCHEMA_TICKET_ETAT.colonnes)


@pytest.mark.parametrize(("version", "motif"), [(None, "absente"), ("2.0.0", "incompatible")])
def test_version_refusee(tmp_path: Path, version: str | None, motif: str) -> None:
    _ecrire(tmp_path, _etats(), version)
    with pytest.raises(UsineErreur, match=motif):
        ConsultationPassage(tmp_path).tickets_etats()


def test_schema_refuse(tmp_path: Path) -> None:
    _ecrire(tmp_path, _etats().drop("domaine"))
    with pytest.raises(UsineErreur, match="SCHEMA_TICKET_ETAT"):
        ConsultationPassage(tmp_path).tickets_etats()


# --- Passage publié (graine 42, Date d'arrêté 2026-10-09) ---


@pytest.fixture(scope="module")
def racine(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return preparer_racine(tmp_path_factory.mktemp("racine"))


@pytest.fixture(scope="module")
def lance(racine: Path) -> PassageLance:
    return lancer_rapport(racine, DATE_ARRETE, horloge_figee(), lambda: "aaaaaa")


@pytest.fixture
def passage(lance: PassageLance, tmp_path: Path) -> Path:
    """Copie privée du Passage publié, modifiable par le test."""
    copie = tmp_path / "passages" / DATE_ARRETE.isoformat() / lance.repertoire.name
    shutil.copytree(lance.repertoire, copie)
    return copie


def test_manifeste_et_dates(lance: PassageLance) -> None:
    consultation = ConsultationPassage(lance.repertoire)
    assert consultation.manifeste() == lance.manifeste
    dates = consultation.dates_disponibles()
    assert dates[-1] == DATE_ARRETE
    assert list(dates) == sorted(set(dates))


def test_meteo_et_evolution(lance: PassageLance) -> None:
    consultation = ConsultationPassage(lance.repertoire)
    meteos = consultation.meteo()
    assert [m.entite for m in meteos] == ["ENT-A", "ENT-B"]
    assert all(m.date_arrete == DATE_ARRETE for m in meteos)
    assert [m.entite for m in consultation.meteo(entite="ENT-B")] == ["ENT-B"]
    veille = consultation.meteo(date(2026, 10, 8))
    evolutions = consultation.evolution_meteo()
    assert [e.entite for e in evolutions] == ["ENT-A", "ENT-B"]
    for evolution, meteo, meteo_j1 in zip(evolutions, meteos, veille, strict=True):
        assert (evolution.date_j1, evolution.date_j5) == (date(2026, 10, 8), date(2026, 10, 2))
        assert evolution.couleur is meteo.couleur
        assert evolution.couleur_j1 is meteo_j1.couleur
        assert isinstance(evolution.couleur_j5, Couleur)
        meteo_j5 = consultation.meteo(date(2026, 10, 2), entite=evolution.entite)
        assert evolution.couleur_j5 is meteo_j5[0].couleur


def test_evolution_hors_historique(lance: PassageLance) -> None:
    premiere = ConsultationPassage(lance.repertoire).dates_disponibles()[0]
    evolutions = ConsultationPassage(lance.repertoire).evolution_meteo(premiere)
    assert all(e.couleur_j1 is None and e.couleur_j5 is None for e in evolutions)


def test_tables_filtrees(lance: PassageLance) -> None:
    consultation = ConsultationPassage(lance.repertoire)
    instantanes = consultation.instantanes(entite="ENT-A")
    assert set(instantanes["date"].to_list()) == {DATE_ARRETE}
    assert set(instantanes["entite"].to_list()) == {"ENT-A"}
    indicateurs = consultation.indicateurs(date(2026, 10, 8))
    assert set(indicateurs["date"].to_list()) == {date(2026, 10, 8)}


def test_fichiers_absents_palier_1(lance: PassageLance) -> None:
    consultation = ConsultationPassage(lance.repertoire)
    kpi = consultation.kpi()
    assert kpi.is_empty()
    assert kpi.schema == dict(SCHEMA_KPI.colonnes)
    assert consultation.tendances().is_empty()
    assert consultation.textes_tickets().is_empty()
    assert consultation.explications() == ()
    assert consultation.narrations() == ()
    assert consultation.classification() == ()
    assert consultation.repartition_causes().is_empty()
    assert consultation.previsions() == ()
    assert consultation.risques() == ()
    assert consultation.traces() == ()


def test_anomalies(lance: PassageLance) -> None:
    consultation = ConsultationPassage(lance.repertoire)
    toutes = consultation.anomalies()
    etats = consultation.tickets_etats().filter(
        (pl.col("type_ticket") == "anomalie") & ~pl.col("statut").is_in(["fermee", "rejetee"])
    )
    assert toutes.total == len(toutes.anomalies) == etats.height > 1
    numeros = [int(a.cle_ticket.split("-")[1]) for a in toutes.anomalies]
    assert numeros == sorted(numeros)
    assert all(
        a.statut not in (StatutAnomalie.fermee, StatutAnomalie.rejetee) for a in toutes.anomalies
    )
    limitees = consultation.anomalies(limite=2)
    assert limitees.anomalies == toutes.anomalies[:2]
    assert limitees.total == toutes.total
    premiere = toutes.anomalies[0]
    filtres: list[tuple[dict[str, Any], Callable[[AnomalieResume], bool]]] = [
        (
            {"entite": premiere.entite, "gravite": premiere.gravite},
            lambda a: (a.entite, a.gravite) == (premiere.entite, premiere.gravite),
        ),
        ({"phase": premiere.phase}, lambda a: a.phase is premiere.phase),
        ({"domaine": premiere.domaine}, lambda a: a.domaine == premiere.domaine),
    ]
    for arguments, garde in filtres:
        attendues = tuple(a for a in toutes.anomalies if garde(a))
        assert attendues, arguments
        filtrees = consultation.anomalies(**arguments)
        assert (filtrees.anomalies, filtrees.total) == (attendues, len(attendues)), arguments
    ligne = etats.filter(pl.col("cle_ticket") == premiere.cle_ticket).row(0, named=True)
    entree: date = ligne["date_derniere_entree"]
    attendu = sum(1 for j in pl.date_range(entree, DATE_ARRETE, eager=True) if j.weekday() < 5)
    assert premiere.age_jours_ouvres == attendu - 1


def test_dernier_passage(passage: Path) -> None:
    racine = passage.parents[1]
    manifeste = json.loads((passage / "manifeste.json").read_text(encoding="utf-8"))

    def copier(jour: str, passage_id: str, fin: str) -> Path:
        cible = racine / jour / passage_id
        shutil.copytree(passage, cible)
        contenu = {**manifeste, "passage_id": passage_id, "date_arrete": jour}
        contenu["horodatage_fin"] = fin
        (cible / "manifeste.json").write_text(json.dumps(contenu), encoding="utf-8")
        return cible

    copier("2026-10-08", "20261013T070000Z-000001", "2026-10-13T08:00:00Z")
    copier("2026-10-09", "20261012T090000Z-000002", "2026-10-12T09:30:00Z")
    en_cours = racine / ".en-cours-20261014T070000Z-000003"
    shutil.copytree(passage, en_cours)
    echec = racine / "echecs" / "20261014T070000Z-000004"
    shutil.copytree(passage, echec)
    dernier = ConsultationPassage(passage).dernier_passage()
    assert dernier is not None
    assert dernier.passage_id == "20261012T090000Z-000002"
    # Même résultat depuis un Passage en construction.
    assert ConsultationPassage(en_cours).dernier_passage() == dernier


def test_dernier_passage_ignore_un_manifeste_illisible(
    passage: Path, caplog: pytest.LogCaptureFixture
) -> None:
    racine = passage.parents[1]
    mauvais = racine / "2026-10-12" / "20261013T070000Z-00000f"
    shutil.copytree(passage, mauvais)
    contenu = json.loads((mauvais / "manifeste.json").read_text(encoding="utf-8"))
    contenu[CLE_VERSION] = "1.0.0"
    (mauvais / "manifeste.json").write_text(json.dumps(contenu), encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        dernier = ConsultationPassage(passage).dernier_passage()
    assert dernier is not None
    assert dernier.passage_id == passage.name
    assert str(mauvais / "manifeste.json") in caplog.text


def test_date_du_passage_en_construction(lance: PassageLance, tmp_path: Path) -> None:
    """Sans manifeste, la Date d'arrêté donnée au lecteur fait foi."""
    en_cours = tmp_path / ".en-cours-20261012T073000Z-aaaaaa"
    shutil.copytree(lance.repertoire, en_cours)
    (en_cours / "manifeste.json").unlink()
    veille = date(2026, 10, 8)
    consultation = ConsultationPassage(en_cours, date_arrete=veille)
    assert {m.date_arrete for m in consultation.meteo()} == {veille}
    assert set(consultation.tickets_etats()["date"].to_list()) == {veille}


def _trace() -> EntreeTrace:
    return EntreeTrace(
        type_trace=TypeTrace.prevision,
        horodatage=datetime(2026, 10, 12, 7, 30, tzinfo=UTC),
        passage_id="20261012T073000Z-aaaaaa",
        date_arrete=DATE_ARRETE,
        entite="ENT-A",
        version_grille="abc",
        version_donnees="def",
        entree_pseudonymisee="entrée",
        sortie="sortie",
    )


def test_traces(passage: Path) -> None:
    (passage / "trace").mkdir()
    chemin = passage / "trace" / "llm.jsonl"
    chemin.write_text(_trace().model_dump_json() + "\n", encoding="utf-8")
    assert ConsultationPassage(passage).traces() == (_trace(),)
    chemin.write_text(_trace().model_dump_json() + "\n{}\n", encoding="utf-8")
    with pytest.raises(UsineErreur, match=r"llm\.jsonl, ligne 2"):
        ConsultationPassage(passage).traces()


def test_explications_selon_palier(passage: Path) -> None:
    explication = SortieExplication(
        date_arrete=DATE_ARRETE,
        entite="ENT-A",
        texte="Texte.",
        citations=("DEMO-6",),
        brouillon_commentaire="Brouillon.",
    )
    modele = EnveloppeFichier[tuple[SortieExplication, ...]]
    enveloppe = modele(passage_id=passage.name, date_arrete=DATE_ARRETE, contenu=(explication,))
    (passage / "llm").mkdir()
    (passage / "llm" / "explications.json").write_text(
        enveloppe.model_dump_json(), encoding="utf-8"
    )
    consultation = ConsultationPassage(passage)
    assert consultation.explications(palier=1) == ()
    assert consultation.explications(palier=2) == (explication,)
    assert consultation.explications(entite="ENT-B") == ()


def test_aucun_passage(tmp_path: Path) -> None:
    racine = tmp_path / "passages"
    assert ConsultationPassage(tmp_path, racine_passages=racine).dernier_passage() is None
    racine.mkdir()
    assert ConsultationPassage(tmp_path, racine_passages=racine).dernier_passage() is None


def test_manifeste_absent(tmp_path: Path) -> None:
    with pytest.raises(UsineErreur, match=r"manifeste\.json"):
        ConsultationPassage(tmp_path).manifeste()


def test_version_etrangere_meteo(passage: Path) -> None:
    chemin = passage / "meteo.json"
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    contenu[CLE_VERSION] = "1.0.0"
    chemin.write_text(json.dumps(contenu), encoding="utf-8")
    with pytest.raises(UsineErreur, match=r"meteo\.json.*1\.0\.0.*0\.1\.0"):
        ConsultationPassage(passage).meteo(DATE_ARRETE)


def test_version_etrangere_manifeste(passage: Path) -> None:
    chemin = passage / "manifeste.json"
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    contenu[CLE_VERSION] = "1.0.0"
    chemin.write_text(json.dumps(contenu), encoding="utf-8")
    with pytest.raises(UsineErreur, match=r"manifeste\.json.*1\.0\.0"):
        ConsultationPassage(passage).manifeste()


def test_url_ticket(tmp_path: Path) -> None:
    avec = ConsultationPassage(tmp_path, url_jira="https://demo-usine.atlassian.net/")
    assert avec.url_ticket("DEMO-7") == "https://demo-usine.atlassian.net/browse/DEMO-7"
    assert ConsultationPassage(tmp_path).url_ticket("DEMO-7") is None
