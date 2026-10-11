"""Fabriques des adaptateurs de `FournisseurLLM` soumis à la suite de contrat.

Chaque fabrique prépare l'adaptateur (réponses scriptées ou enregistrées) pour : une sortie
structurée `SortieEssai`, puis un tour d'Agent qui appelle l'outil `NOM_OUTIL` ; et un second
adaptateur dont le tour d'Agent demande un outil qu'il n'a pas reçu.
"""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from tests.doublures import FournisseurFactice, ReponseAgentScriptee
from usine.contrats.llm import AppelOutil, MessageAgent
from usine.ports import FournisseurLLM

NOM_OUTIL = "get_meteo"


class SortieEssai(BaseModel):
    """Schéma de sortie structurée de la suite."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reponse: str


@dataclass(frozen=True)
class CasFournisseurLLM:
    """Adaptateur à éprouver et données d'essai."""

    fournisseur: FournisseurLLM
    fournisseur_outil_inconnu: FournisseurLLM
    prompt: str
    messages: tuple[MessageAgent, ...]


MESSAGES = (
    MessageAgent(role="systeme", contenu="Tu réponds à partir des outils."),
    MessageAgent(role="utilisateur", contenu="Quelle est la Météo de ENT-A ?"),
)


def fabrique_factice() -> CasFournisseurLLM:
    """Doublure scriptée."""
    appel = AppelOutil(id_appel="a1", nom_outil=NOM_OUTIL, arguments={"entite": "ENT-A"})
    inconnu = AppelOutil(id_appel="a2", nom_outil="supprimer_ticket", arguments={})
    return CasFournisseurLLM(
        fournisseur=FournisseurFactice(
            reponses_structurees=[SortieEssai(reponse="ENT-A est rouge.")],
            reponses_agent=[ReponseAgentScriptee("ENT-A est rouge.", (appel,))],
        ),
        fournisseur_outil_inconnu=FournisseurFactice(
            reponses_agent=[ReponseAgentScriptee("…", (inconnu,))],
        ),
        prompt="Classe l'Anomalie DEMO-1.",
        messages=MESSAGES,
    )


FABRIQUES: list[tuple[str, Callable[[], CasFournisseurLLM]]] = [
    ("factice", fabrique_factice),
]
