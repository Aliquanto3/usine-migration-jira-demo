"""Outils des tests de l'adaptateur Cloud : serveur simulé des fixtures et flux attendu.

Les fixtures `tests/fixtures/jira_cloud/source_*` décrivent quatre tickets fictifs du projet
`DEMO` : une Anomalie à transitions et champs personnalisés (DEMO-1), un Cas de test dont
l'item `status` est ignoré (DEMO-2), une Anomalie au changelog en ligne tronqué, complété sur
deux pages (DEMO-3), et une Certification avec un item hors type (DEMO-4).
"""

import json
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import SecretStr

from tests.unit.adaptateurs.jira_http.outils import Attentes, config_jira, fixture
from usine.adaptateurs.jira_cloud import SourceJiraCloud
from usine.adaptateurs.jira_http import ClientJiraLecture, construire_client_lecture
from usine.contrats.config import ConfigJira
from usine.contrats.evenements import Evenement, NatureEvenement, SourceEvenement
from usine.contrats.tickets import Champ, TypeTicket

CHEMIN_RECHERCHE = "/rest/api/3/search/jql"
CHEMIN_CHANGELOG_DEMO_3 = "/rest/api/3/issue/DEMO-3/changelog"


class ServeurFixtures:
    """Répond aux requêtes de l'adaptateur par les fixtures `source_*` et les enregistre.

    Toute autre requête fait échouer le test (réponse 599 et `inattendues`).
    """

    def __init__(self, reponses: dict[str, dict[str, Any]] | None = None) -> None:
        self.reponses = {
            "recherche_1": fixture("jira_cloud/source_recherche_page_1.json"),
            "recherche_2": fixture("jira_cloud/source_recherche_page_2.json"),
            "changelog_0": fixture("jira_cloud/source_changelog_DEMO-3_page_1.json"),
            "changelog_2": fixture("jira_cloud/source_changelog_DEMO-3_page_2.json"),
            **(reponses or {}),
        }
        self.requetes: list[httpx.Request] = []
        self.inattendues: list[str] = []

    def _route(self, requete: httpx.Request) -> str | None:
        chemin = requete.url.path
        if requete.method == "POST" and chemin == CHEMIN_RECHERCHE:
            jeton = json.loads(requete.content).get("nextPageToken")
            return {None: "recherche_1", "page-2": "recherche_2"}.get(jeton)
        if requete.method == "GET" and chemin == CHEMIN_CHANGELOG_DEMO_3:
            return f"changelog_{requete.url.params.get('startAt')}"
        return None

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        self.requetes.append(requete)
        route = self._route(requete)
        if route is None or route not in self.reponses:
            self.inattendues.append(f"{requete.method} {requete.url}")
            return httpx.Response(599)
        return httpx.Response(200, json=self.reponses[route])

    def client(self, config: ConfigJira | None = None) -> ClientJiraLecture:
        """Client de lecture Cloud branché sur ce serveur."""
        return construire_client_lecture(
            config or config_jira("cloud"),
            email="lecteur@example.invalid",
            jeton_lecture=SecretStr("jeton-lecture"),
            pat=None,
            attendre=Attentes(),
            transport_http=httpx.MockTransport(self),
        )


def source_fixtures(
    serveur: ServeurFixtures | None = None, config: ConfigJira | None = None
) -> SourceJiraCloud:
    """`SourceJiraCloud` sur les fixtures, avec `config/jira.yaml`."""
    config = config or config_jira("cloud")
    return SourceJiraCloud((serveur or ServeurFixtures()).client(config), config)


def _instant(texte: str) -> datetime:
    return datetime.fromisoformat(texte).replace(tzinfo=UTC)


def _creation(id_ticket: str, cle: str, type_ticket: TypeTicket, instant: str) -> Evenement:
    return Evenement(
        id_evenement=f"C-{id_ticket}",
        cle_ticket=cle,
        type_ticket=type_ticket,
        horodatage=_instant(instant),
        nature=NatureEvenement.creation,
        source=SourceEvenement.jira_cloud,
    )


def _initial(
    id_ticket: str, cle: str, type_ticket: TypeTicket, instant: str, champ: Champ, vers: str
) -> Evenement:
    return Evenement(
        id_evenement=f"C-{id_ticket}-{champ.value}",
        cle_ticket=cle,
        type_ticket=type_ticket,
        horodatage=_instant(instant),
        nature=NatureEvenement.modification_champ,
        champ=champ,
        vers=vers,
        source=SourceEvenement.jira_cloud,
    )


def _item(
    id_evenement: str,
    cle: str,
    type_ticket: TypeTicket,
    instant: str,
    champ: Champ,
    de: str | None,
    vers: str | None,
) -> Evenement:
    nature = (
        NatureEvenement.transition if champ is Champ.statut else NatureEvenement.modification_champ
    )
    return Evenement(
        id_evenement=id_evenement,
        cle_ticket=cle,
        type_ticket=type_ticket,
        horodatage=_instant(instant),
        nature=nature,
        champ=champ,
        de=de,
        vers=vers,
        source=SourceEvenement.jira_cloud,
    )


