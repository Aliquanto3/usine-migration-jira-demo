"""Plan d'injection : état de chaque ticket à la Date d'injection, dans l'ordre des clés (FR-5).

Cœur pur : ni réseau, ni horloge, ni I/O. `planifier` replie les événements du Journal de
jour local ≤ Date d'injection en valeurs canoniques finales, ticket par ticket, triés par
`rang_cle` de la clé générée ; `champs_creation` en tire le corps de `POST /rest/api/3/issue` ;
`chemin_statuts` donne le plus court chemin du workflow H-17 vers le statut final.
"""

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any

from usine.contrats.calendrier import jour_local
from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import EnteteJournal, Evenement, NatureEvenement
from usine.contrats.tickets import (
    CHAMPS_PAR_TYPE,
    DOMAINES_CANONIQUES,
    Champ,
    StatutAnomalie,
    TypeTicket,
    rang_cle,
)

STATUT_INITIAL = StatutAnomalie.nouvelle
"""Statut d'une Anomalie à sa création (transition initiale du workflow H-17)."""

TRANSITIONS_H17: tuple[tuple[StatutAnomalie, StatutAnomalie], ...] = (
    (StatutAnomalie.nouvelle, StatutAnomalie.en_analyse),
    (StatutAnomalie.en_analyse, StatutAnomalie.en_correction),
    (StatutAnomalie.en_analyse, StatutAnomalie.rejetee),
    (StatutAnomalie.en_correction, StatutAnomalie.a_retester),
    (StatutAnomalie.a_retester, StatutAnomalie.fermee),
    (StatutAnomalie.a_retester, StatutAnomalie.en_correction),
    (StatutAnomalie.fermee, StatutAnomalie.en_analyse),
    (StatutAnomalie.rejetee, StatutAnomalie.en_analyse),
)
"""Transitions `(départ, arrivée)` du workflow fictif des Anomalies (H-17), ordre fixe."""

CHAMPS_SELECTION: Mapping[Champ, str] = MappingProxyType(
    {
        Champ.entite: "Entité",
        Champ.vague: "Vague",
        Champ.domaine: "Domaine",
        Champ.gravite: "Gravité",
        Champ.phase: "Phase",
        Champ.statut_test: "Statut du test",
        Champ.statut_certification: "Statut de certification",
    }
)
"""Nom Jira de chaque champ personnalisé (liste de sélection) du Programme, ordre fixe."""

CHAMPS_LIBRES: tuple[Champ, ...] = tuple(
    champ for champ in CHAMPS_SELECTION if DOMAINES_CANONIQUES[champ] is None
)
"""Listes de sélection à valeur libre : leurs options sont les valeurs du Journal."""

CHAMPS_STANDARD: Mapping[Champ, str] = MappingProxyType(
    {Champ.statut: "status", Champ.titre: "summary", Champ.description: "description"}
)
"""Identifiant des champs standard Jira portés par un ticket du Programme."""

LONGUEUR_MAX_RESUME = 255
"""Longueur maximale d'un `summary` Jira."""


@dataclass(frozen=True)
class TicketPlanifie:
    """Ticket à créer : clé générée, type et valeurs canoniques à la Date d'injection."""

    cle: str
    type_ticket: TypeTicket
    valeurs: Mapping[Champ, str]

    @property
    def statut_final(self) -> StatutAnomalie | None:
        """Statut d'arrivée d'une Anomalie (`None` pour les autres types)."""
        if self.type_ticket is not TypeTicket.anomalie:
            return None
        return StatutAnomalie(self.valeurs.get(Champ.statut, STATUT_INITIAL))


@dataclass(frozen=True)
class PlanInjection:
    """Tickets à créer, triés par `rang_cle`, et options des listes à valeur libre."""

    date_injection: date
    tickets: tuple[TicketPlanifie, ...]
    valeurs_libres: Mapping[Champ, tuple[str, ...]]
    """Valeurs de tout le Journal pour Entité, Vague et Domaine, triées."""


def planifier(entete: EnteteJournal, evenements: Iterable[Evenement]) -> PlanInjection:
    """Plan d'injection du Journal `(entete, evenements)`.

    État injecté = repli de tous les événements du ticket de jour local ≤ Date d'injection.
    Un ticket sans création à cette date, une création en double ou un type incohérent lève
    une `UsineErreur` : la correspondance des clés du manifeste doit couvrir tout le Journal.
    """
    date_injection = entete.date_injection
    types: dict[str, TypeTicket] = {}
    valeurs: dict[str, dict[Champ, str]] = {}
    libres: dict[Champ, set[str]] = {champ: set() for champ in CHAMPS_LIBRES}
    vus: set[str] = set()
    for evenement in evenements:
        cle = evenement.cle_ticket
        vus.add(cle)
        champ = evenement.champ
        if champ is not None and champ in libres:
            libres[champ].update(v for v in (evenement.de, evenement.vers) if v is not None)
        if jour_local(evenement.horodatage) > date_injection:
            continue
        if evenement.nature is NatureEvenement.creation:
            if cle in types:
                raise UsineErreur(f"Journal : ticket {cle} créé deux fois")
            types[cle] = evenement.type_ticket
            valeurs[cle] = {}
            continue
        if cle not in types:
            raise UsineErreur(f"Journal : ticket {cle} modifié avant sa création")
        if evenement.type_ticket is not types[cle]:
            raise UsineErreur(
                f"Journal : ticket {cle} de type {types[cle].value} puis"
                f" {evenement.type_ticket.value}"
            )
        if evenement.nature is NatureEvenement.alignement or champ is None:
            continue
        if evenement.vers is None:
            valeurs[cle].pop(champ, None)
        else:
            valeurs[cle][champ] = evenement.vers
    tardifs = sorted(vus - set(types), key=rang_cle)
    if tardifs:
        raise UsineErreur(
            f"Journal : {len(tardifs)} ticket(s) sans création au plus tard le"
            f" {date_injection.isoformat()} (Date d'injection) : {', '.join(tardifs[:5])}"
        )
    tickets = tuple(
        TicketPlanifie(cle, types[cle], MappingProxyType(dict(valeurs[cle])))
        for cle in sorted(types, key=rang_cle)
    )
    for ticket in tickets:
        _verifier_ticket(ticket)
    return PlanInjection(
        date_injection,
        tickets,
        MappingProxyType({champ: tuple(sorted(libres[champ])) for champ in CHAMPS_LIBRES}),
    )


