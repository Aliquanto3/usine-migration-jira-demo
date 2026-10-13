"""Tests du contrôle rapide des agents (mode hook et garde contre les boucles)."""

import io
import json
import tempfile
from pathlib import Path

import pytest

from outils import controle_rapide


@pytest.fixture
def hook(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[Path]:
    """Hook branché sur un dépôt factice dont le contrôle échoue toujours."""
    controles: list[Path] = []

    def controler(racine: Path) -> int:
        controles.append(racine)
        return 2

    monkeypatch.setattr(controle_rapide, "_controler", controler)
    monkeypatch.setattr(controle_rapide, "_cibles_du_hook", lambda racine: [racine])
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    return controles


def _lancer(monkeypatch: pytest.MonkeyPatch, entree: str, racine: Path) -> int:
    monkeypatch.setattr("sys.stdin", io.StringIO(entree))
    return controle_rapide._hook(racine)


def test_hook_bloque_au_plus_deux_fois_par_agent(
    hook: list[Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    entree = json.dumps({"agent_id": "a1"})
    codes = [_lancer(monkeypatch, entree, tmp_path) for _ in range(3)]
    assert codes == [2, 2, 0]
    assert len(hook) == 2


def test_hook_compte_par_agent(
    hook: list[Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for _ in range(2):
        _lancer(monkeypatch, json.dumps({"agent_id": "a1"}), tmp_path)
    assert _lancer(monkeypatch, json.dumps({"agent_id": "a2"}), tmp_path) == 2


def test_hook_tolere_une_entree_illisible(
    hook: list[Path], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert _lancer(monkeypatch, "pas du json", tmp_path) == 2


def test_cibles_sans_lane_en_cours_rend_le_depot_principal(tmp_path: Path) -> None:
    racine = Path(__file__).resolve().parents[3]
    cibles = controle_rapide._cibles_du_hook(racine)
    assert cibles
    assert all(cible.exists() for cible in cibles)
