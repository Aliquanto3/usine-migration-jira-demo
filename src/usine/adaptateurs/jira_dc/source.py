"""`SourceJiraDC` : port `SourceTickets` sur l'API REST v2 de Jira Data Center (AD-5, AD-23).

Lecture seule, par `ClientJiraLecture` (liste blanche DC) :

1. `GET /rest/api/2/field` : noms d'affichage des champs personnalisés. Le changelog DC ne
   porte pas toujours de `fieldId` ; un item `custom` sans `fieldId` est alors résolu par son
   nom d'affichage (`field`) parmi les champs personnalisés du site. Un nom porté par plusieurs
   champs personnalisés dont au moins un est configuré (`config/jira.yaml`) lève une
   `UsineErreur` ; un nom inconnu, ou celui d'un seul champ non configuré, est ignoré, son rang
   dans l'historique conservé (les identifiants d'événements restent ceux de Cloud) ;
2. `GET /rest/api/2/search` (`expand=changelog`), paginé par curseur de clé : chaque page est
   une recherche `startAt=0`, la suivante reprend par `key > "<dernière clé reçue>"`. Triée par
   clé (projet puis numéro : `DEMO-9` avant `DEMO-10`), la recherche ne saute ni ne répète
   aucun ticket même si l'ensemble des résultats change entre deux pages (fenêtre `updated`
   relative réévaluée, ticket créé ou sorti de la fenêtre) ; seule la suppression du ticket
   servant de curseur fait refuser la JQL par Jira (erreur HTTP, donc `UsineErreur`). La
   borne de `startAt` de DC (fenêtre de 10 000 résultats) ne s'applique jamais. Arrêt sur une
   page vide ou dont le `total` ne dépasse pas le nombre de tickets reçus ;
3. pour chaque ticket au changelog en ligne tronqué : `GET /rest/api/2/issue/{cle}`
   (`expand=changelog`), fusionné et dédoublonné par id d'historique. Encore tronqué : erreur.

JQL, champs demandés, restriction `updated >= "-<n>m"` et conversion sont ceux de Cloud
(`jira_cloud`) : le flux rendu est celui de Cloud, à `source = jira_dc` près.
"""

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from datetime import datetime
from types import MappingProxyType
from typing import Any

from usine.adaptateurs.jira_cloud.conversion import (
    FICHIER_CONFIG,
    convertir_ticket,
    trier_evenements,
)
from usine.adaptateurs.jira_cloud.source import (
    _maintenant,
    champs_demandes,
    changelog_tronque,
    minutes_depuis,
    requete_jql,
)
from usine.adaptateurs.jira_http import ClientJiraLecture
from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import Evenement, SourceEvenement
from usine.contrats.tickets import rang_cle

CHEMIN_RECHERCHE = "/rest/api/2/search"
"""Recherche JQL Data Center, paginée ici par curseur de clé."""
CHEMIN_CHAMPS = "/rest/api/2/field"
"""Liste des champs du site (tableau JSON) : identifiant et nom d'affichage."""
TAILLE_PAGE_RECHERCHE = 100
"""Tickets demandés par page de recherche ; le serveur peut plafonner."""
_ITEM_IGNORE: Mapping[str, Any] = MappingProxyType({"field": None, "fieldtype": None})
"""Item de remplacement d'un champ personnalisé inconnu : sans identifiant, ignoré."""


def chemin_ticket(cle: str) -> str:
    """Ticket DC (avec `expand=changelog` : changelog complet)."""
    return f"/rest/api/2/issue/{cle}"


def identifiants_par_nom(champs_jira: Iterable[object], config: ConfigJira) -> dict[str, list[str]]:
    """Nom d'affichage → identifiants des champs personnalisés du site.

    `champs_jira` est la réponse de `GET /rest/api/2/field` ; seuls les champs personnalisés
    (`custom: true` ou `customfield_…`) sont retenus, configurés ou non. Un nom porté par
    plusieurs champs dont au moins un est configuré garde tous ses identifiants (ambigu) ; porté
    par plusieurs champs tous non configurés, il n'en garde qu'un (ignoré à la conversion).
    """
    configures = set(config.champs.values())
    par_nom: dict[str, list[str]] = {}
    for champ in champs_jira:
        if not isinstance(champ, Mapping):
            raise UsineErreur(f"Jira GET {CHEMIN_CHAMPS} : champ illisible ({champ!r})")
        identifiant = champ.get("id")
        nom = champ.get("name")
        if not isinstance(identifiant, str) or not isinstance(nom, str):
            raise UsineErreur(f"Jira GET {CHEMIN_CHAMPS} : champ illisible ({champ!r})")
        personnalise = champ.get("custom") is True or identifiant.startswith("customfield_")
        if personnalise and identifiant not in par_nom.get(nom, []):
            par_nom.setdefault(nom, []).append(identifiant)
    return {
        nom: identifiants if configures.intersection(identifiants) else identifiants[:1]
        for nom, identifiants in par_nom.items()
    }


