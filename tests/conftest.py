"""Configuration commune des tests : aucun accès réseau hors `@pytest.mark.reseau` (NFR-7)."""

import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

RACINE_DEPOT = Path(__file__).resolve().parents[1]

_HOTES_LOCAUX = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture
def racine_depot() -> Path:
    """Racine du dépôt."""
    return RACINE_DEPOT


@pytest.fixture(autouse=True)
def _sans_reseau(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Refuse toute connexion hors boucle locale, sauf pour les tests marqués `reseau`."""
    if request.node.get_closest_marker("reseau") is not None:
        yield
        return
    connecter = socket.socket.connect

    def connecter_local(self: socket.socket, adresse: Any) -> None:
        if isinstance(adresse, tuple) and adresse[0] not in _HOTES_LOCAUX:
            raise RuntimeError(f"accès réseau interdit hors @pytest.mark.reseau : {adresse!r}")
        connecter(self, adresse)

    monkeypatch.setattr(socket.socket, "connect", connecter_local)
    yield
