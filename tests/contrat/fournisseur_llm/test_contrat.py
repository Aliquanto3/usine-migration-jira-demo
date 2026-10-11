"""Contrat de `FournisseurLLM` : deux méthodes, outils reçus seulement (AD-13, AD-20)."""

from collections.abc import Mapping

import pytest
from pydantic import BaseModel, JsonValue

from tests.contrat.fournisseur_llm.fabriques import NOM_OUTIL, CasFournisseurLLM, SortieEssai
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import (
    OutilAgent,
    ParametresAppel,
    ReponseAgentBrute,
    ReponseStructuree,
    Tache,
)
from usine.ports import FournisseurLLM

PARAMETRES_STRUCTURE = ParametresAppel(tache=Tache.classification, max_jetons_sortie=200)
PARAMETRES_AGENT = ParametresAppel(tache=Tache.agent, max_jetons_sortie=200)


class _Arguments(BaseModel):
    entite: str | None = None


class _Enregistreur:
    """Outil qui note chacun de ses appels."""

    def __init__(self) -> None:
        self.appels: list[Mapping[str, JsonValue]] = []

    def __call__(self, arguments: Mapping[str, JsonValue]) -> str:
        self.appels.append(arguments)
        return '{"entite": "ENT-A", "couleur": "rouge"}'


def _outils(enregistreur: _Enregistreur) -> tuple[OutilAgent, ...]:
    def inutile(arguments: Mapping[str, JsonValue]) -> str:
        raise AssertionError("outil jamais demandé par le script")

    return (
        OutilAgent(NOM_OUTIL, "Météo d'une Entité.", _Arguments, enregistreur),
        OutilAgent("get_tendance", "Tendances.", _Arguments, inutile),
    )


def test_implemente_le_port(cas: CasFournisseurLLM) -> None:
    assert isinstance(cas.fournisseur, FournisseurLLM)


def test_version_modele_fournisseur_deux_points_modele(cas: CasFournisseurLLM) -> None:
    fournisseur, _, modele = cas.fournisseur.version_modele.partition(":")
    assert fournisseur
    assert modele


def test_generer_structure_valide_le_schema(cas: CasFournisseurLLM) -> None:
    reponse = cas.fournisseur.generer_structure(cas.prompt, SortieEssai, PARAMETRES_STRUCTURE)
    assert isinstance(reponse, ReponseStructuree)
    assert isinstance(reponse.sortie, SortieEssai)
    assert reponse.brut
    assert reponse.version_modele == cas.fournisseur.version_modele


def test_executer_agent_n_appelle_que_les_outils_recus(cas: CasFournisseurLLM) -> None:
    enregistreur = _Enregistreur()
    outils = _outils(enregistreur)
    reponse = cas.fournisseur.executer_agent(cas.messages, outils, PARAMETRES_AGENT)
    assert isinstance(reponse, ReponseAgentBrute)
    assert reponse.texte
    assert enregistreur.appels, "l'outil scripté n'a pas été appelé"
    noms_recus = {outil.nom for outil in outils}
    demandes = {appel.nom_outil for m in reponse.messages for appel in m.appels_outils}
    assert demandes <= noms_recus
    resultats = [m for m in reponse.messages if m.role == "outil"]
    assert len(resultats) == len(enregistreur.appels)


def test_outil_inconnu_refuse(cas: CasFournisseurLLM) -> None:
    enregistreur = _Enregistreur()
    with pytest.raises(UsineErreur):
        cas.fournisseur_outil_inconnu.executer_agent(
            cas.messages, _outils(enregistreur), PARAMETRES_AGENT
        )
    assert not enregistreur.appels