def _verifier_ticket(ticket: TicketPlanifie) -> None:
    titre = ticket.valeurs.get(Champ.titre)
    if titre is None or not titre.strip():
        raise UsineErreur(f"Journal : ticket {ticket.cle} sans titre à la Date d'injection")
    if "\n" in titre or len(titre) > LONGUEUR_MAX_RESUME:
        raise UsineErreur(
            f"Journal : ticket {ticket.cle} : titre sur plusieurs lignes ou de plus de"
            f" {LONGUEUR_MAX_RESUME} caractères (summary Jira)"
        )


def chemin_statuts(depart: StatutAnomalie, arrivee: StatutAnomalie) -> tuple[StatutAnomalie, ...]:
    """Statuts traversés de `depart` à `arrivee` par le plus court chemin H-17, départ exclu.

    Parcours en largeur dans l'ordre de `TRANSITIONS_H17` : le chemin est déterministe.
    """
    precedents: dict[StatutAnomalie, StatutAnomalie | None] = {depart: None}
    file = deque([depart])
    while file:
        courant = file.popleft()
        if courant is arrivee:
            break
        for de, vers in TRANSITIONS_H17:
            if de is courant and vers not in precedents:
                precedents[vers] = courant
                file.append(vers)
    if arrivee not in precedents:  # « Nouvelle » n'est atteinte que par la création.
        raise UsineErreur(f"workflow H-17 : {arrivee.value} inaccessible depuis {depart.value}")
    chemin: list[StatutAnomalie] = []
    etape: StatutAnomalie | None = arrivee
    while etape is not None and etape is not depart:
        chemin.append(etape)
        etape = precedents[etape]
    return tuple(reversed(chemin))


def document_adf(texte: str) -> dict[str, Any]:
    """Document ADF du texte : un paragraphe par ligne, paragraphe vide sans nœud texte."""
    paragraphes: list[dict[str, Any]] = []
    for ligne in texte.split("\n"):
        paragraphe: dict[str, Any] = {"type": "paragraph"}
        if ligne:
            paragraphe["content"] = [{"type": "text", "text": ligne}]
        paragraphes.append(paragraphe)
    return {"type": "doc", "version": 1, "content": paragraphes}


def noms_jira(config: ConfigJira) -> Mapping[Champ, Mapping[str, str]]:
    """Pour chaque Champ à domaine fermé : valeur canonique → premier nom Jira de `valeurs`."""
    noms: dict[Champ, Mapping[str, str]] = {}
    for champ, domaine in DOMAINES_CANONIQUES.items():
        if domaine is None:
            continue
        table: dict[str, str] = {}
        for nom, canonique in config.valeurs.get(champ, {}).items():
            table.setdefault(canonique, nom)
        manquantes = sorted(domaine - set(table))
        if manquantes:
            raise UsineErreur(
                f"config/jira.yaml : valeurs.{champ.value} : valeur canonique sans nom Jira :"
                f" {', '.join(manquantes)}"
            )
        noms[champ] = MappingProxyType(table)
    return MappingProxyType(noms)


def champs_creation(
    ticket: TicketPlanifie,
    *,
    cle_projet: str,
    id_type: str,
    identifiants: Mapping[Champ, str],
    noms: Mapping[Champ, Mapping[str, str]],
) -> dict[str, Any]:
    """Objet `fields` de `POST /rest/api/3/issue` pour `ticket`.

    Le statut n'y figure pas (il est atteint par les transitions) ; `identifiants` donne
    l'identifiant Jira de chaque liste de sélection, `noms` le nom Jira des valeurs fermées.
    """
    champs: dict[str, Any] = {
        "project": {"key": cle_projet},
        "issuetype": {"id": id_type},
        "summary": ticket.valeurs[Champ.titre],
    }
    description = ticket.valeurs.get(Champ.description)
    if description is not None:
        champs["description"] = document_adf(description)
    for champ in CHAMPS_SELECTION:
        if champ not in CHAMPS_PAR_TYPE[ticket.type_ticket]:
            continue
        valeur = ticket.valeurs.get(champ)
        if valeur is None:
            continue
        nom = valeur if DOMAINES_CANONIQUES[champ] is None else noms[champ][valeur]
        champs[identifiants[champ]] = {"value": nom}
    return champs
