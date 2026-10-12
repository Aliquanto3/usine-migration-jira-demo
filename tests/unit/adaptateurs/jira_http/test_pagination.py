"""Pagination Jira par jeton (Cloud) et par position (DC), sur fixtures (Story 2.1, AD-5)."""

import base64
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from tests.unit.adaptateurs.jira_http.outils import (
    Attentes,
    ServeurSimule,
    config_jira,
    corps_json,
    fixture,
)
from usine.adaptateurs.jira_http import (
    ClientJiraLecture,
    construire_client_lecture,
    paginer_par_jeton,
    paginer_par_position,
)
from usine.contrats.erreurs import UsineErreur


def _client(
    serveur: ServeurSimule, mode: str, attentes: Attentes | None = None
) -> ClientJiraLecture:
    return construire_client_lecture(
        config_jira(mode),
        email="pilote@example.invalid",
        jeton_lecture=SecretStr("jeton-lecture"),
        pat=SecretStr("pat-dc"),
        attendre=attentes if attentes is not None else Attentes(),
        transport_http=serveur.transport,
    )


def _cles(elements: list[Any]) -> list[str]:
    return [element["key"] for element in elements]


def test_cloud_search_jql_post_avec_429() -> None:
    serveur = ServeurSimule(
        httpx.Response(200, json=fixture("jira_cloud/recherche_page_1.json")),
        httpx.Response(429, headers={"Retry-After": "7"}),
        httpx.Response(200, json=fixture("jira_cloud/recherche_page_2.json")),
    )
    attentes = Attentes()
    with _client(serveur, "cloud", attentes) as client:
        elements = list(
            client.paginer_par_jeton(
                "POST",
                "/rest/api/3/search/jql",
                "issues",
                corps={"jql": "project = DEMO", "maxResults": 2},
            )
        )
    assert _cles(elements) == ["DEMO-1", "DEMO-2", "DEMO-3"]
    assert attentes.durees == [7.0]
    premiere, _, deuxieme = serveur.requetes
    assert corps_json(premiere) == {"jql": "project = DEMO", "maxResults": 2}
    assert corps_json(deuxieme) == {
        "jql": "project = DEMO",
        "maxResults": 2,
        "nextPageToken": "page-2",
    }
    attendu = base64.b64encode(b"pilote@example.invalid:jeton-lecture").decode()
    assert {r.headers["Authorization"] for r in serveur.requetes} == {f"Basic {attendu}"}


def test_cloud_search_jql_get_jeton_en_parametre() -> None:
    serveur = ServeurSimule(
        httpx.Response(200, json=fixture("jira_cloud/recherche_page_1.json")),
        httpx.Response(200, json=fixture("jira_cloud/recherche_page_2.json")),
    )
    with _client(serveur, "cloud") as client:
        elements = list(
            client.paginer_par_jeton(
                "GET", "/rest/api/3/search/jql", "issues", params={"jql": "project = DEMO"}
            )
        )
    assert _cles(elements) == ["DEMO-1", "DEMO-2", "DEMO-3"]
    assert "nextPageToken" not in serveur.requetes[0].url.params
    assert serveur.requetes[1].url.params["nextPageToken"] == "page-2"
    assert serveur.requetes[1].url.params["jql"] == "project = DEMO"


def test_cloud_changelog_bulkfetch() -> None:
    serveur = ServeurSimule(
        httpx.Response(200, json=fixture("jira_cloud/bulkfetch_page_1.json")),
        httpx.Response(200, json=fixture("jira_cloud/bulkfetch_page_2.json")),
    )
    with _client(serveur, "cloud") as client:
        elements = list(
            client.paginer_par_jeton(
                "POST",
                "/rest/api/3/changelog/bulkfetch",
                "issueChangeLogs",
                corps={"issueIdsOrKeys": ["DEMO-1", "DEMO-2"]},
            )
        )
    assert [e["issueId"] for e in elements] == ["10001", "10002"]
    assert corps_json(serveur.requetes[1])["nextPageToken"] == "page-2"


