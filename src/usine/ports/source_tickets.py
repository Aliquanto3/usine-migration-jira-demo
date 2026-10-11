"""Port `SourceTickets` : flux d'`Evenement` canoniques (AD-3, AD-20)."""

from collections.abc import Iterator
from datetime import datetime
from typing import Protocol, runtime_checkable

from usine.contrats.evenements import Evenement


@runtime_checkable
class SourceTickets(Protocol):
    """Source d'événements : Journal, Jira Cloud, Jira Data Center ou composite."""

    def evenements(self, depuis: datetime | None = None) -> Iterator[Evenement]:
        """Événements d'horodatage ≥ `depuis` (tous si `None`), par horodatage croissant.

        Chaque `id_evenement` est unique ; `depuis` sans fuseau lève une `UsineErreur`.
        """
        ...
