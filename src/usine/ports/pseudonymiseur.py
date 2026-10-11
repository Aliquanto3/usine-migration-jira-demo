"""Port `Pseudonymiseur` : jetons dérivés et stables (AD-15)."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Pseudonymiseur(Protocol):
    """Remplace les identifiants sensibles par `<TYPE>_<6 hex>` ; clés de ticket intactes."""

    def pseudonymiser(self, texte: str) -> str:
        """Texte pseudonymisé ; la correspondance est conservée pour la ré-identification."""
        ...

    def reidentifier(self, texte: str) -> str:
        """Remplace, localement, les jetons connus par leur valeur d'origine."""
        ...

    def apercu(self, texte: str) -> str:
        """Comme `pseudonymiser`, sans écrire la table de correspondance (FR-31)."""
        ...
