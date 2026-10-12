"""Injection des tickets dans le projet préparé, idempotente, dans l'ordre des clés (FR-5, AD-4).

Cœur sans réseau ni horloge propres : client, horloge et limiteur de débit arrivent de la
composition. Avant toute écriture de ticket, les tickets du projet sont listés exactement
(`POST /rest/api/3/search/jql`, paginé par `nextPageToken`) et rapprochés du plan
(`rapprocher`, fonction pure) : un ticket déjà présent est repris (amené à son statut cible
s'il n'y est pas), jamais recréé ni modifié ; seuls les tickets absents sont créés, par
`POST /rest/api/3/issue`, dans l'ordre des clés. Une Anomalie suit le plus court chemin du
workflow H-17 jusqu'à son statut à la Date d'injection. La fin d'injection est le plus tardif
de l'horloge locale et de `serverTime`, lus après la dernière écriture : la coupure stricte
de la Source composite ne reprend ainsi aucune écriture de l'injecteur.
"""

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from types import MappingProxyType
from typing import Any

from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import ManifesteInjection
from usine.contrats.tickets import Champ, StatutAnomalie
from usine.generateur.injecteur.plan import (
    STATUT_INITIAL,
    PlanInjection,
    TicketPlanifie,
    champs_creation,
    chemin_statuts,
    noms_jira,
)
from usine.generateur.injecteur.site import API, ClientJira, SiteDemo

TAILLE_PAGE_RECHERCHE = 100
"""Tickets demandés par page de `search/jql`."""


@dataclass(frozen=True)
class EtatInjectionPartielle:
    """Ce qu'une injection interrompue a déjà écrit (`etat_injection_partielle.json`)."""

    cle_projet: str
    date_injection: date
    debut_injection: datetime
    tickets_crees: tuple[str, ...]
    """Clés Jira des tickets créés par l'injection interrompue, dans l'ordre de création."""
    correspondance_cles: Mapping[str, str]
    """Clé générée → clé Jira, pour tous les tickets connus (repris et créés)."""
    derniere_erreur: str
    url_site: str | None = None
    """Site de l'injection (absent d'un état partiel de la Story 1.6)."""
    id_projet: str | None = None
    """Identifiant Jira du projet (absent d'un état partiel de la Story 1.6)."""
    tickets_repris: tuple[str, ...] = ()
    """Clés Jira des tickets déjà présents, repris par l'injection interrompue."""

    def vers_json(self) -> dict[str, Any]:
        """Contenu JSON de l'état partiel."""
        return {
            "url_site": self.url_site,
            "cle_projet": self.cle_projet,
            "id_projet": self.id_projet,
            "date_injection": self.date_injection.isoformat(),
            "debut_injection": self.debut_injection.isoformat(),
            "tickets_crees": list(self.tickets_crees),
            "tickets_repris": list(self.tickets_repris),
            "correspondance_cles": dict(self.correspondance_cles),
            "derniere_erreur": self.derniere_erreur,
        }

    @classmethod
    def depuis_json(cls, contenu: object, origine: str) -> "EtatInjectionPartielle":
        """Relit le contenu de `vers_json` ; `origine` nomme le fichier dans les erreurs."""

        def erreur(motif: str) -> UsineErreur:
            return UsineErreur(f"{origine} : état d'injection partielle illisible ({motif})")

        if not isinstance(contenu, dict):
            raise erreur("objet JSON attendu")

        def texte(cle: str) -> str:
            valeur = contenu.get(cle)
            if not isinstance(valeur, str) or not valeur:
                raise erreur(f"{cle} : texte attendu")
            return valeur

        def texte_facultatif(cle: str) -> str | None:
            return None if contenu.get(cle) is None else texte(cle)

        def cles(cle: str) -> tuple[str, ...]:
            valeur = contenu.get(cle, [])
            if not isinstance(valeur, list) or not all(isinstance(v, str) for v in valeur):
                raise erreur(f"{cle} : liste de clés attendue")
            return tuple(valeur)

        correspondance = contenu.get("correspondance_cles")
        if not isinstance(correspondance, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in correspondance.items()
        ):
            raise erreur("correspondance_cles : objet clé générée → clé Jira attendu")
        try:
            date_injection = date.fromisoformat(texte("date_injection"))
            debut = datetime.fromisoformat(texte("debut_injection"))
        except ValueError as exc:
            raise erreur(str(exc)) from None
        if debut.tzinfo is None or debut.utcoffset() is None:
            raise erreur("debut_injection sans fuseau")
        return cls(
            cle_projet=texte("cle_projet"),
            date_injection=date_injection,
            debut_injection=debut,
            tickets_crees=cles("tickets_crees"),
            correspondance_cles=MappingProxyType(dict(correspondance)),
            derniere_erreur=str(contenu.get("derniere_erreur", "")),
            url_site=texte_facultatif("url_site"),
            id_projet=texte_facultatif("id_projet"),
            tickets_repris=cles("tickets_repris"),
        )


