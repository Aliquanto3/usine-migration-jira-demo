"""Injection des tickets dans le projet préparé, un à un, dans l'ordre des clés (FR-5, AD-4).

Cœur sans réseau ni horloge propres : client, horloge et limiteur de débit arrivent de la
composition. Un projet déjà peuplé est refusé (réinjection : Story 1.7). Chaque ticket est
créé par `POST /rest/api/3/issue`, puis une Anomalie suit le plus court chemin du workflow
H-17 jusqu'à son statut à la Date d'injection. La fin d'injection est le plus tardif de
l'horloge locale et de `serverTime`, lus après la dernière écriture : la coupure stricte de
la Source composite ne reprend ainsi aucune écriture de l'injecteur.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from types import MappingProxyType
from typing import Any

from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import ManifesteInjection
from usine.contrats.tickets import Champ, StatutAnomalie, TypeTicket
from usine.generateur.injecteur.plan import (
    STATUT_INITIAL,
    PlanInjection,
    TicketPlanifie,
    champs_creation,
    chemin_statuts,
    noms_jira,
)
from usine.generateur.injecteur.site import API, ClientJira, SiteDemo


@dataclass(frozen=True)
class EtatInjectionPartielle:
    """Ce qu'une injection interrompue a déjà écrit (`etat_injection_partielle.json`)."""

    cle_projet: str
    date_injection: date
    debut_injection: datetime
    tickets_crees: tuple[str, ...]
    """Clés Jira des tickets créés, dans l'ordre de création."""
    correspondance_cles: Mapping[str, str]
    """Clé générée → clé Jira, pour les tickets créés."""
    derniere_erreur: str

    def vers_json(self) -> dict[str, Any]:
        """Contenu JSON de l'état partiel."""
        return {
            "cle_projet": self.cle_projet,
            "date_injection": self.date_injection.isoformat(),
            "debut_injection": self.debut_injection.isoformat(),
            "tickets_crees": list(self.tickets_crees),
            "correspondance_cles": dict(self.correspondance_cles),
            "derniere_erreur": self.derniere_erreur,
        }


class InjectionInterrompue(UsineErreur):
    """Injection arrêtée après au moins une écriture possible : aucun manifeste écrit."""

    def __init__(self, message: str, etat: EtatInjectionPartielle) -> None:
        super().__init__(message)
        self.etat = etat


def lire_server_time(reponse: Mapping[str, Any]) -> datetime:
    """`serverTime` de `GET /serverInfo` (`2026-10-12T14:00:00.000+0200`) en UTC."""
    texte = reponse.get("serverTime")
    contexte = f"Jira GET {API}/serverInfo"
    if not isinstance(texte, str):
        raise UsineErreur(f"{contexte} : réponse sans serverTime")
    try:
        instant = datetime.fromisoformat(texte)
    except ValueError:
        raise UsineErreur(f"{contexte} : serverTime illisible {texte!r}") from None
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise UsineErreur(f"{contexte} : serverTime sans fuseau {texte!r}")
    return instant.astimezone(UTC)


class _Transitions:
    """Transitions disponibles par statut d'Anomalie, lues une fois puis gardées en cache."""

    def __init__(
        self,
        client: ClientJira,
        noms: Mapping[str, str],
        limiter: Callable[[], None],
    ) -> None:
        self._client = client
        self._noms = noms
        self._limiter = limiter
        self._cache: dict[StatutAnomalie, dict[str, str]] = {}

    def identifiant(self, cle: str, depart: StatutAnomalie, arrivee: StatutAnomalie) -> str:
        if depart not in self._cache:
            chemin = f"{API}/issue/{cle}/transitions"
            self._limiter()
            reponse = self._client.requete("GET", chemin)
            transitions = reponse.get("transitions")
            if not isinstance(transitions, list):
                raise UsineErreur(f"Jira GET {chemin} : réponse sans liste 'transitions'")
            par_arrivee: dict[str, str] = {}
            for transition in transitions:
                if not isinstance(transition, dict) or not isinstance(transition.get("to"), dict):
                    continue
                nom = transition["to"].get("name")
                identifiant = transition.get("id")
                if isinstance(nom, str) and isinstance(identifiant, str | int):
                    par_arrivee.setdefault(nom, str(identifiant))
            self._cache[depart] = par_arrivee
        nom_arrivee = self._noms[arrivee]
        if nom_arrivee not in self._cache[depart]:
            raise UsineErreur(
                f"Jira : ticket {cle} : aucune transition de « {self._noms[depart]} » vers"
                f" « {nom_arrivee} » (workflow H-17 attendu)"
            )
        return self._cache[depart][nom_arrivee]


