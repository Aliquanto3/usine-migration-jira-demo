"""Arguments et résultats des outils de l'Agent (FR-39)."""

from datetime import date

import pytest
from pydantic import ValidationError

from usine.contrats.agent import AnomalieResume, ResultatListAnomalies
from usine.contrats.tickets import Gravite, Phase, StatutAnomalie

D = date(2026, 10, 12)


def _anomalie(cle: str) -> AnomalieResume:
    return AnomalieResume(
        cle_ticket=cle,
        entite="ENT-A",
        gravite=Gravite.bloquante,
        phase=Phase.recette,
        domaine="credits",
        statut=StatutAnomalie.en_analyse,
        age_jours_ouvres=3,
    )


def test_total_compte_avant_la_limite() -> None:
    resultat = ResultatListAnomalies(date_arrete=D, anomalies=(_anomalie("DEMO-1"),), total=12)
    assert resultat.total == 12


@pytest.mark.parametrize("statut", [StatutAnomalie.fermee, StatutAnomalie.rejetee])
def test_anomalie_fermee_refusee(statut: StatutAnomalie) -> None:
    with pytest.raises(ValidationError, match="fermée"):
        AnomalieResume.model_validate(_anomalie("DEMO-1").model_dump() | {"statut": statut})


def test_total_inferieur_aux_anomalies_listees() -> None:
    with pytest.raises(ValidationError, match="total"):
        ResultatListAnomalies(
            date_arrete=D, anomalies=(_anomalie("DEMO-1"), _anomalie("DEMO-2")), total=1
        )
