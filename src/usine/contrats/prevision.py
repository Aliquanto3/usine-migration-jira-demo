"""Séries de stock, Prévisions de sortie du rouge et Risques d'entrée en rouge (AD-18).

Une Prévision est statistique, jamais produite par un LLM (FR-20, FR-21). Probabilités et
facteurs sont des fractions entières.
"""

from datetime import date
from enum import StrEnum
from typing import Self

import polars as pl
from pydantic import Field, model_validator

from usine.contrats.meteo import CodeIndicateur
from usine.contrats.modele import Enregistrement
from usine.contrats.schemas import SchemaTable

SCHEMA_SERIE_STOCK = SchemaTable(
    "SCHEMA_SERIE_STOCK",
    {
        "serie": pl.Utf8(),
        "date": pl.Date(),
        "stock": pl.Int64(),
        "entrees": pl.Int64(),
        "sorties": pl.Int64(),
    },
    non_nulles=frozenset({"serie", "date", "stock", "entrees", "sorties"}),
)
"""`SerieStock` : stock, Entrées et Sorties par Jour ouvré d'une série (Entité ou projet)."""


class MethodePrevision(StrEnum):
    """Méthode qui a produit la Prévision."""

    baseline = "baseline"
    ml = "ml"


class StatutPrevision(StrEnum):
    """Issue d'une Prévision de sortie du rouge."""

    sortie_projetee = "sortie_projetee"
    pas_de_sortie_projetee = "pas_de_sortie_projetee"
    regle_non_projetable = "regle_non_projetable"


class FacteurExplicatif(Enregistrement):
    """Facteur explicatif déterministe (stock, Entrées, Sorties, vélocité, évolution)."""

    nom: str = Field(min_length=1)
    libelle: str = Field(min_length=1)
    numerateur: int
    denominateur: int = Field(gt=0)


class Prevision(Enregistrement):
    """Prévision de sortie du rouge d'une Entité rouge (FR-20)."""

    date_arrete: date
    entite: str = Field(min_length=1)
    methode: MethodePrevision
    statut: StatutPrevision
    date_sortie_estimee: date | None = None
    date_sortie_optimiste: date | None = None
    date_sortie_pessimiste: date | None = None
    probabilite_numerateur: int = Field(ge=0)
    probabilite_denominateur: int = Field(gt=0)
    """Probabilité de sortie dans l'horizon."""
    horizon_jours_ouvres: int = Field(gt=0)
    facteurs: tuple[FacteurExplicatif, ...]
    regles_non_projetables: tuple[CodeIndicateur, ...] = ()
    version_grille: str = Field(min_length=1)

    @model_validator(mode="after")
    def _coherence(self) -> Self:
        if self.probabilite_numerateur > self.probabilite_denominateur:
            raise ValueError("probabilité supérieure à 1")
        projetee = self.statut is StatutPrevision.sortie_projetee
        if projetee != (self.date_sortie_estimee is not None):
            raise ValueError("une date de sortie estimée existe si et seulement si projetée")
        if not projetee and (
            self.date_sortie_optimiste is not None or self.date_sortie_pessimiste is not None
        ):
            raise ValueError("une fourchette de sortie exige une sortie projetée")
        dates = [
            d
            for d in (
                self.date_sortie_optimiste,
                self.date_sortie_estimee,
                self.date_sortie_pessimiste,
            )
            if d is not None
        ]
        if dates != sorted(dates):
            raise ValueError("ordre attendu : optimiste ≤ estimée ≤ pessimiste")
        if any(d <= self.date_arrete for d in dates):
            raise ValueError("date de sortie non postérieure à la Date d'arrêté")
        if (self.statut is StatutPrevision.regle_non_projetable) != bool(
            self.regles_non_projetables
        ):
            raise ValueError("« regle_non_projetable » exige la liste des règles concernées")
        return self


class RisqueEntreeRouge(Enregistrement):
    """Risque qu'une Entité non rouge franchisse un seuil rouge dans l'horizon (FR-21)."""

    date_arrete: date
    entite: str = Field(min_length=1)
    indicateur: CodeIndicateur
    date_franchissement_estimee: date
    horizon_jours_ouvres: int = Field(gt=0)
    numerateur: int
    denominateur: int = Field(gt=0)
    """Valeur courante de l'indicateur."""
    seuil_numerateur: int
    seuil_denominateur: int = Field(gt=0)
    version_grille: str = Field(min_length=1)

    @model_validator(mode="after")
    def _indicateur(self) -> Self:
        projetables = {CodeIndicateur.ind_1, CodeIndicateur.ind_3, CodeIndicateur.ind_4}
        if self.indicateur not in projetables:
            raise ValueError(f"{self.indicateur} n'est pas projeté (IND-1, IND-3, IND-4)")
        if self.date_franchissement_estimee <= self.date_arrete:
            raise ValueError("date de franchissement non postérieure à la Date d'arrêté")
        return self


class ContenuPrevisions(Enregistrement):
    """Contenu de `previsions.json` : Prévisions des Entités rouges et Risques d'entrée en rouge."""

    previsions: tuple[Prevision, ...]
    risques: tuple[RisqueEntreeRouge, ...]
