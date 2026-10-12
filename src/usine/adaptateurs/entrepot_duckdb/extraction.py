"""Extraction incrémentale : de la source à l'entrepôt, depuis `repère − marge` (FR-6, AD-6).

Le nouveau repère est l'instant `horloge()` pris avant l'appel à la source : toute
modification faite pendant l'extraction est revue au Passage suivant. Événements et repère
sont validés ensemble par `EntrepotExtraction.enregistrer`, ou pas du tout.

Avec `aligner` (source composite, H-27), les événements stockés et les nouveaux sont
matérialisés, puis les alignements détectés à l'instant du repère et encore inconnus de
l'entrepôt sont ajoutés au même `enregistrer` : événements, alignements et repère sont
validés dans une seule transaction, et un alignement n'est persisté qu'une fois.

`EtapeExtraction` (port `Etape`) est la seule à ouvrir l'entrepôt, avec la composition.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from usine.adaptateurs.entrepot_duckdb.entrepot import EntrepotDuckDB
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import Evenement
from usine.contrats.passage import ContextePassage, ResultatEtape, StatutEtape
from usine.ports import EntrepotExtraction, SourceTickets
from usine.ports.consultation import Consultation

Aligneur = Callable[[Iterable[Evenement], datetime], Iterable[Evenement]]
"""Détecteur d'alignements : `(événements Jira connus, instant de détection) -> alignements`."""


def _maintenant() -> datetime:
    return datetime.now(UTC)


def _horodatage(evenement: Evenement) -> datetime:
    return evenement.horodatage


@dataclass(frozen=True)
class ResultatExtraction:
    """Bilan d'une extraction validée."""

    ajouts: int
    """Événements nouvellement stockés (alignements compris)."""
    repere: datetime
    """Repère enregistré, pris avant l'appel à la source."""
    depuis: datetime | None
    """Instant demandé à la source (`None` au premier Passage)."""
    alignements: int = 0
    """Alignements nouvellement stockés par cette extraction (0 sans `aligner`)."""
    evenements: tuple[Evenement, ...] | None = None
    """Avec `aligner` : événements stockés après l'extraction, par horodatage ; sinon `None`."""


def extraire(
    source: SourceTickets,
    entrepot: EntrepotExtraction,
    marge: timedelta,
    horloge: Callable[[], datetime] = _maintenant,
    aligner: Aligneur | None = None,
) -> ResultatExtraction:
    """Stocke les événements de `source` depuis `repère − marge` et avance le repère.

    Avec `aligner`, ajoute dans la même transaction les alignements détectés à l'instant du
    repère sur tous les événements (stockés puis nouveaux, dédoublonnés par `id_evenement`).
    """
    precedent = entrepot.repere()
    repere = horloge()
    depuis = None if precedent is None else precedent - marge
    if aligner is None:
        ajouts = entrepot.enregistrer(source.evenements(depuis), repere)
        return ResultatExtraction(ajouts=ajouts, repere=repere, depuis=depuis)
    stockes = list(entrepot.evenements())
    connus = {evenement.id_evenement for evenement in stockes}
    nouveaux: list[Evenement] = []
    for evenement in source.evenements(depuis):
        if evenement.id_evenement not in connus:
            connus.add(evenement.id_evenement)
            nouveaux.append(evenement)
    # Tri stable : à horodatage égal, l'ordre de l'entrepôt (lot, rang) est gardé.
    tous = sorted([*stockes, *nouveaux], key=_horodatage)
    detectes: list[Evenement] = []
    for alignement in aligner(tous, repere):
        if alignement.id_evenement not in connus:
            connus.add(alignement.id_evenement)
            detectes.append(alignement)
    ajouts = entrepot.enregistrer([*nouveaux, *detectes], repere)
    return ResultatExtraction(
        ajouts=ajouts,
        repere=repere,
        depuis=depuis,
        alignements=len(detectes),
        evenements=tuple(sorted([*tous, *detectes], key=_horodatage)),
    )


class EtapeExtraction:
    """Étape `extraction` : ouvre l'entrepôt `chemin` et y verse la source.

    `fermer` (ex. fermeture du client Jira de la source) est appelé après l'étape, qu'elle
    réussisse ou échoue. Avec `aligner`, l'étape persiste aussi les alignements détectés et
    expose les événements extraits (`evenements_extraits`) à la source composite.
    """

    def __init__(
        self,
        source: SourceTickets,
        chemin: Path,
        marge: timedelta,
        horloge: Callable[[], datetime] = _maintenant,
        fermer: Callable[[], None] | None = None,
        aligner: Aligneur | None = None,
    ) -> None:
        self._source = source
        self._chemin = chemin
        self._marge = marge
        self._horloge = horloge
        self._fermer = fermer
        self._aligner = aligner
        self._resultat: ResultatExtraction | None = None

    @property
    def source(self) -> SourceTickets:
        """Source des événements extraits."""
        return self._source

    @property
    def chemin(self) -> Path:
        """Chemin de l'entrepôt DuckDB."""
        return self._chemin

    @property
    def marge(self) -> timedelta:
        """Marge de recouvrement retranchée au repère."""
        return self._marge

    @property
    def aligner(self) -> Aligneur | None:
        """Détecteur d'alignements (`None` : extraction sans alignement)."""
        return self._aligner

    def fermer(self) -> None:
        """Appelle `fermer` du constructeur une seule fois (après l'étape ou en fin de Passage)."""
        fermer, self._fermer = self._fermer, None
        if fermer is not None:
            fermer()

    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        """Extrait dans l'entrepôt ; une erreur laisse événements et repère inchangés."""
        self._resultat = None
        try:
            self._resultat = extraire(
                self._source,
                EntrepotDuckDB(self._chemin),
                self._marge,
                self._horloge,
                self._aligner,
            )
        finally:
            self.fermer()
        return ResultatEtape(StatutEtape.reussie)

    def _bilan(self, quoi: str) -> ResultatExtraction:
        if self._resultat is None:
            raise UsineErreur(
                f"{self._chemin} : étape « extraction » non exécutée ou en échec, {quoi} inconnu"
            )
        return self._resultat

    def nb_alignements(self) -> int:
        """Alignements nouvellement persistés par la dernière exécution (0 sans `aligner`)."""
        return self._bilan("nombre d'alignements").alignements

    def evenements_extraits(self) -> tuple[Evenement, ...]:
        """Événements de l'entrepôt après la dernière exécution, alignements compris.

        `UsineErreur` si l'étape n'a pas été exécutée, a échoué ou n'a pas d'`aligner`.
        """
        if self._aligner is None:
            raise UsineErreur(
                f"{self._chemin} : étape « extraction » sans détecteur d'alignements,"
                " événements extraits non matérialisés"
            )
        evenements = self._bilan("flux extrait").evenements
        if evenements is None:  # pragma: no cover - toujours renseigné avec `aligner`
            raise UsineErreur(f"{self._chemin} : événements extraits non matérialisés")
        return evenements
