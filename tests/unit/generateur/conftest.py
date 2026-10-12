"""Marqueur `lent` des tests du générateur (Story 1.3).

Un test `lent` (génération complète, plusieurs graines) est sauté par la suite par défaut ;
`uv run pytest -m lent` le sélectionne et l'exécute. Le marqueur est enregistré ici plutôt
que dans `pyproject.toml`, qui n'appartient pas à la lane.
"""

import re

import pytest

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
