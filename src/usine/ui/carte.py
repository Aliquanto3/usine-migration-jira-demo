"""Carte météo du dernier Passage, sans Streamlit : lignes à afficher, lues via `Consultation`."""

from collections.abc import Mapping
from datetime import date
from types import MappingProxyType
from typing import Protocol

from usine.contrats.format import formater_date
from usine.contrats.meteo import Couleur, MeteoEntite
from usine.contrats.passage import ManifestePassage

LIBELLES_COULEURS: Mapping[Couleur, str] = MappingProxyType(
    {
        Couleur.vert: "Vert",
        Couleur.jaune: "Jaune",
        Couleur.orange: "Orange",
        Couleur.rouge: "Rouge",
    }
)
"""Libellé français de chaque couleur de Météo."""

PASTILLES: Mapping[Couleur, str] = MappingProxyType(
    {Couleur.vert: "🟢", Couleur.jaune: "🟡", Couleur.orange: "🟠", Couleur.rouge: "🔴"}
)
"""Pastille affichée devant chaque couleur."""


class LectureMeteo(Protocol):
    """Lectures de la `Consultation` dont la carte a besoin."""

    def manifeste(self) -> ManifestePassage:
        """Manifeste du Passage lu."""
        ...

    def meteo(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[MeteoEntite, ...]:
        """Météo par Entité à la date (Date d'arrêté du Passage par défaut)."""
        ...


def date_carte(consultation: LectureMeteo) -> str:
    """Date d'arrêté du Passage, au format `JJ/MM/AAAA`."""
    return formater_date(consultation.manifeste().date_arrete)


def lignes_carte(consultation: LectureMeteo) -> list[dict[str, str]]:
    """Une ligne par Entité : son code et le libellé français de sa couleur."""
    return [
        {
            "Entité": meteo.entite,
            "Météo": f"{PASTILLES[meteo.couleur]} {LIBELLES_COULEURS[meteo.couleur]}",
        }
        for meteo in consultation.meteo()
    ]
