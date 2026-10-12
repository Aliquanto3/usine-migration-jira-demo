"""Contrôles déterministes des sorties LLM (AD-12, FR-32).

`controler_citations` garde les seules phrases qui citent au moins une clé de ticket et
aucune clé hors des tickets autorisés. N'est une Citation qu'une clé dont le projet (partie
avant le dernier `-`) est celui d'au moins un ticket autorisé : `IND-1`, `ENT-12`, `UTF-8` ou
`SHA-256` ont la forme d'une clé de ticket mais sont ignorés. Les clés de ticket ne sont jamais
pseudonymisées : le contrôle s'applique donc indifféremment avant ou après la
ré-identification.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass

from usine.contrats.tickets import MOTIF_CLE_TICKET, rang_cle

_CLE_TICKET = re.compile(rf"\b{MOTIF_CLE_TICKET}\b")
_FIN_DE_PHRASE = re.compile(r"(?<=[.!?])\s+|\s*\n\s*")
"""Une phrase finit par `.`, `!` ou `?` suivi d'un blanc (ou de la fin), ou par un saut de ligne."""


@dataclass(frozen=True)
class ControleCitations:
    """Résultat de `controler_citations`."""

    texte: str
    """Phrases retenues, jointes par une espace."""
    citations: tuple[str, ...]
    """Clés citées par les phrases retenues, sans doublon, triées."""
    phrases_retirees: int
    phrases_total: int


def decouper_phrases(texte: str) -> tuple[str, ...]:
    """Phrases de `texte` ; coupe après `.`, `!` ou `?` suivi d'un blanc, et à chaque ligne."""
    morceaux = (phrase.strip() for phrase in _FIN_DE_PHRASE.split(texte.strip()))
    return tuple(phrase for phrase in morceaux if phrase)


def projet(cle: str) -> str:
    """Projet d'une clé : partie avant le dernier `-` (`DEMO-12` → `DEMO`)."""
    return cle.rpartition("-")[0]


def citations(phrase: str, projets: frozenset[str]) -> frozenset[str]:
    """Clés de ticket citées par `phrase` dont le projet figure dans `projets`."""
    return frozenset(cle for cle in _CLE_TICKET.findall(phrase) if projet(cle) in projets)


def controler_citations(texte: str, tickets_autorises: Iterable[str]) -> ControleCitations:
    """Retire chaque phrase sans clé de ticket ou citant une clé hors de `tickets_autorises`."""
    autorises = frozenset(tickets_autorises)
    projets = frozenset(projet(cle) for cle in autorises)
    retenues: list[str] = []
    citees: set[str] = set()
    phrases = decouper_phrases(texte)
    for phrase in phrases:
        cles = citations(phrase, projets)
        if cles and cles <= autorises:
            retenues.append(phrase)
            citees |= cles
    return ControleCitations(
        texte=" ".join(retenues),
        citations=tuple(sorted(citees, key=rang_cle)),
        phrases_retirees=len(phrases) - len(retenues),
        phrases_total=len(phrases),
    )


def retirer_citations_hors(texte: str, tickets_autorises: Iterable[str]) -> str:
    """Retire de `texte` les phrases qui citent une clé hors de `tickets_autorises`.

    Une phrase sans Citation reste (brouillon de commentaire).
    """
    autorises = frozenset(tickets_autorises)
    projets = frozenset(projet(cle) for cle in autorises)
    return " ".join(
        phrase for phrase in decouper_phrases(texte) if citations(phrase, projets) <= autorises
    )
