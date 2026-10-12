"""Suivi de la progression : choix du fichier, lecture ouvrir-lire-fermer, état par étape."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from usine.contrats.erreurs import UsineErreur
from usine.contrats.format import ESPACE_INSECABLE
from usine.contrats.passage import Etape, EvenementProgression, StatutEtape
from usine.ui.progression import (
    EN_ATTENTE,
    LIBELLES_ETATS,
    SuiviEtape,
    etape_en_echec,
    etat_des_etapes,
    fichier_nouveau,
    fichiers_progression,
    ligne_suivi,
    lire_progression,
    suivi_des_etapes,
    texte_duree,
)

PASSAGE = "20261012T073000Z-aaaaaa"
INSTANT = datetime(2026, 10, 12, 7, 30, tzinfo=UTC)


def _evenement(etape: Etape, statut: StatutEtape, secondes: float = 0.0) -> EvenementProgression:
    instant = INSTANT + timedelta(seconds=secondes)
    return EvenementProgression(passage_id=PASSAGE, etape=etape, statut=statut, horodatage=instant)


def _ligne(etape: Etape, statut: StatutEtape) -> str:
    return _evenement(etape, statut).model_dump_json() + "\n"


def _repertoire(racine: Path) -> Path:
    repertoire = racine / "sorties" / "progression"
    repertoire.mkdir(parents=True, exist_ok=True)
    return repertoire


def test_sans_repertoire_aucun_fichier(tmp_path: Path) -> None:
    assert fichiers_progression(tmp_path) == frozenset()
    assert fichier_nouveau(frozenset(), tmp_path) is None


def test_le_nouveau_fichier_est_suivi(tmp_path: Path) -> None:
    repertoire = _repertoire(tmp_path)
    for nom in ("20261008T070000Z-111111.jsonl", "20261009T070000Z-222222.jsonl"):
        (repertoire / nom).write_text("", encoding="utf-8")
    (repertoire / "notes.txt").write_text("", encoding="utf-8")
    avant = fichiers_progression(tmp_path)
    assert len(avant) == 2
    assert fichier_nouveau(avant, tmp_path) is None
    nouveau = repertoire / "20261012T073000Z-aaaaaa.jsonl"
    nouveau.write_text("", encoding="utf-8")
    assert fichier_nouveau(avant, tmp_path) == nouveau
    (repertoire / "20261012T080000Z-bbbbbb.jsonl").write_text("", encoding="utf-8")
    assert fichier_nouveau(avant, tmp_path) == nouveau


def test_progression_par_etape(tmp_path: Path) -> None:
    chemin = _repertoire(tmp_path) / f"{PASSAGE}.jsonl"
    chemin.write_text(
        _ligne(Etape.extraction, StatutEtape.en_cours)
        + _ligne(Etape.extraction, StatutEtape.reussie)
        + _ligne(Etape.instantanes, StatutEtape.en_cours),
        encoding="utf-8",
    )
    etats = dict(etat_des_etapes(lire_progression(chemin)))
    assert list(etats) == list(Etape)
    assert etats[Etape.extraction] == StatutEtape.reussie
    assert etats[Etape.instantanes] == StatutEtape.en_cours
    assert all(etats[e] == EN_ATTENTE for e in list(Etape)[2:])
    assert LIBELLES_ETATS[etats[Etape.extraction]] == "Réussie"
    assert LIBELLES_ETATS[etats[Etape.kpi]] == "En attente"


def test_ligne_partielle_ignoree(tmp_path: Path) -> None:
    chemin = tmp_path / f"{PASSAGE}.jsonl"
    complete = _ligne(Etape.extraction, StatutEtape.reussie)
    suivante = _ligne(Etape.instantanes, StatutEtape.en_cours)
    chemin.write_text(complete + "\n" + suivante[:25], encoding="utf-8")
    assert lire_progression(chemin) == (_evenement(Etape.extraction, StatutEtape.reussie),)
    with chemin.open("a", encoding="utf-8") as fichier:
        fichier.write(suivante[25:])
    assert len(lire_progression(chemin)) == 2


def test_echec_affiche(tmp_path: Path) -> None:
    chemin = tmp_path / f"{PASSAGE}.jsonl"
    chemin.write_text(
        _ligne(Etape.kpi, StatutEtape.en_cours) + _ligne(Etape.kpi, StatutEtape.echouee),
        encoding="utf-8",
    )
    etats = dict(etat_des_etapes(lire_progression(chemin)))
    assert etats[Etape.kpi] == StatutEtape.echouee
    assert LIBELLES_ETATS[etats[Etape.kpi]] == "Échec"


def test_fichier_absent_et_ligne_invalide(tmp_path: Path) -> None:
    chemin = tmp_path / f"{PASSAGE}.jsonl"
    assert lire_progression(chemin) == ()
    chemin.write_text('{"etape": "inconnue"}\n', encoding="utf-8")
    with pytest.raises(UsineErreur, match="ligne 1"):
        lire_progression(chemin)


def test_libelles_de_tous_les_etats() -> None:
    assert set(LIBELLES_ETATS) == {*StatutEtape, EN_ATTENTE}


def _suivis(*evenements: EvenementProgression) -> dict[Etape, SuiviEtape]:
    suivis = suivi_des_etapes(evenements)
    assert [suivi.etape for suivi in suivis] == list(Etape)
    return {suivi.etape: suivi for suivi in suivis}


def test_suivi_en_cours() -> None:
    suivis = _suivis(
        _evenement(Etape.extraction, StatutEtape.en_cours, 1.0),
        _evenement(Etape.extraction, StatutEtape.reussie, 1.5),
        _evenement(Etape.instantanes, StatutEtape.en_cours, 1.5),
    )
    assert suivis[Etape.extraction] == SuiviEtape(
        Etape.extraction, StatutEtape.reussie, timedelta(seconds=0.5)
    )
    assert ligne_suivi(suivis[Etape.extraction]) == "- **extraction** : Réussie (0,5 s)"
    assert suivis[Etape.instantanes].duree is None
    assert ligne_suivi(suivis[Etape.instantanes]) == "- **instantanes** : En cours"
    assert ligne_suivi(suivis[Etape.kpi]) == "- **kpi** : En attente"


def test_suivi_sautee_meme_instant() -> None:
    suivis = _suivis(
        _evenement(Etape.classification, StatutEtape.en_cours, 2.0),
        _evenement(Etape.classification, StatutEtape.sautee, 2.0),
    )
    # `formater_nombre` retire les zéros non significatifs : « 0 s » (et non « 0,0 s »)
    assert ligne_suivi(suivis[Etape.classification]) == "- **classification** : Sautée (0 s)"


def test_suivi_final_sans_en_cours() -> None:
    suivis = _suivis(_evenement(Etape.kpi, StatutEtape.reussie, 3.0))
    assert suivis[Etape.kpi].duree is None
    assert ligne_suivi(suivis[Etape.kpi]) == "- **kpi** : Réussie"


def test_suivi_derniers_evenements_et_incoherence() -> None:
    suivis = _suivis(
        _evenement(Etape.extraction, StatutEtape.en_cours, 0.0),
        _evenement(Etape.extraction, StatutEtape.reussie, 5.0),
        _evenement(Etape.extraction, StatutEtape.en_cours, 6.0),
        _evenement(Etape.extraction, StatutEtape.reussie, 6.25),
        _evenement(Etape.kpi, StatutEtape.en_cours, 9.0),
        _evenement(Etape.kpi, StatutEtape.reussie, 8.0),
    )
    assert suivis[Etape.extraction].duree == timedelta(seconds=0.25)
    assert suivis[Etape.kpi].duree is None  # fin antérieure au début : aucune durée affichée


def test_etape_en_echec() -> None:
    assert etape_en_echec(()) is None
    reussie = _evenement(Etape.extraction, StatutEtape.reussie)
    assert etape_en_echec([reussie]) is None
    evenements = [
        reussie,
        _evenement(Etape.kpi, StatutEtape.en_cours, 1.0),
        _evenement(Etape.kpi, StatutEtape.echouee, 1.3),
    ]
    assert etape_en_echec(evenements) is Etape.kpi
    assert ligne_suivi(_suivis(*evenements)[Etape.kpi]) == "- **kpi** : Échec (0,3 s)"


def test_texte_duree() -> None:
    assert texte_duree(timedelta(seconds=0.3)) == "0,3 s"
    assert texte_duree(timedelta(seconds=1234.56)) == f"1{ESPACE_INSECABLE}234,6 s"
    assert texte_duree(timedelta(seconds=2)) == "2 s"
    assert texte_duree(timedelta(0)) == "0 s"
