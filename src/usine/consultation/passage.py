"""`ConsultationPassage` minimal : lecture d'un Passage par les étapes de la Chaîne (AD-22).

Seule `tickets_etats` est lue ici (Story 0.5) ; les autres lectures du port `Consultation`
arrivent avec la Story 0.6. Chaque fichier est lu en ouvrir-lire-fermer.
"""

from datetime import date
from pathlib import Path
from typing import NoReturn

import polars as pl

from usine.contrats.agent import ResultatListAnomalies
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import SortieClassification, SortieExplication, SortieNarration
from usine.contrats.meteo import EvolutionMeteo, MeteoEntite
from usine.contrats.passage import FICHIERS_PASSAGE, ManifestePassage
from usine.contrats.prevision import Prevision, RisqueEntreeRouge
from usine.contrats.schemas import SchemaTable, valider
from usine.contrats.tickets import SCHEMA_TICKET_ETAT, Gravite, Phase
from usine.contrats.trace import EntreeTrace
from usine.contrats.versions import CLE_VERSION, verifier_version
from usine.ports.consultation import Palier

MESSAGE_STORY_0_6 = "lecture disponible à la Story 0.6"


def _indisponible() -> NoReturn:
    raise UsineErreur(MESSAGE_STORY_0_6)


def lire_table(chemin: Path, schema: SchemaTable) -> pl.DataFrame:
    """Lit une table Parquet d'un Passage : version de contrats vérifiée, puis schéma validé."""
    try:
        metadonnees = pl.read_parquet_metadata(chemin)
    except FileNotFoundError as exc:
        raise UsineErreur(f"{chemin} : fichier du Passage introuvable") from exc
    except (OSError, pl.exceptions.PolarsError) as exc:
        raise UsineErreur(f"{chemin} : fichier Parquet illisible ({exc})") from exc
    version = metadonnees.get(CLE_VERSION)
    if version is None:
        raise UsineErreur(f"{chemin} : métadonnée « {CLE_VERSION} » absente")
    try:
        verifier_version(version)
    except UsineErreur as exc:
        raise UsineErreur(f"{chemin} : {exc}") from exc
    try:
        table = pl.read_parquet(chemin)
    except (OSError, pl.exceptions.PolarsError) as exc:
        raise UsineErreur(f"{chemin} : fichier Parquet illisible ({exc})") from exc
    try:
        return valider(table, schema)
    except UsineErreur as exc:
        raise UsineErreur(f"{chemin} : {exc}") from exc


class ConsultationPassage:
    """Lecteur minimal d'un Passage (publié ou en construction) dans `repertoire`."""

    def __init__(self, repertoire: Path) -> None:
        self._repertoire = repertoire
        self._tickets_etats: pl.DataFrame | None = None

    @property
    def repertoire(self) -> Path:
        """Répertoire du Passage lu."""
        return self._repertoire

    def tickets_etats(self, date_arrete: date | None = None) -> pl.DataFrame:
        """Table `SCHEMA_TICKET_ETAT` à la date donnée (`None` : dernière date de la table).

        La table est lue une fois, puis gardée en mémoire : un fichier de Passage n'est écrit
        qu'une fois.
        """
        if self._tickets_etats is None:
            self._tickets_etats = lire_table(
                self._repertoire / FICHIERS_PASSAGE["tickets_etats"], SCHEMA_TICKET_ETAT
            )
        table = self._tickets_etats
        if date_arrete is None:
            derniere = table.get_column("date").max()
            if not isinstance(derniere, date):
                return table
            date_arrete = derniere
        return table.filter(pl.col("date") == date_arrete)

    # --- Lectures de la Story 0.6 ---

    def dernier_passage(self) -> ManifestePassage | None:
        """Disponible à la Story 0.6."""
        _indisponible()

    def manifeste(self) -> ManifestePassage:
        """Disponible à la Story 0.6."""
        _indisponible()

    def dates_disponibles(self) -> tuple[date, ...]:
        """Disponible à la Story 0.6."""
        _indisponible()

    def meteo(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[MeteoEntite, ...]:
        """Disponible à la Story 0.6."""
        _indisponible()

    def evolution_meteo(self, date_arrete: date | None = None) -> tuple[EvolutionMeteo, ...]:
        """Disponible à la Story 0.6."""
        _indisponible()

    def instantanes(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> pl.DataFrame:
        """Disponible à la Story 0.6."""
        _indisponible()

    def indicateurs(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> pl.DataFrame:
        """Disponible à la Story 0.6."""
        _indisponible()

    def kpi(self, date_arrete: date | None = None, entite: str | None = None) -> pl.DataFrame:
        """Disponible à la Story 0.6."""
        _indisponible()

    def tendances(self, entite: str | None = None, code_kpi: str | None = None) -> pl.DataFrame:
        """Disponible à la Story 0.6."""
        _indisponible()

    def textes_tickets(self) -> pl.DataFrame:
        """Disponible à la Story 0.6."""
        _indisponible()

    def anomalies(
        self,
        date_arrete: date | None = None,
        entite: str | None = None,
        gravite: Gravite | None = None,
        phase: Phase | None = None,
        domaine: str | None = None,
        limite: int | None = None,
    ) -> ResultatListAnomalies:
        """Disponible à la Story 0.6."""
        _indisponible()

    def previsions(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[Prevision, ...]:
        """Disponible à la Story 0.6."""
        _indisponible()

    def risques(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[RisqueEntreeRouge, ...]:
        """Disponible à la Story 0.6."""
        _indisponible()

    def classification(self, palier: Palier = 2) -> tuple[SortieClassification, ...]:
        """Disponible à la Story 0.6."""
        _indisponible()

    def repartition_causes(self, entite: str | None = None, palier: Palier = 2) -> pl.DataFrame:
        """Disponible à la Story 0.6."""
        _indisponible()

    def explications(
        self, entite: str | None = None, palier: Palier = 2
    ) -> tuple[SortieExplication, ...]:
        """Disponible à la Story 0.6."""
        _indisponible()

    def narrations(
        self, entite: str | None = None, palier: Palier = 2
    ) -> tuple[SortieNarration, ...]:
        """Disponible à la Story 0.6."""
        _indisponible()

    def traces(self) -> tuple[EntreeTrace, ...]:
        """Disponible à la Story 0.6."""
        _indisponible()

    def url_ticket(self, cle: str) -> str | None:
        """Disponible à la Story 0.6."""
        _indisponible()
