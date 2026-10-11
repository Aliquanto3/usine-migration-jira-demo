"""Calendrier : Jours ouvrés, fuseau, Fenêtre glissante, semaines (AD-17)."""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from usine.contrats.calendrier import (
    dernier_jour_ouvre_ecoule,
    est_jour_ouvre,
    fenetre_glissante,
    jour_local,
    jour_ouvre_de,
    jour_ouvre_precedent,
    jour_ouvre_suivant,
    jours_ouvres,
    semaine_programme,
)
from usine.contrats.erreurs import UsineErreur

LUNDI = date(2026, 10, 12)


def test_jours_ouvres_du_lundi_au_vendredi() -> None:
    semaine = [date(2026, 10, 12 + i) for i in range(7)]
    assert [est_jour_ouvre(d) for d in semaine] == [True] * 5 + [False] * 2


def test_samedi_soir_utc_rattache_au_lundi() -> None:
    samedi = datetime(2026, 10, 10, 23, 0, tzinfo=UTC)
    assert jour_local(samedi) == date(2026, 10, 11)
    assert jour_ouvre_de(samedi) == LUNDI


def test_soiree_en_semaine_rattachee_au_lendemain_local() -> None:
    assert jour_ouvre_de(datetime(2026, 10, 12, 22, 30, tzinfo=UTC)) == date(2026, 10, 13)


def test_heure_d_hiver() -> None:
    assert jour_local(datetime(2026, 12, 14, 22, 30, tzinfo=UTC)) == date(2026, 12, 14)
    assert jour_local(datetime(2026, 12, 14, 23, 30, tzinfo=UTC)) == date(2026, 12, 15)


def test_horodatage_naif_refuse() -> None:
    with pytest.raises(UsineErreur):
        jour_local(datetime(2026, 10, 12, 10, 0))  # noqa: DTZ001


def test_jour_ouvre_suivant() -> None:
    assert jour_ouvre_suivant(date(2026, 10, 9)) == LUNDI
    assert jour_ouvre_suivant(LUNDI) == date(2026, 10, 13)


def test_j_moins_n() -> None:
    assert jour_ouvre_precedent(LUNDI, 5) == date(2026, 10, 5)
    assert jour_ouvre_precedent(LUNDI, 1) == date(2026, 10, 9)
    assert jour_ouvre_precedent(LUNDI) == date(2026, 10, 9)
    assert jour_ouvre_precedent(LUNDI, 0) == LUNDI


def test_j_moins_n_negatif_refuse() -> None:
    with pytest.raises(UsineErreur):
        jour_ouvre_precedent(LUNDI, -1)


def test_jours_ouvres_bornes_incluses() -> None:
    assert jours_ouvres(date(2026, 10, 9), LUNDI) == (date(2026, 10, 9), LUNDI)
    assert jours_ouvres(LUNDI, date(2026, 10, 9)) == ()


def test_fenetre_glissante() -> None:
    fenetre = fenetre_glissante(LUNDI)
    assert fenetre == (
        date(2026, 10, 6),
        date(2026, 10, 7),
        date(2026, 10, 8),
        date(2026, 10, 9),
        LUNDI,
    )


def test_fenetre_glissante_date_non_ouvree() -> None:
    with pytest.raises(UsineErreur, match="2026-10-11"):
        fenetre_glissante(date(2026, 10, 11))


def test_fenetre_glissante_taille_invalide() -> None:
    with pytest.raises(UsineErreur):
        fenetre_glissante(LUNDI, 0)


def test_semaine_programme() -> None:
    ancrage = date(2026, 8, 17)
    assert semaine_programme(ancrage, ancrage) == 1
    assert semaine_programme(date(2026, 8, 21), ancrage) == 1
    assert semaine_programme(date(2026, 8, 24), ancrage) == 2
    assert semaine_programme(date(2026, 10, 9), ancrage) == 8


def test_semaine_programme_ancrage_non_lundi() -> None:
    with pytest.raises(UsineErreur):
        semaine_programme(date(2026, 10, 9), date(2026, 8, 18))


def test_semaine_programme_avant_ancrage() -> None:
    with pytest.raises(UsineErreur):
        semaine_programme(date(2026, 8, 14), date(2026, 8, 17))


def test_dernier_jour_ouvre_ecoule() -> None:
    assert dernier_jour_ouvre_ecoule(LUNDI) == date(2026, 10, 9)
    assert dernier_jour_ouvre_ecoule(date(2026, 10, 11)) == date(2026, 10, 9)
    assert dernier_jour_ouvre_ecoule(date(2026, 10, 14)) == date(2026, 10, 13)


def test_datetime_refuse_comme_date() -> None:
    with pytest.raises(UsineErreur):
        est_jour_ouvre(datetime(2026, 10, 12, tzinfo=UTC))


INTERDITS = (
    "Europe/Paris",
    "zoneinfo",
    ".weekday(",
    ".isoweekday(",
    ".isocalendar(",
    "pytz",
    "dateutil",
)


def test_seul_le_calendrier_definit_le_temps(racine_depot: Path) -> None:
    calendrier = racine_depot / "src" / "usine" / "contrats" / "calendrier.py"
    fautifs = [
        f"{chemin.relative_to(racine_depot)} : {interdit}"
        for chemin in sorted((racine_depot / "src" / "usine").rglob("*.py"))
        if chemin != calendrier
        for interdit in INTERDITS
        if interdit in chemin.read_text(encoding="utf-8")
    ]
    assert fautifs == []
