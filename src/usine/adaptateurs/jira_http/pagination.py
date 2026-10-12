"""Pagination Jira : par jeton (Cloud) et par position (Data Center), séquentielle (AD-5).

Les deux fonctions sont des itérateurs d'éléments : les pages sont demandées une à une, au
fil de la consommation, jamais en parallèle.
"""

from collections.abc import Iterator, Mapping
from typing import Any, Protocol

from usine.contrats.erreurs import UsineErreur

TAILLE_PAGE = 100
"""Taille de page demandée par défaut ; le serveur peut la plafonner."""


class Requeteur(Protocol):
    """Fonction d'envoi d'une requête Jira (transport ou client) rendant l'objet JSON."""

    def __call__(
        self,
        methode: str,
        chemin: str,
        *,
        params: Mapping[str, Any] | None = None,
        corps: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]: ...


def _elements(page: dict[str, Any], cle: str, contexte: str) -> list[Any]:
    elements = page.get(cle)
    if not isinstance(elements, list):
        raise UsineErreur(f"{contexte} : réponse sans liste {cle!r}")
    return elements


def paginer_par_jeton(
    requete: Requeteur,
    methode: str,
    chemin: str,
    cle: str,
    *,
    params: Mapping[str, Any] | None = None,
    corps: Mapping[str, Any] | None = None,
) -> Iterator[Any]:
    """Éléments de `cle` sur toutes les pages, en suivant `nextPageToken` (Jira Cloud).

    Le jeton part dans le corps pour un POST, dans les paramètres sinon. La dernière page n'a
    pas de jeton (ou porte `isLast: true`) ; une page courte n'arrête pas la pagination. Un
    jeton déjà vu lève une `UsineErreur` (boucle de pagination).
    """
    methode = methode.upper()
    contexte = f"Jira {methode} {chemin}"
    jeton: str | None = None
    vus: set[str] = set()
    while True:
        params_page = dict(params) if params is not None else None
        corps_page = dict(corps) if corps is not None else None
        if jeton is not None:
            if methode == "POST":
                corps_page = {**(corps_page or {}), "nextPageToken": jeton}
            else:
                params_page = {**(params_page or {}), "nextPageToken": jeton}
        page = requete(methode, chemin, params=params_page, corps=corps_page)
        yield from _elements(page, cle, contexte)
        suivant = page.get("nextPageToken")
        if suivant is None or suivant == "" or page.get("isLast") is True:
            return
        if not isinstance(suivant, str):
            raise UsineErreur(f"{contexte} : nextPageToken illisible ({type(suivant).__name__})")
        if suivant in vus:
            raise UsineErreur(f"{contexte} : boucle de pagination (nextPageToken déjà reçu)")
        vus.add(suivant)
        jeton = suivant


def _entier(valeur: object) -> int | None:
    return valeur if isinstance(valeur, int) and not isinstance(valeur, bool) else None


def paginer_par_position(
    requete: Requeteur,
    chemin: str,
    cle: str,
    *,
    params: Mapping[str, Any] | None = None,
    taille_page: int = TAILLE_PAGE,
) -> Iterator[Any]:
    """Éléments de `cle` sur toutes les pages `startAt`/`maxResults` (Jira Data Center, GET).

    `startAt` avance du nombre d'éléments reçus, pas du `maxResults` demandé : le serveur peut
    plafonner la page. Arrêt sur `isLast: true`, sur `startAt >= total` ou sur une page vide.
    """
    if taille_page < 1:
        raise UsineErreur(f"taille_page : au moins 1 attendu, reçu {taille_page}")
    contexte = f"Jira GET {chemin}"
    debut = 0
    while True:
        params_page = {**(params or {}), "startAt": debut, "maxResults": taille_page}
        page = requete("GET", chemin, params=params_page)
        elements = _elements(page, cle, contexte)
        yield from elements
        if not elements or page.get("isLast") is True:
            return
        debut += len(elements)
        total = _entier(page.get("total"))
        if total is not None and debut >= total:
            return