class InjectionInterrompue(UsineErreur):
    """Injection arrêtée après au moins une écriture possible : aucun manifeste écrit."""

    def __init__(self, message: str, etat: EtatInjectionPartielle) -> None:
        super().__init__(message)
        self.etat = etat


@dataclass(frozen=True)
class TicketExistant:
    """Ticket déjà présent dans le projet, tel que listé par `search/jql`."""

    cle: str
    id_type: str
    resume: str
    """`summary` Jira."""
    statut: str
    """Nom Jira du statut."""


@dataclass(frozen=True)
class EtatPrecedent:
    """Ce qu'une injection précédente sur le même site a laissé (manifeste, état partiel)."""

    debut: datetime
    """Début de l'injection d'origine, conservé."""
    fin: datetime | None
    """Fin d'injection du manifeste précédent ; `None` si elle n'est pas sûre."""
    correspondance: Mapping[str, str]
    """Clé générée → clé Jira déjà connue."""


@dataclass(frozen=True)
class Etape:
    """Traitement d'un ticket du plan : reprise (`cle_jira` connue) ou création."""

    ticket: TicketPlanifie
    cle_jira: str | None
    """Clé Jira du ticket repris ; `None` : ticket à créer."""
    depart: StatutAnomalie | None
    """Statut de départ d'une Anomalie (courant si reprise, initial si création)."""
    chemin: tuple[StatutAnomalie, ...]
    """Statuts à traverser jusqu'au statut cible (vide : aucune transition)."""


@dataclass(frozen=True)
class Rapprochement:
    """Plan rapproché des tickets du projet, dans l'ordre des clés."""

    etapes: tuple[Etape, ...]

    @property
    def repris(self) -> tuple[Etape, ...]:
        """Tickets déjà présents."""
        return tuple(e for e in self.etapes if e.cle_jira is not None)

    @property
    def a_creer(self) -> tuple[Etape, ...]:
        """Tickets absents, à créer."""
        return tuple(e for e in self.etapes if e.cle_jira is None)


@dataclass(frozen=True)
class BilanInjection:
    """Issue d'une injection réussie."""

    manifeste: ManifesteInjection
    crees: tuple[str, ...]
    """Clés Jira des tickets créés, dans l'ordre de création."""
    repris: tuple[str, ...]
    """Clés Jira des tickets déjà présents, repris."""
    transitions: int
    """Transitions envoyées."""


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


def _numero(cle: str) -> int:
    numero = cle.rpartition("-")[2]
    return int(numero) if numero.isdigit() else 0


def _ticket_existant(element: object, contexte: str) -> TicketExistant:
    if not isinstance(element, dict):
        raise UsineErreur(f"{contexte} : ticket illisible")
    cle = element.get("key")
    champs = element.get("fields")
    if not isinstance(cle, str) or not cle or not isinstance(champs, dict):
        raise UsineErreur(f"{contexte} : ticket sans clé ou sans champs")
    type_ticket = champs.get("issuetype")
    statut = champs.get("status")
    resume = champs.get("summary")
    id_type = type_ticket.get("id") if isinstance(type_ticket, dict) else None
    nom_statut = statut.get("name") if isinstance(statut, dict) else None
    if isinstance(id_type, bool) or not isinstance(id_type, str | int):
        raise UsineErreur(f"{contexte} : ticket {cle} sans type")
    if not isinstance(nom_statut, str) or not isinstance(resume, str):
        raise UsineErreur(f"{contexte} : ticket {cle} sans statut ou sans résumé")
    return TicketExistant(cle, str(id_type), resume, nom_statut)


def lister_tickets(
    client: ClientJira, cle_projet: str, limiter: Callable[[], None]
) -> tuple[TicketExistant, ...]:
    """Tous les tickets du projet `cle_projet`, triés par numéro de clé.

    `POST /rest/api/3/search/jql`, paginé par `nextPageToken` ; `limiter` est appelé avant
    chaque page. Index de recherche à cohérence différée : un ticket tout juste créé peut
    manquer.
    """
    chemin = f"{API}/search/jql"
    contexte = f"Jira POST {chemin}"
    corps: dict[str, Any] = {
        "jql": f'project = "{cle_projet}" ORDER BY key ASC',
        "fields": ["summary", "issuetype", "status"],
        "maxResults": TAILLE_PAGE_RECHERCHE,
    }
    tickets: dict[str, TicketExistant] = {}
    jetons: set[str] = set()
    while True:
        limiter()
        page = client.requete("POST", chemin, corps=corps)
        elements = page.get("issues")
        if not isinstance(elements, list):
            raise UsineErreur(f"{contexte} : réponse sans liste 'issues'")
        for element in elements:
            ticket = _ticket_existant(element, contexte)
            tickets[ticket.cle] = ticket
        jeton = page.get("nextPageToken")
        if page.get("isLast") is True:
            break
        if not isinstance(jeton, str) or not jeton:
            raise UsineErreur(f"{contexte} : page non terminale sans nextPageToken")
        if jeton in jetons:
            raise UsineErreur(f"{contexte} : jeton de page {jeton!r} rendu deux fois")
        jetons.add(jeton)
        corps = {**corps, "nextPageToken": jeton}
    return tuple(sorted(tickets.values(), key=lambda t: (_numero(t.cle), t.cle)))


