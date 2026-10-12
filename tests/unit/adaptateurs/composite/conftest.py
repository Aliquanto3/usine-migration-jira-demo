"""Réseau coupé pour les tests de la source composite (Story 2.6) : aucun appel Jira réel."""

import pytest

from tests.unit.adaptateurs.journal.outils import couper_reseau


@pytest.fixture(autouse=True)
def sans_reseau(monkeypatch: pytest.MonkeyPatch) -> None:
    """Connexions socket interdites pendant chaque test du répertoire."""
    couper_reseau(monkeypatch)
