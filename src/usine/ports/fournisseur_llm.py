"""Port `FournisseurLLM` : deux méthodes, jamais combinées (AD-13)."""

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from usine.contrats.llm import (
    MessageAgent,
    OutilAgent,
    ParametresAppel,
    ReponseAgentBrute,
    ReponseStructuree,
)


@runtime_checkable
class FournisseurLLM(Protocol):
    """Fournisseur LLM ; seul `ia.passerelle` l'appelle (AD-12)."""

    @property
    def version_modele(self) -> str:
        """`fournisseur:modele` (`contrats.versions.version_modele`)."""
        ...

    def generer_structure[T: BaseModel](
        self, prompt: str, schema: type[T], parametres: ParametresAppel
    ) -> ReponseStructuree[T]:
        """Sortie structurée validée par `schema`, sans outil."""
        ...

    def executer_agent(
        self,
        messages: Sequence[MessageAgent],
        outils: Sequence[OutilAgent],
        parametres: ParametresAppel,
    ) -> ReponseAgentBrute:
        """Conversation d'Agent en texte libre ; n'appelle que les `outils` reçus."""
        ...
