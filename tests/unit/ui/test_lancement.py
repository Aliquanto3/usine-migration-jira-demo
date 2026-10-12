"""Lancement de `usine rapport` en sous-processus, sans bloquer."""

import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from usine.cli import app
from usine.ui.lancement import commande_rapport, fichier_erreurs, lancer_chaine, lire_erreurs


class _PopenEspion:
    def __init__(self) -> None:
        self.appels: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, commande: list[str], **options: Any) -> Any:
        self.appels.append((commande, options))
        return "processus"


def test_commande_et_racine(tmp_path: Path) -> None:
    espion = _PopenEspion()
    processus: object = lancer_chaine(tmp_path, popen=espion)
    assert processus == "processus"
    ((commande, options),) = espion.appels
    assert commande == [sys.executable, "-m", "usine", "rapport"]
    assert options["cwd"] == tmp_path
    assert options["stdout"] == subprocess.DEVNULL


def test_date_arrete_transmise() -> None:
    assert commande_rapport(date(2026, 10, 9))[-2:] == ["--date-arrete", "2026-10-09"]


def test_python_m_usine(tmp_path: Path) -> None:
    resultat = subprocess.run(
        [sys.executable, "-m", "usine", "ui", "--help"],
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )
    assert resultat.returncode == 0, resultat.stderr
    assert b"Streamlit" in resultat.stdout


def test_erreurs_dans_un_fichier_temporaire(tmp_path: Path) -> None:
    espion = _PopenEspion()
    erreurs = fichier_erreurs()
    lancer_chaine(tmp_path, popen=espion, erreurs=erreurs)
    assert espion.appels[0][1]["stderr"] is erreurs
    erreurs.write("Erreur : échec\n".encode())
    assert lire_erreurs(erreurs) == "Erreur : échec"
    assert erreurs.closed


def test_vrai_processus_erreurs_volumineuses(tmp_path: Path) -> None:
    script = "import sys; sys.stderr.write('x' * 200_000); sys.exit(2)"

    def popen(commande: list[str], **options: Any) -> "subprocess.Popen[bytes]":
        return subprocess.Popen([sys.executable, "-c", script], **options)

    erreurs = fichier_erreurs()
    processus = lancer_chaine(tmp_path, popen=popen, erreurs=erreurs)
    assert processus.wait(timeout=60) == 2
    assert lire_erreurs(erreurs) == "x" * 200_000
    assert erreurs.closed


def test_option_date_arrete_de_la_cli() -> None:
    resultat = CliRunner().invoke(app, ["rapport", "--help"])
    assert resultat.exit_code == 0
    # Sous GitHub Actions, Rich force la couleur : les séquences ANSI coupent le nom d'option.
    texte = re.sub(r"\x1b\[[0-9;]*m", "", resultat.output)
    assert commande_rapport(date(2026, 10, 9))[-2] in texte
