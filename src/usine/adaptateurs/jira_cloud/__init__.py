"""Adaptateur Jira Cloud v3 : `SourceTickets` sur la recherche JQL et le changelog (AD-3, AD-23).

- `source` : `SourceJiraCloud`, qui lit Jira par `ClientJiraLecture` seulement (liste
  blanche), complète les changelogs tronqués et rend un flux d'`Evenement` trié ;
- `conversion` : fonctions pures de conversion d'un ticket et de son changelog en `Evenement`
  canoniques, selon la table `ConfigJira` (`config/jira.yaml`), appliquée ici seulement ;
- `fixtures` : rafraîchissement anonymisé des fixtures depuis le vrai site (recette, 2.7).
"""

from usine.adaptateurs.jira_cloud.conversion import (
    convertir_ticket,
    lire_horodatage,
    ordonner_historiques,
    texte_adf,
    trier_evenements,
    type_canonique,
    valeur_canonique,
    valeur_courante,
)
from usine.adaptateurs.jira_cloud.fixtures import (
    anonymiser,
    rafraichir_fixtures,
    verifier_sans_secret,
)
from usine.adaptateurs.jira_cloud.source import (
    SourceJiraCloud,
    champs_demandes,
    changelog_tronque,
    chemin_changelog,
    minutes_depuis,
    requete_jql,
)

__all__ = [
    "SourceJiraCloud",
    "anonymiser",
    "champs_demandes",
    "changelog_tronque",
    "chemin_changelog",
    "convertir_ticket",
    "lire_horodatage",
    "minutes_depuis",
    "ordonner_historiques",
    "rafraichir_fixtures",
    "requete_jql",
    "texte_adf",
    "trier_evenements",
    "type_canonique",
    "valeur_canonique",
    "valeur_courante",
    "verifier_sans_secret",
]
