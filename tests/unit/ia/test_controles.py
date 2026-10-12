"""`controler_citations` : retrait des phrases sans Citation ou à Citation fautive (FR-32)."""

from datetime import date
from fractions import Fraction

import pytest

from usine.ia.controles import (
    controler_citations,
    controler_nombres,
    decouper_phrases,
    retirer_citations_hors,
)


def test_exemple_de_la_spec() -> None:
    texte = "DEMO-3 bloque la recette. DEMO-9 aggrave le retard. Le stock monte (DEMO-7)."
    controle = controler_citations(texte, {"DEMO-3", "DEMO-7"})
    assert controle.texte == "DEMO-3 bloque la recette. Le stock monte (DEMO-7)."
    assert controle.citations == ("DEMO-3", "DEMO-7")
    assert controle.phrases_retirees == 1
    assert controle.phrases_total == 3


def test_phrase_sans_citation_retiree() -> None:
    controle = controler_citations("DEMO-3 bloque. Le retard se creuse.", {"DEMO-3"})
    assert controle.texte == "DEMO-3 bloque."
    assert controle.phrases_retirees == 1


def test_phrase_mixte_retiree() -> None:
    controle = controler_citations("DEMO-3 et DEMO-9 bloquent.", {"DEMO-3"})
    assert controle.texte == ""
    assert controle.citations == ()
    assert controle.phrases_retirees == 1


def test_aucun_ticket_autorise() -> None:
    controle = controler_citations("DEMO-3 bloque.", ())
    assert (controle.texte, controle.phrases_retirees, controle.phrases_total) == ("", 1, 1)


def test_decoupage() -> None:
    assert decouper_phrases("Un taux de 3.5 reste. Vraiment ! Et ensuite ? Fin") == (
        "Un taux de 3.5 reste.",
        "Vraiment !",
        "Et ensuite ?",
        "Fin",
    )
    assert decouper_phrases("   ") == ()


def test_citations_triees_sans_doublon() -> None:
    controle = controler_citations(
        "DEMO-10 et DEMO-2 bloquent. DEMO-2 encore.", {"DEMO-2", "DEMO-10"}
    )
    assert controle.citations == ("DEMO-2", "DEMO-10")
    assert controle.phrases_retirees == 0


def test_jeton_n_est_pas_une_cle() -> None:
    controle = controler_citations("COMPTE_a1b2c3 est cité.", {"DEMO-1"})
    assert controle.phrases_retirees == 1


def test_code_indicateur_n_est_pas_une_citation() -> None:
    controle = controler_citations("IND-1 dépasse son seuil à cause de DEMO-3.", {"DEMO-3"})
    assert controle.texte == "IND-1 dépasse son seuil à cause de DEMO-3."
    assert controle.citations == ("DEMO-3",)
    assert controle.phrases_retirees == 0


def test_code_entite_n_est_pas_une_citation() -> None:
    controle = controler_citations(
        "ENT-12 est freinée par DEMO-3. ENT-12 est en rouge.", {"DEMO-3"}
    )
    assert controle.texte == "ENT-12 est freinée par DEMO-3."
    assert controle.citations == ("DEMO-3",)
    assert controle.phrases_retirees == 1  # la seconde phrase ne cite aucun ticket


def test_saut_de_ligne_termine_une_phrase() -> None:
    texte = "- DEMO-3 bloque la recette\n- le retard se creuse\n\n- DEMO-7 monte"
    assert decouper_phrases(texte) == (
        "- DEMO-3 bloque la recette",
        "- le retard se creuse",
        "- DEMO-7 monte",
    )
    controle = controler_citations(texte, {"DEMO-3", "DEMO-7"})
    assert controle.phrases_retirees == 1
    assert controle.phrases_total == 3
    assert controle.citations == ("DEMO-3", "DEMO-7")


def test_utf_8_n_est_pas_une_citation() -> None:
    controle = controler_citations("DEMO-3 casse l'encodage UTF-8.", {"DEMO-3"})
    assert controle.texte == "DEMO-3 casse l'encodage UTF-8."
    assert controle.citations == ("DEMO-3",)
    assert controle.phrases_retirees == 0


def test_retirer_citations_hors() -> None:
    texte = "Relancer DEMO-3. Voir aussi DEMO-9. Merci à l'équipe."
    assert retirer_citations_hors(texte, {"DEMO-3"}) == "Relancer DEMO-3. Merci à l'équipe."


