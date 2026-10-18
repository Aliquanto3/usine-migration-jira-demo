"""Formatage français des nombres, des dates et des heures, partagé par tous (AD-11).

Milliers séparés par une espace insécable (U+00A0), virgule décimale, arrondi au demi
supérieur ; les zéros non significatifs après la virgule sont retirés. Une heure affichée est
l'heure de Paris (`calendrier.FUSEAU`, heure d'été et d'hiver), sans mention de fuseau : les
données restent en UTC, seule la mise en forme convertit (décision du 18/10/2026).
"""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from usine.contrats.calendrier import FUSEAU
from usine.contrats.erreurs import UsineErreur

ESPACE_INSECABLE = "\u00a0"


def _decimal(valeur: int | float | Decimal | Fraction) -> Decimal:
    if isinstance(valeur, bool):
        raise UsineErreur(f"nombre attendu, pas un booléen : {valeur!r}")
    if isinstance(valeur, Fraction):
        return Decimal(valeur.numerator) / Decimal(valeur.denominator)
    if isinstance(valeur, float):
        resultat = Decimal(repr(valeur))
    elif isinstance(valeur, int | Decimal):
        resultat = Decimal(valeur)
    else:
        raise UsineErreur(f"nombre attendu, pas {type(valeur).__name__} : {valeur!r}")
    if not resultat.is_finite():
        raise UsineErreur(f"nombre fini attendu : {valeur!r}")
    return resultat


def _verifier_decimales(decimales: int) -> None:
    if type(decimales) is not int or decimales < 0:
        raise UsineErreur(f"nombre de décimales invalide : {decimales!r}")


def _ecrire(valeur: Decimal, decimales: int) -> str:
    arrondi = valeur.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)
    signe, texte = ("-", f"{-arrondi:f}") if arrondi < 0 else ("", f"{arrondi:f}")
    entiere, _, fraction = texte.partition(".")
    fraction = fraction.rstrip("0")
    groupes = f"{int(entiere):,}".replace(",", ESPACE_INSECABLE)
    return f"{signe}{groupes},{fraction}" if fraction else f"{signe}{groupes}"


def formater_entier(valeur: int) -> str:
    """Entier avec milliers séparés : `1234567` → `1 234 567`."""
    if type(valeur) is not int:
        raise UsineErreur(f"entier attendu, pas {type(valeur).__name__} : {valeur!r}")
    return _ecrire(Decimal(valeur), 0)


def formater_nombre(valeur: int | float | Decimal | Fraction, decimales: int = 1) -> str:
    """Nombre arrondi à `decimales` : `12345.5` → `12 345,5`, `1234567` → `1 234 567`."""
    _verifier_decimales(decimales)
    return _ecrire(_decimal(valeur), decimales)


def formater_fraction(valeur: Fraction, decimales: int = 1) -> str:
    """Fraction écrite en décimal : `Fraction(3, 2)` → `1,5`."""
    if not isinstance(valeur, Fraction):
        raise UsineErreur(f"Fraction attendue, pas {type(valeur).__name__} : {valeur!r}")
    return formater_nombre(valeur, decimales)


def formater_pourcentage(valeur: Fraction, decimales: int = 1) -> str:
    """Fraction écrite en pourcentage : `Fraction(1, 8)` → `12,5 %`."""
    if not isinstance(valeur, Fraction):
        raise UsineErreur(f"Fraction attendue, pas {type(valeur).__name__} : {valeur!r}")
    return f"{formater_nombre(valeur * 100, decimales)}{ESPACE_INSECABLE}%"


def formater_date(valeur: date) -> str:
    """Date au format `JJ/MM/AAAA`."""
    if isinstance(valeur, datetime) or not isinstance(valeur, date):
        raise UsineErreur(f"date attendue (sans heure), pas {valeur!r}")
    return f"{valeur.day:02d}/{valeur.month:02d}/{valeur.year:04d}"


def heure_de_paris(instant: datetime) -> datetime:
    """Instant avec fuseau ramené à l'heure de Paris ; un `datetime` naïf est refusé."""
    if not isinstance(instant, datetime) or instant.utcoffset() is None:
        raise UsineErreur(f"instant avec fuseau attendu, pas {instant!r}")
    return instant.astimezone(FUSEAU)


def formater_heure(instant: datetime, *, secondes: bool = True) -> str:
    """Heure de Paris `HH:MM:SS` (ou `HH:MM`), sans mention de fuseau."""
    paris = heure_de_paris(instant)
    return f"{paris:%H:%M:%S}" if secondes else f"{paris:%H:%M}"


def formater_horodatage(instant: datetime, *, secondes: bool = True) -> str:
    """Date et heure de Paris : `13/10/2026 00:12:00` (ou `13/10/2026 00:12`)."""
    paris = heure_de_paris(instant)
    return f"{formater_date(paris.date())} {formater_heure(paris, secondes=secondes)}"
