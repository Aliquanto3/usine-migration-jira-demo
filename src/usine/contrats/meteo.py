"""Météo d'une Entité et Règles déclenchantes (FR-16, FR-17, FR-19)."""

from datetime import date
from enum import StrEnum
from fractions import Fraction
from typing import Self

from pydantic import Field, model_validator

from usine.contrats.calendrier import jour_ouvre_precedent
from usine.contrats.modele import Enregistrement


class Couleur(StrEnum):
    """Couleur de Météo, ordonnée par gravité : `vert < jaune < orange < rouge`.

    Les comparaisons d'ordre suivent la gravité, pas l'alphabet ; comparer une `Couleur` à
    toute autre valeur (y compris un `str` brut) lève `TypeError`.
    """

    vert = "vert"
    jaune = "jaune"
    orange = "orange"
    rouge = "rouge"

    @property
    def rang(self) -> int:
        """Rang de gravité : 0 pour vert, 3 pour rouge."""
        return _ORDRE_COULEURS.index(self)

    def _rang_de(self, autre: object, operateur: str) -> int:
        if not isinstance(autre, Couleur):
            raise TypeError(
                f"comparaison « {operateur} » impossible entre Couleur et {type(autre).__name__}"
            )
        return autre.rang

    def __lt__(self, autre: object) -> bool:
        return self.rang < self._rang_de(autre, "<")

    def __le__(self, autre: object) -> bool:
        return self.rang <= self._rang_de(autre, "<=")

    def __gt__(self, autre: object) -> bool:
        return self.rang > self._rang_de(autre, ">")

    def __ge__(self, autre: object) -> bool:
        return self.rang >= self._rang_de(autre, ">=")


_ORDRE_COULEURS: tuple[Couleur, ...] = tuple(Couleur)


class CodeIndicateur(StrEnum):
    """Indicateurs de météo de la Grille."""

    ind_1 = "IND-1"
    ind_2 = "IND-2"
    ind_3 = "IND-3"
    ind_4 = "IND-4"
    ind_5 = "IND-5"
    ind_6 = "IND-6"
    ind_7 = "IND-7"
    ind_8 = "IND-8"


class Operateur(StrEnum):
    """Opérateur d'un seuil de la Grille : la règle se déclenche si `valeur <op> seuil`."""

    superieur_ou_egal = ">="
    superieur = ">"


class RegleDeclenchante(Enregistrement):
    """Règle de la Grille franchie : valeur, seuil et tickets en cause (FR-17)."""

    code: CodeIndicateur
    couleur: Couleur
    operateur: Operateur
    numerateur: int
    denominateur: int = Field(ge=0)
    """Valeur mesurée ; `denominateur = 0` avec `numerateur > 0` vaut l'infini."""
    seuil_numerateur: int
    seuil_denominateur: int = Field(gt=0)
    tickets_en_cause: tuple[str, ...]

    @model_validator(mode="after")
    def _valeur(self) -> Self:
        if self.denominateur == 0 and self.numerateur <= 0:
            raise ValueError("valeur 0/0 : un indicateur non évaluable ne déclenche pas")
        if self.couleur is Couleur.vert:
            raise ValueError("une Règle déclenchante n'est jamais verte")
        if not self.franchit_le_seuil:
            raise ValueError(
                f"règle {self.code} : la valeur {self.numerateur}/{self.denominateur} ne"
                f" franchit pas le seuil {self.operateur} {self.seuil_numerateur}"
                f"/{self.seuil_denominateur}"
            )
        return self

    @property
    def franchit_le_seuil(self) -> bool:
        """Vrai si `valeur <operateur> seuil` ; une valeur infinie franchit tout seuil."""
        if self.denominateur == 0:
            return self.numerateur > 0
        valeur = Fraction(self.numerateur, self.denominateur)
        seuil = Fraction(self.seuil_numerateur, self.seuil_denominateur)
        if self.operateur is Operateur.superieur_ou_egal:
            return valeur >= seuil
        return valeur > seuil


class MeteoEntite(Enregistrement):
    """Météo d'une Entité à une Date d'arrêté ; la couleur la plus grave l'emporte."""

    date_arrete: date
    entite: str = Field(min_length=1)
    couleur: Couleur
    regles: tuple[RegleDeclenchante, ...]
    """Toutes les Règles déclenchantes de la couleur retenue (vide si vert)."""
    version_grille: str = Field(min_length=1)

    @model_validator(mode="after")
    def _regles(self) -> Self:
        if (self.couleur is Couleur.vert) != (not self.regles):
            raise ValueError("une Météo est verte si et seulement si aucune règle ne se déclenche")
        for regle in self.regles:
            if regle.couleur is not self.couleur:
                raise ValueError(
                    f"règle {regle.code} {regle.couleur} sous une Météo {self.couleur}"
                )
        return self


class EvolutionMeteo(Enregistrement):
    """Météo d'une Entité à J, J-1 et J-5 (FR-19).

    `date_j1` et `date_j5` sont toujours renseignées (J-1 et J-5 en Jours ouvrés) ;
    `couleur_j1` et `couleur_j5` valent `None` si la date n'est pas couverte par le Passage.
    """

    entite: str = Field(min_length=1)
    date_arrete: date
    couleur: Couleur
    date_j1: date
    couleur_j1: Couleur | None
    date_j5: date
    couleur_j5: Couleur | None

    @model_validator(mode="after")
    def _ordre_des_dates(self) -> Self:
        if not self.date_j5 < self.date_j1 < self.date_arrete:
            raise ValueError("ordre attendu : J-5 < J-1 < Date d'arrêté")
        for nom, valeur, rang in (("date_j1", self.date_j1, 1), ("date_j5", self.date_j5, 5)):
            attendue = jour_ouvre_precedent(self.date_arrete, rang)
            if valeur != attendue:
                raise ValueError(
                    f"{nom} = {valeur.isoformat()}, attendu J-{rang} = {attendue.isoformat()}"
                )
        return self

    @property
    def change_depuis_j1(self) -> bool:
        """Vrai si la couleur a changé depuis J-1 (connue)."""
        return self.couleur_j1 is not None and self.couleur_j1 is not self.couleur

    @property
    def change_depuis_j5(self) -> bool:
        """Vrai si la couleur a changé depuis J-5 (connue)."""
        return self.couleur_j5 is not None and self.couleur_j5 is not self.couleur
