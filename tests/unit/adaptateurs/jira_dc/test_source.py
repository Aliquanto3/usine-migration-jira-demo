"""`SourceJiraDC` : flux, requêtes, curseur de clé, noms de champs, lecture seule (2.4)."""

import copy
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from tests.unit.adaptateurs.jira_dc.outils import (
    CHEMIN_CHAMPS,
    CHEMIN_DEMO_3,
    CHEMIN_RECHERCHE,
    PAT,
    ServeurFixturesDC,
    evenements_attendus,
    source_fixtures_dc,
)
from tests.unit.adaptateurs.jira_http.outils import Attentes, config_jira
from usine.adaptateurs.jira_dc import (
    TAILLE_PAGE_RECHERCHE,
    SourceJiraDC,
    identifiants_par_nom,
    resoudre_items,
)
from usine.adaptateurs.jira_http import (
    LISTE_BLANCHE_LECTURE,
    RequeteJiraInterdite,
    construire_client_lecture,
    requete_autorisee,
)
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import SourceEvenement
from usine.ports import SourceTickets

JQL = 'project = "DEMO" AND issuetype in ("Anomalie", "Cas de test", "Certification")'
CHAMPS = (
    "status,customfield_10043,customfield_10044,customfield_10045,customfield_10046,"
    "customfield_10047,summary,description,customfield_10048,customfield_10049,issuetype,created"
)


PAGE_VIDE: dict[str, Any] = {"startAt": 0, "maxResults": 100, "total": 0, "issues": []}


def _page(serveur: ServeurFixturesDC, route: str, total: object) -> dict[str, Any]:
    page: dict[str, Any] = copy.deepcopy(serveur.reponses[route])
    page["total"] = total
    return page


def _recherches(serveur: ServeurFixturesDC) -> list[tuple[str, str, str]]:
    return [
        (r.url.params["jql"], r.url.params["startAt"], r.url.params["maxResults"])
        for r in serveur.requetes
        if r.url.path == CHEMIN_RECHERCHE
    ]


def test_rend_le_flux_cloud_a_la_source_pres() -> None:
    rendus = tuple(source_fixtures_dc().evenements())
    assert rendus == evenements_attendus()
    assert {e.source for e in rendus} == {SourceEvenement.jira_dc}


def test_implemente_le_port() -> None:
    assert isinstance(source_fixtures_dc(), SourceTickets)


def test_requetes_emises() -> None:
    serveur = ServeurFixturesDC()
    list(source_fixtures_dc(serveur).evenements())
    assert serveur.inattendues == []
    assert [(r.method, r.url.path) for r in serveur.requetes] == [
        ("GET", CHEMIN_CHAMPS),
        ("GET", CHEMIN_RECHERCHE),
        ("GET", CHEMIN_RECHERCHE),
        ("GET", CHEMIN_DEMO_3),
    ]
    # Première page courte (2 tickets, `total` 4) : la suivante reprend après DEMO-2.
    recherches = [dict(r.url.params) for r in serveur.requetes[1:3]]
    assert recherches == [
        {
            "jql": f"{JQL}{curseur} ORDER BY key ASC",
            "fields": CHAMPS,
            "expand": "changelog",
            "startAt": "0",
            "maxResults": "100",
        }
        for curseur in ("", ' AND key > "DEMO-2"')
    ]
    assert dict(serveur.requetes[3].url.params) == {"expand": "changelog"}
    assert all(r.headers["Authorization"] == f"Bearer {PAT}" for r in serveur.requetes)


def test_seules_les_lectures_de_la_liste_blanche_dc_sont_emises() -> None:
    serveur = ServeurFixturesDC()
    list(source_fixtures_dc(serveur).evenements())
    assert all(requete_autorisee("dc", r.method, r.url.path) for r in serveur.requetes)
    assert {r.method for r in serveur.requetes} == {"GET"}
    assert ("GET", "/rest/api/2/field") in LISTE_BLANCHE_LECTURE["dc"]


def test_lecture_seule_un_client_cloud_n_envoie_rien() -> None:
    serveur = ServeurFixturesDC()
    client_cloud = construire_client_lecture(
        config_jira("cloud"),
        email="lecteur@example.invalid",
        jeton_lecture=SecretStr("jeton-lecture"),
        pat=None,
        attendre=Attentes(),
        transport_http=httpx.MockTransport(serveur),
    )
    with pytest.raises(RequeteJiraInterdite, match="/rest/api/2/field"):
        list(SourceJiraDC(client_cloud, config_jira("dc")).evenements())
    assert serveur.requetes == []


