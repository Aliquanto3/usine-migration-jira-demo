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


_SECRETS_JIRA = ("JIRA_EMAIL", "JIRA_TOKEN_LECTURE", "JIRA_TOKEN_INJECTION", "JIRA_DC_PAT")


@pytest.fixture(autouse=True, scope="session")
def _sans_secret_jira() -> Iterator[None]:
    """Neutralise les secrets Jira du shell du développeur : ils activeraient l'extraction Jira.

    Portée session : elle précède aussi les fixtures de module qui publient un Passage. Un test
    qui en a besoin les pose lui-même (`monkeypatch.setenv`). Le `.env` de la racine du dépôt
    n'est pas concerné : les Passages de test tournent sur des racines temporaires.
    """
    with pytest.MonkeyPatch.context() as patch:
        for variable in _SECRETS_JIRA:
            patch.delenv(variable, raising=False)
        yield
