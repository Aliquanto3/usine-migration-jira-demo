"""Fabriques des adaptateurs de `Pseudonymiseur` soumis à la suite de contrat.

Deux appels d'une même fabrique doivent rendre des adaptateurs de même clé, sans table de
correspondance partagée (répertoire temporaire neuf pour un adaptateur persistant).
"""

from collections.abc import Callable
from dataclasses import dataclass

from tests.doublures import PseudonymiseurFactice
from usine.ports import Pseudonymiseur


@dataclass(frozen=True)
class ExempleSensible:
    """Texte d'essai, valeurs sensibles fictives qu'il contient et clés de ticket à garder."""

    texte: str
    valeurs_sensibles: tuple[str, ...]
    cles_ticket: tuple[str, ...] = ()


@dataclass(frozen=True)
class CasPseudonymiseur:
    """Adaptateur à éprouver et exemples sensibles."""

    pseudonymiseur: Pseudonymiseur
    exemples: tuple[ExempleSensible, ...]


EXEMPLES = (
    ExempleSensible(
        "Le compte FR76 1234 5678 9012 de Mme Exemplaire est rejeté (voir DEMO-204518).",
        ("FR76 1234 5678 9012", "Mme Exemplaire"),
        ("DEMO-204518",),
    ),
    ExempleSensible(
        "Client n° 204519 : écart de solde, doublon de DEMO-7 ; M. Fictif relance.",
        ("204519", "M. Fictif"),
        ("DEMO-7",),
    ),
    ExempleSensible("Aucune donnée sensible dans DEMO-12.", (), ("DEMO-12",)),
)

MOTIFS_FACTICES = {
    "COMPTE": r"FR\d{2}(?: \d{4}){3}",
    "CLIENT": r"\b(?:M\.|Mme) [A-Z][a-zé]+",
    "IDENTIFIANT": r"\b\d{6}\b",
}


def fabrique_factice() -> CasPseudonymiseur:
    """Doublure par expressions régulières et HMAC."""
    return CasPseudonymiseur(
        PseudonymiseurFactice(b"cle-de-test-fictive", MOTIFS_FACTICES),
        EXEMPLES,
    )


FABRIQUES: list[tuple[str, Callable[[], CasPseudonymiseur]]] = [
    ("factice", fabrique_factice),
]
