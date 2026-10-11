"""Journal de traçabilité : une entrée par appel LLM et par Prévision (AD-12, AD-16, FR-34).

Une trace ne contient que des textes pseudonymisés.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from usine.contrats.calendrier import Horodatage
from usine.contrats.llm import StatutControle, Tache
from usine.contrats.modele import Enregistrement, PassageId


class TypeTrace(StrEnum):
    """Nature de l'entrée tracée."""

    llm = "llm"
    prevision = "prevision"


class EntreeTrace(Enregistrement):
    """Entrée du Journal de traçabilité, avec les quatre versions et le `passage_id`."""

    type_trace: TypeTrace
    horodatage: Horodatage
    passage_id: PassageId
    """Passage produit (Chaîne) ou consulté (Agent)."""
    date_arrete: date
    entite: str | None = None
    tache: Tache | None = None
    cible: str | None = None
    """Clé de ticket (classification) ou Entité (explication, narration)."""
    fournisseur: str | None = None
    version_prompt: str | None = None
    version_modele: str | None = None
    version_grille: str = Field(min_length=1)
    version_donnees: str = Field(min_length=1)
    entree_pseudonymisee: str
    sortie: str
    statut_controle: StatutControle | None = None
    phrases_retirees: int = Field(default=0, ge=0)
    depuis_cache: bool = False
    jetons_entree: int = Field(default=0, ge=0)
    jetons_sortie: int = Field(default=0, ge=0)
    cout_estime_eur: Decimal = Field(default=Decimal(0), ge=0)

    @model_validator(mode="after")
    def _type(self) -> Self:
        if self.type_trace is TypeTrace.llm:
            manquants = [
                nom
                for nom in ("tache", "fournisseur", "version_prompt", "version_modele")
                if getattr(self, nom) is None
            ]
            if manquants:
                raise ValueError(f"trace LLM sans {', '.join(manquants)}")
            if self.statut_controle is None:
                raise ValueError("trace LLM sans statut de contrôle")
        elif self.tache is not None or self.depuis_cache:
            raise ValueError("une trace de Prévision ne porte ni tâche LLM ni cache")
        return self
