"""`composition.apercu_pseudonymisation` : aperçu local de la Pseudonymisation (Story 7.7, AD-15).

Aucun appel LLM ; la clé vient de `monkeypatch`, jamais d'un `.env`.
"""

import shutil
from pathlib import Path

import pytest

from tests.unit.chaine.environnement import RACINE_DEPOT
from usine import composition
from usine.adaptateurs.pseudonymisation import MOTIFS_PAR_DEFAUT, PseudonymiseurHmac
from usine.contrats.erreurs import UsineErreur
from usine.contrats.passage import CHEMIN_PSEUDONYMES

CLE = "cle-de-test-fictive"
COMPTE = "FR76 9999 9123 4567 8901 2345 678"
TEXTE = f"Cas cité sur DEMO-12 : compte {COMPTE}, client M. Fictivia EXEMPLON."


@pytest.fixture(autouse=True)
def _environnement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("USINE_CLE_PSEUDO", raising=False)


def test_sans_cle(tmp_path: Path) -> None:
    with pytest.raises(UsineErreur, match="USINE_CLE_PSEUDO"):
        composition.apercu_pseudonymisation(tmp_path)


def test_cle_vide_ou_trop_courte(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for valeur in ("   ", "courte"):
        monkeypatch.setenv("USINE_CLE_PSEUDO", valeur)
        with pytest.raises(UsineErreur, match="USINE_CLE_PSEUDO"):
            composition.apercu_pseudonymisation(tmp_path)


def test_moteur_regex_sans_ecriture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USINE_CLE_PSEUDO", CLE)
    apercu = composition.apercu_pseudonymisation(tmp_path)  # sans config : MOTIFS_PAR_DEFAUT
    version = apercu(TEXTE)
    attendu = PseudonymiseurHmac(CLE.encode(), MOTIFS_PAR_DEFAUT, _TableRefus()).apercu(TEXTE)
    assert version == attendu
    assert COMPTE not in version
    assert "COMPTE_" in version
    assert "DEMO-12" in version  # clé de ticket intacte
    assert not (tmp_path / CHEMIN_PSEUDONYMES).exists()
    assert not (tmp_path / "donnees").exists()


def test_moteur_presidio_du_depot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spacy = pytest.importorskip("spacy")
    if not spacy.util.is_package("fr_core_news_md"):
        pytest.skip("modèle spaCy fr_core_news_md absent")
    shutil.copytree(RACINE_DEPOT / "config", tmp_path / "config")
    monkeypatch.setenv("USINE_CLE_PSEUDO", CLE)
    version = composition.apercu_pseudonymisation(tmp_path)(TEXTE)
    assert COMPTE not in version
    assert "DEMO-12" in version
    assert not (tmp_path / CHEMIN_PSEUDONYMES).exists()


def test_table_apercu_refuse_l_ecriture() -> None:
    table = composition._TableApercu()
    assert table.lire({"COMPTE_abcdef"}) == {}
    with pytest.raises(UsineErreur, match="lecture seule"):
        table.enregistrer({"COMPTE_abcdef": COMPTE})


class _TableRefus:
    def enregistrer(self, correspondances: object) -> None:
        raise AssertionError("aucune écriture attendue")

    def lire(self, jetons: object) -> dict[str, str]:
        return {}
