"""Version des contrats et empreintes (AD-2, AD-16)."""

import hashlib
from datetime import UTC, datetime, timedelta, timezone

import pytest

from usine.contrats import CONTRATS_VERSION
from usine.contrats.erreurs import UsineErreur
from usine.contrats.versions import (
    verifier_version,
    version_donnees,
    version_grille,
    version_majeure,
    version_modele,
    version_prompt,
)

OCTETS = b"a: 1\n"
SHA = hashlib.sha256(OCTETS).hexdigest()


def test_version_courante() -> None:
    assert CONTRATS_VERSION == "0.1.0"
    assert version_majeure(CONTRATS_VERSION) == 0


@pytest.mark.parametrize("version", ["1", "1.0", "a.b.c", "01.0.0", "", "1.0.0-rc1"])
def test_version_illisible(version: str) -> None:
    with pytest.raises(UsineErreur, match="illisible"):
        version_majeure(version)


def test_verifier_version_meme_majeure() -> None:
    verifier_version("0.9.3")


def test_verifier_version_majeure_differente() -> None:
    with pytest.raises(UsineErreur) as erreur:
        verifier_version("1.0.0")
    assert "1.0.0" in str(erreur.value)
    assert CONTRATS_VERSION in str(erreur.value)


def test_version_grille() -> None:
    assert version_grille(OCTETS) == SHA[:12]
    assert len(version_grille(OCTETS)) == 12


def test_version_prompt() -> None:
    assert version_prompt(OCTETS) == SHA
    assert len(version_prompt(OCTETS)) == 64


def test_version_modele() -> None:
    assert version_modele("anthropic", "m") == "anthropic:m"


@pytest.mark.parametrize(("fournisseur", "modele"), [("", "m"), ("a", ""), ("a:b", "m")])
def test_version_modele_invalide(fournisseur: str, modele: str) -> None:
    with pytest.raises(UsineErreur):
        version_modele(fournisseur, modele)


def test_version_donnees_sans_extraction() -> None:
    assert version_donnees(b"x", None) == hashlib.sha256(b"x").hexdigest()


def test_version_donnees_avec_extraction_ramenee_en_utc() -> None:
    paris = timezone(timedelta(hours=2))
    horodatage = datetime(2026, 10, 12, 10, 0, tzinfo=paris)
    attendu = hashlib.sha256(b"x\n2026-10-12T08:00:00+00:00").hexdigest()
    assert version_donnees(b"x", horodatage) == attendu
    assert version_donnees(b"x", horodatage.astimezone(UTC)) == attendu
    assert len(attendu) == 64


def test_version_donnees_horodatage_naif_refuse() -> None:
    with pytest.raises(UsineErreur):
        version_donnees(b"x", datetime(2026, 10, 12, 10, 0))  # noqa: DTZ001
