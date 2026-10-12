"""Contrat de la liste blanche du client de lecture, par plateforme (Story 2.1, AD-5).

L'extraction ne peut émettre aucune écriture vers Jira : toute requête hors liste blanche est
refusée **avant** envoi, et le transport HTTP ne reçoit rien.
"""

import httpx
import pytest
from pydantic import SecretStr

from tests.unit.adaptateurs.jira_http.outils import Attentes, ServeurSimule, config_jira
from usine.adaptateurs.jira_http import (
    LISTE_BLANCHE_LECTURE,
    ClientJiraLecture,
    Plateforme,
    RequeteJiraInterdite,
    construire_client_lecture,
    requete_autorisee,
)
from usine.contrats.erreurs import UsineErreur

PLATEFORMES: tuple[Plateforme, ...] = ("cloud", "dc")

INTERDITES: dict[Plateforme, list[tuple[str, str]]] = {
    "cloud": [
        ("POST", "/rest/api/3/issue"),
        ("POST", "/rest/api/3/issue/bulk"),
        ("PUT", "/rest/api/3/issue/DEMO-1"),
        ("DELETE", "/rest/api/3/issue/DEMO-1"),
        ("PATCH", "/rest/api/3/issue/DEMO-1"),
        ("POST", "/rest/api/3/issue/DEMO-1/transitions"),
        ("POST", "/rest/api/3/issue/DEMO-1/comment"),
        ("POST", "/rest/api/3/issue/DEMO-1/changelog"),
        ("POST", "/rest/api/3/issue/DEMO-1"),
        ("POST", "/rest/api/2/issue"),
        ("GET", "/rest/api/2/search"),
        ("POST", "/rest/api/2/search"),
        ("GET", "/rest/api/2/issue/DEMO-1"),
        ("DELETE", "/rest/api/3/search/jql"),
        ("PUT", "/rest/api/3/field"),
    ],
    "dc": [
        ("POST", "/rest/api/2/issue"),
        ("PUT", "/rest/api/2/issue/DEMO-1"),
        ("DELETE", "/rest/api/2/issue/DEMO-1"),
        ("POST", "/rest/api/2/issue/DEMO-1/transitions"),
        ("POST", "/rest/api/2/issue/DEMO-1/comment"),
        ("POST", "/rest/api/3/issue"),
        ("POST", "/rest/api/3/search/jql"),
        ("POST", "/rest/api/3/changelog/bulkfetch"),
        ("GET", "/rest/api/3/issue/DEMO-1"),
        ("PUT", "/rest/api/2/search"),
    ],
}

PIEGES: dict[Plateforme, list[str]] = {
    "cloud": [
        "/rest/api/3/issue/../issue",
        "/rest/api/3/issue/DEMO-1/../../issue",
        "/rest/api/3/issue/./changelog",
        "/rest/api/3/issue/..",
        "/rest/api/3/search/jql?x=1",
        "/rest/api/3/search/jql#f",
        "/rest/api/3//search/jql",
        "/rest/api/3/issue/DEMO%2D1",
        "/rest/api/3/issue/DEMO-1/",
        "https://autre.example.invalid/rest/api/3/myself",
        "//autre.example.invalid/rest/api/3/myself",
        "rest/api/3/myself",
        "/api/3/myself",
        "/rest/api/3/issue/DEMO 1",
        "/rest/api/3/issue/DEMO\\1",
        "",
    ],
    "dc": [
        "/rest/api/2/issue/../issue",
        "/rest/api/2/search?jql=x",
        "https://autre.example.invalid/rest/api/2/myself",
        "/rest/api/2//search",
        "/rest/api/2/issue/%2e%2e",
    ],
}

