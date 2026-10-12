"""Suite de contrat `SourceTickets` exécutée sur `SourceJiraCloud` (AD-20, AD-21).

`tests/contrat/` appartient à `main` : ce module réimporte ses tests inchangés et fournit sa
propre fixture `cas`. La fabrique Cloud rejoindra `fabriques.py` par une PR courte sur `main`.
"""

import pytest

from tests.contrat.source_tickets.fabriques import CasSourceTickets
from tests.contrat.source_tickets.test_contrat import (  # noqa: F401
    test_creation_suivie_de_ses_attributs_au_meme_horodatage,
    test_depuis_garde_les_evenements_a_partir_de_l_instant,
    test_depuis_sans_fuseau_refuse,
    test_horodatages_en_utc,
    test_implemente_le_port,
    test_ordre_chronologique_et_identifiants_uniques,
    test_rend_les_evenements_attendus,
    test_valeurs_dans_le_domaine_canonique,
)
from tests.unit.adaptateurs.jira_cloud.outils import evenements_attendus, source_fixtures


def fabrique_jira_cloud() -> CasSourceTickets:
    """`SourceJiraCloud` sur les fixtures `tests/fixtures/jira_cloud/source_*`."""
    return CasSourceTickets(source_fixtures(), evenements_attendus())


@pytest.fixture
def cas() -> CasSourceTickets:
    """Un cas neuf par test : `SourceJiraCloud` sur un serveur simulé neuf."""
    return fabrique_jira_cloud()


def test_tous_les_tests_du_contrat_sont_reimportes() -> None:
    from tests.contrat.source_tickets import test_contrat

    contrat = {nom for nom in vars(test_contrat) if nom.startswith("test_")}
    manquants = sorted(nom for nom in contrat if globals().get(nom) is not vars(test_contrat)[nom])
    assert manquants == [], f"tests du contrat non réimportés : {manquants}"
