"""Clients Jira : lecture à liste blanche (extraction) et écriture (injecteur) (AD-5).

`ClientJiraLecture` vérifie chaque requête contre `LISTE_BLANCHE_LECTURE` **avant** tout
envoi : un filtre « GET seulement » ne suffirait pas, puisque des lectures passent par POST
(`search/jql`, `changelog/bulkfetch`). `ClientJiraEcriture` n'a pas de liste blanche ; seule
la composition du générateur le construit, avec `JIRA_TOKEN_INJECTION` (garde structurelle :
`tests/unit/adaptateurs/jira_http/test_ecriture.py`).
"""

import re
import time
from collections.abc import Callable, Iterator, Mapping
from types import MappingProxyType, TracebackType
from typing import Any, Self

import httpx
from pydantic import SecretStr

from usine.adaptateurs.jira_http import pagination
from usine.adaptateurs.jira_http.transport import Authentification, Plateforme, TransportJira
from usine.contrats.config import ConfigJira
from usine.contrats.erreurs import UsineErreur

LISTE_BLANCHE_LECTURE: Mapping[Plateforme, frozenset[tuple[str, str]]] = MappingProxyType(
    {
        "cloud": frozenset(
            {
                ("GET", "/rest/api/3/search/jql"),
                ("POST", "/rest/api/3/search/jql"),
                ("POST", "/rest/api/3/search/approximate-count"),
                ("POST", "/rest/api/3/changelog/bulkfetch"),
                ("GET", "/rest/api/3/issue/{cle}"),
                ("GET", "/rest/api/3/issue/{cle}/changelog"),
                ("GET", "/rest/api/3/field"),
                ("GET", "/rest/api/3/serverInfo"),
                ("GET", "/rest/api/3/myself"),
            }
        ),
        "dc": frozenset(
            {
                ("GET", "/rest/api/2/search"),
                ("POST", "/rest/api/2/search"),
                ("GET", "/rest/api/2/issue/{cle}"),
                ("GET", "/rest/api/2/field"),
                ("GET", "/rest/api/2/serverInfo"),
                ("GET", "/rest/api/2/myself"),
            }
        ),
    }
)
"""Requêtes `(méthode, gabarit de chemin)` permises au client de lecture, par plateforme.

Un segment `{x}` accepte un segment `[A-Za-z0-9_.~-]+`, sauf `.` et `..`.
"""

_SEGMENT_VARIABLE = re.compile(r"[A-Za-z0-9_.~-]+")
_GABARIT_VARIABLE = re.compile(r"\{[a-z_]+\}")
_FRAGMENTS_INTERDITS = ("?", "#", "//", "%", "\\")


class RequeteJiraInterdite(UsineErreur):
    """Requête refusée par le client de lecture : hors de la liste blanche de sa plateforme."""


def _correspond(chemin: str, gabarit: str) -> bool:
    segments = chemin.split("/")
    attendus = gabarit.split("/")
    if len(segments) != len(attendus):
        return False
    for segment, attendu in zip(segments, attendus, strict=True):
        if _GABARIT_VARIABLE.fullmatch(attendu):
            if segment in {".", ".."} or not _SEGMENT_VARIABLE.fullmatch(segment):
                return False
        elif segment != attendu:
            return False
    return True


def requete_autorisee(plateforme: Plateforme, methode: str, chemin: str) -> bool:
    """Vrai si `methode chemin` figure dans la liste blanche de lecture de `plateforme`."""
    if not chemin.startswith("/rest/") or any(f in chemin for f in _FRAGMENTS_INTERDITS):
        return False
    if any(segment in {".", ".."} for segment in chemin.split("/")):
        return False
    methode = methode.upper()
    return any(
        m == methode and _correspond(chemin, gabarit)
        for m, gabarit in LISTE_BLANCHE_LECTURE[plateforme]
    )


