"""Racine d'essai d'un Passage : configuration livrée et Journal généré (graine 42)."""

import shutil
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from usine.composition import generer_journal
from usine.config import charger_yaml
from usine.contrats.config import ConfigProgramme

RACINE_DEPOT = Path(__file__).resolve().parents[3]
DATE_GENERATION = date(2026, 10, 12)
DATE_ARRETE = date(2026, 10, 9)
INSTANT = datetime(2026, 10, 12, 7, 30, tzinfo=UTC)


def preparer_racine(racine: Path, journal: bool = True) -> Path:
    """Copie `config/` sous `racine` et y génère le Journal (graine 42, 2026-10-12)."""
    shutil.copytree(RACINE_DEPOT / "config", racine / "config")
    if journal:
        programme = charger_yaml(racine / "config" / "programme.yaml", ConfigProgramme)
        generer_journal(programme, 42, DATE_GENERATION, racine)
    return racine


def horloge_figee(instant: datetime = INSTANT) -> Callable[[], datetime]:
    """Horloge figée."""
    return lambda: instant


def horloge_pas_a_pas(instant: datetime = INSTANT) -> Callable[[], datetime]:
    """Horloge qui avance d'une seconde à chaque lecture."""
    compteur = iter(range(10_000))
    return lambda: instant + timedelta(seconds=next(compteur))