def test_jeton_repete_leve() -> None:
    page = {"issues": [{"key": "DEMO-1"}], "nextPageToken": "boucle"}
    serveur = ServeurSimule(httpx.Response(200, json=page), httpx.Response(200, json=page))
    with (
        _client(serveur, "cloud") as client,
        pytest.raises(UsineErreur, match="boucle de pagination"),
    ):
        list(client.paginer_par_jeton("POST", "/rest/api/3/search/jql", "issues"))
    assert len(serveur.requetes) == 2


def test_page_sans_liste_leve() -> None:
    serveur = ServeurSimule(httpx.Response(200, json={"autre": []}))
    with _client(serveur, "cloud") as client, pytest.raises(UsineErreur, match="'issues'"):
        list(client.paginer_par_jeton("POST", "/rest/api/3/search/jql", "issues"))


def test_dc_search_par_position_avec_plafond_serveur() -> None:
    serveur = ServeurSimule(
        httpx.Response(200, json=fixture("jira_dc/recherche_page_1.json")),
        httpx.Response(200, json=fixture("jira_dc/recherche_page_2.json")),
    )
    with _client(serveur, "dc") as client:
        elements = list(
            client.paginer_par_position(
                "/rest/api/2/search", "issues", params={"jql": "project = DEMO"}, taille_page=50
            )
        )
    assert _cles(elements) == ["DEMO-1", "DEMO-2", "DEMO-3"]
    assert len(serveur.requetes) == 2
    premiere, deuxieme = (r.url.params for r in serveur.requetes)
    assert (premiere["startAt"], premiere["maxResults"]) == ("0", "50")
    assert (deuxieme["startAt"], deuxieme["maxResults"]) == ("2", "50")
    assert deuxieme["jql"] == "project = DEMO"
    assert {r.headers["Authorization"] for r in serveur.requetes} == {"Bearer pat-dc"}


def test_dc_page_vide_avant_total_arrete() -> None:
    serveur = ServeurSimule(
        httpx.Response(200, json=fixture("jira_dc/recherche_page_1.json")),
        httpx.Response(200, json={"startAt": 2, "maxResults": 2, "total": 3, "issues": []}),
    )
    with _client(serveur, "dc") as client:
        elements = list(client.paginer_par_position("/rest/api/2/search", "issues"))
    assert _cles(elements) == ["DEMO-1", "DEMO-2"]
    assert len(serveur.requetes) == 2


def test_position_is_last_arrete() -> None:
    pages = [
        {"values": [1, 2], "isLast": False},
        {"values": [3], "isLast": True},
    ]
    appels: list[dict[str, Any]] = []

    def requete(
        methode: str,
        chemin: str,
        *,
        params: Any = None,
        corps: Any = None,
    ) -> dict[str, Any]:
        appels.append(dict(params))
        return pages[len(appels) - 1]

    assert list(paginer_par_position(requete, "/rest/x", "values", taille_page=2)) == [1, 2, 3]
    assert [a["startAt"] for a in appels] == [0, 2]


def test_jeton_dernier_page_marquee_is_last() -> None:
    pages = [{"issues": [1], "nextPageToken": "a", "isLast": True}]

    def requete(
        methode: str,
        chemin: str,
        *,
        params: Any = None,
        corps: Any = None,
    ) -> dict[str, Any]:
        return pages.pop(0)

    assert list(paginer_par_jeton(requete, "POST", "/rest/x", "issues")) == [1]


def test_pagination_paresseuse() -> None:
    serveur = ServeurSimule(
        httpx.Response(200, json=fixture("jira_cloud/recherche_page_1.json")),
    )
    with _client(serveur, "cloud") as client:
        iterateur = client.paginer_par_jeton("POST", "/rest/api/3/search/jql", "issues")
        assert serveur.requetes == []
        assert next(iterateur)["key"] == "DEMO-1"
        assert len(serveur.requetes) == 1
