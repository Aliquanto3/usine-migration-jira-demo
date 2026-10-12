"""Outils de consultation de l'Agent, en lecture seule (FR-39, FR-41, AD-11).

Chaque outil prend un `Arguments*` de `contrats.agent` et rend le `Resultat*` correspondant,
lu par le seul port `Consultation`, ou `AucuneDonnee` si la Date d'arrêté demandée n'est pas
couverte par le Passage. Aucun chiffre n'est calculé ici : le filtre `statut` ne fait que
sélectionner des lignes. La sérialisation en texte et la Pseudonymisation reviennent à la
passerelle de l'Agent (Story 7.9).
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from usine.contrats.agent import (
    ArgumentsGetMeteo,
    ArgumentsGetPrevision,
    ArgumentsGetRisques,
    ArgumentsGetTendance,
    ArgumentsListAnomalies,
    AucuneDonnee,
    PointTendance,
    ResultatGetMeteo,
    ResultatGetPrevision,
    ResultatGetRisques,
    ResultatGetTendance,
    ResultatListAnomalies,
)
from usine.contrats.modele import Enregistrement
from usine.ports.consultation import Consultation

NOMS_OUTILS = ("get_meteo", "list_anomalies", "get_tendance", "get_prevision", "get_risques")
"""Noms exacts des outils de l'Agent, tous en lecture seule."""

_CHAMPS_TENDANCE = tuple(PointTendance.model_fields)


@dataclass(frozen=True)
class DefinitionOutil:
    """Outil de l'Agent : la passerelle (Story 7.9) en construit un `OutilAgent`."""

    nom: str
    description: str
    arguments: type[Enregistrement]
    executer: Callable[[Mapping[str, Any]], Enregistrement]
    """Valide les arguments JSON (`ValidationError` sinon) et rend le résultat ; une
    `UsineErreur` de la `Consultation` (Passage illisible) remonte telle quelle."""


class OutilsConsultation:
    """Les cinq outils de l'Agent, servis par une `Consultation`."""

    def __init__(self, consultation: Consultation) -> None:
        self._consultation = consultation

    def _date(self, date_arrete: date | None) -> date | AucuneDonnee:
        """Date d'arrêté à lire, ou `AucuneDonnee` si le Passage ne la couvre pas."""
        dates = self._consultation.dates_disponibles()
        if not dates:
            return AucuneDonnee(date_arrete=date_arrete)
        jour = (
            date_arrete if date_arrete is not None else self._consultation.manifeste().date_arrete
        )
        if jour not in dates:
            return AucuneDonnee(date_arrete=jour)
        return jour

    def get_meteo(self, arguments: ArgumentsGetMeteo) -> ResultatGetMeteo | AucuneDonnee:
        """Météo, Règles déclenchantes et évolution J-1 / J-5 (FR-17, FR-19, FR-43)."""
        jour = self._date(arguments.date_arrete)
        if isinstance(jour, AucuneDonnee):
            return jour
        evolutions = self._consultation.evolution_meteo(jour)
        if arguments.entite is not None:
            evolutions = tuple(e for e in evolutions if e.entite == arguments.entite)
        return ResultatGetMeteo(
            date_arrete=jour,
            meteos=self._consultation.meteo(jour, arguments.entite),
            evolutions=evolutions,
        )

    def list_anomalies(
        self, arguments: ArgumentsListAnomalies
    ) -> ResultatListAnomalies | AucuneDonnee:
        """Anomalies ouvertes filtrées ; `total` compte les Anomalies filtrées avant la limite."""
        jour = self._date(arguments.date_arrete)
        if isinstance(jour, AucuneDonnee):
            return jour
        resultat = self._consultation.anomalies(
            date_arrete=jour,
            entite=arguments.entite,
            gravite=arguments.gravite,
            phase=arguments.phase,
            domaine=arguments.domaine,
            limite=arguments.limite if arguments.statut is None else None,
        )
        if arguments.statut is None:
            return resultat
        retenues = tuple(a for a in resultat.anomalies if a.statut == arguments.statut)
        return ResultatListAnomalies(
            date_arrete=resultat.date_arrete,
            anomalies=retenues[: arguments.limite],
            total=len(retenues),
        )

    def get_tendance(self, arguments: ArgumentsGetTendance) -> ResultatGetTendance:
        """Points de Tendance hebdomadaire (FR-12) ; liste vide si rien ne correspond."""
        table = self._consultation.tendances(arguments.entite, arguments.code_kpi)
        return ResultatGetTendance(
            points=tuple(
                PointTendance.model_validate(ligne)
                for ligne in table.select(_CHAMPS_TENDANCE).iter_rows(named=True)
            )
        )

    def get_prevision(
        self, arguments: ArgumentsGetPrevision
    ) -> ResultatGetPrevision | AucuneDonnee:
        """Prévisions de sortie du rouge (FR-20)."""
        jour = self._date(arguments.date_arrete)
        if isinstance(jour, AucuneDonnee):
            return jour
        return ResultatGetPrevision(
            date_arrete=jour, previsions=self._consultation.previsions(jour, arguments.entite)
        )

    def get_risques(self, arguments: ArgumentsGetRisques) -> ResultatGetRisques | AucuneDonnee:
        """Risques d'entrée en rouge (FR-21)."""
        jour = self._date(arguments.date_arrete)
        if isinstance(jour, AucuneDonnee):
            return jour
        return ResultatGetRisques(
            date_arrete=jour, risques=self._consultation.risques(jour, arguments.entite)
        )


def _definition[A: Enregistrement](
    nom: str,
    description: str,
    arguments: type[A],
    methode: Callable[[A], Enregistrement],
) -> DefinitionOutil:
    def executer(valeurs: Mapping[str, Any]) -> Enregistrement:
        return methode(arguments.model_validate(valeurs))

    return DefinitionOutil(nom, description, arguments, executer)


def outils_consultation(consultation: Consultation) -> tuple[DefinitionOutil, ...]:
    """Les cinq outils de l'Agent, dans l'ordre de `NOMS_OUTILS`."""
    outils = OutilsConsultation(consultation)
    return (
        _definition(
            "get_meteo",
            "Météo des Entités, Règles déclenchantes et évolution J-1 / J-5 à une Date d'arrêté.",
            ArgumentsGetMeteo,
            outils.get_meteo,
        ),
        _definition(
            "list_anomalies",
            "Anomalies ouvertes à une Date d'arrêté, filtrées par Entité, Gravité, Phase,"
            " domaine ou statut ; `total` compte les Anomalies filtrées avant la limite.",
            ArgumentsListAnomalies,
            outils.list_anomalies,
        ),
        _definition(
            "get_tendance",
            "Tendance hebdomadaire des KPI, par Entité et par KPI.",
            ArgumentsGetTendance,
            outils.get_tendance,
        ),
        _definition(
            "get_prevision",
            "Prévisions de sortie du rouge à une Date d'arrêté.",
            ArgumentsGetPrevision,
            outils.get_prevision,
        ),
        _definition(
            "get_risques",
            "Risques d'entrée en rouge à une Date d'arrêté.",
            ArgumentsGetRisques,
            outils.get_risques,
        ),
    )
