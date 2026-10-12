"""Préparation du site : création par nom, idempotence, contrôle createmeta (Story 1.6)."""

import re

import pytest

from tests.unit.generateur.injecteur.conftest import FabriqueClient
from tests.unit.generateur.injecteur.faux_jira import API, FauxJira
from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur
from usine.contrats.tickets import Champ, TypeTicket
from usine.generateur.injecteur.plan import CHAMPS_SELECTION, PlanInjection
from usine.generateur.injecteur.site import (
    NOM_ECRAN,
    NOM_SCHEMA_TYPES,
    NOM_WORKFLOW,
    SiteDemo,
    preparer_site,
)

_CHEMINS_PERMIS = re.compile(
    r"/rest/api/3/(issuetype|field(/search|/[^/]+/context(/[^/]+/option)?)?|workflows/search"
    r"|workflows/create|statuses/search|workflowscheme|issuetypescheme|screens(/\d+/tabs"
    r"(/\d+/fields)?)?|screenscheme|issuetypescreenscheme|project(/search)?|myself"
    r"|issue/createmeta/[A-Z0-9]+/issuetypes(/\d+)?|search/approximate-count|issue"
    r"|issue/[A-Z0-9]+-\d+/transitions|serverInfo)"
)
"""Points d'accès REST du spike : aucun import CSV ou JSON, aucune opération en masse."""


def verifier_sans_import(faux: FauxJira) -> None:
    """Chaque requête vise un point d'accès REST unitaire, jamais un import (AD-4)."""
    for requete in faux.requetes:
        assert _CHEMINS_PERMIS.fullmatch(requete.chemin), requete.chemin
        assert not re.search(r"import|csv|bulk", requete.chemin, re.IGNORECASE)


def _preparer(
    faux: FauxJira, fabrique: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> SiteDemo:
    return preparer_site(fabrique(faux), config, plan.valeurs_libres)


def test_site_vierge(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    site = _preparer(faux, fabrique_client, config, plan)
    noms_types = {t["id"]: t["name"] for t in faux.types if "scope" not in t}
    assert {noms_types[site.types[t]] for t in TypeTicket} == {
        "Anomalie",
        "Cas de test",
        "Certification",
    }
    # Le type « Anomalie » d'un projet (scope) n'est pas repris : un type global est créé.
    assert site.types[TypeTicket.anomalie] != "10002"
    assert {faux.champs[site.champs[c]]["name"] for c in CHAMPS_SELECTION} == set(
        CHAMPS_SELECTION.values()
    )
    assert faux.options_du_champ("Gravité") == ["Bloquante", "Majeure", "Mineure"]
    assert faux.options_du_champ("Statut du test") == ["OK", "KO", "Non exécuté"]
    assert faux.options_du_champ("Entité") == ["ENT-A", "ENT-B"]
    assert faux.options_du_champ("Domaine") == ["achats", "comptabilite", "paie"]
    assert set(faux.workflows) == {NOM_WORKFLOW}
    noms_statuts = [s["name"] for s in faux.statuts]
    assert noms_statuts.count("Fermée") == 1  # statut existant réutilisé par son id
    assert {"Nouvelle", "En analyse", "En correction", "À retester", "Rejetée"} <= set(noms_statuts)
    projet = faux.projet("DEMO")
    assert site.id_projet == projet["id"]
    assert projet["projectTypeKey"] == "software" and projet["leadAccountId"] == "compte-1"
    (schema_workflow,) = faux.schemas_workflow
    assert schema_workflow["defaultWorkflow"] == "jira"
    assert schema_workflow["issueTypeMappings"] == {site.types[TypeTicket.anomalie]: NOM_WORKFLOW}
    (ecran,) = faux.ecrans
    assert ecran["name"] == NOM_ECRAN
    (onglet,) = faux.onglets[str(ecran["id"])]
    assert onglet["name"] == "Général"
    assert faux.champs_onglet[str(onglet["id"])] == [
        "summary",
        "description",
        "issuetype",
        *(site.champs[c] for c in CHAMPS_SELECTION),
    ]
    assert faux.projets[0]["key"] == "KAN" and len(faux.projets[0]) == 3  # KAN intact
    assert "projet DEMO" in site.crees and f"workflow {NOM_WORKFLOW}" in site.crees
    json_site = site.vers_json()
    assert json_site["champs"]["gravite"] == site.champs[Champ.gravite]
    assert json_site["champs"]["statut"] == "status"
    assert json_site["types_tickets"]["Cas de test"] == site.types[TypeTicket.cas_de_test]
    verifier_sans_import(faux)


def test_site_deja_prepare_ne_cree_rien(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    premier = _preparer(faux, fabrique_client, config, plan)
    faux.requetes.clear()
    second = _preparer(faux, fabrique_client, config, plan)
    assert faux.ecritures() == []
    assert second.crees == ()
    assert (second.types, second.champs, second.id_projet) == (
        premier.types,
        premier.champs,
        premier.id_projet,
    )
    verifier_sans_import(faux)


def test_site_deja_prepare_ajoute_seulement_les_options_manquantes(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    _preparer(faux, fabrique_client, config, plan)
    faux.requetes.clear()
    libres = {**plan.valeurs_libres, Champ.vague: ("V1", "V2")}
    site = preparer_site(fabrique_client(faux), config, libres)
    (ecriture,) = faux.ecritures()
    assert ecriture.chemin.endswith("/option")
    assert ecriture.corps == {"options": [{"value": "V2", "disabled": False}]}
    assert site.crees == ("option Vague=V2",)
    assert faux.options_du_champ("Vague") == ["V1", "V2"]


def test_projet_mal_configure_champ_absent_de_l_ecran(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    site = _preparer(faux, fabrique_client, config, plan)
    (onglet,) = faux.onglets[str(faux.ecrans[0]["id"])]
    faux.champs_onglet[str(onglet["id"])].remove(site.champs[Champ.phase])
    faux.requetes.clear()
    with pytest.raises(UsineErreur, match=r"« Anomalie ».*Phase"):
        _preparer(faux, fabrique_client, config, plan)
    assert faux.ecritures() == []  # écran existant jamais modifié


def test_projet_mal_configure_type_absent(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    site = _preparer(faux, fabrique_client, config, plan)
    schema = next(s for s in faux.schemas_types if s["name"] == NOM_SCHEMA_TYPES)
    schema["issueTypeIds"].remove(site.types[TypeTicket.certification])
    with pytest.raises(UsineErreur, match="« Certification » non créable"):
        _preparer(faux, fabrique_client, config, plan)


def test_nom_ambigu_refuse(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    faux = FauxJira()
    for identifiant in ("customfield_1", "customfield_2"):
        faux.champs[identifiant] = {"id": identifiant, "name": "Entité"}
    with pytest.raises(UsineErreur, match="2 champs nommés « Entité »"):
        _preparer(faux, fabrique_client, config, plan)
    assert not any(r.chemin == f"{API}/field" for r in faux.ecritures())


def test_recherche_de_champ_par_nom_exact(
    fabrique_client: FabriqueClient, config: ConfigJira, plan: PlanInjection
) -> None:
    """`field/search?query=` cherche une sous-chaîne : « Phase de test » n'est pas « Phase »."""
    faux = FauxJira()
    faux.champs["customfield_9"] = {"id": "customfield_9", "name": "Phase de test"}
    site = _preparer(faux, fabrique_client, config, plan)
    assert site.champs[Champ.phase] != "customfield_9"
    assert any(
        r.chemin == f"{API}/field/search" and r.params.get("query") == "Phase"
        for r in faux.requetes
    )
