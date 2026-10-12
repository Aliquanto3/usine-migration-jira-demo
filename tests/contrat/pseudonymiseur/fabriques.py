"""Fabriques des adaptateurs de `Pseudonymiseur` soumis à la suite de contrat.

Deux appels d'une même fabrique doivent rendre des adaptateurs de même clé, sans table de
correspondance partagée (répertoire temporaire neuf pour un adaptateur persistant).
"""

import atexit
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from tests.doublures import PseudonymiseurFactice
from usine.adaptateurs.presidio import PseudonymiseurPresidio
from usine.adaptateurs.pseudonymisation import PseudonymiseurHmac
from usine.adaptateurs.stockage_sqlite import TablePseudonymesSqlite
from usine.contrats.config import ConfigPseudonymisation, Reconnaisseur
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
    ExempleSensible(
        # Le motif DOSSIER chevauche la clé ABC-2024 : la clé reste, le reste disparaît.
        "Dossier ABC-2024-5678-9012 bloqué (voir DEMO-8).",
        ("5678-9012",),
        ("ABC-2024", "DEMO-8"),
    ),
)

MOTIFS_FACTICES = {
    "COMPTE": r"FR\d{2}(?: \d{4}){3}",
    "CLIENT": r"\b(?:M\.|Mme) [A-Z][a-zé]+",
    "IDENTIFIANT": r"\b\d{6}\b",
    "DOSSIER": r"\d{4}-\d{4}-\d{4}",
}


def fabrique_factice() -> CasPseudonymiseur:
    """Doublure par expressions régulières et HMAC."""
    return CasPseudonymiseur(
        PseudonymiseurFactice(b"cle-de-test-fictive", MOTIFS_FACTICES),
        EXEMPLES,
    )


def _table_neuve() -> TablePseudonymesSqlite:
    """Table SQLite dans un répertoire temporaire neuf."""
    repertoire = Path(tempfile.mkdtemp(prefix="pseudonymes-"))
    atexit.register(shutil.rmtree, repertoire, ignore_errors=True)
    return TablePseudonymesSqlite(repertoire / "pseudonymes.sqlite")


def fabrique_hmac() -> CasPseudonymiseur:
    """Adaptateur de repli regex, table SQLite neuve."""
    return CasPseudonymiseur(
        PseudonymiseurHmac(b"cle-de-test-fictive", MOTIFS_FACTICES, _table_neuve()),
        EXEMPLES,
    )


CONFIG_PRESIDIO = ConfigPseudonymisation(
    entites_presidio=("PERSON",),
    reconnaisseurs=tuple(Reconnaisseur(type_jeton=t, motif=m) for t, m in MOTIFS_FACTICES.items()),
)
"""Motifs factices en reconnaisseurs maison, plus les personnes du modèle spaCy."""


@cache
def _moteur_presidio() -> PseudonymiseurPresidio:
    """Moteur Presidio construit une fois par session (chargement spaCy lent)."""
    return PseudonymiseurPresidio(b"cle-de-test-fictive", CONFIG_PRESIDIO, _table_neuve())


def fabrique_presidio() -> CasPseudonymiseur:
    """Moteur du Palier 2 : analyseur partagé, table SQLite neuve à chaque appel."""
    return CasPseudonymiseur(_moteur_presidio().avec_table(_table_neuve()), EXEMPLES)


FABRIQUES: list[tuple[str, Callable[[], CasPseudonymiseur]]] = [
    ("factice", fabrique_factice),
    ("hmac", fabrique_hmac),
    ("presidio", fabrique_presidio),
]
