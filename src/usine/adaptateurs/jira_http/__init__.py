"""Transport HTTP Jira commun aux adaptateurs Cloud et DC et à l'injecteur (AD-5).

- `transport` : authentification Cloud (e-mail + jeton) et DC (PAT), reprise sur 429 selon
  `Retry-After`, erreurs en `UsineErreur`, redirections non suivies ;
- `pagination` : par jeton (`nextPageToken`, Cloud) et par position (`startAt`, DC) ;
- `clients` : `ClientJiraLecture`, qui refuse avant envoi toute requête hors liste blanche,
  et `ClientJiraEcriture`, réservé à la composition du générateur.

Les identifiants arrivent en paramètres : ce paquet n'importe pas `usine.config`.
"""

from usine.adaptateurs.jira_http.clients import (
    LISTE_BLANCHE_LECTURE,
    ClientJiraEcriture,
    ClientJiraLecture,
    RequeteJiraInterdite,
    construire_client_ecriture,
    construire_client_lecture,
    requete_autorisee,
)
from usine.adaptateurs.jira_http.pagination import paginer_par_jeton, paginer_par_position
from usine.adaptateurs.jira_http.transport import Authentification, Plateforme, TransportJira

__all__ = [
    "LISTE_BLANCHE_LECTURE",
    "Authentification",
    "ClientJiraEcriture",
    "ClientJiraLecture",
    "Plateforme",
    "RequeteJiraInterdite",
    "TransportJira",
    "construire_client_ecriture",
    "construire_client_lecture",
    "paginer_par_jeton",
    "paginer_par_position",
    "requete_autorisee",
]
