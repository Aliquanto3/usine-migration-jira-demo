"""`SourceJiraCloud` : requêtes émises, changelog tronqué, `depuis` et lecture seule (Story 2.2)."""

import copy
import json
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr

from tests.unit.adaptateurs.jira_cloud.outils import (
    CHEMIN_CHANGELOG_DEMO_3,
    CHEMIN_RECHERCHE,
    ServeurFixtures,
    evenements_attendus,
    source_fixtures,
)
from tests.unit.adaptateurs.jira_http.outils import Attentes, config_jira
from usine.adaptateurs.jira_cloud import (
    SourceJiraCloud,
    champs_demandes,
    changelog_tronque,
    requete_jql,
)
from usine.adaptateurs.jira_http import RequeteJiraInterdite, construire_client_lecture
from usine.contrats.erreurs import UsineErreur
from usine.ports import SourceTickets


def test_rend_exactement_le_flux_attendu() -> None:
    rendus = tuple(source_fixtures().evenements())
    assert rendus == evenements_attendus()


def test_implemente_le_port() -> None:
    assert isinstance(source_fixtures(), SourceTickets)


def test_requetes_emises() -> None:
    serveur = ServeurFixtures()
    list(source_fixtures(serveur).evenements())
    assert serveur.inattendues == []
    assert [(r.method, r.url.path) for r in serveur.requetes] == [
        ("POST", CHEMIN_RECHERCHE),
        ("POST", CHEMIN_RECHERCHE),
        ("GET", CHEMIN_CHANGELOG_DEMO_3),
        ("GET", CHEMIN_CHANGELOG_DEMO_3),
    ]
    premier = json.loads(serveur.requetes[0].content)
    assert premier == {
        "jql": 'project = "DEMO" AND issuetype in ("Anomalie", "Cas de test", "Certification")'
        " ORDER BY key ASC",
        "fields": [
            "status",
            "customfield_10001",
            "customfield_10002",
            "customfield_10003",
            "customfield_10004",
            "customfield_10005",
            "summary",
            "description",
            "customfield_10006",
            "customfield_10007",
            "issuetype",
            "created",
        ],
        "expand": "changelog",
        "maxResults": 100,
    }
    assert json.loads(serveur.requetes[1].content) == {**premier, "nextPageToken": "page-2"}
    assert [r.url.params.get("startAt") for r in serveur.requetes[2:]] == ["0", "2"]


def test_changelog_tronque_complete_sans_doublon() -> None:
    rendus = [e for e in source_fixtures().evenements() if e.cle_ticket == "DEMO-3"]
    ids = [e.id_evenement for e in rendus]
    assert len(ids) == len(set(ids))
    assert {"20005-1", "20006-1", "20007-1", "20007-2", "20008-1"} <= set(ids)
    initiale = next(e for e in rendus if e.id_evenement == "C-10003-gravite")
    assert initiale.vers == "majeure"


def test_changelog_complet_sans_complement() -> None:
    serveur = ServeurFixtures()
    page_2 = copy.deepcopy(serveur.reponses["recherche_2"])
    changelog = page_2["issues"][0]["changelog"]
    complement = serveur.reponses["changelog_2"]["values"]
    changelog["histories"] += complement
    changelog["maxResults"] = changelog["total"] = 4
    serveur.reponses["recherche_2"] = page_2
    rendus = tuple(source_fixtures(serveur).evenements())
    assert rendus == evenements_attendus()
    assert all(r.method == "POST" for r in serveur.requetes)


@pytest.mark.parametrize(
    ("changelog", "tronque"),
    [
        (None, True),
        ({"histories": []}, True),
        ({"histories": [{"id": "1"}], "total": 2}, True),
        ({"histories": [{"id": "1"}], "total": 1}, False),
        ({"histories": [], "total": 0}, False),
    ],
)
def test_detection_de_la_troncature(changelog: dict[str, object] | None, tronque: bool) -> None:
    ticket = {"key": "DEMO-1"} if changelog is None else {"key": "DEMO-1", "changelog": changelog}
    assert changelog_tronque(ticket) is tronque


def test_depuis_filtre_cote_client() -> None:
    depuis = datetime(2026, 9, 4, 8, 0, tzinfo=UTC)
    rendus = list(source_fixtures().evenements(depuis))
    attendus = [e for e in evenements_attendus() if e.horodatage >= depuis]
    assert rendus == attendus
    assert rendus[0].id_evenement == "20006-1"


def test_depuis_sans_fuseau_refuse_avant_toute_requete() -> None:
    serveur = ServeurFixtures()
    with pytest.raises(UsineErreur, match="sans fuseau"):
        list(source_fixtures(serveur).evenements(datetime(2026, 9, 4)))  # noqa: DTZ001
    assert serveur.requetes == []


def test_lecture_seule_un_client_hors_liste_blanche_n_envoie_rien() -> None:
    serveur = ServeurFixtures()
    client_dc = construire_client_lecture(
        config_jira("dc"),
        email=None,
        jeton_lecture=None,
        pat=SecretStr("pat"),
        attendre=Attentes(),
        transport_http=httpx.MockTransport(serveur),
    )
    with pytest.raises(RequeteJiraInterdite, match="search/jql"):
        list(SourceJiraCloud(client_dc, config_jira("cloud")).evenements())
    assert serveur.requetes == []


def test_seules_les_lectures_autorisees_sont_emises() -> None:
    serveur = ServeurFixtures()
    list(source_fixtures(serveur).evenements())
    assert {(r.method, r.url.path) for r in serveur.requetes} <= {
        ("POST", CHEMIN_RECHERCHE),
        ("GET", CHEMIN_CHANGELOG_DEMO_3),
    }


def test_jql_echappe_les_guillemets() -> None:
    config = config_jira("cloud")
    config = config.model_copy(
        update={"types_tickets": {'Bug "X"': config.types_tickets["Anomalie"]}}
    )
    assert requete_jql(config) == (
        'project = "DEMO" AND issuetype in ("Bug \\"X\\"") ORDER BY key ASC'
    )


def test_champs_demandes_sans_doublon() -> None:
    demandes = champs_demandes(config_jira("cloud"))
    assert len(demandes) == len(set(demandes))
    assert demandes[-2:] == ["issuetype", "created"]


def test_type_jira_inconnu_nomme_la_configuration() -> None:
    serveur = ServeurFixtures()
    page = copy.deepcopy(serveur.reponses["recherche_1"])
    page["issues"][1]["fields"]["issuetype"]["name"] = "Bug"
    serveur.reponses["recherche_1"] = page
    with pytest.raises(UsineErreur) as erreur:
        list(source_fixtures(serveur).evenements())
    message = str(erreur.value)
    assert "config/jira.yaml" in message
    assert "types_tickets" in message
    assert "'Bug'" in message
    assert "DEMO-2" in message
