"""Réseau coupé pour les tests de l'adaptateur Journal (Story 2.5).

Toute connexion socket est interdite dans ce répertoire : le Journal se lit sans réseau (FR-8).
Le test à la volumétrie de `config/programme.yaml` porte le marqueur `lent`, déclaré dans
`pyproject.toml` et exclu par défaut (`uv run pytest -m lent` le lance).
"""

import pytest

from tests.unit.adaptateurs.journal.outils import couper_reseau


@pytest.fixture(autouse=True)
def sans_reseau(monkeypatch: pytest.MonkeyPatch) -> None:
    """Connexions socket interdites pendant chaque test du répertoire."""
    couper_reseau(monkeypatch)