def _compter_tickets(client: ClientJira, site: SiteDemo) -> int:
    types = ", ".join(site.types[t] for t in TypeTicket)
    jql = f'project = "{site.cle_projet}" AND issuetype in ({types})'
    reponse = client.requete("POST", f"{API}/search/approximate-count", corps={"jql": jql})
    nombre = reponse.get("count")
    if not isinstance(nombre, int) or isinstance(nombre, bool):
        raise UsineErreur(f"Jira POST {API}/search/approximate-count : réponse sans count")
    return nombre


def _creer(
    client: ClientJira,
    ticket: TicketPlanifie,
    site: SiteDemo,
    noms: Mapping[Champ, Mapping[str, str]],
    limiter: Callable[[], None],
) -> str:
    champs = champs_creation(
        ticket,
        cle_projet=site.cle_projet,
        id_type=site.types[ticket.type_ticket],
        identifiants=site.champs,
        noms=noms,
    )
    limiter()
    reponse = client.requete("POST", f"{API}/issue", corps={"fields": champs})
    cle = reponse.get("key")
    if not isinstance(cle, str) or not cle:
        raise UsineErreur(f"Jira POST {API}/issue : ticket {ticket.cle} créé sans clé rendue")
    return cle


def injecter(
    client: ClientJira,
    plan: PlanInjection,
    site: SiteDemo,
    config: ConfigJira,
    horloge: Callable[[], datetime],
    limiter: Callable[[], None],
) -> ManifesteInjection:
    """Crée les tickets du plan dans le projet du site et rend le manifeste d'injection.

    `limiter` est appelé avant chaque requête (débit plafonné) ; `horloge` rend l'instant
    courant avec fuseau. Projet déjà peuplé : `UsineErreur`, rien n'est créé. Erreur après
    le premier envoi d'écriture : `InjectionInterrompue`, qui porte l'état partiel.
    """
    debut = horloge()
    limiter()
    deja = _compter_tickets(client, site)
    if deja:
        raise UsineErreur(
            f"Jira : projet {site.cle_projet} déjà peuplé ({deja} ticket(s) Anomalie, Cas de"
            " test ou Certification) : réinjection et reprise relèvent de la Story 1.7 ;"
            " aucun ticket créé"
        )
    noms = noms_jira(config)
    transitions = _Transitions(client, noms[Champ.statut], limiter)
    correspondance: dict[str, str] = {}
    crees: list[str] = []
    try:
        for ticket in plan.tickets:
            cle_jira = _creer(client, ticket, site, noms, limiter)
            crees.append(cle_jira)
            correspondance[ticket.cle] = cle_jira
            final = ticket.statut_final
            if final is None:
                continue
            courant = StatutAnomalie(STATUT_INITIAL)
            for suivant in chemin_statuts(courant, final):
                identifiant = transitions.identifiant(cle_jira, courant, suivant)
                limiter()
                client.requete(
                    "POST",
                    f"{API}/issue/{cle_jira}/transitions",
                    corps={"transition": {"id": identifiant}},
                )
                courant = suivant
        limiter()
        serveur = lire_server_time(client.requete("GET", f"{API}/serverInfo"))
        fin = max(horloge(), serveur)
        return ManifesteInjection(
            date_injection=plan.date_injection,
            debut_injection=debut,
            horodatage_fin_injection=fin,
            cle_projet=site.cle_projet,
            correspondance_cles=MappingProxyType(dict(correspondance)),
        )
    except Exception as exc:  # toute erreur après un envoi possible : état partiel conservé.
        message = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        etat = EtatInjectionPartielle(
            cle_projet=site.cle_projet,
            date_injection=plan.date_injection,
            debut_injection=debut,
            tickets_crees=tuple(crees),
            correspondance_cles=MappingProxyType(dict(correspondance)),
            derniere_erreur=message,
        )
        raise InjectionInterrompue(
            f"injection interrompue après {len(crees)} ticket(s) créé(s) sur"
            f" {len(plan.tickets)} : {message}",
            etat,
        ) from exc