def rapprocher(
    plan: PlanInjection,
    existants: Sequence[TicketExistant],
    site: SiteDemo,
    config: ConfigJira,
    precedent: EtatPrecedent | None,
) -> Rapprochement:
    """Rapproche le plan des tickets du projet ; pur, calculé avant toute écriture.

    Un ticket planifié est repris s'il est présent sous sa clé connue (`precedent`), sinon
    sous sa clé générée si aucune autre clé générée ne la revendique : même type Jira et même
    `summary` (espaces de bord ignorés) exigés. Toute incohérence lève une `UsineErreur` :
    ticket étranger au plan ou d'identité différente, ticket connu absent, statut inconnu ou
    statut cible inaccessible par le workflow H-17.
    """
    connus = dict(precedent.correspondance) if precedent is not None else {}
    hors_plan = sorted(set(connus) - {t.cle for t in plan.tickets})
    if hors_plan:
        raise UsineErreur(
            "correspondance de l'injection précédente : clé(s) générée(s) absente(s) du"
            f" Journal : {', '.join(hors_plan[:5])} ; rien n'est écrit"
        )
    doublons = sorted(c for c, n in Counter(connus.values()).items() if n > 1)
    if doublons:
        raise UsineErreur(
            "correspondance de l'injection précédente non injective :"
            f" {', '.join(doublons[:5])} ; rien n'est écrit"
        )
    revendiquees = set(connus.values())
    par_cle = {t.cle: t for t in existants}
    statuts = config.valeurs.get(Champ.statut, {})
    etapes: list[Etape] = []
    reprises: set[str] = set()
    for ticket in plan.tickets:
        cle_connue = connus.get(ticket.cle)
        if cle_connue is not None:
            existant = par_cle.get(cle_connue)
            if existant is None:
                raise UsineErreur(
                    f"Jira : ticket {cle_connue} (clé générée {ticket.cle}), connu de"
                    " l'injection précédente, absent du projet : index de recherche en retard"
                    " (relancer dans une minute) ou ticket supprimé ; rien n'est écrit"
                )
        else:
            existant = par_cle.get(ticket.cle)
            if existant is not None and existant.cle in revendiquees:
                existant = None
        if existant is None:
            etapes.append(_etape_creation(ticket))
            continue
        _verifier_identite(ticket, existant, site)
        reprises.add(existant.cle)
        etapes.append(_etape_reprise(ticket, existant, statuts))
    etrangers = [t.cle for t in existants if t.cle not in reprises]
    if etrangers:
        raise UsineErreur(
            f"Jira : projet {site.cle_projet} : {len(etrangers)} ticket(s) sans correspondant"
            f" dans le Journal : {', '.join(etrangers[:5])} ; rien n'est écrit (retirer ce"
            " ticket du projet, ou injecter dans un autre projet ou un autre site)"
        )
    return Rapprochement(tuple(etapes))


def _verifier_identite(ticket: TicketPlanifie, existant: TicketExistant, site: SiteDemo) -> None:
    attendu = site.types[ticket.type_ticket]
    if existant.id_type != attendu:
        raise UsineErreur(
            f"Jira : ticket {existant.cle} de type {existant.id_type}, le ticket {ticket.cle}"
            f" du Journal est de type {attendu} ({ticket.type_ticket.value}) ; rien n'est écrit"
        )
    if existant.resume.strip() != ticket.valeurs[Champ.titre].strip():
        raise UsineErreur(
            f"Jira : ticket {existant.cle} de résumé différent de celui du ticket {ticket.cle}"
            " du Journal ; rien n'est écrit"
        )


def _chemin(ticket: TicketPlanifie, depart: StatutAnomalie, cle: str) -> tuple[StatutAnomalie, ...]:
    final = ticket.statut_final
    if final is None:
        return ()
    try:
        return chemin_statuts(depart, final)
    except UsineErreur as exc:
        raise UsineErreur(f"Jira : ticket {cle} : {exc} ; rien n'est écrit") from None


