"""Les sept ports sont des `typing.Protocol` complets (AD-2, AD-11, AD-13, AD-22)."""

import inspect
from typing import Protocol, get_type_hints

import pytest

import usine.ports as ports
from tests.doublures import (
    CacheMemoire,
    FournisseurFactice,
    PseudonymiseurFactice,
    SourceEnMemoire,
)
from usine.contrats.passage import ContextePassage, ResultatEtape

PORTS = (
    "SourceTickets",
    "EntrepotExtraction",
    "FournisseurLLM",
    "Pseudonymiseur",
    "CacheLLM",
    "Consultation",
    "Etape",
)

LECTURES_CONSULTATION = {
    "dernier_passage",
    "manifeste",
    "dates_disponibles",
    "meteo",
    "evolution_meteo",
    "indicateurs",
    "kpi",
    "instantanes",
    "tendances",
    "tickets_etats",
    "textes_tickets",
    "anomalies",
    "previsions",
    "risques",
    "classification",
    "repartition_causes",
    "explications",
    "narrations",
    "traces",
    "url_ticket",
}


def _membres(port: type) -> set[str]:
    return {nom for nom in vars(port) if not nom.startswith("_")}


def test_reexportes() -> None:
    assert set(ports.__all__) == set(PORTS)


@pytest.mark.parametrize("nom", PORTS)
def test_est_un_protocole(nom: str) -> None:
    port = getattr(ports, nom)
    assert Protocol in port.__mro__
    assert getattr(port, "_is_protocol", False)


def test_fournisseur_deux_methodes() -> None:
    membres = _membres(ports.FournisseurLLM)
    assert {"generer_structure", "executer_agent", "version_modele"} <= membres
    assert isinstance(inspect.getattr_static(ports.FournisseurLLM, "version_modele"), property)


def test_consultation_complete() -> None:
    assert _membres(ports.Consultation) >= LECTURES_CONSULTATION


@pytest.mark.parametrize(
    "lecture", ["classification", "repartition_causes", "explications", "narrations", "anomalies"]
)
def test_lectures_llm_filtrees_par_palier(lecture: str) -> None:
    parametre = inspect.signature(getattr(ports.Consultation, lecture)).parameters["palier"]
    assert parametre.default == 2


def test_parametres_de_filtre() -> None:
    anomalies = inspect.signature(ports.Consultation.anomalies).parameters
    assert set(anomalies) >= {"date_arrete", "entite", "gravite", "phase", "domaine", "limite"}
    assert anomalies["limite"].default is None
    tendances = inspect.signature(ports.Consultation.tendances).parameters
    assert tendances["code_kpi"].default is None
    dernier = inspect.signature(ports.Consultation.dernier_passage).parameters
    assert dernier["sans_classification_initiale"].default is False


def test_cache_llm_signature() -> None:
    assert _membres(ports.CacheLLM) >= {"lire", "ecrire"}
    assert get_type_hints(ports.CacheLLM.lire) == {"cle": str, "return": str | None}
    assert get_type_hints(ports.CacheLLM.ecrire) == {"cle": str, "brut": str, "return": type(None)}


def test_etape_signature() -> None:
    indications = get_type_hints(ports.Etape.executer)
    assert indications["ctx"] == ContextePassage[ports.Consultation]
    assert indications["return"] is ResultatEtape


def test_doublures_implementent_les_ports() -> None:
    assert isinstance(FournisseurFactice(), ports.FournisseurLLM)
    assert isinstance(PseudonymiseurFactice(b"k", {}), ports.Pseudonymiseur)
    assert isinstance(SourceEnMemoire([]), ports.SourceTickets)
    assert isinstance(CacheMemoire(), ports.CacheLLM)
