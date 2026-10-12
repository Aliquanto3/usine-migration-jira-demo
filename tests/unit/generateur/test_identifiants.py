"""Identifiants sensibles fictifs (Story 1.4) : formats, clés fausses, noms inventés."""

import random
import re

import pytest

from usine.adaptateurs.pseudonymisation import MOTIFS_PAR_DEFAUT
from usine.contrats.llm import MOTIF_TYPE_JETON
from usine.generateur.identifiants import (
    CIVILITES,
    NOMS_FICTIFS,
    PRENOMS_FICTIFS,
    TypeIdentifiant,
    iban_fictif,
    iban_valide,
    identifiant_client_fictif,
    luhn_valide,
    nom_client_fictif,
    phrase_identifiants,
)

MOTIF_IBAN = re.compile(MOTIFS_PAR_DEFAUT["COMPTE"])
"""Motif `COMPTE` de la Pseudonymisation, importé pour suivre toute évolution."""

TIRAGES = 500

_BBAN_FICTIF = "99999" + "000001234567890123"
"""BBAN de code banque fictif `99999` : aucun numéro réel dans les tests."""
_CLE_JUSTE = 98 - int(_BBAN_FICTIF + "152700") % 97
"""Clé ISO 13616 calculée sur l'IBAN réarrangé (`FR` = 15 27, clé provisoire 00)."""


def _groupe(compact: str) -> str:
    return " ".join(compact[i : i + 4] for i in range(0, len(compact), 4))


IBAN_JUSTE = f"FR{_CLE_JUSTE:02d}{_BBAN_FICTIF}"
IBAN_CLE_FAUSSE = f"FR{_CLE_JUSTE + 1:02d}{_BBAN_FICTIF}"


@pytest.fixture
def rng() -> random.Random:
    return random.Random(2026)


@pytest.mark.parametrize(
    ("iban", "attendu"),
    [
        (_groupe(IBAN_JUSTE), True),
        (IBAN_JUSTE, True),
        (_groupe(IBAN_CLE_FAUSSE), False),
        ("FR", False),
        ("FR76-3000", False),
        ("FR76²000", False),
    ],
)
def test_iban_valide(iban: str, attendu: bool) -> None:
    assert iban_valide(iban) is attendu


@pytest.mark.parametrize(
    ("nombre", "attendu"),
    [
        ("79927398713", True),
        ("79927398710", False),
        ("0", True),
        ("", False),
        ("12a4", False),
        ("12²4", False),
    ],
)
def test_luhn_valide(nombre: str, attendu: bool) -> None:
    assert luhn_valide(nombre) is attendu


def test_iban_fictif_format_et_cle_fausse(rng: random.Random) -> None:
    valeurs = {iban_fictif(rng) for _ in range(TIRAGES)}
    assert len(valeurs) > TIRAGES * 0.9
    for iban in valeurs:
        assert MOTIF_IBAN.fullmatch(iban), iban
        assert iban.replace(" ", "")[4:9] == "99999"
        assert not iban_valide(iban), iban


def test_identifiant_client_fictif_luhn_faux(rng: random.Random) -> None:
    for _ in range(TIRAGES):
        identifiant = identifiant_client_fictif(rng)
        assert re.fullmatch(r"99\d{8}", identifiant), identifiant
        assert not luhn_valide(identifiant), identifiant


def test_nom_client_fictif_listes_inventees(rng: random.Random) -> None:
    racines = ("fict", "simul", "exempl", "leurr", "maquett", "factic")
    for nom in (*PRENOMS_FICTIFS, *NOMS_FICTIFS):
        assert nom.lower().startswith(racines), nom
    for _ in range(TIRAGES):
        civilite, prenom, nom = nom_client_fictif(rng).split(" ")
        assert civilite in CIVILITES
        assert prenom in PRENOMS_FICTIFS
        assert nom in NOMS_FICTIFS
        assert nom == nom.upper()


def test_types_au_format_des_jetons() -> None:
    assert {t.value for t in TypeIdentifiant} == {"COMPTE", "CLIENT", "ID_CLIENT"}
    for type_identifiant in TypeIdentifiant:
        assert re.fullmatch(MOTIF_TYPE_JETON, type_identifiant.value)


def test_phrase_identifiants(rng: random.Random) -> None:
    sous_ensembles = set()
    for _ in range(TIRAGES):
        phrase, identifiants = phrase_identifiants("ENT-B", rng)
        assert 1 <= len(identifiants) <= 3
        types = tuple(t for t, _ in identifiants)
        assert types == tuple(t for t in TypeIdentifiant if t in types)
        sous_ensembles.add(types)
        assert phrase.startswith("Cas cité par l'Entité ENT-B : ")
        assert phrase.endswith(".")
        for _, valeur in identifiants:
            assert valeur in phrase
    assert len(sous_ensembles) == 7  # tous les sous-ensembles non vides de 3 types


def test_deterministe() -> None:
    def tirage(graine: int) -> list[object]:
        rng = random.Random(graine)
        return [
            iban_fictif(rng),
            nom_client_fictif(rng),
            identifiant_client_fictif(rng),
            phrase_identifiants("ENT-A", rng),
        ]

    assert tirage(7) == tirage(7)
    assert tirage(7) != tirage(8)
