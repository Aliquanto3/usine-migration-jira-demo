"""Racine d'essai d'un Passage : configuration et gabarit livrés, Journal généré (graine 42)."""

import shutil
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from usine.composition import generer_journal
from usine.config import charger_yaml
from usine.contrats.config import ConfigProgramme
from usine.contrats.passage import EXCLUSIONS_REJEU

RACINE_DEPOT = Path(__file__).resolve().parents[3]
DATE_GENERATION = date(2026, 10, 12)
DATE_ARRETE = date(2026, 10, 9)
INSTANT = datetime(2026, 10, 12, 7, 30, tzinfo=UTC)


def preparer_racine(racine: Path, journal: bool = True) -> Path:
    """Copie `config/` et `gabarits/` sous `racine` et y génère le Journal (graine 42)."""
    shutil.copytree(RACINE_DEPOT / "config", racine / "config")
    shutil.copytree(RACINE_DEPOT / "gabarits", racine / "gabarits")
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


def sans_exclusions(nom: str, valeur: object) -> object:
    """`valeur` (fichier `nom` de `FICHIERS_PASSAGE`) sans ses champs exclus du Rejeu (AD-7)."""
    exclus = EXCLUSIONS_REJEU.get(nom, frozenset())

    def retirer(valeur: object, chemin: str) -> object:
        if isinstance(valeur, dict):
            return {
                cle: retirer(v, f"{chemin}.{cle}" if chemin else cle)
                for cle, v in valeur.items()
                if (f"{chemin}.{cle}" if chemin else cle) not in exclus
            }
        if isinstance(valeur, list):
            return [retirer(v, f"{chemin}[]") for v in valeur]
        return valeur

    return retirer(valeur, "")
