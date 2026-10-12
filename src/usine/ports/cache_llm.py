"""Port `CacheLLM` : cache des réponses brutes du fournisseur LLM (AD-12)."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class CacheLLM(Protocol):
    """Cache clé → réponse brute, avant contrôle ; seule la passerelle LLM l'appelle.

    La clé est celle d'AD-12 (JSON trié) ; la valeur est une `contrats.llm.EnveloppeCache`
    sérialisée en JSON. Une écriture sous une clé existante remplace la valeur.
    """

    def lire(self, cle: str) -> str | None:
        """Valeur enregistrée sous `cle`, ou `None`."""
        ...

    def ecrire(self, cle: str, brut: str) -> None:
        """Enregistre (ou remplace) la valeur sous `cle`."""
        ...
