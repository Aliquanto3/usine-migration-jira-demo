"""Réseau coupé pour les tests de la source composite (Story 2.6) : aucun appel Jira réel.

Seuls les tests marqués `@pytest.mark.reseau` (recette en direct, Story 2.7) y échappent.
"""

import pytest

from tests.unit.adaptateurs.journal.outils import couper_reseau


@pytest.fixture(autouse=True)
def sans_reseau(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Connexions socket interdites pendant chaque test du répertoire, sauf `reseau`."""
    if request.node.get_closest_marker("reseau") is None:
        couper_reseau(monkeypatch)
