"""Commande `usine ui` : démarre `streamlit run` sur la page de l'UI."""

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from usine.cli import app
from usine.contrats.erreurs import UsineErreur
from usine.ui import cli as cli_ui


def test_aide() -> None:
    resultat = CliRunner().invoke(app, ["ui", "--help"])
    assert resultat.exit_code == 0, resultat.output


def test_lance_streamlit(monkeypatch: pytest.MonkeyPatch) -> None:
    appels: list[list[str]] = []

    def executer(commande: list[str], **_options: Any) -> subprocess.CompletedProcess[bytes]:
        appels.append(commande)
        return subprocess.CompletedProcess(commande, 3)

    monkeypatch.setattr(subprocess, "run", executer)
    resultat = CliRunner().invoke(app, ["ui"])
    assert resultat.exit_code == 3
    assert appels == [[sys.executable, "-m", "streamlit", "run", str(cli_ui.CHEMIN_APP)]]
    assert cli_ui.CHEMIN_APP.is_file()


def test_interruption(monkeypatch: pytest.MonkeyPatch) -> None:
    def interrompre(commande: list[str], **_options: Any) -> subprocess.CompletedProcess[bytes]:
        raise KeyboardInterrupt

    monkeypatch.setattr(subprocess, "run", interrompre)
    assert CliRunner().invoke(app, ["ui"]).exit_code == 0


def test_streamlit_introuvable(monkeypatch: pytest.MonkeyPatch) -> None:
    def echouer(commande: list[str], **_options: Any) -> subprocess.CompletedProcess[bytes]:
        raise FileNotFoundError(2, "introuvable", commande[0])

    monkeypatch.setattr(subprocess, "run", echouer)
    resultat = CliRunner().invoke(app, ["ui"])
    assert resultat.exit_code == 1
    assert "lancement de Streamlit impossible" in resultat.stderr


def test_racine_ui(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert cli_ui.racine_ui() == tmp_path
    (tmp_path / ".env").write_text("USINE_RACINE=autre\n", encoding="utf-8")
    assert cli_ui.racine_ui() == Path("autre")
    monkeypatch.setenv("USINE_RACINE", str(tmp_path / "depot"))
    assert cli_ui.racine_ui() == tmp_path / "depot"
    monkeypatch.setenv("USINE_RACINE", "  ")
    assert cli_ui.racine_ui() == tmp_path  # blanche : le répertoire courant


def test_racine_ui_secrets_illisibles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("USINE_MODE_REPLI", "peut-être")
    with pytest.raises(UsineErreur, match="USINE_MODE_REPLI"):
        cli_ui.racine_ui()
