"""Formatage français (AD-11)."""

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction

import pytest

from usine.contrats.erreurs import UsineErreur
from usine.contrats.format import (
    formater_date,
    formater_entier,
    formater_fraction,
    formater_heure,
    formater_horodatage,
    formater_nombre,
    formater_pourcentage,
    heure_de_paris,
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


def test_horodatage_ete_change_de_jour() -> None:
    """Heure d'été (UTC+2) : 12/10/2026 22:12 UTC = 13/10/2026 00:12 à Paris."""
    instant = datetime(2026, 10, 12, 22, 12, tzinfo=UTC)
    assert formater_horodatage(instant) == "13/10/2026 00:12:00"
    assert formater_horodatage(instant, secondes=False) == "13/10/2026 00:12"
    assert formater_heure(instant) == "00:12:00"
    assert formater_heure(instant, secondes=False) == "00:12"


def test_horodatage_hiver() -> None:
    """Heure d'hiver (UTC+1) : 15/01/2026 22:12 UTC = 15/01/2026 23:12 à Paris."""
    instant = datetime(2026, 1, 15, 22, 12, 5, tzinfo=UTC)
    assert formater_horodatage(instant) == "15/01/2026 23:12:05"
    assert formater_horodatage(instant, secondes=False) == "15/01/2026 23:12"


def test_horodatage_hiver_change_de_jour_et_autre_fuseau() -> None:
    assert formater_horodatage(datetime(2026, 12, 31, 23, 30, tzinfo=UTC)) == (
        "01/01/2027 00:30:00"
    )
    new_york = timezone(timedelta(hours=-4))
    assert formater_heure(datetime(2026, 10, 12, 18, 12, tzinfo=new_york)) == "00:12:00"


def test_horodatage_sans_mention_de_fuseau() -> None:
    texte = formater_horodatage(datetime(2026, 10, 12, 7, 30, tzinfo=UTC))
    assert texte == "12/10/2026 09:30:00"
    assert "UTC" not in texte


_NAIF = datetime(2026, 10, 12, 22, 12)  # noqa: DTZ001 : instant naïf voulu


@pytest.mark.parametrize("valeur", [_NAIF, date(2026, 10, 12), "x"])
def test_horodatage_naif_ou_non_instant_refuse(valeur: object) -> None:
    with pytest.raises(UsineErreur, match="fuseau"):
        heure_de_paris(valeur)  # type: ignore[arg-type]
    with pytest.raises(UsineErreur):
        formater_horodatage(valeur)  # type: ignore[arg-type]
