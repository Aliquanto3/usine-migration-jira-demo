"""Passages publiés pour les tests du rendu : normal et en Mode repli (graine 42, 2026-10-09)."""

from pathlib import Path

import pytest

from tests.unit.chaine.environnement import DATE_ARRETE, horloge_figee, preparer_racine
from usine.composition import lancer_rapport
from usine.consultation.passage import ConsultationPassage


def _publier(
    racine: Path, mode_repli: bool, monkeypatch: pytest.MonkeyPatch, sans_jira: bool = False
) -> Path:
    preparer_racine(racine)
    if sans_jira:
        (racine / "config" / "jira.yaml").unlink()
    monkeypatch.chdir(racine)  # aucun `.env` du poste lu par `Secrets`
    if mode_repli:
        monkeypatch.setenv("USINE_MODE_REPLI", "1")
    else:
        monkeypatch.delenv("USINE_MODE_REPLI", raising=False)
    return lancer_rapport(racine, DATE_ARRETE, horloge_figee(), lambda: "abcdef").repertoire


@pytest.fixture(scope="module")
def passage(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Répertoire d'un Passage publié avec `config/jira.yaml`."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        return _publier(tmp_path_factory.mktemp("normal"), False, monkeypatch)


@pytest.fixture(scope="module")
def passage_repli(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Répertoire d'un Passage publié en Mode repli (`USINE_MODE_REPLI=1`)."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        return _publier(tmp_path_factory.mktemp("repli"), True, monkeypatch)


@pytest.fixture(scope="module")
def passage_sans_jira(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Répertoire d'un Passage publié sans `config/jira.yaml`."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        return _publier(tmp_path_factory.mktemp("sans-jira"), False, monkeypatch, sans_jira=True)


@pytest.fixture
def consultation(passage: Path) -> ConsultationPassage:
    """Consultation du Passage publié, avec l'URL du site Jira de `config/jira.yaml`."""
    return ConsultationPassage(passage, url_jira="https://demo-usine.atlassian.net")
