"""Verrou exclusif d'un Passage (`donnees/.verrou-passage`, AD-8).

Le verrou est un fichier créé atomiquement (`O_CREAT | O_EXCL`) : deux Passages ne peuvent
pas tourner en même temps. Il est rendu à la sortie du bloc, en succès comme en échec.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from usine.contrats.erreurs import UsineErreur


@contextmanager
def verrou_exclusif(chemin: Path) -> Iterator[Path]:
    """Prend le verrou `chemin` pour la durée du bloc ; refuse s'il est déjà pris."""
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        descripteur = os.open(chemin, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise UsineErreur(
            f"{chemin} : verrou de Passage déjà pris (un Passage est en cours ; s'il a été"
            f" interrompu, supprimer ce fichier)"
        ) from exc
    except OSError as exc:
        raise UsineErreur(
            f"{chemin} : verrou de Passage impossible à créer ({exc.strerror or exc})"
        ) from exc
    try:
        try:
            os.write(descripteur, f"{os.getpid()}\n".encode("ascii"))
        finally:
            os.close(descripteur)
        yield chemin
    finally:
        chemin.unlink(missing_ok=True)
