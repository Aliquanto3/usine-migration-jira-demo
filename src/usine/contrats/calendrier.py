"""Temps du démonstrateur : seule source du fuseau, des Jours ouvrés et des semaines (AD-17).

Jour ouvré = du lundi au vendredi, sans jour férié (H-1). Un horodatage est rattaché à un jour
dans le fuseau du Programme (H-25). Fenêtre glissante = 5 derniers Jours ouvrés, Date d'arrêté
comprise (H-19).
"""

from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import AfterValidator, AwareDatetime

from usine.contrats.erreurs import UsineErreur

FUSEAU = ZoneInfo("Europe/Paris")
"""Fuseau de rattachement des horodatages à un jour (H-25)."""

TAILLE_FENETRE_GLISSANTE = 5
"""Nombre de Jours ouvrés d'une Fenêtre glissante (H-19)."""

_UN_JOUR = timedelta(days=1)


def _en_utc(horodatage: datetime) -> datetime:
    return horodatage.astimezone(UTC)


Horodatage = Annotated[AwareDatetime, AfterValidator(_en_utc)]
"""Instant avec fuseau, ramené en UTC par les modèles ; un `datetime` naïf est refusé."""


def _date_pure(d: date) -> date:
    if isinstance(d, datetime) or not isinstance(d, date):
        raise UsineErreur(f"date attendue (sans heure), pas {d!r}")
    return d


def _instant(ts: datetime) -> datetime:
    if not isinstance(ts, datetime) or ts.tzinfo is None or ts.utcoffset() is None:
        raise UsineErreur(f"horodatage avec fuseau attendu, pas {ts!r}")
    return ts


def est_jour_ouvre(d: date) -> bool:
    """Vrai si `d` est un Jour ouvré (lundi à vendredi)."""
    return _date_pure(d).weekday() < 5


def jour_local(ts: datetime) -> date:
    """Jour de `ts` dans le fuseau du Programme."""
    return _instant(ts).astimezone(FUSEAU).date()


def jour_ouvre_suivant(d: date) -> date:
    """Premier Jour ouvré strictement après `d`."""
    suivant = _date_pure(d) + _UN_JOUR
    while not est_jour_ouvre(suivant):
        suivant += _UN_JOUR
    return suivant


def jour_ouvre_de(ts: datetime) -> date:
    """Jour ouvré de rattachement de `ts` : premier Jour ouvré ≥ son jour local."""
    jour = jour_local(ts)
    return jour if est_jour_ouvre(jour) else jour_ouvre_suivant(jour)


def jour_ouvre_precedent(d: date, n: int = 1) -> date:
    """J-n : recule de `n` Jours ouvrés depuis `d` (J-0 = `d`, J-1 d'un lundi = vendredi)."""
    if type(n) is not int or n < 0:
        raise UsineErreur(f"nombre de Jours ouvrés invalide : {n!r} (entier ≥ 0 attendu)")
    jour = _date_pure(d)
    for _ in range(n):
        jour -= _UN_JOUR
        while not est_jour_ouvre(jour):
            jour -= _UN_JOUR
    return jour


def jours_ouvres(debut: date, fin: date) -> tuple[date, ...]:
    """Jours ouvrés de `debut` à `fin` inclus, dans l'ordre (vide si `debut > fin`)."""
    jour, fin = _date_pure(debut), _date_pure(fin)
    jours: list[date] = []
    while jour <= fin:
        if est_jour_ouvre(jour):
            jours.append(jour)
        jour += _UN_JOUR
    return tuple(jours)


def fenetre_glissante(d: date, taille: int = TAILLE_FENETRE_GLISSANTE) -> tuple[date, ...]:
    """Les `taille` derniers Jours ouvrés, `d` compris, dans l'ordre chronologique."""
    if not est_jour_ouvre(d):
        raise UsineErreur(f"Fenêtre glissante : {d.isoformat()} n'est pas un Jour ouvré")
    if type(taille) is not int or taille < 1:
        raise UsineErreur(f"Fenêtre glissante : taille invalide {taille!r} (entier ≥ 1 attendu)")
    return tuple(jour_ouvre_precedent(d, n) for n in range(taille - 1, -1, -1))


def semaine_programme(d: date, ancrage: date) -> int:
    """Numéro de semaine du Programme de `d` (1 = semaine de l'ancrage, un lundi)."""
    verifier_lundi(ancrage)
    if _date_pure(d) < ancrage:
        raise UsineErreur(
            f"date {d.isoformat()} antérieure à l'ancrage des semaines {ancrage.isoformat()}"
        )
    return (d - ancrage).days // 7 + 1


def verifier_lundi(d: date) -> date:
    """Renvoie `d` s'il tombe un lundi ; sinon lève une `UsineErreur`."""
    if _date_pure(d).weekday() != 0:
        raise UsineErreur(f"ancrage des semaines {d.isoformat()} : un lundi est attendu")
    return d


def dernier_jour_ouvre_ecoule(aujourd_hui: date) -> date:
    """Dernier Jour ouvré strictement antérieur à `aujourd_hui` (Date d'arrêté par défaut)."""
    return jour_ouvre_precedent(aujourd_hui, 1)
