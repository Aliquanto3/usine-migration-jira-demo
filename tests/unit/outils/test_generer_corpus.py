"""Outil `outils/generer_corpus.py` : Corpus provisoire ou produit par un faux LLM (Story 1.2)."""

from pathlib import Path

import pytest

from outils.generer_corpus import generer, main
from tests.doublures.fournisseur_factice import FournisseurFactice
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import Tache
from usine.contrats.tickets import CauseRacine
from usine.generateur.corpus import ReponseCorpus, TexteTicket, charger_corpus

RACINE = Path(__file__).resolve().parents[3]
CORPUS_VERSIONNE = RACINE / "donnees" / "corpus" / "textes.json"
PROGRAMME_REDUIT = RACINE / "tests" / "unit" / "generateur" / "programme_reduit.yaml"
"""Domaines `comptabilite`, `achats`, `paie`."""


def _reponses(nombre: int) -> list[ReponseCorpus]:
    return [
        ReponseCorpus(
            textes=(TexteTicket(titre=f"Titre {r}", description=f"Constaté sur {{entite}} ({r})"),)
        )
        for r in range(nombre)
    ]


def test_outil_faux_llm(tmp_path: Path) -> None:
    nombre = (3 + 1) * (len(CauseRacine) + 1) + 1
    fournisseur = FournisseurFactice(
        reponses_structurees=_reponses(nombre), version_modele="factice:redacteur"
    )
    sortie = tmp_path / "corpus" / "textes.json"
    chemin = generer(
        fournisseur, config=PROGRAMME_REDUIT, sortie=sortie, version_corpus="llm-essai"
    )
    assert chemin == sortie
    corpus = charger_corpus(chemin)
    assert corpus.modele_corpus == "factice:redacteur"
    assert corpus.version_corpus == "llm-essai"
    assert tuple(corpus.domaines) == ("comptabilite", "achats", "paie")
    assert len(fournisseur.appels) == nombre
    assert all(a.methode == "generer_structure" for a in fournisseur.appels)
    assert all(a.parametres.tache is Tache.narration for a in fournisseur.appels)


def test_outil_sans_fournisseur_ni_provisoire(tmp_path: Path) -> None:
    sortie = tmp_path / "textes.json"
    with pytest.raises(UsineErreur, match=r"Story 6\.1.*--provisoire"):
        generer(None, config=PROGRAMME_REDUIT, sortie=sortie)
    assert not sortie.exists()


def test_outil_provisoire_identique_au_versionne(tmp_path: Path) -> None:
    sortie = tmp_path / "textes.json"
    generer(None, provisoire=True, sortie=sortie)
    assert sortie.read_bytes() == CORPUS_VERSIONNE.read_bytes()


def test_outil_provisoire_ignore_le_fournisseur(tmp_path: Path) -> None:
    fournisseur = FournisseurFactice()
    sortie = tmp_path / "textes.json"
    generer(fournisseur, provisoire=True, config=PROGRAMME_REDUIT, sortie=sortie)
    assert charger_corpus(sortie).modele_corpus == "gabarits-provisoires"
    assert fournisseur.appels == []


def test_main_provisoire(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sortie = tmp_path / "textes.json"
    code = main(["--provisoire", "--sortie", str(sortie), "--version-corpus", "provisoire-9"])
    assert code == 0
    assert str(sortie) in capsys.readouterr().out
    assert charger_corpus(sortie).version_corpus == "provisoire-9"


def test_main_sans_provisoire(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sortie = tmp_path / "textes.json"
    assert main(["--sortie", str(sortie)]) == 1
    erreur = capsys.readouterr().err
    assert "Story 6.1" in erreur
    assert "--provisoire" in erreur
    assert not sortie.exists()


def test_main_config_non_utf8(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = tmp_path / "programme.yaml"
    config.write_bytes("domaines: [comptabilité]\n".encode("latin-1"))
    assert main(["--provisoire", "--config", str(config), "--sortie", str(tmp_path / "t")]) == 1
    assert str(config) in capsys.readouterr().err


def test_main_config_illisible(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config = tmp_path / "absente.yaml"
    assert main(["--provisoire", "--config", str(config), "--sortie", str(tmp_path / "t")]) == 1
    assert str(config) in capsys.readouterr().err
