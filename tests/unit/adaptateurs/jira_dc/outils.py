"""Outils des tests de l'adaptateur Data Center : serveur simulé des fixtures et flux attendu.

Les fixtures `tests/fixtures/jira_dc/source_*` transposent en API v2 les fixtures Cloud
`tests/fixtures/jira_cloud/source_*` : mêmes quatre tickets fictifs du projet `DEMO`, en deux
pages de recherche (la seconde répond à `key > "DEMO-2"` ; la première, courte, annonce un
`total` de 4), description en texte, items de changelog sans
`fieldId` (champs personnalisés nommés par leur nom d'affichage, résolu par `/field`), et
changelog en ligne de DEMO-3 tronqué, complet dans `source_issue_DEMO-3.json`.
"""

import json
import re
from typing import Any

import httpx
from pydantic import SecretStr

from tests.unit.adaptateurs.jira_cloud.outils import (
    evenements_attendus as evenements_attendus_cloud,
)
from tests.unit.adaptateurs.jira_http.outils import (
    FIXTURES,
    Attentes,
    config_jira,
    fixture,
)
from usine.adaptateurs.jira_dc import SourceJiraDC
from usine.adaptateurs.jira_http import ClientJiraLecture, construire_client_lecture
from usine.contrats.config import ConfigJira
from usine.contrats.evenements import Evenement, SourceEvenement

CHEMIN_RECHERCHE = "/rest/api/2/search"
CHEMIN_CHAMPS = "/rest/api/2/field"
CHEMIN_DEMO_3 = "/rest/api/2/issue/DEMO-3"
PAT = "pat-dc-fictif"

_APRES = re.compile(r' AND key > "([^"]+)"')


class ServeurFixturesDC:
    """Répond aux requêtes de l'adaptateur DC par les fixtures `source_*` et les enregistre.

    Routes : `champs`, `recherche` (première page), `recherche_apres_<clé>` (page suivante,
    `key > "<clé>"`, toujours `startAt=0`) et `issue_<clé>`. Toute autre requête fait échouer
    le test (réponse 599 et `inattendues`).
    """

    def __init__(self, reponses: dict[str, Any] | None = None) -> None:
        self.reponses: dict[str, Any] = {
            "champs": fixture_liste("jira_dc/source_champs.json"),
            "recherche": fixture("jira_dc/source_recherche_page_1.json"),
            "recherche_apres_DEMO-2": fixture("jira_dc/source_recherche_page_2.json"),
            "issue_DEMO-3": fixture("jira_dc/source_issue_DEMO-3.json"),
            **(reponses or {}),
        }
        self.requetes: list[httpx.Request] = []
        self.inattendues: list[str] = []

    def _route(self, requete: httpx.Request) -> str | None:
        if requete.method != "GET":
            return None
        chemin = requete.url.path
        if chemin == CHEMIN_CHAMPS:
            return "champs"
        if chemin == CHEMIN_RECHERCHE:
            if requete.url.params.get("startAt") != "0":
                return None  # pagination par curseur de clé : toujours depuis le début
            apres = _APRES.search(requete.url.params.get("jql", ""))
            return "recherche" if apres is None else f"recherche_apres_{apres[1]}"
        if chemin.startswith("/rest/api/2/issue/"):
            return f"issue_{chemin.rsplit('/', 1)[1]}"
        return None

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        self.requetes.append(requete)
        route = self._route(requete)
        if route is None or route not in self.reponses:
            self.inattendues.append(f"{requete.method} {requete.url}")
            return httpx.Response(599)
        return httpx.Response(200, json=self.reponses[route])

    def client(self, config: ConfigJira | None = None) -> ClientJiraLecture:
        """Client de lecture DC (PAT) branché sur ce serveur."""
        return construire_client_lecture(
            config or config_jira("dc"),
            email=None,
            jeton_lecture=None,
            pat=SecretStr(PAT),
            attendre=Attentes(),
            transport_http=httpx.MockTransport(self),
        )


def fixture_liste(nom: str) -> list[Any]:
    """Réponse enregistrée `tests/fixtures/<nom>` qui est un tableau JSON."""
    donnees = json.loads((FIXTURES / nom).read_text(encoding="utf-8"))
    assert isinstance(donnees, list)
    return donnees


def source_fixtures_dc(
    serveur: ServeurFixturesDC | None = None, config: ConfigJira | None = None, **options: Any
) -> SourceJiraDC:
    """`SourceJiraDC` sur les fixtures, avec `config/jira.yaml` en mode `dc`."""
    config = config or config_jira("dc")
    return SourceJiraDC((serveur or ServeurFixturesDC()).client(config), config, **options)


def evenements_attendus() -> tuple[Evenement, ...]:
    """Flux attendu des fixtures DC : celui de Cloud, à `source = jira_dc` près."""
    return tuple(
        e.model_copy(update={"source": SourceEvenement.jira_dc})
        for e in evenements_attendus_cloud()
    )