def test_pagination_par_curseur_de_cle() -> None:
    serveur = ServeurFixturesDC()
    serveur.reponses["recherche"] = _page(serveur, "recherche", 99)
    serveur.reponses["recherche_apres_DEMO-2"] = _page(serveur, "recherche_apres_DEMO-2", 99)
    serveur.reponses["recherche_apres_DEMO-4"] = PAGE_VIDE
    rendus = tuple(source_fixtures_dc(serveur, taille_page=2).evenements())
    assert serveur.inattendues == []
    assert rendus == evenements_attendus()
    # `total` non concluant : arrêt sur la page vide.
    assert _recherches(serveur) == [
        (f"{JQL} ORDER BY key ASC", "0", "2"),
        (f'{JQL} AND key > "DEMO-2" ORDER BY key ASC', "0", "2"),
        (f'{JQL} AND key > "DEMO-4" ORDER BY key ASC', "0", "2"),
    ]


def test_page_sans_total_poursuit_jusqu_a_la_page_vide() -> None:
    serveur = ServeurFixturesDC()
    serveur.reponses["recherche_apres_DEMO-2"] = _page(serveur, "recherche_apres_DEMO-2", None)
    serveur.reponses["recherche_apres_DEMO-4"] = PAGE_VIDE
    assert tuple(source_fixtures_dc(serveur).evenements()) == evenements_attendus()
    assert serveur.inattendues == []
    assert len(_recherches(serveur)) == 3


def test_page_vide_d_emblee_aucun_ticket() -> None:
    serveur = ServeurFixturesDC({"recherche": PAGE_VIDE})
    assert tuple(source_fixtures_dc(serveur).evenements()) == ()
    assert len(_recherches(serveur)) == 1


def test_total_atteint_arrete_la_recherche() -> None:
    serveur = ServeurFixturesDC()
    serveur.reponses["recherche"] = _page(serveur, "recherche", 2)
    rendus = tuple(source_fixtures_dc(serveur).evenements())
    assert {e.cle_ticket for e in rendus} == {"DEMO-1", "DEMO-2"}
    assert len(_recherches(serveur)) == 1


def test_page_sans_progression_refusee() -> None:
    serveur = ServeurFixturesDC()
    serveur.reponses["recherche_apres_DEMO-2"] = _page(serveur, "recherche", 99)
    with pytest.raises(UsineErreur, match="sans progression"):
        list(source_fixtures_dc(serveur).evenements())


def test_taille_page_par_defaut_et_invalide() -> None:
    assert TAILLE_PAGE_RECHERCHE == 100
    with pytest.raises(UsineErreur, match="taille de page"):
        source_fixtures_dc(taille_page=0)


def test_depuis_restreint_la_recherche_et_filtre_cote_client() -> None:
    serveur = ServeurFixturesDC()
    depuis = datetime(2026, 9, 4, 8, 0, tzinfo=UTC)
    maintenant = depuis + timedelta(hours=2, seconds=1)
    rendus = list(source_fixtures_dc(serveur, horloge=lambda: maintenant).evenements(depuis))
    jql = [r.url.params["jql"] for r in serveur.requetes if r.url.path == CHEMIN_RECHERCHE]
    assert jql == [
        f'{JQL} AND updated >= "-121m" ORDER BY key ASC',
        f'{JQL} AND updated >= "-121m" AND key > "DEMO-2" ORDER BY key ASC',
    ]
    assert rendus == [e for e in evenements_attendus() if e.horodatage >= depuis]


def test_depuis_sans_fuseau_refuse_avant_toute_requete() -> None:
    serveur = ServeurFixturesDC()
    with pytest.raises(UsineErreur, match="sans fuseau"):
        list(source_fixtures_dc(serveur).evenements(datetime(2026, 9, 4)))  # noqa: DTZ001
    assert serveur.requetes == []


def test_changelog_complet_sans_complement() -> None:
    serveur = ServeurFixturesDC()
    page_2 = copy.deepcopy(serveur.reponses["recherche_apres_DEMO-2"])
    page_2["issues"][0]["changelog"] = copy.deepcopy(serveur.reponses["issue_DEMO-3"]["changelog"])
    serveur.reponses["recherche_apres_DEMO-2"] = page_2
    assert tuple(source_fixtures_dc(serveur).evenements()) == evenements_attendus()
    assert CHEMIN_DEMO_3 not in {r.url.path for r in serveur.requetes}


