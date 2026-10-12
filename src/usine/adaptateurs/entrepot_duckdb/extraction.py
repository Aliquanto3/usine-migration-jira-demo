"""Extraction incrémentale : de la source à l'entrepôt, depuis `repère − marge` (FR-6, AD-6).

Le nouveau repère est l'instant `horloge()` pris avant l'appel à la source : toute
modification faite pendant l'extraction est revue au Passage suivant. Événements et repère
sont validés ensemble par `EntrepotExtraction.enregistrer`, ou pas du tout.

`EtapeExtraction` (port `Etape`) est la seule à ouvrir l'entrepôt, avec la composition.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from usine.adaptateurs.entrepot_duckdb.entrepot import EntrepotDuckDB
from usine.contrats.passage import ContextePassage, ResultatEtape, StatutEtape
from usine.ports import EntrepotExtraction, SourceTickets
from usine.ports.consultation import Consultation


def _maintenant() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ResultatExtraction:
    """Bilan d'une extraction validée."""

    ajouts: int
    """Événements nouvellement stockés."""
    repere: datetime
    """Repère enregistré, pris avant l'appel à la source."""
    depuis: datetime | None
    """Instant demandé à la source (`None` au premier Passage)."""


def extraire(
    source: SourceTickets,
    entrepot: EntrepotExtraction,
    marge: timedelta,
    horloge: Callable[[], datetime] = _maintenant,
) -> ResultatExtraction:
    """Stocke les événements de `source` depuis `repère − marge` et avance le repère."""
    precedent = entrepot.repere()
    repere = horloge()
    depuis = None if precedent is None else precedent - marge
    ajouts = entrepot.enregistrer(source.evenements(depuis), repere)
    return ResultatExtraction(ajouts=ajouts, repere=repere, depuis=depuis)


class EtapeExtraction:
    """Étape `extraction` : ouvre l'entrepôt `chemin` et y verse la source."""

    def __init__(
        self,
        source: SourceTickets,
        chemin: Path,
        marge: timedelta,
        horloge: Callable[[], datetime] = _maintenant,
    ) -> None:
        self._source = source
        self._chemin = chemin
        self._marge = marge
        self._horloge = horloge

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Extrait dans l'entrepôt ; une erreur laisse événements et repère inchangés."""
        extraire(self._source, EntrepotDuckDB(self._chemin), self._marge, self._horloge)
        return ResultatEtape(StatutEtape.reussie)