# --- `controler_nombres` (AD-14, Story 6.7) ---

VALEURS = (Fraction(3, 5), 10, date(2026, 10, 15), date(2026, 10, 1), 1234, -3)


@pytest.mark.parametrize(
    "texte",
    [
        "Sortie estimée le 15/10/2026 avec 60 % de probabilité.",
        "Probabilité de 60\u00a0% sur 10 jours ouvrés.",
        "Probabilité 0,6, soit 3/5.",
        "Le stock atteint 1 234 tickets.",
        "Le stock atteint 1\u00a0234 tickets.",
        "Le stock atteint 1\u202f234 tickets.",
        "Sortie le 2026-10-15.",
        "Sortie le 15 octobre 2026.",
        "Sortie vers le 15 octobre.",
        "Point de départ le 1er octobre.",
        "Le stock baisse de 3 tickets.",
        "DEMO-12 et IND-1 pèsent sur ENT-A, à J-5 ; voir COMPTE_1a2b3c.",
        "La Prévision reste incertaine.",
    ],
)
def test_nombres_conformes(texte: str) -> None:
    controle = controler_nombres(texte, VALEURS)
    assert controle.conforme, controle.refuses


@pytest.mark.parametrize(
    ("texte", "refuses"),
    [
        ("Sortie dans 12 jours.", ("12",)),
        ("Sortie le 20/10/2026.", ("20/10/2026",)),
        ("Sortie le 2026-10-20.", ("2026-10-20",)),
        ("Sortie le 20 octobre 2026.", ("20 octobre 2026",)),
        ("Probabilité de 70 %.", ("70 %",)),
        ("Probabilité 0,7 ; ratio 4/5.", ("0,7", "4/5")),
        ("Stock 1 235 ; horizon 10 ; date 31/02/2026.", ("1 235", "31/02/2026")),
    ],
)
def test_nombres_refuses(texte: str, refuses: tuple[str, ...]) -> None:
    controle = controler_nombres(texte, VALEURS)
    assert not controle.conforme
    assert controle.refuses == refuses


def test_arrondi_au_nombre_de_decimales_ecrit() -> None:
    tiers = (Fraction(1, 3),)
    assert controler_nombres("Soit 33 % ou 33,3 % ou 0,33.", tiers).conforme
    assert not controler_nombres("Soit 33,4 %.", tiers).conforme


def test_entier_n_est_pas_l_arrondi_d_une_fraction() -> None:
    """« 1 » n'est pas 3/5 arrondi ; « 60 % » l'est (forme pourcentage)."""
    assert controler_nombres("Une chance sur 1.", (Fraction(3, 5),)).refuses == ("1",)
    assert controler_nombres("Soit 60 %.", (Fraction(3, 5),)).conforme


@pytest.mark.parametrize(("texte", "refuse"), [("Sortie en 12j.", "12"), ("Au 4e jour.", "4")])
def test_nombre_colle_a_des_lettres_est_controle(texte: str, refuse: str) -> None:
    assert controler_nombres(texte, VALEURS).refuses == (refuse,)


def test_nombre_a_trop_de_decimales_refuse_sans_erreur() -> None:
    texte = "Probabilité 0," + "6" * 40 + "."
    assert not controler_nombres(texte, VALEURS).conforme


@pytest.mark.parametrize(
    ("texte", "refuses"),
    [
        ("Sortie dans 99, puis rien.", ("99",)),
        ("Probabilité 10 %, donc faible.", ("10 %",)),
        ("Sortie le 15/12.", ("15/12",)),
        ("Sortie le 20/10/26.", ("20/10/26",)),
        ("Taux 2.15 ou 15.10.2026.", ("2.15", "15.10.2026")),
        ("Sortie le 20 oct. 2026.", ("20 oct. 2026",)),
    ],
)
def test_revue_de_suivi_formes_refusees(texte: str, refuses: tuple[str, ...]) -> None:
    assert controler_nombres(texte, (*VALEURS, 15, 12)).refuses == refuses


@pytest.mark.parametrize(
    "texte", ["Sortie le 15/10, horizon 10, fin.", "Sortie le 15/10/26.", "Le 15 oct. 2026."]
)
def test_revue_de_suivi_formes_acceptees(texte: str) -> None:
    assert controler_nombres(texte, VALEURS).conforme