def evenements_attendus() -> tuple[Evenement, ...]:
    """Flux attendu des fixtures, écrit à la main, dans l'ordre de rendu."""
    a, t, c = TypeTicket.anomalie, TypeTicket.cas_de_test, TypeTicket.certification
    d1, d2, d3, d4 = "2026-09-01T09:00", "2026-09-01T11:00", "2026-09-02T09:00", "2026-09-10T09:00"
    return (
        _creation("10001", "DEMO-1", a, d1),
        _initial("10001", "DEMO-1", a, d1, Champ.statut, "nouvelle"),
        _initial("10001", "DEMO-1", a, d1, Champ.entite, "ENT-A"),
        _initial("10001", "DEMO-1", a, d1, Champ.vague, "V1"),
        _initial("10001", "DEMO-1", a, d1, Champ.domaine, "Comptabilité"),
        _initial("10001", "DEMO-1", a, d1, Champ.gravite, "bloquante"),
        _initial("10001", "DEMO-1", a, d1, Champ.phase, "recette"),
        _initial("10001", "DEMO-1", a, d1, Champ.titre, "Écart de solde"),
        _initial(
            "10001",
            "DEMO-1",
            a,
            d1,
            Champ.description,
            "Le solde du compte diffère.\nÉcart constaté en recette.",
        ),
        _creation("10002", "DEMO-2", t, d2),
        _initial("10002", "DEMO-2", t, d2, Champ.entite, "ENT-A"),
        _initial("10002", "DEMO-2", t, d2, Champ.vague, "V1"),
        _initial("10002", "DEMO-2", t, d2, Champ.domaine, "Comptabilité"),
        _initial("10002", "DEMO-2", t, d2, Champ.phase, "recette"),
        _initial("10002", "DEMO-2", t, d2, Champ.titre, "Contrôle des soldes repris"),
        _initial("10002", "DEMO-2", t, d2, Champ.statut_test, "non_execute"),
        _item("20001-1", "DEMO-1", a, "2026-09-02T08:00", Champ.statut, "nouvelle", "en_analyse"),
        _item("20001-3", "DEMO-1", a, "2026-09-02T08:00", Champ.gravite, "bloquante", "majeure"),
        _creation("10003", "DEMO-3", a, d3),
        _initial("10003", "DEMO-3", a, d3, Champ.statut, "nouvelle"),
        _initial("10003", "DEMO-3", a, d3, Champ.entite, "ENT-B"),
        _initial("10003", "DEMO-3", a, d3, Champ.vague, "V2"),
        _initial("10003", "DEMO-3", a, d3, Champ.domaine, "Paie"),
        _initial("10003", "DEMO-3", a, d3, Champ.gravite, "majeure"),
        _initial("10003", "DEMO-3", a, d3, Champ.phase, "migration_a_blanc"),
        _initial("10003", "DEMO-3", a, d3, Champ.titre, "Rubrique de paie absente"),
        _initial(
            "10003",
            "DEMO-3",
            a,
            d3,
            Champ.description,
            "La rubrique 1200 est absente après migration.",
        ),
        _item("20005-1", "DEMO-3", a, "2026-09-03T08:00", Champ.statut, "nouvelle", "en_analyse"),
        _item(
            "20002-1", "DEMO-1", a, "2026-09-03T14:30", Champ.statut, "en_analyse", "en_correction"
        ),
        _item(
            "20006-1", "DEMO-3", a, "2026-09-04T08:00", Champ.statut, "en_analyse", "en_correction"
        ),
        _item(
            "20003-1",
            "DEMO-1",
            a,
            "2026-09-04T09:15",
            Champ.titre,
            "Écart de solde",
            "Écart de solde après reprise",
        ),
        _item("20004-2", "DEMO-2", t, "2026-09-05T16:00", Champ.statut_test, "non_execute", "ko"),
        _item(
            "20007-1", "DEMO-3", a, "2026-09-08T08:00", Champ.statut, "en_correction", "a_retester"
        ),
        _item("20007-2", "DEMO-3", a, "2026-09-08T08:00", Champ.gravite, "majeure", "mineure"),
        _item("20008-1", "DEMO-3", a, "2026-09-09T08:00", Champ.statut, "a_retester", "fermee"),
        _creation("10004", "DEMO-4", c, d4),
        _initial("10004", "DEMO-4", c, d4, Champ.entite, "ENT-A"),
        _initial("10004", "DEMO-4", c, d4, Champ.vague, "V1"),
        _initial("10004", "DEMO-4", c, d4, Champ.titre, "Certification ENT-A, vague V1"),
        _initial("10004", "DEMO-4", c, d4, Champ.statut_certification, "reservee"),
        _item(
            "20009-2",
            "DEMO-4",
            c,
            "2026-09-11T10:00",
            Champ.statut_certification,
            "reservee",
            "accordee",
        ),
    )
