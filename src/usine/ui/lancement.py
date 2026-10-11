"""Lancement de la Chaîne depuis l'UI : `usine rapport` dans un sous-processus non bloquant."""

import subprocess
import sys
import tempfile
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import IO

Lanceur = Callable[..., "subprocess.Popen[bytes]"]
"""Signature de `subprocess.Popen`, injectable en test."""


def commande_rapport(date_arrete: date | None = None) -> list[str]:
    """`python -m usine rapport [--date-arrete AAAA-MM-JJ]` avec l'interpréteur courant."""
    commande = [sys.executable, "-m", "usine", "rapport"]
    if date_arrete is not None:
        commande += ["--date-arrete", date_arrete.isoformat()]
    return commande


def lancer_chaine(
    racine: Path,
    date_arrete: date | None = None,
    popen: Lanceur = subprocess.Popen,
    erreurs: IO[bytes] | None = None,
) -> "subprocess.Popen[bytes]":
    """Démarre `usine rapport` dans `racine` et rend la main aussitôt.

    La sortie standard est ignorée ; l'erreur standard va dans `erreurs` (fichier temporaire
    lu après la fin du processus, jamais un tube qui pourrait se remplir et le bloquer).
    """
    return popen(
        commande_rapport(date_arrete),
        cwd=racine,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL if erreurs is None else erreurs,
    )


def fichier_erreurs() -> IO[bytes]:
    """Fichier temporaire anonyme qui reçoit l'erreur standard de la Chaîne."""
    return tempfile.TemporaryFile()


def lire_erreurs(erreurs: IO[bytes]) -> str:
    """Contenu du fichier d'erreurs, puis fermeture (le fichier temporaire disparaît)."""
    try:
        erreurs.seek(0)
        return erreurs.read().decode("utf-8", errors="replace").strip()
    finally:
        erreurs.close()
