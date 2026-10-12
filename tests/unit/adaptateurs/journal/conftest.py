"""Marqueur `lent` et réseau coupé pour les tests de l'adaptateur Journal (Story 2.5).

Un test `lent` (Journal à la volumétrie de `config/programme.yaml`) est sauté par la suite par
défaut ; `uv run pytest -m lent` le sélectionne et l'exécute. Le marqueur est enregistré ici
plutôt que dans `pyproject.toml`, qui n'appartient pas à la lane. Toute connexion socket est
interdite dans ce répertoire : le Journal se lit sans réseau (FR-8).
"""

import re

import pytest

from tests.unit.adaptateurs.journal.outils import couper_reseau

_MARQUEUR = "lent"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", f"{_MARQUEUR}: test long, sauté par défaut, lancé par `-m {_MARQUEUR}`"
    )


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Saute un test `lent` sauf si l'expression `-m` nomme le marqueur."""
    expression = item.config.getoption("markexpr", default="") or ""
    if item.get_closest_marker(_MARQUEUR) and not re.search(rf"\b{_MARQUEUR}\b", expression):
        pytest.skip(f"test {_MARQUEUR} : lancer `uv run pytest -m {_MARQUEUR}`")


@pytest.fixture(autouse=True)
def sans_reseau(monkeypatch: pytest.MonkeyPatch) -> None:
    """Connexions socket interdites pendant chaque test du répertoire."""
    couper_reseau(monkeypatch)
