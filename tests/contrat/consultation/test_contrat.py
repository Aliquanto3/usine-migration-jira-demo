"""Contrat de `Consultation` : lecteur unique d'un Passage (AD-11, AD-20)."""

import pytest

from tests.contrat.consultation.fabriques import CasConsultation
from usine.contrats.agent import ResultatListAnomalies
from usine.contrats.calcul import SCHEMA_INDICATEUR, SCHEMA_INSTANTANE, SCHEMA_KPI, SCHEMA_TENDANCE
from usine.contrats.llm import SCHEMA_REPARTITION_CAUSES
from usine.contrats.meteo import MeteoEntite
from usine.contrats.passage import ManifestePassage
from usine.contrats.schemas import valider
from usine.contrats.tickets import SCHEMA_TICKET_ETAT, SCHEMA_TICKET_TEXTE
from usine.ports import Consultation


def test_implemente_le_port(cas: CasConsultation) -> None:
    assert isinstance(cas.consultation, Consultation)


def test_manifeste_et_dernier_passage(cas: CasConsultation) -> None:
    manifeste = cas.consultation.manifeste()
    assert isinstance(manifeste, ManifestePassage)
    dernier = cas.consultation.dernier_passage()
    assert dernier is not None
    assert (dernier.date_arrete, dernier.horodatage_fin) >= (
        manifeste.date_arrete,
        manifeste.horodatage_fin,
    )


def test_dates_disponibles_ordonnees(cas: CasConsultation) -> None:
    dates = cas.consultation.dates_disponibles()
    assert list(dates) == sorted(set(dates))
    assert cas.consultation.manifeste().date_arrete == dates[-1]


def test_meteo_a_la_date_du_passage_par_defaut(cas: CasConsultation) -> None:
    date_arrete = cas.consultation.manifeste().date_arrete
    meteos = cas.consultation.meteo()
    assert meteos
    assert all(isinstance(m, MeteoEntite) and m.date_arrete == date_arrete for m in meteos)
    filtrees = cas.consultation.meteo(entite=cas.entite)
    assert [m.entite for m in filtrees] == [cas.entite]


def test_evolution_meteo_par_entite(cas: CasConsultation) -> None:
    entites = {m.entite for m in cas.consultation.meteo()}
    assert {e.entite for e in cas.consultation.evolution_meteo()} == entites


def test_tables_validees(cas: CasConsultation) -> None:
    c = cas.consultation
    valider(c.instantanes(), SCHEMA_INSTANTANE)
    valider(c.indicateurs(), SCHEMA_INDICATEUR)
    valider(c.kpi(), SCHEMA_KPI)
    valider(c.tendances(), SCHEMA_TENDANCE)
    valider(c.tickets_etats(), SCHEMA_TICKET_ETAT)
    valider(c.textes_tickets(), SCHEMA_TICKET_TEXTE)
    valider(c.repartition_causes(), SCHEMA_REPARTITION_CAUSES)


def test_anomalies(cas: CasConsultation) -> None:
    resultat = cas.consultation.anomalies(entite=cas.entite)
    assert isinstance(resultat, ResultatListAnomalies)
    assert resultat.total >= len(resultat.anomalies)
    assert all(a.entite == cas.entite for a in resultat.anomalies)


def test_anomalies_limitees(cas: CasConsultation) -> None:
    toutes = cas.consultation.anomalies()
    limitees = cas.consultation.anomalies(limite=1)
    assert len(limitees.anomalies) <= 1
    assert limitees.total == toutes.total


def test_tendances_filtrees_par_kpi(cas: CasConsultation) -> None:
    tendances = cas.consultation.tendances()
    for code_kpi in tendances["code_kpi"].unique().to_list()[:1]:
        filtrees = cas.consultation.tendances(code_kpi=code_kpi)
        assert filtrees["code_kpi"].unique().to_list() == [code_kpi]


def test_palier_1_sans_sortie_llm(cas: CasConsultation) -> None:
    c = cas.consultation
    assert c.classification(palier=1) == ()
    assert c.explications(palier=1) == ()
    assert c.narrations(palier=1) == ()
    assert c.repartition_causes(palier=1).is_empty()
    anomalies = c.anomalies(palier=1)
    assert anomalies.total == c.anomalies().total
    assert all(a.cause_racine_proposee is None for a in anomalies.anomalies)


def test_dernier_passage_sans_classification_initiale(cas: CasConsultation) -> None:
    """FR-44 : le filtre ne rend jamais un Passage de classification initiale."""
    dernier = cas.consultation.dernier_passage(sans_classification_initiale=True)
    assert dernier is None or not dernier.classification_initiale


@pytest.mark.parametrize("cle", ["DEMO-1"])
def test_url_ticket(cas: CasConsultation, cle: str) -> None:
    url = cas.consultation.url_ticket(cle)
    assert url is None or cle in url
