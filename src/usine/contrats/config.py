"""Modèles de configuration validant les fichiers `config/*.yaml` (AD-19).

Amorce de la Story 0.1, complétée par la Story 0.2.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict


def _entier_exact(valeur: object) -> object:
    """Refuse tout ce qui n'est pas un `int` (ni `bool`, ni `float`).

    `strict=True` ne suffit pas pour un `Literal[1, 2]` : Pydantic y accepte `True` et `2.0`,
    égaux à 1 et 2.
    """
    if type(valeur) is not int:
        raise ValueError(f"entier attendu, pas {type(valeur).__name__}")
    return valeur


class ConfigChaine(BaseModel):
    """Configuration de la Chaîne de reporting (`config/chaine.yaml`)."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    palier: Annotated[Literal[1, 2], BeforeValidator(_entier_exact)]
