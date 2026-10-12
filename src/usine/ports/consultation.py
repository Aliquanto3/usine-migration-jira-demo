"""Port `Consultation` : lecteur unique d'un Passage (AD-11).

Un `date_arrete` à `None` désigne la Date d'arrêté du Passage lu. Toute lecture qui porte une
sortie du Palier 2 prend un filtre `palier` (FR-46) : `palier=1` la renvoie vide, ou sans la
cause racine proposée pour `anomalies`. Les tables sont validées par leur `SCHEMA_X`.
"""

from datetime import date
from typing import Literal, Protocol, runtime_checkable

import polars as pl

from usine.contrats.agent import ResultatListAnomalies
from usine.contrats.llm import SortieClassification, SortieExplication, SortieNarration
from usine.contrats.meteo import EvolutionMeteo, MeteoEntite
from usine.contrats.passage import ManifestePassage
from usine.contrats.prevision import Prevision, RisqueEntreeRouge
from usine.contrats.tickets import Gravite, Phase
from usine.contrats.trace import EntreeTrace

Palier = Literal[1, 2]


@runtime_checkable
class Consultation(Protocol):
    """Lectures d'un Passage, publié ou en cours, pour les étapes, le rendu, l'UI et l'Agent."""

    def dernier_passage(
        self, sans_classification_initiale: bool = False
    ) -> ManifestePassage | None:
        """Dernier Passage publié : maximum de `(date_arrete, horodatage_fin)` (AD-7).

        `sans_classification_initiale=True` écarte les Passages qui ont fait la classification
        initiale (mesure de FR-44, AD-8).
        """
        ...

    def manifeste(self) -> ManifestePassage:
        """Manifeste du Passage lu."""
        ...

    def dates_disponibles(self) -> tuple[date, ...]:
        """Jours ouvrés couverts par le Passage, dans l'ordre."""
        ...

    def meteo(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[MeteoEntite, ...]:
        """Météo et Règles déclenchantes (FR-17, FR-43)."""
        ...

    def evolution_meteo(self, date_arrete: date | None = None) -> tuple[EvolutionMeteo, ...]:
        """Météo à J, J-1 et J-5 par Entité (FR-19)."""
        ...

    def instantanes(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> pl.DataFrame:
        """Table `SCHEMA_INSTANTANE`."""
        ...

    def indicateurs(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> pl.DataFrame:
        """Table `SCHEMA_INDICATEUR`."""
        ...

    def kpi(self, date_arrete: date | None = None, entite: str | None = None) -> pl.DataFrame:
        """Table `SCHEMA_KPI` ; `entite=None` rend aussi le périmètre Programme."""
        ...

    def tendances(self, entite: str | None = None, code_kpi: str | None = None) -> pl.DataFrame:
        """Table `SCHEMA_TENDANCE` (FR-12), filtrée par Entité et par KPI."""
        ...

    def tickets_etats(self, date_arrete: date | None = None) -> pl.DataFrame:
        """Table `SCHEMA_TICKET_ETAT` à la date donnée."""
        ...

    def textes_tickets(self) -> pl.DataFrame:
        """Table `SCHEMA_TICKET_TEXTE` à la Date d'arrêté du Passage."""
        ...

    def anomalies(
        self,
        date_arrete: date | None = None,
        entite: str | None = None,
        gravite: Gravite | None = None,
        phase: Phase | None = None,
        domaine: str | None = None,
        limite: int | None = None,
        palier: Palier = 2,
    ) -> ResultatListAnomalies:
        """Anomalies ouvertes filtrées (FR-26 onglet 5, FR-39).

        `limite` borne le nombre d'Anomalies rendues (`None` : toutes) ; `total` les compte
        avant la limite. En `palier=1`, `cause_racine_proposee` vaut `None` partout (FR-46).
        """
        ...

    def previsions(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[Prevision, ...]:
        """Prévisions de sortie du rouge (FR-20)."""
        ...

    def risques(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[RisqueEntreeRouge, ...]:
        """Risques d'entrée en rouge (FR-21)."""
        ...

    def classification(self, palier: Palier = 2) -> tuple[SortieClassification, ...]:
        """Causes racines proposées (FR-35)."""
        ...

    def repartition_causes(self, entite: str | None = None, palier: Palier = 2) -> pl.DataFrame:
        """Table `SCHEMA_REPARTITION_CAUSES`."""
        ...

    def explications(
        self, entite: str | None = None, palier: Palier = 2
    ) -> tuple[SortieExplication, ...]:
        """Explications sourcées et Brouillons de commentaire (FR-32, FR-33)."""
        ...

    def narrations(
        self, entite: str | None = None, palier: Palier = 2
    ) -> tuple[SortieNarration, ...]:
        """Narrations des Prévisions (FR-24)."""
        ...

    def traces(self) -> tuple[EntreeTrace, ...]:
        """Journal de traçabilité du Passage (FR-34, onglet 9)."""
        ...

    def url_ticket(self, cle: str) -> str | None:
        """Lien Jira du ticket (FR-29) ; `None` en Mode repli."""
        ...
