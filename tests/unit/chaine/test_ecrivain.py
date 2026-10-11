"""`EcrivainPassage` : construction, publication et abandon d'un Passage (Story 0.5)."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest

from tests.unit.chaine.environnement import INSTANT, horloge_figee
from usine.chaine.ecrivain import EcrivainPassage
from usine.contrats.calcul import SCHEMA_INDICATEUR
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import Couleur, MeteoEntite
from usine.contrats.passage import (
    Etape,
    EvenementProgression,
    ExecutionEtape,
    ManifestePassage,
    StatutEtape,
    lire_enveloppe,
)
from usine.contrats.trace import EntreeTrace, TypeTrace
from usine.contrats.versions import CLE_VERSION, CONTRATS_VERSION

ID = "20261012T073000Z-abc123"
DATE = date(2026, 10, 9)


@pytest.fixture
def ecrivain(tmp_path: Path) -> EcrivainPassage:
    ecrivain = EcrivainPassage(tmp_path / "sorties", horloge_figee())
    ecrivain.commencer(ID, DATE)
    return ecrivain


def _indicateurs() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "date": [DATE],
            "entite": ["ENT-A"],
            "code": ["IND-1"],
            "statut": ["evalue"],
            "motif": [""],
            "numerateur": [0],
            "denominateur": [1],
            "couleur": ["vert"],
        },
        schema=dict(SCHEMA_INDICATEUR.colonnes),
    )


def _manifeste(passage_id: str = ID) -> ManifestePassage:
    return ManifestePassage(
        passage_id=passage_id,
        date_arrete=DATE,
        palier=1,
        source="journal",
        horodatage_debut=INSTANT,
        horodatage_fin=INSTANT,
        version_grille="abcdef012345",
        version_donnees="0" * 64,
        cout_llm_eur=Decimal(0),
        nb_alignements=0,
        nb_tickets=0,
        etapes=(
            ExecutionEtape(
                etape=Etape.extraction,
                statut=StatutEtape.reussie,
                horodatage_debut=INSTANT,
                horodatage_fin=INSTANT,
            ),
        ),
    )


def test_commencer(ecrivain: EcrivainPassage, tmp_path: Path) -> None:
    assert ecrivain.repertoire == tmp_path / "sorties" / "passages" / f".en-cours-{ID}"
    assert ecrivain.repertoire.is_dir()
    with pytest.raises(UsineErreur, match="déjà engagé"):
        ecrivain.commencer(ID, DATE)


def test_table_parquet_avec_version(ecrivain: EcrivainPassage) -> None:
    ecrivain.ecrire({"indicateurs": _indicateurs()})
    chemin = ecrivain.repertoire / "indicateurs.parquet"
    assert pl.read_parquet_metadata(chemin)[CLE_VERSION] == CONTRATS_VERSION
    assert pl.read_parquet(chemin).equals(_indicateurs())
    assert "indicateurs" in ecrivain.ecrits


def test_table_hors_schema(ecrivain: EcrivainPassage) -> None:
    with pytest.raises(UsineErreur, match="SCHEMA_INDICATEUR"):
        ecrivain.ecrire({"indicateurs": pl.DataFrame({"x": [1]})})
    with pytest.raises(UsineErreur, match="DataFrame"):
        ecrivain.ecrire({"indicateurs": b"pas une table"})


def test_json_enveloppe(ecrivain: EcrivainPassage) -> None:
    meteo = (
        MeteoEntite(
            date_arrete=DATE,
            entite="ENT-A",
            couleur=Couleur.vert,
            regles=(),
            version_grille="abcdef012345",
        ),
    )
    ecrivain.ecrire({"meteo": meteo})
    enveloppe = lire_enveloppe(
        (ecrivain.repertoire / "meteo.json").read_bytes(), tuple[MeteoEntite, ...]
    )
    assert enveloppe.passage_id == ID
    assert enveloppe.date_arrete == DATE
    assert enveloppe.contenu == meteo
    with pytest.raises(UsineErreur, match="aucun Passage commencé"):
        EcrivainPassage(ecrivain.racine_sorties).ecrire({"meteo": meteo})


def test_octets_et_refus(ecrivain: EcrivainPassage) -> None:
    ecrivain.ecrire({"rapport_xlsx": b"PK\x03\x04"})
    assert (ecrivain.repertoire / "rapport-2026-10-09.xlsx").read_bytes() == b"PK\x03\x04"
    with pytest.raises(UsineErreur, match="déjà écrite"):
        ecrivain.ecrire({"rapport_xlsx": b"x"})
    with pytest.raises(UsineErreur, match="octets"):
        ecrivain.ecrire({"rapport_pptx": "texte"})
    for reserve in ("manifeste", "trace_llm", "trace_previsions"):
        with pytest.raises(UsineErreur, match="réservée"):
            ecrivain.ecrire({reserve: b"x"})
    with pytest.raises(UsineErreur, match="inconnu"):
        ecrivain.ecrire({"inconnu": b"x"})


def _trace(passage_id: str = ID) -> EntreeTrace:
    return EntreeTrace(
        type_trace=TypeTrace.prevision,
        horodatage=INSTANT,
        passage_id=passage_id,
        date_arrete=DATE,
        entite="ENT-A",
        version_grille="abcdef012345",
        version_donnees="0" * 64,
        entree_pseudonymisee="entrée",
        sortie="sortie",
    )


def test_traces(ecrivain: EcrivainPassage) -> None:
    ecrivain.ajouter_traces([_trace(), _trace()])
    lignes = (ecrivain.repertoire / "trace" / "previsions.jsonl").read_text("utf-8").splitlines()
    assert [EntreeTrace.model_validate_json(ligne) for ligne in lignes] == [_trace(), _trace()]
    assert not (ecrivain.repertoire / "trace" / "llm.jsonl").exists()
    with pytest.raises(UsineErreur, match="20261012T073000Z-ffffff"):
        ecrivain.ajouter_traces([_trace("20261012T073000Z-ffffff")])


def test_progression_hors_passage(ecrivain: EcrivainPassage, tmp_path: Path) -> None:
    ecrivain.progression(Etape.kpi, StatutEtape.en_cours)
    ecrivain.progression(Etape.kpi, StatutEtape.echouee, "boum")
    chemin = tmp_path / "sorties" / "progression" / f"{ID}.jsonl"
    assert ecrivain.chemin_progression == chemin
    lignes = [
        EvenementProgression.model_validate_json(x)
        for x in chemin.read_text("utf-8").split("\n")
        if x
    ]
    assert [(e.etape, e.statut, e.message) for e in lignes] == [
        (Etape.kpi, StatutEtape.en_cours, ""),
        (Etape.kpi, StatutEtape.echouee, "boum"),
    ]
    assert not list(ecrivain.repertoire.rglob("*.jsonl"))


def test_publier(ecrivain: EcrivainPassage, tmp_path: Path) -> None:
    ecrivain.ecrire({"indicateurs": _indicateurs()})
    with pytest.raises(UsineErreur, match="manifeste"):
        ecrivain.publier(_manifeste("20261012T073000Z-ffffff"))
    cible = ecrivain.publier(_manifeste())
    assert cible == tmp_path / "sorties" / "passages" / "2026-10-09" / ID
    assert ecrivain.repertoire_publie == cible
    assert sorted(p.name for p in cible.iterdir()) == ["indicateurs.parquet", "manifeste.json"]
    manifeste = json.loads((cible / "manifeste.json").read_text("utf-8"))
    assert manifeste["passage_id"] == ID
    assert not list((tmp_path / "sorties" / "passages").glob(".en-cours-*"))


def test_abandonner(ecrivain: EcrivainPassage, tmp_path: Path) -> None:
    ecrivain.ecrire({"indicateurs": _indicateurs()})
    cible = ecrivain.abandonner()
    assert cible == tmp_path / "sorties" / "echecs" / ID
    assert (cible / "indicateurs.parquet").exists()
    assert not (cible / "manifeste.json").exists()
    assert not ecrivain.repertoire.exists()
    assert ecrivain.abandonner() is None
    assert EcrivainPassage(tmp_path).abandonner() is None


def test_etat_terminal(ecrivain: EcrivainPassage, tmp_path: Path) -> None:
    ecrivain.publier(_manifeste())
    for ecrire in (
        lambda: ecrivain.ecrire({"indicateurs": _indicateurs()}),
        lambda: ecrivain.ajouter_traces([_trace()]),
        lambda: ecrivain.publier(_manifeste()),
    ):
        with pytest.raises(UsineErreur, match="déjà publié"):
            ecrire()
    assert not ecrivain.repertoire.exists()
    assert ecrivain.abandonner() is None

    abandonne = EcrivainPassage(tmp_path / "autres", horloge_figee())
    abandonne.commencer(ID, DATE)
    abandonne.abandonner()
    with pytest.raises(UsineErreur, match="déjà abandonné"):
        abandonne.ecrire({"indicateurs": _indicateurs()})
    with pytest.raises(UsineErreur, match="déjà abandonné"):
        abandonne.publier(_manifeste())
    assert not abandonne.repertoire.exists()
