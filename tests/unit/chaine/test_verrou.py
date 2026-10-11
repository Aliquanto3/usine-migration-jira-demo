"""Verrou exclusif d'un Passage (Story 0.5)."""

from pathlib import Path

import pytest

from usine.chaine.verrou import verrou_exclusif
from usine.contrats.erreurs import UsineErreur


def test_pris_puis_rendu(tmp_path: Path) -> None:
    chemin = tmp_path / "donnees" / ".verrou-passage"
    with verrou_exclusif(chemin) as pris:
        assert pris == chemin
        assert chemin.exists()
    assert not chemin.exists()


def test_rendu_en_echec(tmp_path: Path) -> None:
    chemin = tmp_path / ".verrou-passage"
    with pytest.raises(RuntimeError), verrou_exclusif(chemin):
        raise RuntimeError("boum")
    assert not chemin.exists()


def test_deja_pris(tmp_path: Path) -> None:
    chemin = tmp_path / ".verrou-passage"
    chemin.write_text("autre\n", encoding="utf-8")
    with pytest.raises(UsineErreur, match="verrou-passage"), verrou_exclusif(chemin):
        pytest.fail("le bloc ne doit pas s'exécuter")
    assert chemin.read_text(encoding="utf-8") == "autre\n"


def test_imbrique_refuse(tmp_path: Path) -> None:
    chemin = tmp_path / ".verrou-passage"
    with verrou_exclusif(chemin):
        with pytest.raises(UsineErreur, match="déjà pris"), verrou_exclusif(chemin):
            pass
        assert chemin.exists()
    assert not chemin.exists()