AUTORISEES: dict[Plateforme, list[tuple[str, str]]] = {
    "cloud": [
        ("POST", "/rest/api/3/search/jql"),
        ("get", "/rest/api/3/search/jql"),
        ("POST", "/rest/api/3/changelog/bulkfetch"),
        ("POST", "/rest/api/3/search/approximate-count"),
        ("GET", "/rest/api/3/issue/DEMO-12"),
        ("GET", "/rest/api/3/issue/10001/changelog"),
        ("GET", "/rest/api/3/field"),
        ("GET", "/rest/api/3/serverInfo"),
        ("GET", "/rest/api/3/myself"),
    ],
    "dc": [
        ("GET", "/rest/api/2/search"),
        ("POST", "/rest/api/2/search"),
        ("GET", "/rest/api/2/issue/DEMO-12"),
        ("GET", "/rest/api/2/field"),
        ("GET", "/rest/api/2/serverInfo"),
        ("GET", "/rest/api/2/myself"),
    ],
}

POST_DE_LECTURE = {
    "/rest/api/3/search/jql",
    "/rest/api/3/search/approximate-count",
    "/rest/api/3/changelog/bulkfetch",
    "/rest/api/2/search",
}


def _client(serveur: ServeurSimule, plateforme: Plateforme) -> ClientJiraLecture:
    return construire_client_lecture(
        config_jira(plateforme),
        email="pilote@example.invalid",
        jeton_lecture=SecretStr("jeton-lecture"),
        pat=SecretStr("pat-dc"),
        attendre=Attentes(),
        transport_http=serveur.transport,
    )


def _cas_interdits() -> list[tuple[Plateforme, str, str]]:
    return [
        *((p, m, c) for p in PLATEFORMES for m, c in INTERDITES[p]),
        *((p, m, c) for p in PLATEFORMES for c in PIEGES[p] for m in ("GET", "POST")),
    ]


@pytest.mark.parametrize(("plateforme", "methode", "chemin"), _cas_interdits())
def test_requete_interdite_jamais_envoyee(
    plateforme: Plateforme, methode: str, chemin: str
) -> None:
    serveur = ServeurSimule()
    with _client(serveur, plateforme) as client:
        with pytest.raises(RequeteJiraInterdite) as exc:
            client.requete(methode, chemin, corps={"fields": {}})
        with pytest.raises(RequeteJiraInterdite):
            client.requete_liste(methode, chemin)
        with pytest.raises(RequeteJiraInterdite):
            client.paginer_par_jeton(methode, chemin, "issues")
        if methode == "GET":
            with pytest.raises(RequeteJiraInterdite):
                client.paginer_par_position(chemin, "issues")
    assert serveur.requetes == []
    assert isinstance(exc.value, UsineErreur)
    assert f"{methode.upper()} {chemin}" in str(exc.value)
    assert "jeton-lecture" not in str(exc.value)


@pytest.mark.parametrize(
    ("plateforme", "methode", "chemin"),
    [(p, m, c) for p in PLATEFORMES for m, c in AUTORISEES[p]],
)
def test_requete_autorisee_envoyee(plateforme: Plateforme, methode: str, chemin: str) -> None:
    serveur = ServeurSimule(httpx.Response(200, json={"ok": True}))
    with _client(serveur, plateforme) as client:
        assert client.requete(methode, chemin) == {"ok": True}
    (requete,) = serveur.requetes
    assert (requete.method, requete.url.path) == (methode.upper(), chemin)


@pytest.mark.parametrize("plateforme", PLATEFORMES)
def test_liste_blanche_sans_ecriture(plateforme: Plateforme) -> None:
    """Seuls GET et les POST de lecture connus figurent dans la liste blanche."""
    for methode, gabarit in LISTE_BLANCHE_LECTURE[plateforme]:
        assert methode in {"GET", "POST"}, (methode, gabarit)
        if methode == "POST":
            assert gabarit in POST_DE_LECTURE, gabarit
        version = "3" if plateforme == "cloud" else "2"
        assert gabarit.startswith(f"/rest/api/{version}/"), gabarit


def test_listes_blanches_par_plateforme() -> None:
    assert set(LISTE_BLANCHE_LECTURE) == set(PLATEFORMES)
    assert requete_autorisee("cloud", "POST", "/rest/api/3/search/jql")
    assert not requete_autorisee("dc", "POST", "/rest/api/3/search/jql")
    assert requete_autorisee("dc", "POST", "/rest/api/2/search")
    assert not requete_autorisee("cloud", "POST", "/rest/api/2/search")
