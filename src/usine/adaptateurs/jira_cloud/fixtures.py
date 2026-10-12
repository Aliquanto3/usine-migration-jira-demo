"""Rafraîchissement anonymisé des fixtures Jira Cloud depuis le vrai site (Story 2.7).

`rafraichir_fixtures` lit une page de recherche par `ClientJiraLecture` (liste blanche), puis
l'anonymise avant toute écriture :

- l'hôte du site devient `https://jira.example.invalid` ;
- tout objet utilisateur (porteur d'`accountId`) devient le compte fictif `COMPTE_FICTIF` ;
- les items de changelog d'un champ utilisateur perdent leurs identifiants et noms réels ;
- `emailAddress` est supprimé, `nextPageToken` retiré (la page devient la dernière).

`verifier_sans_secret` contrôle ensuite le texte : hôte réel, adresse e-mail ou préfixe de
jeton Atlassian (`ATATT`) lèvent une `UsineErreur` qui nomme le motif, jamais la valeur, et
aucun fichier n'est écrit. Les fixtures écrites sont `direct_*` : les fixtures construites
(`source_*`, `recherche_*`, `bulkfetch_*`) ne sont jamais écrasées.
"""

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from usine.adaptateurs.jira_cloud.source import CHEMIN_RECHERCHE, champs_demandes, requete_jql
from usine.adaptateurs.jira_http import ClientJiraLecture
from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur

URL_FICTIVE = "https://jira.example.invalid"
"""Hôte des fixtures versionnées, à la place du site réel."""
COMPTE_FICTIF: Mapping[str, str] = {"accountId": "compte-fictif", "displayName": "Compte fictif"}
"""Remplaçant de tout objet utilisateur Jira."""
FICHIER_RECHERCHE = "direct_recherche_page_1.json"
"""Fixture de la recherche directe, distincte des fixtures construites."""

_CLES_SUPPRIMEES = frozenset({"emailAddress", "nextPageToken"})
_CHAMPS_UTILISATEUR = frozenset({"assignee", "reporter", "creator"})
_COURRIEL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_PREFIXE_JETON = "ATATT"


def _hote(url_site: str) -> str:
    hote = urlsplit(url_site).hostname
    if not hote:
        raise UsineErreur(f"config/jira.yaml : url_site : {url_site!r} : hôte illisible")
    return hote


def _remplacer_hote(texte: str, url_site: str) -> str:
    hote = _hote(url_site)
    motif = re.compile(rf"https?://{re.escape(hote)}(?::\d+)?", re.IGNORECASE)
    texte = motif.sub(URL_FICTIVE, texte)
    return re.sub(re.escape(hote), urlsplit(URL_FICTIVE).netloc, texte, flags=re.IGNORECASE)


def _item_utilisateur(item: Mapping[str, Any]) -> bool:
    return (
        "tmpFromAccountId" in item
        or "tmpToAccountId" in item
        or (item.get("fieldtype") == "jira" and item.get("field") in _CHAMPS_UTILISATEUR)
    )


def _anonymiser_item(item: Mapping[str, Any], url_site: str) -> dict[str, Any]:
    resultat: dict[str, Any] = {}
    for cle, valeur in item.items():
        if cle in {"from", "to", "tmpFromAccountId", "tmpToAccountId"} and valeur is not None:
            resultat[cle] = COMPTE_FICTIF["accountId"]
        elif cle in {"fromString", "toString"} and valeur is not None:
            resultat[cle] = COMPTE_FICTIF["displayName"]
        else:
            resultat[cle] = anonymiser(valeur, url_site)
    return resultat


def anonymiser(objet: Any, url_site: str) -> Any:
    """Copie anonymisée d'un objet JSON de Jira (voir le module) ; `objet` n'est pas modifié."""
    if isinstance(objet, str):
        return _remplacer_hote(objet, url_site)
    if isinstance(objet, list):
        return [anonymiser(element, url_site) for element in objet]
    if isinstance(objet, Mapping):
        if "accountId" in objet:
            return dict(COMPTE_FICTIF)
        if _item_utilisateur(objet):
            return _anonymiser_item(objet, url_site)
        resultat = {
            _remplacer_hote(str(cle), url_site): anonymiser(valeur, url_site)
            for cle, valeur in objet.items()
            if cle not in _CLES_SUPPRIMEES
        }
        if "nextPageToken" in objet and "isLast" in objet:
            resultat["isLast"] = True
        return resultat
    return objet


def verifier_sans_secret(texte: str, url_site: str) -> None:
    """Lève une `UsineErreur` si `texte` porte l'hôte réel, un e-mail ou un jeton Atlassian.

    Le message nomme le motif trouvé, jamais la valeur.
    """
    motifs: list[str] = []
    if _hote(url_site).lower() in texte.lower():
        motifs.append("hôte du site Jira réel")
    if _COURRIEL.search(texte):
        motifs.append("adresse e-mail")
    if _PREFIXE_JETON in texte:
        motifs.append(f"préfixe de jeton Atlassian ({_PREFIXE_JETON})")
    if motifs:
        raise UsineErreur(
            f"fixture Jira refusée : résidu sensible ({', '.join(motifs)}) ; aucun fichier écrit"
        )


def rafraichir_fixtures(
    client: ClientJiraLecture, config: ConfigJira, sortie: Path, nb_tickets: int
) -> Path:
    """Écrit `sortie/direct_recherche_page_1.json` : une page de recherche anonymisée.

    Une seule requête `POST search/jql` (`maxResults` = `nb_tickets`, `expand` changelog) ;
    `sortie` est créé s'il manque. Rend le chemin écrit.
    """
    if nb_tickets < 1:
        raise UsineErreur(f"--nb-tickets : au moins 1 ticket, pas {nb_tickets}")
    corps = {
        "jql": requete_jql(config),
        "fields": champs_demandes(config),
        "expand": "changelog",
        "maxResults": nb_tickets,
    }
    page = client.requete("POST", CHEMIN_RECHERCHE, corps=corps)
    texte = json.dumps(anonymiser(page, config.url_site), ensure_ascii=False, indent=2) + "\n"
    verifier_sans_secret(texte, config.url_site)
    chemin = sortie / FICHIER_RECHERCHE
    try:
        sortie.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise UsineErreur(f"{chemin} : écriture impossible ({exc.strerror or exc})") from exc
    return chemin
