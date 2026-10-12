"""`EntrepotDuckDB` : stockage atomique, dédoublonnage, relecture en UTC et erreurs (Story 2.3)."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from tests.contrat.source_tickets.fabriques import evenements_essai
from tests.unit.adaptateurs.jira_cloud.outils import evenements_attendus
from usine.adaptateurs.entrepot_duckdb import CHEMIN_ENTREPOT, EntrepotDuckDB
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import Evenement
from usine.ports import EntrepotExtraction

REPERE = datetime(2026, 10, 12, 6, 30, tzinfo=UTC)


def _entrepot(tmp_path: Path) -> EntrepotDuckDB:
    return EntrepotDuckDB(tmp_path / "donnees" / "entrepot.duckdb")


def test_chemin_par_defaut() -> None:
    assert Path("donnees") / "entrepot.duckdb" == CHEMIN_ENTREPOT


def test_implemente_le_port(tmp_path: Path) -> None:
    assert isinstance(_entrepot(tmp_path), EntrepotExtraction)


def test_entrepot_neuf_sans_repere_ni_evenement(tmp_path: Path) -> None:
    entrepot = _entrepot(tmp_path)
    assert entrepot.chemin.is_file()
    assert entrepot.repere() is None
    assert list(entrepot.evenements()) == []


def test_enregistre_puis_relit_les_evenements_et_le_repere(tmp_path: Path) -> None:
    entrepot = _entrepot(tmp_path)
    attendus = evenements_attendus()
    assert entrepot.enregistrer(attendus, REPERE) == len(attendus)
    assert tuple(entrepot.evenements()) == attendus
    assert entrepot.repere() == REPERE
    # Une nouvelle instance relit le même fichier.
    assert tuple(_entrepot(tmp_path).evenements()) == attendus


def test_relecture_en_utc(tmp_path: Path) -> None:
    entrepot = _entrepot(tmp_path)
    paris = timezone(timedelta(hours=2))
    entrepot.enregistrer(evenements_essai(), datetime(2026, 10, 12, 8, 30, tzinfo=paris))
    assert entrepot.repere() == REPERE
    assert entrepot.repere().tzinfo is UTC  # type: ignore[union-attr]
    assert all(e.horodatage.tzinfo is UTC for e in entrepot.evenements())


def test_relecture_par_horodatage_puis_ordre_d_insertion(tmp_path: Path) -> None:
    entrepot = _entrepot(tmp_path)
    essai = evenements_essai()
    # Lot 1 : la fin du flux ; lot 2 : le début, inséré après mais horodaté avant.
    entrepot.enregistrer(essai[6:], REPERE)
    entrepot.enregistrer(essai[:6], REPERE)
    assert tuple(entrepot.evenements()) == essai


def test_meme_horodatage_garde_l_ordre_d_insertion(tmp_path: Path) -> None:
    entrepot = _entrepot(tmp_path)
    essai = evenements_essai()
    creation, *attributs = essai[:4]
    ordre = (attributs[2], creation, attributs[0], attributs[1])
    entrepot.enregistrer(ordre, REPERE)
    assert tuple(entrepot.evenements()) == ordre


def test_doublons_stockes_une_fois_le_premier_gagne(tmp_path: Path) -> None:
    entrepot = _entrepot(tmp_path)
    essai = evenements_essai()
    assert entrepot.enregistrer(essai[:3], REPERE) == 3
    modifie = essai[2].model_copy(update={"vers": "majeure"})
    repete = essai[4]
    autre = repete.model_copy(update={"horodatage": repete.horodatage + timedelta(hours=1)})
    # Lot : un id déjà stocké (contenu différent), un id nouveau répété deux fois.
    ajouts = entrepot.enregistrer([modifie, repete, autre, essai[3]], REPERE + timedelta(hours=1))
    assert ajouts == 2
    stockes = {e.id_evenement: e for e in entrepot.evenements()}
    assert len(stockes) == 5
    assert stockes[essai[2].id_evenement] == essai[2]
    assert stockes[repete.id_evenement] == repete
    assert entrepot.repere() == REPERE + timedelta(hours=1)


def test_rejeu_identique_n_ajoute_rien_et_avance_le_repere(tmp_path: Path) -> None:
    entrepot = _entrepot(tmp_path)
    attendus = evenements_attendus()
    entrepot.enregistrer(attendus, REPERE)
    suivant = REPERE + timedelta(days=1)
    assert entrepot.enregistrer(attendus, suivant) == 0
    assert tuple(entrepot.evenements()) == attendus
    assert entrepot.repere() == suivant


def test_lot_vide_avance_le_repere(tmp_path: Path) -> None:
    entrepot = _entrepot(tmp_path)
    assert entrepot.enregistrer([], REPERE) == 0
    assert entrepot.repere() == REPERE
    assert list(entrepot.evenements()) == []


def test_repere_sans_fuseau_refuse_rien_d_ecrit(tmp_path: Path) -> None:
    entrepot = _entrepot(tmp_path)
    consommes: list[Evenement] = []

    def flux() -> Iterator[Evenement]:
        for evenement in evenements_essai():
            consommes.append(evenement)
            yield evenement

    with pytest.raises(UsineErreur, match="sans fuseau") as erreur:
        entrepot.enregistrer(flux(), datetime(2026, 10, 12, 6, 30))  # noqa: DTZ001
    assert str(entrepot.chemin) in str(erreur.value)
    assert consommes == []
    assert entrepot.repere() is None
    assert list(entrepot.evenements()) == []


class _Coupure(Exception):
    pass


def test_iterable_qui_leve_annule_tout(tmp_path: Path) -> None:
    entrepot = _entrepot(tmp_path)
    essai = evenements_essai()
    entrepot.enregistrer(essai[:2], REPERE)

    def flux() -> Iterator[Evenement]:
        yield from essai[2:5]
        raise _Coupure

    with pytest.raises(_Coupure):
        entrepot.enregistrer(flux(), REPERE + timedelta(hours=1))
    assert tuple(entrepot.evenements()) == essai[:2]
    assert entrepot.repere() == REPERE


def test_chemin_repertoire_refuse_en_nommant_le_fichier(tmp_path: Path) -> None:
    repertoire = tmp_path / "entrepot.duckdb"
    repertoire.mkdir()
    with pytest.raises(UsineErreur) as erreur:
        EntrepotDuckDB(repertoire)
    assert str(repertoire) in str(erreur.value)


def test_base_corrompue_refusee_en_nommant_le_fichier(tmp_path: Path) -> None:
    chemin = tmp_path / "entrepot.duckdb"
    chemin.write_bytes(b"ceci n'est pas une base DuckDB" * 200)
    with pytest.raises(UsineErreur) as erreur:
        EntrepotDuckDB(chemin)
    assert str(chemin) in str(erreur.value)


def test_repertoire_parent_impossible_nomme_le_fichier(tmp_path: Path) -> None:
    fichier = tmp_path / "fichier"
    fichier.write_text("x", encoding="utf-8")
    chemin = fichier / "entrepot.duckdb"
    with pytest.raises(UsineErreur) as erreur:
        EntrepotDuckDB(chemin)
    assert str(chemin) in str(erreur.value)


def test_aucune_connexion_ne_reste_ouverte(tmp_path: Path) -> None:
    entrepot = _entrepot(tmp_path)
    entrepot.enregistrer(evenements_essai(), REPERE)
    list(entrepot.evenements())
    # Sous Windows, un fichier encore ouvert ne peut être ni renommé ni supprimé.
    deplace = entrepot.chemin.with_name("deplace.duckdb")
    entrepot.chemin.rename(deplace)
    deplace.unlink()


def test_aucune_connexion_ne_reste_ouverte_apres_annulation(tmp_path: Path) -> None:
    entrepot = _entrepot(tmp_path)

    def flux() -> Iterator[Evenement]:
        yield from evenements_essai()[:3]
        raise _Coupure

    with pytest.raises(_Coupure):
        entrepot.enregistrer(flux(), REPERE)
    deplace = entrepot.chemin.with_name("deplace.duckdb")
    entrepot.chemin.rename(deplace)
    deplace.unlink()
