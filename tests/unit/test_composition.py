"""Racine de composition : secrets lus par `charger_secrets`, URL Jira résolue une fois."""

from datetime import date
from pathlib import Path

import pytest

from tests.unit.chaine.environnement import preparer_racine
from usine import composition
from usine.config import charger_yaml
from usine.contrats.config import ConfigJira, ConfigProgramme
from usine.contrats.erreurs import UsineErreur


@pytest.fixture
def racine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("USINE_MODE_REPLI", raising=False)
    return preparer_racine(tmp_path, journal=False)


def test_url_jira(racine: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    url = charger_yaml(racine / "config" / "jira.yaml", ConfigJira).url_site
    assert composition.url_jira(racine) == url
    monkeypatch.setenv("USINE_MODE_REPLI", "1")
    assert composition.url_jira(racine) is None


def test_url_jira_sans_configuration(racine: Path) -> None:
    (racine / "config" / "jira.yaml").unlink()
    assert composition.url_jira(racine) is None


def test_secrets_illisibles(racine: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USINE_MODE_REPLI", "peut-être")
    with pytest.raises(UsineErreur, match="USINE_MODE_REPLI"):
        composition.construire_rapport(racine)


def test_generer_journal_delegue(racine: Path) -> None:
    programme = charger_yaml(racine / "config" / "programme.yaml", ConfigProgramme)
    chemin = composition.generer_journal(programme, 42, date(2026, 10, 12), racine)
    assert chemin == racine / "donnees" / "journal.jsonl"
    assert chemin.is_file()
    assert (racine / "donnees" / "verite_terrain.json").is_file()


def test_grille_incoherente_refusee_au_chargement(racine: Path) -> None:
    """FR-18 : orange plus sévère que rouge refusé avant tout Passage (Story 3.4)."""
    chemin = racine / "config" / "grille_meteo.yaml"
    texte = chemin.read_text(encoding="utf-8")
    assert 'orange: ">= 1"' in texte
    chemin.write_text(texte.replace('orange: ">= 1"', 'orange: ">= 4"', 1), encoding="utf-8")
    with pytest.raises(UsineErreur) as erreur:
        composition.construire_rapport(racine)
    message = str(erreur.value)
    assert str(chemin) in message
    assert "IND-1" in message
    assert "« >= 4 »" in message
