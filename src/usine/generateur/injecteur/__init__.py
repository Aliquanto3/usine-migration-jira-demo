"""Injecteur Jira Cloud : seul écrivain Jira du démonstrateur (FR-5, AD-4, AD-5).

- `plan` : état de chaque ticket à la Date d'injection, ordre des clés, corps de création ;
- `site` : préparation idempotente du site (types, champs, workflow H-17, schémas, projet) ;
- `injection` : liste exacte des tickets du projet, rapprochement avec le plan, reprise ou
  création des tickets, transitions, manifeste d'injection (réinjection idempotente) ;
- `cli` : composition (secrets, client d'écriture, débit, fichiers écrits), seule à
  construire le client d'écriture ; ce paquet ne l'importe pas.
"""

from usine.generateur.injecteur.injection import (
    BilanInjection,
    Etape,
    EtatInjectionPartielle,
    EtatPrecedent,
    InjectionInterrompue,
    Rapprochement,
    TicketExistant,
    injecter,
    lister_tickets,
    rapprocher,
)
from usine.generateur.injecteur.plan import (
    TRANSITIONS_H17,
    PlanInjection,
    TicketPlanifie,
    champs_creation,
    chemin_statuts,
    document_adf,
    planifier,
)
from usine.generateur.injecteur.site import ClientJira, SiteDemo, preparer_site

__all__ = [
    "TRANSITIONS_H17",
    "BilanInjection",
    "ClientJira",
    "Etape",
    "EtatInjectionPartielle",
    "EtatPrecedent",
    "InjectionInterrompue",
    "PlanInjection",
    "Rapprochement",
    "SiteDemo",
    "TicketExistant",
    "TicketPlanifie",
    "champs_creation",
    "chemin_statuts",
    "document_adf",
    "injecter",
    "lister_tickets",
    "planifier",
    "preparer_site",
    "rapprocher",
]
