"""Contrat de `Pseudonymiseur` : jetons dérivés, stables, clés de ticket intactes (AD-15)."""

import re
from collections.abc import Callable

from tests.contrat.pseudonymiseur.fabriques import CasPseudonymiseur
from usine.contrats.llm import CANDIDAT_JETON as JETON
from usine.ports import Pseudonymiseur


def test_implemente_le_port(cas: CasPseudonymiseur) -> None:
    assert isinstance(cas.pseudonymiseur, Pseudonymiseur)


def test_retire_chaque_valeur_sensible(cas: CasPseudonymiseur) -> None:
    for exemple in cas.exemples:
        sortie = cas.pseudonymiseur.pseudonymiser(exemple.texte)
        for valeur in exemple.valeurs_sensibles:
            assert valeur not in sortie
        assert len(JETON.findall(sortie)) >= len(exemple.valeurs_sensibles)


def test_garde_les_cles_de_ticket(cas: CasPseudonymiseur) -> None:
    for exemple in cas.exemples:
        sortie = cas.pseudonymiseur.pseudonymiser(exemple.texte)
        for cle in exemple.cles_ticket:
            assert re.search(rf"\b{re.escape(cle)}\b", sortie), cle


def test_texte_sans_valeur_sensible_inchange(cas: CasPseudonymiseur) -> None:
    for exemple in cas.exemples:
        if not exemple.valeurs_sensibles:
            assert cas.pseudonymiseur.pseudonymiser(exemple.texte) == exemple.texte


def test_jetons_stables_entre_appels_et_instances(
    fabrique: Callable[[], CasPseudonymiseur],
) -> None:
    premier, second = fabrique(), fabrique()
    for exemple in premier.exemples:
        sortie = premier.pseudonymiseur.pseudonymiser(exemple.texte)
        assert premier.pseudonymiseur.pseudonymiser(exemple.texte) == sortie
        assert second.pseudonymiseur.pseudonymiser(exemple.texte) == sortie


def test_reidentification_locale(cas: CasPseudonymiseur) -> None:
    for exemple in cas.exemples:
        sortie = cas.pseudonymiseur.pseudonymiser(exemple.texte)
        assert cas.pseudonymiseur.reidentifier(sortie) == exemple.texte


def test_apercu_identique_sans_ecrire_la_table(fabrique: Callable[[], CasPseudonymiseur]) -> None:
    reference, apercu = fabrique(), fabrique()
    for exemple in reference.exemples:
        attendu = reference.pseudonymiseur.pseudonymiser(exemple.texte)
        vu = apercu.pseudonymiseur.apercu(exemple.texte)
        assert vu == attendu
        assert apercu.pseudonymiseur.reidentifier(vu) == vu
