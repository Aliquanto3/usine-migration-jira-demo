"""`SourceEnMemoire` : `SourceTickets` sur une liste d'`Evenement` fournie (AD-3)."""

from collections.abc import Iterable, Iterator
from datetime import datetime

from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import Evenement, NatureEvenement


class SourceEnMemoire:
    """Rend les événements reçus par horodatage croissant.

    À horodatage égal, une création passe en tête ; sinon l'ordre d'arrivée est gardé.
    """

    def __init__(self, evenements: Iterable[Evenement]) -> None:
        self._evenements = tuple(
            sorted(
                evenements,
                key=lambda e: (e.horodatage, e.nature is not NatureEvenement.creation),
            )
        )
        ids = [e.id_evenement for e in self._evenements]
        if len(set(ids)) != len(ids):
            raise UsineErreur("SourceEnMemoire : id_evenement en double")

    def evenements(self, depuis: datetime | None = None) -> Iterator[Evenement]:
        """Événements d'horodatage ≥ `depuis` (tous si `None`)."""
        if depuis is not None and (depuis.tzinfo is None or depuis.utcoffset() is None):
            raise UsineErreur(f"SourceEnMemoire : « depuis » sans fuseau : {depuis!r}")
        for evenement in self._evenements:
            if depuis is None or evenement.horodatage >= depuis:
                yield evenement