class _ClientJira:
    """Socle commun : délégation au transport et fermeture."""

    def __init__(self, transport: TransportJira) -> None:
        self._transport = transport

    @property
    def plateforme(self) -> Plateforme:
        """Plateforme Jira du transport."""
        return self._transport.plateforme

    def _verifier(self, methode: str, chemin: str) -> None:
        """Contrôle avant envoi ; le client d'écriture n'en fait aucun."""

    def requete(
        self,
        methode: str,
        chemin: str,
        *,
        params: Mapping[str, Any] | None = None,
        corps: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Envoie une requête et rend l'objet JSON de la réponse."""
        self._verifier(methode, chemin)
        return self._transport.requete(methode, chemin, params=params, corps=corps)

    def paginer_par_jeton(
        self,
        methode: str,
        chemin: str,
        cle: str,
        *,
        params: Mapping[str, Any] | None = None,
        corps: Mapping[str, Any] | None = None,
    ) -> Iterator[Any]:
        """Éléments de `cle` sur toutes les pages `nextPageToken` (contrôle dès l'appel)."""
        self._verifier(methode, chemin)
        return pagination.paginer_par_jeton(
            self.requete, methode, chemin, cle, params=params, corps=corps
        )

    def paginer_par_position(
        self,
        chemin: str,
        cle: str,
        *,
        params: Mapping[str, Any] | None = None,
        taille_page: int = pagination.TAILLE_PAGE,
    ) -> Iterator[Any]:
        """Éléments de `cle` sur toutes les pages `startAt` (contrôle dès l'appel)."""
        self._verifier("GET", chemin)
        return pagination.paginer_par_position(
            self.requete, chemin, cle, params=params, taille_page=taille_page
        )

    def fermer(self) -> None:
        """Ferme le transport."""
        self._transport.fermer()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        type_exc: type[BaseException] | None,
        exc: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self.fermer()

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._transport!r})"


class ClientJiraLecture(_ClientJira):
    """Client de l'extraction : refuse avant envoi toute requête hors liste blanche."""

    def _verifier(self, methode: str, chemin: str) -> None:
        if not requete_autorisee(self.plateforme, methode, chemin):
            raise RequeteJiraInterdite(
                f"Jira {methode.upper()} {chemin} : requête interdite au client de lecture"
                f" ({self.plateforme}), hors liste blanche ; aucune requête envoyée"
            )


class ClientJiraEcriture(_ClientJira):
    """Client de l'injecteur (`JIRA_TOKEN_INJECTION`), sans liste blanche."""


def construire_client_lecture(
    config: ConfigJira,
    *,
    email: str | None,
    jeton_lecture: SecretStr | None,
    pat: SecretStr | None,
    attendre: Callable[[float], None] = time.sleep,
    transport_http: httpx.BaseTransport | None = None,
) -> ClientJiraLecture:
    """Client de lecture de la plateforme `config.mode` (Cloud : e-mail et jeton ; DC : PAT)."""
    if config.mode == "cloud":
        authentification = Authentification.cloud(
            email, jeton_lecture, variable_jeton="JIRA_TOKEN_LECTURE"
        )
    else:
        authentification = Authentification.dc(pat)
    transport = TransportJira(
        config.url_site,
        authentification,
        config.tentatives_max,
        attendre=attendre,
        transport_http=transport_http,
    )
    return ClientJiraLecture(transport)


def construire_client_ecriture(
    config: ConfigJira,
    *,
    email: str | None,
    jeton_injection: SecretStr | None,
    attendre: Callable[[float], None] = time.sleep,
    transport_http: httpx.BaseTransport | None = None,
) -> ClientJiraEcriture:
    """Client d'écriture de l'injecteur, Jira Cloud seulement (FR-5)."""
    if config.mode != "cloud":
        raise UsineErreur(
            f"config/jira.yaml : mode : {config.mode!r} : le client d'écriture (injection)"
            " ne vise que Jira Cloud (mode: cloud)"
        )
    authentification = Authentification.cloud(
        email, jeton_injection, variable_jeton="JIRA_TOKEN_INJECTION"
    )
    transport = TransportJira(
        config.url_site,
        authentification,
        config.tentatives_max,
        attendre=attendre,
        transport_http=transport_http,
    )
    return ClientJiraEcriture(transport)
