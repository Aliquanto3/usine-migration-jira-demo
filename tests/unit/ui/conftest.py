"""Racine d'essai partagée par les tests de l'UI : un Passage publié (graine 42, 2026-10-09)."""

import shutil
from pathlib import Path

import pytest

from tests.unit.chaine.environnement import (
    DATE_ARRETE,
    RACINE_DEPOT,
    horloge_figee,
    preparer_racine,
)
from usine.composition import lancer_rapport
from usine.ui.outillage import FICHIER_FICHE


@pytest.fixture(scope="module")
def racine_publiee(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Racine où un Passage a été publié le 09/10/2026, avec la fiche outillage du dépôt."""
    with pytest.MonkeyPatch.context() as environnement:
        environnement.delenv("USINE_MODE_REPLI", raising=False)
        environnement.delenv("USINE_RACINE", raising=False)
        racine = preparer_racine(tmp_path_factory.mktemp("ui"))
        lancer_rapport(racine, DATE_ARRETE, horloge_figee(), lambda: "aaaaaa")
        (racine / "docs").mkdir(exist_ok=True)
        shutil.copyfile(RACINE_DEPOT / FICHIER_FICHE, racine / FICHIER_FICHE)
    return racine


@pytest.fixture(autouse=True)
def _sans_mode_repli(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ni Mode repli ni racine imposés par l'environnement du poste."""
    monkeypatch.delenv("USINE_MODE_REPLI", raising=False)
    monkeypatch.delenv("USINE_RACINE", raising=False)
