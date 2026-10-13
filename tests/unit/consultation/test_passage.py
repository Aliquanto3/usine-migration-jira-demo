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

from tests.unit.chaine.environnement import (
    DATE_ARRETE,
    contenu_previsions,
    horloge_figee,
    preparer_racine,
)
from usine.composition import PassageLance, construire_rapport, lancer_rapport
from usine.config import charger_yaml
from usine.consultation.passage import ConsultationPassage
from usine.consultation.prevision import previsions_calculees
from usine.contrats.agent import AnomalieResume
from usine.contrats.calcul import SCHEMA_KPI
from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import (
    SCHEMA_REPARTITION_CAUSES,
    SortieClassification,
    SortieExplication,
    SortieNarration,
)
from usine.contrats.meteo import Couleur
from usine.contrats.passage import EnveloppeFichier
from usine.contrats.prevision import ContenuPrevisions
from usine.contrats.tickets import SCHEMA_TICKET_ETAT, CauseRacine, StatutAnomalie
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


def test_palier_1_kpi_et_textes_presents_autres_fichiers_absents(lance: PassageLance) -> None:
    consultation = ConsultationPassage(lance.repertoire)
    kpi = consultation.kpi()  # écrit par `kpi` (Story 5.1)
    assert not kpi.is_empty()
    assert set(kpi["date"].to_list()) == {DATE_ARRETE}
    assert kpi.schema == dict(SCHEMA_KPI.colonnes)
    assert not consultation.tendances().is_empty()
    assert consultation.textes_tickets().height > 0  # écrit par `instantanes` (Story 0.7)
    # Palier 1 : aucune sortie LLM ; `prevision` est câblée (Story 5.3) : traces de Prévision.
    assert consultation.explications() == ()
    assert consultation.narrations() == ()
    assert consultation.classification() == ()
    assert consultation.repartition_causes().is_empty()
    assert consultation.previsions()
    assert {t.type_trace for t in consultation.traces()} == {TypeTrace.prevision}


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
    contenu[CLE_VERSION] = "2.0.0"
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
    previsions = ConsultationPassage(passage).traces()  # `trace/previsions.jsonl` du Passage
    assert previsions
    chemin = passage / "trace" / "llm.jsonl"
    chemin.write_text(_trace().model_dump_json() + "\n", encoding="utf-8")
    # `trace/llm.jsonl`, puis `trace/previsions.jsonl`.
    assert ConsultationPassage(passage).traces() == (_trace(), *previsions)
    chemin.write_text(_trace().model_dump_json() + "\n{}\n", encoding="utf-8")
    with pytest.raises(UsineErreur, match=r"llm\.jsonl, ligne 2"):
        ConsultationPassage(passage).traces()


def _ecrire_sorties_llm(
    passage: Path, cle_classee: str = "DEMO-6", entite: str = "ENT-A"
) -> tuple[SortieExplication, SortieClassification, SortieNarration]:
    """Écrit `llm/*` (une sortie de `entite` chacun) et `repartition_causes.parquet` (`entite`)."""
    explication = SortieExplication(
        date_arrete=DATE_ARRETE,
        entite=entite,
        texte="Texte.",
        citations=(cle_classee,),
        brouillon_commentaire="Brouillon.",
    )
    classification = SortieClassification(
        cle_ticket=cle_classee, cause_racine=CauseRacine.parametrage
    )
    narration = SortieNarration(date_arrete=DATE_ARRETE, entite=entite, texte="Narration.")
    (passage / "llm").mkdir()
    for nom, type_contenu, contenu in (
        ("explications", tuple[SortieExplication, ...], (explication,)),
        ("classification", tuple[SortieClassification, ...], (classification,)),
        ("narrations", tuple[SortieNarration, ...], (narration,)),
    ):
        modele_llm = EnveloppeFichier[type_contenu]  # type: ignore[valid-type]
        (passage / "llm" / f"{nom}.json").write_text(
            modele_llm(
                passage_id=passage.name, date_arrete=DATE_ARRETE, contenu=contenu
            ).model_dump_json(),
            encoding="utf-8",
        )
    repartition = pl.DataFrame(
        {
            "date": [date(2026, 10, 8), DATE_ARRETE],
            "entite": [entite, entite],
            "cause_racine": ["parametrage", "parametrage"],
            "nombre": [2, 1],
            "part": [1.0, 1.0],
        },
        schema=dict(SCHEMA_REPARTITION_CAUSES.colonnes),
    )
    repartition.write_parquet(
        passage / "repartition_causes.parquet", metadata={CLE_VERSION: CONTRATS_VERSION}
    )
    return explication, classification, narration


