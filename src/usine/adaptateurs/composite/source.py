"""`SourceComposite` : le Journal jusqu'à la fin d'injection, puis le changelog Jira (AD-4).

La coupure se fait par instants : tout le Journal (lu aux clés Jira), puis les seuls
événements Jira d'horodatage strictement postérieur à `horodatage_fin_injection` du manifeste
d'injection, alignements compris. Les événements Jira de l'intervalle d'injection (créations
et attributs initiaux posés par l'injecteur) sont ignorés : le Journal en porte déjà l'histoire.
"""

import heapq
from collections.abc import Callable, Iterable, Iterator
from datetime import datetime

from usine.adaptateurs.journal import SourceJournal
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import Evenement, ManifesteInjection


def _horodatage(evenement: Evenement) -> datetime:
    return evenement.horodatage


class SourceComposite:
    """`SourceTickets` composite : Journal, puis événements Jira postérieurs à l'injection.

    `jira` rend, à chaque appel, les événements Jira connus (ex. ceux de l'entrepôt après
    l'étape `extraction`), dans n'importe quel ordre. Le flux est trié par horodatage ; à
    horodatage égal, le Journal passe avant Jira et l'ordre de chaque origine est gardé. Un
    `id_evenement` déjà rendu est ignoré. Un Journal lu sans manifeste d'injection est refusé
    à la construction.
    """

    def __init__(self, journal: SourceJournal, jira: Callable[[], Iterable[Evenement]]) -> None:
        manifeste = journal.manifeste
        if manifeste is None:
            raise UsineErreur(
                f"{journal.chemin} : source composite impossible sans manifeste d'injection"
                " (coupure à horodatage_fin_injection inconnue)"
            )
        self._journal = journal
        self._jira = jira
        self._manifeste = manifeste

    @property
    def journal(self) -> SourceJournal:
        """Journal lu aux clés Jira."""
        return self._journal

    @property
    def manifeste(self) -> ManifesteInjection:
        """Manifeste d'injection qui fixe la coupure."""
        return self._manifeste

    @property
    def horodatage_fin_injection(self) -> datetime:
        """Instant de coupure : seuls les événements Jira strictement postérieurs sont pris."""
        return self._manifeste.horodatage_fin_injection

    def evenements(self, depuis: datetime | None = None) -> Iterator[Evenement]:
        """Événements d'horodatage ≥ `depuis` (tous si `None`), par horodatage croissant."""
        if depuis is not None and (depuis.tzinfo is None or depuis.utcoffset() is None):
            raise UsineErreur(f"source composite : « depuis » sans fuseau : {depuis!r}")
        fin = self.horodatage_fin_injection
        jira = sorted(
            (
                evenement
                for evenement in self._jira()
                if evenement.horodatage > fin and (depuis is None or evenement.horodatage >= depuis)
            ),
            key=_horodatage,
        )
        return self._fusion(self._journal.evenements(depuis), jira)

    @staticmethod
    def _fusion(journal: Iterator[Evenement], jira: list[Evenement]) -> Iterator[Evenement]:
        # `heapq.merge` est stable : à clé égale, le premier itérable (le Journal) passe devant.
        vus: set[str] = set()
        for evenement in heapq.merge(journal, jira, key=_horodatage):
            if evenement.id_evenement in vus:
                continue
            vus.add(evenement.id_evenement)
            yield evenement
