"""Environnement aux versions du spine, secrets et fichiers ignorés par git (AD-19)."""

import subprocess
from importlib.metadata import version
from pathlib import Path

import pytest

# Section « Stack » du spine d'architecture (hors bonus).
VERSIONS_SPINE = {
    "pydantic": "2.14.0",
    "pydantic-settings": "2.15.0",
    "polars": "1.44.2",
    "duckdb": "1.5.6",
    "numpy": "2.4.6",
    "pyarrow": "25.0.1",
    "pyyaml": "6.0.3",
    "typer": "0.27.3",
    "httpx": "0.28.1",
    "pydantic-ai-slim": "2.55.0",
    "presidio-analyzer": "2.2.364",
    "presidio-anonymizer": "2.2.364",
    "spacy": "3.8.16",
    "fr-core-news-md": "3.8.0",
    "openpyxl": "3.1.5",
    "python-pptx": "1.0.2",
    "fastapi": "0.143.3",
    "uvicorn": "0.54.0",
    "markdown-it-py": "4.2.0",
    "tzdata": "2026.5",
    "scikit-learn": "1.9.1",
    "pymongo": "4.18.3",
    "pytest": "9.1.1",
    "ruff": "0.17.0",
    "mypy": "2.4.0",
    "import-linter": "2.15",
    "time-machine": "3.5.1",
}

VARIABLES_SECRETES = [
    "JIRA_EMAIL",
    "JIRA_TOKEN_LECTURE",
    "JIRA_TOKEN_INJECTION",
    "JIRA_DC_PAT",
    "ANTHROPIC_API_KEY",
    "MISTRAL_API_KEY",
    "USINE_CLE_PSEUDO",
    "USINE_MODE_REPLI",
]


@pytest.mark.parametrize(("paquet", "attendue"), sorted(VERSIONS_SPINE.items()))
def test_version_installee(paquet: str, attendue: str) -> None:
    assert version(paquet) == attendue


def test_env_example_liste_les_variables_sans_valeur(racine_depot: Path) -> None:
    lignes = (racine_depot / ".env.example").read_text(encoding="utf-8").splitlines()
    affectations = dict(
        ligne.split("=", 1) for ligne in lignes if ligne.strip() and not ligne.startswith("#")
    )
    for nom in VARIABLES_SECRETES:
        assert nom in affectations, nom
    assert all(valeur.strip() == "" for valeur in affectations.values())


def _ignore(racine: Path, chemin: str) -> bool:
    resultat = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", chemin], cwd=racine, check=False
    )
    return resultat.returncode == 0


@pytest.mark.parametrize(
    "chemin", [".env", "donnees/entrepot.duckdb", "donnees/injection/manifeste.json", "sorties/x"]
)
def test_chemins_ignores(racine_depot: Path, chemin: str) -> None:
    assert _ignore(racine_depot, chemin)


@pytest.mark.parametrize("chemin", [".env.example", "donnees/corpus/textes.json"])
def test_chemins_versionnes(racine_depot: Path, chemin: str) -> None:
    assert not _ignore(racine_depot, chemin)