def test_sorties_llm_selon_palier(passage: Path) -> None:
    explication, classification, narration = _ecrire_sorties_llm(passage)
    consultation = ConsultationPassage(passage)
    assert consultation.explications(palier=1) == ()
    assert consultation.explications(palier=2) == (explication,)
    assert consultation.explications(entite="ENT-B") == ()
    assert consultation.classification(palier=1) == ()
    assert consultation.classification(palier=2) == (classification,)
    assert consultation.narrations(palier=1) == ()
    assert consultation.narrations(palier=2) == (narration,)
    assert consultation.repartition_causes(palier=1).is_empty()
    # Seule la ligne de la Date d'arrêté du Passage est rendue.
    assert consultation.repartition_causes().rows() == [
        (DATE_ARRETE, "ENT-A", "parametrage", 1, 1.0)
    ]


def test_anomalies_passage_vide(tmp_path: Path) -> None:
    with pytest.raises(UsineErreur, match="indéterminable"):
        ConsultationPassage(tmp_path).anomalies()
    datee = ConsultationPassage(tmp_path, date_arrete=DATE_ARRETE).anomalies()
    assert (datee.date_arrete, datee.total) == (DATE_ARRETE, 0)


def test_anomalies_limite_negative(lance: PassageLance) -> None:
    with pytest.raises(UsineErreur, match="limite"):
        ConsultationPassage(lance.repertoire).anomalies(limite=-1)