def _etape_creation(ticket: TicketPlanifie) -> Etape:
    if ticket.statut_final is None:
        return Etape(ticket, None, None, ())
    depart = StatutAnomalie(STATUT_INITIAL)
    return Etape(ticket, None, depart, _chemin(ticket, depart, ticket.cle))


def _etape_reprise(
    ticket: TicketPlanifie, existant: TicketExistant, statuts: Mapping[str, str]
) -> Etape:
    if ticket.statut_final is None:
        return Etape(ticket, existant.cle, None, ())
    canonique = statuts.get(existant.statut)
    if canonique is None:
        raise UsineErreur(
            f"Jira : ticket {existant.cle} au statut « {existant.statut} », absent de"
            " config/jira.yaml (valeurs.statut) ; rien n'est écrit"
        )
    depart = StatutAnomalie(canonique)
    return Etape(ticket, existant.cle, depart, _chemin(ticket, depart, existant.cle))


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


def _dans_l_ordre(correspondance: Mapping[str, str], plan: PlanInjection) -> Mapping[str, str]:
    return MappingProxyType(
        {t.cle: correspondance[t.cle] for t in plan.tickets if t.cle in correspondance}
    )


def injecter(
    client: ClientJira,
    plan: PlanInjection,
    site: SiteDemo,
    config: ConfigJira,
    horloge: Callable[[], datetime],
    limiter: Callable[[], None],
    precedent: EtatPrecedent | None = None,
) -> BilanInjection:
    """Amène le projet du site à l'état du plan et rend le bilan, manifeste compris.

    `limiter` est appelé avant chaque requête (débit plafonné) ; `horloge` rend l'instant
    courant avec fuseau ; `precedent` porte l'injection précédente du même site (début
    d'origine conservé, correspondance connue). Incohérence du rapprochement : `UsineErreur`,
    rien n'est écrit. Erreur après le premier envoi d'écriture : `InjectionInterrompue`, qui
    porte l'état partiel. Sans aucune écriture, la fin d'injection précédente est conservée.
    """
    existants = lister_tickets(client, site.cle_projet, limiter)
    if not existants:  # projet vide (site recréé, même identifiant) : état précédent caduc.
        precedent = None
    debut = precedent.debut if precedent is not None else horloge()
    rapprochement = rapprocher(plan, existants, site, config, precedent)
    noms = noms_jira(config)
    transitions = _Transitions(client, noms[Champ.statut], limiter)
    repris = tuple(e.cle_jira for e in rapprochement.repris if e.cle_jira is not None)
    correspondance = {
        e.ticket.cle: e.cle_jira for e in rapprochement.repris if e.cle_jira is not None
    }
    crees: list[str] = []
    envoyees = 0
    try:
        for etape in rapprochement.etapes:
            cle_jira = etape.cle_jira
            if cle_jira is None:
                cle_jira = _creer(client, etape.ticket, site, noms, limiter)
                crees.append(cle_jira)
                correspondance[etape.ticket.cle] = cle_jira
            courant = etape.depart
            for suivant in etape.chemin:
                if courant is None:  # chemin non vide : Anomalie, départ toujours connu.
                    raise UsineErreur(f"Jira : ticket {cle_jira} : statut de départ inconnu")
                identifiant = transitions.identifiant(cle_jira, courant, suivant)
                limiter()
                client.requete(
                    "POST",
                    f"{API}/issue/{cle_jira}/transitions",
                    corps={"transition": {"id": identifiant}},
                )
                envoyees += 1
                courant = suivant
        if not crees and not envoyees and precedent is not None and precedent.fin is not None:
            fin = precedent.fin
        else:
            limiter()
            serveur = lire_server_time(client.requete("GET", f"{API}/serverInfo"))
            fin = max(horloge(), serveur)
        manifeste = ManifesteInjection(
            date_injection=plan.date_injection,
            debut_injection=debut,
            horodatage_fin_injection=fin,
            cle_projet=site.cle_projet,
            correspondance_cles=_dans_l_ordre(correspondance, plan),
        )
        return BilanInjection(manifeste, tuple(crees), repris, envoyees)
    except Exception as exc:  # toute erreur après un envoi possible : état partiel conservé.
        message = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        etat = EtatInjectionPartielle(
            cle_projet=site.cle_projet,
            date_injection=plan.date_injection,
            debut_injection=debut,
            tickets_crees=tuple(crees),
            correspondance_cles=_dans_l_ordre(correspondance, plan),
            derniere_erreur=message,
            url_site=site.url_site,
            id_projet=site.id_projet,
            tickets_repris=repris,
        )
        raise InjectionInterrompue(
            f"injection interrompue après {len(crees)} ticket(s) créé(s) et {len(repris)}"
            f" repris sur {len(plan.tickets)} : {message}",
            etat,
        ) from exc
