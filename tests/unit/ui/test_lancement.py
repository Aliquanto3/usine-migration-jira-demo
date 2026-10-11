"""Lancement de `usine rapport` en sous-processus, sans bloquer."""

import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

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
