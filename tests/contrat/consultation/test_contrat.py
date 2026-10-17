"""Contrat de `Consultation` : lecteur unique d'un Passage (AD-11, AD-20)."""

from typing import Literal

import pytest

from tests.contrat.consultation.fabriques import CasConsultation
from usine.contrats.agent import ResultatListAnomalies
from usine.contrats.calcul import SCHEMA_INDICATEUR, SCHEMA_INSTANTANE, SCHEMA_KPI, SCHEMA_TENDANCE
from usine.contrats.llm import SCHEMA_REPARTITION_CAUSES
from usine.contrats.meteo import MeteoEntite
from usine.contrats.passage import ManifestePassage
from usine.contrats.prevision import Prevision, RisqueEntreeRouge
from usine.contrats.schemas import valider
from usine.contrats.tickets import SCHEMA_TICKET_ETAT, SCHEMA_TICKET_TEXTE
from usine.contrats.trace import EntreeTrace
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
    """FR-44 : le dernier Passage a fait la classification initiale ; le filtre l'écarte."""
    tous = cas.consultation.dernier_passage()
    assert tous is not None
    assert tous.passage_id == cas.passage_classification_initiale
    assert tous.classification_initiale
    sans = cas.consultation.dernier_passage(sans_classification_initiale=True)
    assert sans is not None
    assert sans.passage_id == cas.consultation.manifeste().passage_id
    assert not sans.classification_initiale


@pytest.mark.parametrize("cle", ["DEMO-1", "DEMO-123"])
def test_url_ticket(cas: CasConsultation, cle: str) -> None:
    """`None` en Mode repli, sinon `<url_site>/browse/<cle>`."""
    url = cas.consultation.url_ticket(cle)
    if not cas.url_attendue:
        assert url is None
        return
    assert url is not None
    assert url.startswith("http")
    assert url.endswith(f"/browse/{cle}")
    assert "//browse" not in url


def test_previsions_et_risques(cas: CasConsultation) -> None:
    """Tuples typés à la Date d'arrêté ; `()` quand la Prévision n'est pas disponible."""
    c = cas.consultation
    date_arrete = c.manifeste().date_arrete
    previsions = c.previsions()
    assert isinstance(previsions, tuple)
    assert all(isinstance(p, Prevision) and p.date_arrete == date_arrete for p in previsions)
    filtrees = c.previsions(entite=cas.entite)
    assert filtrees == tuple(p for p in previsions if p.entite == cas.entite)
    risques = c.risques()
    assert isinstance(risques, tuple)
    assert all(isinstance(r, RisqueEntreeRouge) and r.date_arrete == date_arrete for r in risques)
    assert c.risques(entite=cas.entite) == tuple(r for r in risques if r.entite == cas.entite)
    if cas.avec_sorties:
        assert filtrees
        assert risques


def test_traces(cas: CasConsultation) -> None:
    traces = cas.consultation.traces()
    assert isinstance(traces, tuple)
    assert all(isinstance(t, EntreeTrace) for t in traces)
    if cas.avec_sorties:
        assert traces


def test_palier_1_par_entite(cas: CasConsultation) -> None:
    """FR-46 : en Palier 1, aucune sortie LLM pour l'Entité, même filtrée."""
    c = cas.consultation
    if cas.avec_sorties:
        assert c.explications(entite=cas.entite)
        assert c.narrations(entite=cas.entite)
        assert not c.repartition_causes(entite=cas.entite).is_empty()
        palier_2 = c.anomalies(entite=cas.entite).anomalies
        assert any(a.cause_racine_proposee is not None for a in palier_2)
    assert c.explications(entite=cas.entite, palier=1) == ()
    assert c.narrations(entite=cas.entite, palier=1) == ()
    assert c.repartition_causes(entite=cas.entite, palier=1).is_empty()
    anomalies = c.anomalies(entite=cas.entite, palier=1)
    assert anomalies.total == c.anomalies(entite=cas.entite).total
    assert all(a.cause_racine_proposee is None for a in anomalies.anomalies)


@pytest.mark.parametrize("nom", ["rapport_xlsx", "rapport_pptx"])
def test_livrable(cas: CasConsultation, nom: Literal["rapport_xlsx", "rapport_pptx"]) -> None:
    """Contrats 1.9.0 : octets du livrable du Passage lu, ou `None` s'il est absent (AD-11)."""
    octets = cas.consultation.livrable(nom)
    if cas.avec_livrables:
        assert isinstance(octets, bytes)
        assert octets.startswith(b"PK")  # classeur ou présentation OOXML
    else:
        assert octets is None
    assert cas.consultation.livrable(nom) == octets  # lecture répétable