def test_changelog_encore_tronque_nomme_le_ticket() -> None:
    serveur = ServeurFixturesDC()
    issue = copy.deepcopy(serveur.reponses["issue_DEMO-3"])
    issue["changelog"]["total"] = 5
    serveur.reponses["issue_DEMO-3"] = issue
    with pytest.raises(UsineErreur, match="DEMO-3 : changelog encore tronqué"):
        list(source_fixtures_dc(serveur).evenements())


def test_champ_ambigu_nomme_le_nom() -> None:
    serveur = ServeurFixturesDC()
    champs = copy.deepcopy(serveur.reponses["champs"])
    for champ in champs:
        if champ["id"] == "customfield_10047":
            champ["name"] = "Gravité"
    serveur.reponses["champs"] = champs
    with pytest.raises(UsineErreur, match="« Gravité » ambigu") as erreur:
        list(source_fixtures_dc(serveur).evenements())
    assert "customfield_10046" in str(erreur.value)
    assert "customfield_10047" in str(erreur.value)


def test_homonyme_non_configure_rend_le_nom_ambigu() -> None:
    serveur = ServeurFixturesDC()
    serveur.reponses["champs"] = [
        *serveur.reponses["champs"],
        {"id": "customfield_19999", "name": "Gravité", "custom": True},
    ]
    with pytest.raises(UsineErreur, match="« Gravité » ambigu") as erreur:
        list(source_fixtures_dc(serveur).evenements())
    assert "customfield_19999" in str(erreur.value)


def _remplacer_item_assignee(serveur: ServeurFixturesDC, item: dict[str, Any]) -> None:
    page_1 = copy.deepcopy(serveur.reponses["recherche"])
    page_1["issues"][0]["changelog"]["histories"][0]["items"][1] = item
    serveur.reponses["recherche"] = page_1


@pytest.mark.parametrize("nom", ["Équipe", "Inconnu"])
def test_nom_sans_champ_configure_ignore_rang_conserve(nom: str) -> None:
    """« Équipe » : champ personnalisé non configuré ; « Inconnu » : absent de `/field`."""
    serveur = ServeurFixturesDC()
    _remplacer_item_assignee(
        serveur,
        {"field": nom, "fieldtype": "custom", "fromString": None, "toString": "Valeur fictive"},
    )
    rendus = tuple(source_fixtures_dc(serveur).evenements())
    assert rendus == evenements_attendus()
    # Gravité reste l'item 3 de l'historique 20001.
    assert "20001-3" in {e.id_evenement for e in rendus}


def test_item_personnalise_au_nom_d_un_champ_systeme_ignore() -> None:
    serveur = ServeurFixturesDC()
    _remplacer_item_assignee(
        serveur,
        {
            "field": "Statut",
            "fieldtype": "custom",
            "fromString": "Nouvelle",
            "toString": "Rejetée",
        },
    )
    rendus = tuple(source_fixtures_dc(serveur).evenements())
    assert rendus == evenements_attendus()
    assert "20001-2" not in {e.id_evenement for e in rendus}


def test_identifiant_present_prevaut_sur_le_nom() -> None:
    par_nom = {"Gravité": ["customfield_10046", "customfield_10047"]}
    historiques = [
        {
            "id": "1",
            "items": [
                {"field": "Gravité", "fieldtype": "custom", "fieldId": "customfield_10046"},
                {"field": "status", "fieldtype": "jira"},
            ],
        }
    ]
    assert resoudre_items(historiques, par_nom, "DEMO-1") == historiques


def test_identifiants_par_nom_ne_retient_que_les_champs_personnalises() -> None:
    champs = [
        {"id": "customfield_10046", "name": "Gravité"},
        {"id": "customfield_10046", "name": "Gravité"},
        {"id": "customfield_19999", "name": "Gravité"},
        {"id": "customfield_20001", "name": "Équipe"},
        {"id": "customfield_20002", "name": "Équipe"},
        {"id": "cf-externe", "name": "Externe", "custom": True},
        {"id": "status", "name": "Statut", "custom": False},
        {"id": "assignee", "name": "Responsable"},
    ]
    assert identifiants_par_nom(champs, config_jira("dc")) == {
        "Gravité": ["customfield_10046", "customfield_19999"],
        "Équipe": ["customfield_20001"],
        "Externe": ["cf-externe"],
    }
    with pytest.raises(UsineErreur, match="champ illisible"):
        identifiants_par_nom([{"id": "status"}], config_jira("dc"))


def test_reponse_field_non_tableau_refusee() -> None:
    serveur = ServeurFixturesDC({"champs": {"erreur": "inattendue"}})
    with pytest.raises(UsineErreur, match="tableau JSON attendu"):
        list(source_fixtures_dc(serveur).evenements())
