"""Commande `usine ui` : démarre `streamlit run` sur la page de l'UI."""

import subprocess
import sys
from typing import Any

import pytest
from typer.testing import CliRunner

from usine.cli import app
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
