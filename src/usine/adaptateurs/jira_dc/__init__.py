"""Adaptateur Jira Data Center v2 : `SourceTickets` sur la recherche et le changelog (AD-5).

`SourceJiraDC` lit Jira par `ClientJiraLecture` seulement (liste blanche DC), résout les noms
d'affichage des champs personnalisés du changelog, pagine la recherche par curseur de clé et
réutilise la conversion de `jira_cloud` : son flux est celui de Cloud,
à `source = jira_dc` près.
"""

from usine.adaptateurs.jira_dc.source import (
    CHEMIN_CHAMPS,
    CHEMIN_RECHERCHE,
    TAILLE_PAGE_RECHERCHE,
    SourceJiraDC,
    chemin_ticket,
    identifiants_par_nom,
    resoudre_items,
)

__all__ = [
    "CHEMIN_CHAMPS",
    "CHEMIN_RECHERCHE",
    "TAILLE_PAGE_RECHERCHE",
    "SourceJiraDC",
    "chemin_ticket",
    "identifiants_par_nom",
    "resoudre_items",
]
