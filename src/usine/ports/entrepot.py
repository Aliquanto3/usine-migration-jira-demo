"""Port `EntrepotExtraction` : stockage des événements extraits et du repère (AD-6)."""

from collections.abc import Iterable, Iterator
from datetime import datetime
from typing import Protocol, runtime_checkable

from usine.contrats.evenements import Evenement


@runtime_checkable
class EntrepotExtraction(Protocol):
    """Entrepôt d'extraction, ouvert par la seule étape `extraction`."""

    def repere(self) -> datetime | None:
        """Repère de la dernière extraction validée (`None` avant la première)."""
        ...

    def enregistrer(self, evenements: Iterable[Evenement], repere: datetime) -> int:
        """Enregistre événements et repère dans une même transaction atomique.

        Les événements sont dédoublonnés par `id_evenement` ; renvoie le nombre d'ajouts.
        """
        ...

    def evenements(self) -> Iterator[Evenement]:
        """Tous les événements stockés, alignements compris."""
        ...
