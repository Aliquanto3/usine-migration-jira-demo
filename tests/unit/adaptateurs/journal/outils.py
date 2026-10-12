"""Outils des tests du Journal : réseau coupé et manifeste d'injection fictif (Story 2.5)."""

import socket
from collections.abc import Iterable
from datetime import UTC, datetime, time, timedelta

import pytest

from usine.contrats.evenements import EnteteJournal, Evenement, ManifesteInjection

DECALAGE = 100_000
"""Décalage des numéros de clé : `DEMO-n` → `DEMO-(n + DECALAGE)`."""


def couper_reseau(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fait échouer toute connexion socket pendant le test."""

    def interdit(*args: object, **kwargs: object) -> None:
        raise AssertionError("connexion réseau interdite pendant le test")

    monkeypatch.setattr(socket.socket, "connect", interdit)
    monkeypatch.setattr(socket.socket, "connect_ex", interdit)
    monkeypatch.setattr(socket, "create_connection", interdit)


def cle_jira(cle: str, decalage: int = DECALAGE) -> str:
    """`DEMO-n` → `DEMO-(n + decalage)`."""
    projet, numero = cle.rsplit("-", 1)
    return f"{projet}-{int(numero) + decalage}"


def manifeste_pour(
    entete: EnteteJournal,
    evenements: Iterable[Evenement],
    decalage: int = DECALAGE,
    sans: frozenset[str] = frozenset(),
) -> ManifesteInjection:
    """Manifeste fictif : chaque clé du Journal (sauf `sans`) → `cle_jira(clé, decalage)`."""
    cles = {e.cle_ticket for e in evenements} - sans
    debut = datetime.combine(entete.date_injection, time(18, 0), tzinfo=UTC)
    return ManifesteInjection(
        date_injection=entete.date_injection,
        debut_injection=debut,
        horodatage_fin_injection=debut + timedelta(minutes=20),
        cle_projet="DEMO",
        correspondance_cles={cle: cle_jira(cle, decalage) for cle in sorted(cles)},
    )
