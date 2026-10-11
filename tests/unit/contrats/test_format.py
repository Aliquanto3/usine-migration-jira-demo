"""Formatage français (AD-11)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from fractions import Fraction

import pytest

from usine.contrats.erreurs import UsineErreur
from usine.contrats.format import (
    formater_date,
    formater_entier,
    formater_fraction,
    formater_nombre,
    formater_pourcentage,
)

NBSP = " "


def test_nombre_decimal() -> None:
    assert formater_nombre(12345.5) == f"12{NBSP}345,5"


def test_nombre_entier() -> None:
    assert formater_nombre(1234567) == f"1{NBSP}234{NBSP}567"
    assert formater_entier(1234567) == f"1{NBSP}234{NBSP}567"
    assert formater_entier(0) == "0"
    assert formater_entier(-1234) == f"-1{NBSP}234"


def test_arrondi_au_demi_superieur() -> None:
    assert formater_nombre(2.25) == "2,3"
    assert formater_nombre(2.675, 2) == "2,68"
    assert formater_nombre(Decimal("0.05")) == "0,1"
    assert formater_nombre(-2.25) == "-2,3"


def test_zeros_non_significatifs_retires() -> None:
    assert formater_nombre(12.0) == "12"
    assert formater_nombre(Decimal("1.50"), 2) == "1,5"
    assert formater_nombre(0.04) == "0"


def test_fraction() -> None:
    assert formater_fraction(Fraction(3, 2)) == "1,5"
    assert formater_fraction(Fraction(1, 3), 2) == "0,33"


def test_pourcentage() -> None:
    assert formater_pourcentage(Fraction(1, 8)) == f"12,5{NBSP}%"
    assert formater_pourcentage(Fraction(1, 5)) == f"20{NBSP}%"
    assert formater_pourcentage(Fraction(1, 3)) == f"33,3{NBSP}%"


def test_date() -> None:
    assert formater_date(date(2026, 10, 5)) == "05/10/2026"


@pytest.mark.parametrize("valeur", [True, float("nan"), float("inf"), "12"])
def test_nombre_invalide(valeur: object) -> None:
    with pytest.raises(UsineErreur):
        formater_nombre(valeur)  # type: ignore[arg-type]


def test_entier_refuse_un_flottant() -> None:
    with pytest.raises(UsineErreur):
        formater_entier(1.0)  # type: ignore[arg-type]


def test_pourcentage_exige_une_fraction() -> None:
    with pytest.raises(UsineErreur):
        formater_pourcentage(0.125)  # type: ignore[arg-type]


def test_decimales_negatives_refusees() -> None:
    with pytest.raises(UsineErreur):
        formater_nombre(1, -1)


def test_date_avec_heure_refusee() -> None:
    with pytest.raises(UsineErreur):
        formater_date(datetime(2026, 10, 5, tzinfo=UTC))
