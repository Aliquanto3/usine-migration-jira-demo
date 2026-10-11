"""`controler_citations` : retrait des phrases sans Citation ou à Citation fautive (FR-32)."""

from usine.ia.controles import controler_citations, decouper_phrases, retirer_citations_hors


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