def test_dernier_passage_ignore_un_rangement_incoherent(
    passage: Path, caplog: pytest.LogCaptureFixture
) -> None:
    racine = passage.parents[1]
    # Manifeste du Passage d'origine recopié sous une autre date et un autre identifiant.
    deplace = racine / "2026-10-13" / "20261014T070000Z-00000e"
    shutil.copytree(passage, deplace)
    # Nom de répertoire en forme ISO basique, refusé.
    basique = racine / "20261014" / passage.name
    shutil.copytree(passage, basique)
    contenu = json.loads((basique / "manifeste.json").read_text(encoding="utf-8"))
    contenu["date_arrete"] = "2026-10-14"
    (basique / "manifeste.json").write_text(json.dumps(contenu), encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        dernier = ConsultationPassage(passage).dernier_passage()
    assert dernier is not None
    assert dernier.passage_id == passage.name
    assert dernier.date_arrete == DATE_ARRETE
    assert str(deplace / "manifeste.json") in caplog.text


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
    contenu[CLE_VERSION] = "2.0.0"
    chemin.write_text(json.dumps(contenu), encoding="utf-8")
    with pytest.raises(UsineErreur, match=r"meteo\.json.*2\.0\.0.*1.9.0"):
        ConsultationPassage(passage).meteo(DATE_ARRETE)


def test_version_etrangere_manifeste(passage: Path) -> None:
    chemin = passage / "manifeste.json"
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    contenu[CLE_VERSION] = "2.0.0"
    chemin.write_text(json.dumps(contenu), encoding="utf-8")
    with pytest.raises(UsineErreur, match=r"manifeste\.json.*2\.0\.0"):
        ConsultationPassage(passage).manifeste()


def test_url_ticket(tmp_path: Path) -> None:
    avec = ConsultationPassage(tmp_path, url_jira="https://jira.example.invalid/")
    assert avec.url_ticket("DEMO-7") == "https://jira.example.invalid/browse/DEMO-7"
    assert ConsultationPassage(tmp_path).url_ticket("DEMO-7") is None


def test_dernier_passage_sans_classification_initiale(passage: Path) -> None:
    """FR-44 : la mesure écarte les Passages qui ont fait la classification initiale."""
    racine = passage.parents[1]
    manifeste = json.loads((passage / "manifeste.json").read_text(encoding="utf-8"))
    passage_id = "20261012T090000Z-000002"
    cible = racine / DATE_ARRETE.isoformat() / passage_id
    shutil.copytree(passage, cible)
    contenu = {
        **manifeste,
        "passage_id": passage_id,
        "horodatage_fin": "2026-10-12T09:30:00Z",
        "classification_initiale": True,
    }
    (cible / "manifeste.json").write_text(json.dumps(contenu), encoding="utf-8")
    consultation = ConsultationPassage(passage)
    tous = consultation.dernier_passage()
    assert tous is not None
    assert tous.passage_id == passage_id
    sans = consultation.dernier_passage(sans_classification_initiale=True)
    assert sans is not None
    assert sans.passage_id == passage.name
    assert not sans.classification_initiale


def test_anomalies_cause_proposee_selon_palier(passage: Path) -> None:
    """FR-46 : en Palier 1, aucune cause racine proposée n'est rendue."""
    premiere = ConsultationPassage(passage).anomalies().anomalies[0]
    classification = SortieClassification(
        cle_ticket=premiere.cle_ticket, cause_racine=CauseRacine.parametrage
    )
    modele = EnveloppeFichier[tuple[SortieClassification, ...]]
    enveloppe = modele(passage_id=passage.name, date_arrete=DATE_ARRETE, contenu=(classification,))
    (passage / "llm").mkdir()
    (passage / "llm" / "classification.json").write_text(
        enveloppe.model_dump_json(), encoding="utf-8"
    )
    consultation = ConsultationPassage(passage)
    palier_2 = consultation.anomalies()
    assert palier_2.anomalies[0].cause_racine_proposee is CauseRacine.parametrage
    palier_1 = consultation.anomalies(palier=1)
    assert palier_1.total == palier_2.total
    assert all(a.cause_racine_proposee is None for a in palier_1.anomalies)


# --- Story 5.2 : Prévisions, version du Passage, Palier 1 par Entité, URL Jira ---

VEILLE = date(2026, 10, 8)


def _ecrire_previsions(passage: Path, contenu: ContenuPrevisions) -> Path:
    modele = EnveloppeFichier[ContenuPrevisions]
    chemin = passage / "previsions.json"
    chemin.write_text(
        modele(passage_id=passage.name, date_arrete=DATE_ARRETE, contenu=contenu).model_dump_json(),
        encoding="utf-8",
    )
    return chemin


def _version_etrangere(chemin: Path) -> None:
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    contenu[CLE_VERSION] = "2.0.0"
    chemin.write_text(json.dumps(contenu), encoding="utf-8")


def test_previsions_presentes(passage: Path) -> None:
    du_jour = contenu_previsions(DATE_ARRETE, "grille")
    de_la_veille = contenu_previsions(VEILLE, "grille")
    _ecrire_previsions(
        passage,
        ContenuPrevisions(
            previsions=du_jour.previsions + de_la_veille.previsions,
            risques=du_jour.risques + de_la_veille.risques,
        ),
    )
    consultation = ConsultationPassage(passage)
    assert consultation.previsions() == du_jour.previsions
    assert consultation.previsions(VEILLE) == de_la_veille.previsions
    assert consultation.previsions(entite="ENT-A") == du_jour.previsions
    assert consultation.previsions(entite="ENT-B") == ()
    assert consultation.risques() == du_jour.risques
    assert consultation.risques(entite="ENT-B") == du_jour.risques
    assert consultation.risques(entite="ENT-A") == ()
    assert consultation.risques(VEILLE) == de_la_veille.risques


def test_previsions_passage_reel(lance: PassageLance) -> None:
    """Story 5.3 : une Prévision par Entité rouge et par Jour ouvré, une trace par élément."""
    assert (lance.repertoire / "previsions.json").is_file()
    consultation = ConsultationPassage(lance.repertoire)
    assert previsions_calculees(consultation.manifeste())
    dates = consultation.dates_disponibles()
    assert dates[-1] == DATE_ARRETE
    total = 0
    for jour in dates:
        rouges = [m.entite for m in consultation.meteo(jour) if m.couleur is Couleur.rouge]
        assert [p.entite for p in consultation.previsions(jour)] == rouges, jour
        non_rouges = {m.entite for m in consultation.meteo(jour)} - set(rouges)
        assert {r.entite for r in consultation.risques(jour)} <= non_rouges, jour
        total += len(consultation.previsions(jour)) + len(consultation.risques(jour))
    assert [p.entite for p in consultation.previsions()] == ["ENT-B"]  # flux scripté (1.2)
    assert consultation.previsions(entite="ENT-B") == consultation.previsions()
    traces = consultation.traces()
    assert len(traces) == total
    assert {t.passage_id for t in traces} == {lance.manifeste.passage_id}


def test_previsions_passage_vide(tmp_path: Path) -> None:
    consultation = ConsultationPassage(tmp_path)
    assert consultation.previsions() == ()
    assert consultation.risques() == ()


@pytest.mark.parametrize(
    "lecture",
    [
        lambda c: c.kpi(DATE_ARRETE),
        lambda c: c.traces(),
        lambda c: c.previsions(),
        lambda c: c.meteo(),
        lambda c: c.tickets_etats(DATE_ARRETE),
        lambda c: c.explications(palier=1),
        lambda c: c.repartition_causes(palier=1),
    ],
    ids=[
        "kpi",
        "traces",
        "previsions",
        "meteo",
        "tickets_etats",
        "explications_palier_1",
        "repartition_causes_palier_1",
    ],
)
def test_manifeste_majeur_etranger_refuse_chaque_lecture(
    passage: Path, lecture: Callable[[ConsultationPassage], object]
) -> None:
    """AD-2 : le manifeste fait foi pour tout le Passage, même si ses fichiers sont en 1.x."""
    _ecrire_previsions(passage, contenu_previsions(DATE_ARRETE, "grille"))
    _version_etrangere(passage / "manifeste.json")
    with pytest.raises(UsineErreur, match=r"manifeste\.json.*2\.0\.0"):
        lecture(ConsultationPassage(passage))


def test_previsions_majeur_etranger(passage: Path) -> None:
    _version_etrangere(_ecrire_previsions(passage, contenu_previsions(DATE_ARRETE, "grille")))
    with pytest.raises(UsineErreur, match=r"previsions\.json.*2\.0\.0"):
        ConsultationPassage(passage).previsions()


def test_palier_1_par_entite(passage: Path) -> None:
    """FR-46 : en Palier 1, rien de LLM pour l'Entité ; le déterministe ne change pas.

    ENT-B (Scénario B, enlisée) a des bloquantes ouvertes à la Date d'arrêté ; sur le Programme
    réduit, ENT-A n'a plus de création après la semaine 1 (Story 4.5 : les bloquantes
    scriptées de B prennent les créations de chaque semaine)."""
    entite = "ENT-B"
    ouvertes = ConsultationPassage(passage).anomalies(entite=entite).anomalies
    assert ouvertes, "aucune Anomalie ouverte ENT-B dans le Passage d'essai"
    premiere = ouvertes[0]
    explication, _, narration = _ecrire_sorties_llm(passage, premiere.cle_ticket, entite)
    consultation = ConsultationPassage(passage)
    # Palier 2 : les sorties de l'Entité existent bien.
    assert consultation.explications(entite=entite) == (explication,)
    assert consultation.narrations(entite=entite) == (narration,)
    assert not consultation.repartition_causes(entite=entite).is_empty()
    palier_2 = consultation.anomalies(entite=entite)
    assert palier_2.anomalies[0].cause_racine_proposee is CauseRacine.parametrage
    # Palier 1 : sorties LLM vides ou `None`.
    assert consultation.explications(entite=entite, palier=1) == ()
    assert consultation.narrations(entite=entite, palier=1) == ()
    assert consultation.repartition_causes(entite=entite, palier=1).is_empty()
    palier_1 = consultation.anomalies(entite=entite, palier=1)
    # Lectures déterministes identiques, cause racine proposée exceptée.
    assert palier_1.total == palier_2.total
    assert palier_1.anomalies == tuple(
        a.model_copy(update={"cause_racine_proposee": None}) for a in palier_2.anomalies
    )


def test_url_ticket_par_la_composition(
    racine: Path, lance: PassageLance, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L'URL vient de `config/jira.yaml` via la composition ; `None` en Mode repli."""
    url_site = charger_yaml(racine / "config" / "jira.yaml", ConfigJira).url_site
    for variable in ("USINE_MODE_REPLI", "JIRA_EMAIL", "JIRA_TOKEN_LECTURE", "JIRA_DC_PAT"):
        monkeypatch.delenv(variable, raising=False)
    fabrique = construire_rapport(racine).fabrique_consultation(DATE_ARRETE)
    assert fabrique(lance.repertoire).url_ticket("DEMO-123") == (
        f"{str(url_site).rstrip('/')}/browse/DEMO-123"
    )
    monkeypatch.setenv("USINE_MODE_REPLI", "1")
    repli = construire_rapport(racine).fabrique_consultation(DATE_ARRETE)
    assert repli(lance.repertoire).url_ticket("DEMO-123") is None