def _resoudre_item(item: object, par_nom: Mapping[str, Sequence[str]], cle: str) -> object:
    if not isinstance(item, Mapping) or item.get("fieldtype") != "custom":
        return item
    identifiant = item.get("fieldId")
    nom = item.get("field")
    if (isinstance(identifiant, str) and identifiant) or not isinstance(nom, str):
        return item  # `fieldId` présent, ou item illisible signalé par la conversion
    identifiants = par_nom.get(nom, [])
    if len(identifiants) > 1:
        raise UsineErreur(
            f"Jira : ticket {cle} : champ personnalisé « {nom} » ambigu : ce nom désigne"
            f" plusieurs champs du site, dont un de {FICHIER_CONFIG}"
            f" ({', '.join(identifiants)})"
        )
    if not identifiants:
        return _ITEM_IGNORE
    return {**item, "fieldId": identifiants[0]}


def resoudre_items(
    historiques: Iterable[object], par_nom: Mapping[str, Sequence[str]], cle: str
) -> list[Mapping[str, Any]]:
    """Historiques dont chaque item `custom` sans `fieldId` reçoit l'identifiant de son nom.

    Un nom inconnu devient un item ignoré, au même rang ; celui d'un champ non configuré reçoit
    son identifiant, que la conversion ignore. Un historique sans liste
    d'items est rendu tel quel : la conversion le signale.
    """
    resolus: list[Mapping[str, Any]] = []
    for historique in historiques:
        if not isinstance(historique, Mapping):
            raise UsineErreur(
                f"Jira : ticket {cle} : historique de forme inconnue ({historique!r})"
            )
        if not isinstance(historique.get("items"), list):
            resolus.append(historique)
            continue
        items = [_resoudre_item(item, par_nom, cle) for item in historique["items"]]
        resolus.append({**historique, "items": items})
    return resolus


class SourceJiraDC:
    """Rend les `Evenement` canoniques des tickets du projet `config.cle_projet` (DC)."""

    source = SourceEvenement.jira_dc

    def __init__(
        self,
        client: ClientJiraLecture,
        config: ConfigJira,
        horloge: Callable[[], datetime] = _maintenant,
        taille_page: int = TAILLE_PAGE_RECHERCHE,
    ) -> None:
        if taille_page < 1:
            raise UsineErreur(f"Jira Data Center : taille de page d'au moins 1, pas {taille_page}")
        self._client = client
        self._config = config
        self._horloge = horloge
        self._taille_page = taille_page

    def evenements(self, depuis: datetime | None = None) -> Iterator[Evenement]:
        """Événements d'horodatage ≥ `depuis` (tous si `None`), par horodatage croissant.

        Avec `depuis`, seuls les tickets modifiés depuis cet instant sont recherchés.
        """
        if depuis is not None and (depuis.tzinfo is None or depuis.utcoffset() is None):
            raise UsineErreur(f"Jira Data Center : « depuis » sans fuseau : {depuis!r}")
        minutes = None if depuis is None else minutes_depuis(depuis, self._horloge())
        par_nom = identifiants_par_nom(
            self._client.requete_liste("GET", CHEMIN_CHAMPS), self._config
        )
        par_ticket = [
            convertir_ticket(
                ticket,
                resoudre_items(self._historiques(ticket), par_nom, ticket["key"]),
                self._config,
                self.source,
            )
            for ticket in self._tickets(minutes)
        ]
        for evenement in trier_evenements(par_ticket):
            if depuis is None or evenement.horodatage >= depuis:
                yield evenement

    def _tickets(self, minutes: int | None) -> Iterator[Mapping[str, Any]]:
        """Tickets de la recherche, page par page, par curseur de clé (`key > …`)."""
        champs = ",".join(champs_demandes(self._config))
        apres: str | None = None
        while True:
            params = {
                "jql": requete_jql(self._config, minutes, apres),
                "fields": champs,
                "expand": "changelog",
                "startAt": 0,
                "maxResults": self._taille_page,
            }
            page = self._client.requete("GET", CHEMIN_RECHERCHE, params=params)
            tickets = page.get("issues")
            if not isinstance(tickets, list):
                raise UsineErreur(f"Jira GET {CHEMIN_RECHERCHE} : réponse sans liste 'issues'")
            if not tickets:
                return
            derniere = ""
            for ticket in tickets:
                cle = ticket.get("key") if isinstance(ticket, Mapping) else None
                if not isinstance(cle, str) or not cle:
                    raise UsineErreur(
                        f"Jira GET {CHEMIN_RECHERCHE} : ticket illisible ou sans clé ({ticket!r})"
                    )
                yield ticket
                derniere = cle
            total = page.get("total")
            if isinstance(total, int) and not isinstance(total, bool) and total <= len(tickets):
                return
            if apres is not None and rang_cle(derniere) <= rang_cle(apres):
                raise UsineErreur(
                    f'Jira GET {CHEMIN_RECHERCHE} : page « key > "{apres}" » sans'
                    f" progression (dernière clé reçue {derniere})"
                )
            apres = derniere

    def _historiques(self, ticket: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        changelog = ticket.get("changelog")
        en_ligne = changelog.get("histories") if isinstance(changelog, Mapping) else None
        historiques: list[Mapping[str, Any]] = list(en_ligne) if isinstance(en_ligne, list) else []
        if not changelog_tronque(ticket):
            return historiques
        cle = ticket["key"]
        chemin = chemin_ticket(cle)
        complet = self._client.requete("GET", chemin, params={"expand": "changelog"})
        if changelog_tronque(complet):
            raise UsineErreur(
                f"Jira Data Center : ticket {cle} : changelog encore tronqué après"
                f" GET {chemin} (expand=changelog)"
            )
        # Doublons entre changelog en ligne et complément : `convertir_ticket` les écarte.
        return historiques + list(complet["changelog"]["histories"])
