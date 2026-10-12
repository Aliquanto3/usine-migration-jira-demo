"""`SourceJiraCloud` : port `SourceTickets` sur l'API REST v3 de Jira Cloud (AD-3, AD-5).

Lecture seule, par `ClientJiraLecture` (liste blanche) :

1. `POST /rest/api/3/search/jql` (`expand=changelog`), paginé par `nextPageToken` ;
2. pour chaque ticket dont le changelog en ligne est tronqué (`total` > historiques reçus, ou
   `changelog`/`total` absent) : `GET /rest/api/3/issue/{cle}/changelog`, paginé par position,
   fusionné avec le changelog en ligne et dédoublonné par id d'historique.

Avec `depuis`, la recherche est restreinte par `updated >= "-<n>m"` : une durée relative,
indépendante du fuseau du profil du compte Jira (inconnu), arrondie à la minute supérieure à
partir de l'instant `horloge()` (FR-6). Le filtre `horodatage >= depuis` reste appliqué côté
client aux événements des tickets retenus.

Jira évalue cette fenêtre relative sur sa propre horloge, et de nouveau à chaque page : elle ne
couvre `depuis` que si le décalage d'horloge client/serveur plus la durée de la pagination
restent inférieurs à la marge d'extraction (`marge_extraction_minutes`).
"""

from collections.abc import Callable, Iterator, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from usine.adaptateurs.jira_cloud.conversion import convertir_ticket, trier_evenements
from usine.adaptateurs.jira_http import ClientJiraLecture
from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import Evenement, SourceEvenement
from usine.contrats.tickets import Champ

CHEMIN_RECHERCHE = "/rest/api/3/search/jql"
"""Recherche JQL Cloud (l'ancienne `/rest/api/3/search` renvoie 410)."""
TAILLE_PAGE_RECHERCHE = 100
"""Tickets demandés par page de recherche ; le serveur peut plafonner."""


def chemin_changelog(cle: str) -> str:
    """Changelog paginé d'un ticket Cloud."""
    return f"/rest/api/3/issue/{cle}/changelog"


def _chaine_jql(valeur: str) -> str:
    echappee = valeur.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{echappee}"'


def minutes_depuis(depuis: datetime, maintenant: datetime) -> int:
    """Minutes écoulées de `depuis` à `maintenant`, arrondies au-dessus, au moins 1."""
    return max(1, -((depuis - maintenant) // timedelta(minutes=1)))


def requete_jql(config: ConfigJira, minutes: int | None = None, apres: str | None = None) -> str:
    """JQL des tickets du Programme : projet et types Jira de la table, par clé croissante.

    Avec `minutes`, seuls les tickets modifiés depuis `minutes` minutes (`updated >= "-<n>m"`).
    Avec `apres`, seuls les tickets de clé postérieure (`key > "<apres>"`) : tranche suivante
    d'une recherche Data Center bornée par sa fenêtre de résultats.
    """
    types = ", ".join(_chaine_jql(nom) for nom in config.types_tickets)
    filtre = f"project = {_chaine_jql(config.cle_projet)} AND issuetype in ({types})"
    if minutes is not None:
        if minutes < 1:
            raise UsineErreur(f"Jira : restriction « updated » d'au moins 1 minute, pas {minutes}")
        filtre += f' AND updated >= "-{minutes}m"'
    if apres is not None:
        if not apres.strip():
            raise UsineErreur("Jira : restriction « key > » sur une clé vide")
        filtre += f" AND key > {_chaine_jql(apres)}"
    return f"{filtre} ORDER BY key ASC"


def _maintenant() -> datetime:
    return datetime.now(UTC)


def champs_demandes(config: ConfigJira) -> list[str]:
    """Champs Jira demandés : identifiants de la table (ordre de `Champ`), type, création."""
    demandes = [config.champs[champ] for champ in Champ]
    return list(dict.fromkeys([*demandes, "issuetype", "created"]))


def changelog_tronque(ticket: Mapping[str, Any]) -> bool:
    """Vrai si le changelog en ligne manque ou compte moins d'historiques que son `total`."""
    changelog = ticket.get("changelog")
    if not isinstance(changelog, Mapping):
        return True
    historiques = changelog.get("histories")
    total = changelog.get("total")
    if not isinstance(historiques, list) or not isinstance(total, int) or isinstance(total, bool):
        return True
    return total > len(historiques)


class SourceJiraCloud:
    """Rend les `Evenement` canoniques des tickets du projet `config.cle_projet`."""

    source = SourceEvenement.jira_cloud

    def __init__(
        self,
        client: ClientJiraLecture,
        config: ConfigJira,
        horloge: Callable[[], datetime] = _maintenant,
    ) -> None:
        self._client = client
        self._config = config
        self._horloge = horloge

    def evenements(self, depuis: datetime | None = None) -> Iterator[Evenement]:
        """Événements d'horodatage ≥ `depuis` (tous si `None`), par horodatage croissant.

        Avec `depuis`, seuls les tickets modifiés depuis cet instant sont recherchés.
        """
        if depuis is not None and (depuis.tzinfo is None or depuis.utcoffset() is None):
            raise UsineErreur(f"Jira Cloud : « depuis » sans fuseau : {depuis!r}")
        minutes = None if depuis is None else minutes_depuis(depuis, self._horloge())
        par_ticket = [
            convertir_ticket(ticket, self._historiques(ticket), self._config, self.source)
            for ticket in self._tickets(minutes)
        ]
        for evenement in trier_evenements(par_ticket):
            if depuis is None or evenement.horodatage >= depuis:
                yield evenement

    def _tickets(self, minutes: int | None) -> Iterator[Mapping[str, Any]]:
        corps = {
            "jql": requete_jql(self._config, minutes),
            "fields": champs_demandes(self._config),
            "expand": "changelog",
            "maxResults": TAILLE_PAGE_RECHERCHE,
        }
        for ticket in self._client.paginer_par_jeton(
            "POST", CHEMIN_RECHERCHE, "issues", corps=corps
        ):
            if not isinstance(ticket, Mapping):
                raise UsineErreur(f"Jira POST {CHEMIN_RECHERCHE} : ticket illisible ({ticket!r})")
            yield ticket

    def _historiques(self, ticket: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        changelog = ticket.get("changelog")
        en_ligne = changelog.get("histories") if isinstance(changelog, Mapping) else None
        historiques: list[Mapping[str, Any]] = list(en_ligne) if isinstance(en_ligne, list) else []
        if changelog_tronque(ticket):
            cle = ticket.get("key")
            if not isinstance(cle, str) or not cle:
                raise UsineErreur(f"Jira : ticket sans clé ({ticket.get('id')!r})")
            historiques += self._client.paginer_par_position(chemin_changelog(cle), "values")
        # Doublons entre changelog en ligne et complément : `convertir_ticket` les écarte.
        return historiques
