"""`EtapeRepartitionCauses` : répartition lue via la Consultation, calculée par le domaine."""

from datetime import date
from typing import cast

import polars as pl
import pytest

from tests.unit.ia.espions import DATE_ARRETE, PASSAGE_ID
from usine.contrats.agent import AnomalieResume, ResultatListAnomalies
from usine.contrats.config import ConfigChaine, ConfigUsine
from usine.contrats.llm import SortieClassification
from usine.contrats.passage import ContextePassage, StatutEtape
from usine.contrats.tickets import CauseRacine, Gravite, Phase, StatutAnomalie
from usine.domaine.causes.repartition import repartition
from usine.ia.repartition import EtapeRepartitionCauses
from usine.ports.consultation import Consultation
from usine.ports.etape import Etape as PortEtape


def _anomalie(cle: str, entite: str, cause: CauseRacine | None = None) -> AnomalieResume:
    return AnomalieResume(
        cle_ticket=cle,
        entite=entite,
        gravite=Gravite.majeure,
        phase=Phase.recette,
        domaine="",
        statut=StatutAnomalie.en_analyse,
        age_jours_ouvres=0,
        cause_racine_proposee=cause,
    )


class ConsultationMinimale:
    """Consultation réduite aux Anomalies ouvertes et à la classification."""

    def __init__(
        self,
        anomalies: tuple[AnomalieResume, ...],
        classification: tuple[SortieClassification, ...],
    ) -> None:
        self._anomalies = anomalies
        self._classification = classification
        self.dates: list[date | None] = []

    def anomalies(self, date_arrete: date | None = None) -> ResultatListAnomalies:
        self.dates.append(date_arrete)
        return ResultatListAnomalies(
            date_arrete=DATE_ARRETE, anomalies=self._anomalies, total=len(self._anomalies)
        )

    def classification(self, palier: int = 2) -> tuple[SortieClassification, ...]:
        return self._classification


def _ctx(consultation: ConsultationMinimale) -> ContextePassage[Consultation]:
    return ContextePassage(
        DATE_ARRETE,
        PASSAGE_ID,
        ConfigUsine(chaine=ConfigChaine(palier=2)),
        cast(Consultation, consultation),
    )


def test_repartition_du_passage() -> None:
    consultation = ConsultationMinimale(
        (
            # La cause proposée portée par l'Anomalie est ignorée : la classification fait foi.
            _anomalie("DEMO-1", "ENT-A", CauseRacine.hors_perimetre),
            _anomalie("DEMO-2", "ENT-A"),
            _anomalie("DEMO-3", "ENT-A"),
            _anomalie("DEMO-4", ""),
        ),
        (
            SortieClassification(cle_ticket="DEMO-1", cause_racine=CauseRacine.parametrage),
            SortieClassification(cle_ticket="DEMO-2", cause_racine=CauseRacine.parametrage),
            SortieClassification(cle_ticket="DEMO-3", cause_racine=CauseRacine.environnement),
            SortieClassification(cle_ticket="DEMO-4", cause_racine=CauseRacine.environnement),
            SortieClassification(cle_ticket="DEMO-9", cause_racine=CauseRacine.environnement),
        ),
    )
    etape = EtapeRepartitionCauses(repartition)
    assert isinstance(etape, PortEtape)
    resultat = etape.executer(_ctx(consultation))
    assert resultat.statut is StatutEtape.reussie
    assert resultat.traces == ()
    assert consultation.dates == [DATE_ARRETE]
    table = resultat.sorties["repartition_causes"]
    assert isinstance(table, pl.DataFrame)
    assert table.rows() == [
        (DATE_ARRETE, "ENT-A", "parametrage", 2, pytest.approx(2 / 3)),
        (DATE_ARRETE, "ENT-A", "environnement", 1, pytest.approx(1 / 3)),
    ]


def test_sans_anomalie_ni_classification() -> None:
    resultat = EtapeRepartitionCauses(repartition).executer(_ctx(ConsultationMinimale((), ())))
    assert resultat.statut is StatutEtape.reussie
    table = resultat.sorties["repartition_causes"]
    assert isinstance(table, pl.DataFrame)
    assert table.is_empty()
