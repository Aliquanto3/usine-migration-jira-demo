"""Fabriques des adaptateurs de `Consultation` soumis à la suite de contrat.

Vide jusqu'à la Story 0.6, qui ajoute la `Consultation` réelle sur un Passage d'essai ; la
suite est collectée et ses tests sont ignorés faute d'adaptateur.
"""

from collections.abc import Callable
from dataclasses import dataclass

from usine.ports import Consultation


@dataclass(frozen=True)
class CasConsultation:
    """Consultation d'un Passage d'essai publié, et une Entité qu'il contient."""

    consultation: Consultation
    entite: str


FABRIQUES: list[tuple[str, Callable[[], CasConsultation]]] = []
