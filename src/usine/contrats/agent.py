"""Arguments et résultats des outils de l'Agent, en lecture seule (FR-39, AD-2).

Chaque date absente (`None`) désigne la Date d'arrêté du Passage consulté.
"""

from datetime import date
from typing import Literal, Self

from pydantic import Field, model_validator

from usine.contrats.meteo import EvolutionMeteo, MeteoEntite
from usine.contrats.modele import Enregistrement
from usine.contrats.prevision import Prevision, RisqueEntreeRouge
from usine.contrats.tickets import STATUTS_FERMES, CauseRacine, Gravite, Phase, StatutAnomalie


class ArgumentsGetMeteo(Enregistrement):
    """Arguments de `get_meteo`."""

    date_arrete: date | None = None
    entite: str | None = None


class ResultatGetMeteo(Enregistrement):
    """Météo, Règles déclenchantes et évolution J-1 / J-5."""

    date_arrete: date
    meteos: tuple[MeteoEntite, ...]
    evolutions: tuple[EvolutionMeteo, ...]


class ArgumentsListAnomalies(Enregistrement):
    """Arguments de `list_anomalies` : filtres facultatifs."""

    date_arrete: date | None = None
    entite: str | None = None
    gravite: Gravite | None = None
    phase: Phase | None = None
    domaine: str | None = None
    statut: StatutAnomalie | None = None
    limite: int = Field(default=50, gt=0)


class AnomalieResume(Enregistrement):
    """Anomalie ouverte telle que listée (onglet 5 de l'Excel, Agent)."""

    cle_ticket: str = Field(min_length=1)
    entite: str
    gravite: Gravite
    phase: Phase
    domaine: str
    statut: StatutAnomalie
    age_jours_ouvres: int = Field(ge=0)
    """Âge en Jours ouvrés depuis la dernière Entrée."""
    cause_racine_proposee: CauseRacine | None = None
    """Palier 2 seulement."""

    @model_validator(mode="after")
    def _ouverte(self) -> Self:
        if self.statut in STATUTS_FERMES:
            raise ValueError(f"{self.cle_ticket} : statut « {self.statut} » d'une Anomalie fermée")
        return self


class ResultatListAnomalies(Enregistrement):
    """Anomalies ouvertes filtrées ; `total` compte les Anomalies avant la limite."""

    date_arrete: date
    anomalies: tuple[AnomalieResume, ...]
    total: int = Field(ge=0)

    @model_validator(mode="after")
    def _total(self) -> Self:
        if self.total < len(self.anomalies):
            raise ValueError(
                f"total {self.total} inférieur au nombre d'Anomalies listées"
                f" ({len(self.anomalies)})"
            )
        return self


class ArgumentsGetTendance(Enregistrement):
    """Arguments de `get_tendance`."""

    entite: str | None = None
    code_kpi: str | None = None


class PointTendance(Enregistrement):
    """Une valeur de Tendance hebdomadaire."""

    date: date
    perimetre: str
    code_kpi: str
    dimension: str
    numerateur: int
    denominateur: int = Field(ge=0)


class ResultatGetTendance(Enregistrement):
    """Points de Tendance hebdomadaire."""

    points: tuple[PointTendance, ...]


class ArgumentsGetPrevision(Enregistrement):
    """Arguments de `get_prevision`."""

    date_arrete: date | None = None
    entite: str | None = None


class ResultatGetPrevision(Enregistrement):
    """Prévisions de sortie du rouge."""

    date_arrete: date
    previsions: tuple[Prevision, ...]


class ArgumentsGetRisques(Enregistrement):
    """Arguments de `get_risques`."""

    date_arrete: date | None = None
    entite: str | None = None


class ResultatGetRisques(Enregistrement):
    """Risques d'entrée en rouge."""

    date_arrete: date
    risques: tuple[RisqueEntreeRouge, ...]


class AucuneDonnee(Enregistrement):
    """Résultat d'un outil daté quand le Passage ne couvre pas la Date d'arrêté demandée."""

    date_arrete: date | None
    """Date demandée, sinon `None` quand aucune n'est demandée et que le Passage n'a aucune date."""
    message: Literal["aucune donnée pour cette date"] = "aucune donnée pour cette date"
