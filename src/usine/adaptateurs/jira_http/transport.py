"""Transport HTTP Jira commun : authentification, reprise sur 429, erreurs (AD-5).

Toute anomalie devient une `UsineErreur` qui nomme la méthode, le chemin et, le cas échéant,
le statut HTTP. Ni le corps de la réponse ni un secret n'est recopié dans un message. Les
redirections ne sont pas suivies : l'en-tête d'authentification ne part jamais vers un autre
hôte.
"""

import base64
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from types import TracebackType
from typing import Any, Literal, Self

import httpx
from pydantic import SecretStr

from usine.contrats.erreurs import UsineErreur

ATTENTE_MAX_SECONDES = 120.0
"""Plafond d'une attente avant nouvelle tentative, quel que soit `Retry-After`."""

DELAI_RESEAU_SECONDES = 30.0
"""Délai maximal d'une requête (connexion, lecture, écriture)."""

type Plateforme = Literal["cloud", "dc"]


def _present(valeur: SecretStr | None) -> bool:
    return valeur is not None and bool(valeur.get_secret_value().strip())


class Authentification:
    """En-tête `Authorization` d'une plateforme Jira ; sa valeur n'apparaît dans aucun `repr`."""

    __slots__ = ("_en_tete", "_plateforme")

    def __init__(self, plateforme: Plateforme, en_tete: SecretStr) -> None:
        self._plateforme = plateforme
        self._en_tete = en_tete

    @classmethod
    def cloud(
        cls,
        email: str | None,
        jeton: SecretStr | None,
        *,
        variable_jeton: str = "JIRA_TOKEN_LECTURE",
    ) -> Self:
        """Jira Cloud : `Basic base64(email:jeton)`.

        `variable_jeton` est la variable d'environnement nommée si le jeton manque
        (`JIRA_TOKEN_LECTURE` pour la lecture, `JIRA_TOKEN_INJECTION` pour l'écriture).
        """
        manquantes = []
        if email is None or not email.strip():
            manquantes.append("JIRA_EMAIL")
        if not _present(jeton):
            manquantes.append(variable_jeton)
        if manquantes or jeton is None or email is None:
            raise UsineErreur(
                "authentification Jira Cloud impossible : variable d'environnement absente :"
                f" {', '.join(manquantes)}"
            )
        brut = f"{email.strip()}:{jeton.get_secret_value().strip()}".encode()
        return cls("cloud", SecretStr(f"Basic {base64.b64encode(brut).decode('ascii')}"))

    @classmethod
    def dc(cls, pat: SecretStr | None) -> Self:
        """Jira Data Center : jeton d'accès personnel en `Bearer`."""
        if pat is None or not _present(pat):
            raise UsineErreur(
                "authentification Jira Data Center impossible : variable d'environnement"
                " absente : JIRA_DC_PAT"
            )
        return cls("dc", SecretStr(f"Bearer {pat.get_secret_value().strip()}"))

    @property
    def plateforme(self) -> Plateforme:
        """Plateforme Jira visée par cette authentification."""
        return self._plateforme

    def en_tete(self) -> str:
        """Valeur de l'en-tête `Authorization` (secret : ne jamais la journaliser)."""
        return self._en_tete.get_secret_value()

    def __repr__(self) -> str:
        return f"Authentification({self._plateforme}, **********)"


def _attente_retry_after(valeur: str | None) -> float | None:
    """Attente demandée par `Retry-After` (secondes ou date HTTP), ou `None` si illisible."""
    if valeur is None:
        return None
    valeur = valeur.strip()
    if valeur.isascii() and valeur.isdigit():
        return float(valeur)
    try:
        echeance = parsedate_to_datetime(valeur)
    except (TypeError, ValueError, IndexError):
        return None
    if echeance.tzinfo is None:
        echeance = echeance.replace(tzinfo=UTC)
    return max(0.0, (echeance - datetime.now(UTC)).total_seconds())


class TransportJira:
    """Envoie les requêtes REST à un site Jira et rend la réponse JSON (objet) décodée."""

    def __init__(
        self,
        url_site: str,
        authentification: Authentification,
        tentatives_max: int,
        *,
        attendre: Callable[[float], None] = time.sleep,
        transport_http: httpx.BaseTransport | None = None,
    ) -> None:
        if tentatives_max < 1:
            raise UsineErreur(f"tentatives_max : au moins 1 attendu, reçu {tentatives_max}")
        self._authentification = authentification
        self._tentatives_max = tentatives_max
        self._attendre = attendre
        self._url_site = url_site.rstrip("/")
        self._client = httpx.Client(
            base_url=self._url_site,
            transport=transport_http,
            follow_redirects=False,
            timeout=DELAI_RESEAU_SECONDES,
            headers={"Accept": "application/json"},
        )

    @property
    def plateforme(self) -> Plateforme:
        """Plateforme de l'authentification."""
        return self._authentification.plateforme

    def requete(
        self,
        methode: str,
        chemin: str,
        *,
        params: Mapping[str, Any] | None = None,
        corps: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Envoie `methode chemin`, reprend sur 429, et rend l'objet JSON de la réponse.

        Une réponse sans contenu (204, corps vide) rend `{}`. Un chemin qui n'est pas relatif
        au site (URL absolue, `//hôte`) est refusé avant envoi : le jeton ne quitte pas le site.
        """
        contexte, reponse = self._envoyer(methode, chemin, params, corps)
        donnees = self._decoder(contexte, reponse)
        if donnees is None:
            return {}
        if not isinstance(donnees, dict):
            raise UsineErreur(
                f"{contexte} : statut HTTP {reponse.status_code}, objet JSON attendu,"
                f" reçu {type(donnees).__name__}"
            )
        return donnees

    def requete_liste(
        self,
        methode: str,
        chemin: str,
        *,
        params: Mapping[str, Any] | None = None,
        corps: Mapping[str, Any] | None = None,
    ) -> list[Any]:
        """Comme `requete`, pour un point d'accès qui rend un tableau JSON (`/field`).

        Une réponse vide, ou qui n'est pas un tableau, lève une `UsineErreur`.
        """
        contexte, reponse = self._envoyer(methode, chemin, params, corps)
        donnees = self._decoder(contexte, reponse)
        if not isinstance(donnees, list):
            recu = "une réponse vide" if donnees is None else type(donnees).__name__
            raise UsineErreur(
                f"{contexte} : statut HTTP {reponse.status_code}, tableau JSON attendu, reçu {recu}"
            )
        return donnees

    def _envoyer(
        self,
        methode: str,
        chemin: str,
        params: Mapping[str, Any] | None,
        corps: Mapping[str, Any] | None,
    ) -> tuple[str, httpx.Response]:
        """Envoie la requête et reprend sur 429 ; rend le contexte des erreurs et la réponse."""
        methode = methode.upper()
        contexte = f"Jira {methode} {chemin}"
        if not chemin.startswith("/") or chemin.startswith("//") or "://" in chemin:
            raise UsineErreur(
                f"{contexte} : chemin relatif au site attendu (« /… ») ; aucune requête envoyée"
            )
        for tentative in range(1, self._tentatives_max + 1):
            try:
                reponse = self._client.request(
                    methode,
                    chemin,
                    params=params,
                    json=dict(corps) if corps is not None else None,
                    headers={"Authorization": self._authentification.en_tete()},
                )
            except httpx.InvalidURL:
                raise UsineErreur(
                    f"{contexte} : chemin invalide ; aucune requête envoyée"
                ) from None
            except httpx.RequestError as exc:
                # `from None` : l'exception httpx porte la requête, donc l'en-tête Authorization.
                raise UsineErreur(f"{contexte} : erreur réseau ({type(exc).__name__})") from None
            if reponse.status_code == 429:
                if tentative == self._tentatives_max:
                    raise UsineErreur(
                        f"{contexte} : statut HTTP 429 après {self._tentatives_max} tentatives"
                    )
                demande = _attente_retry_after(reponse.headers.get("Retry-After"))
                # Exposant borné : `2.0 ** 1024` déborde ; le plafond est atteint dès 2 ** 7.
                exponentielle = 2.0 ** min(tentative - 1, 16)
                attente = demande if demande is not None else exponentielle
                self._attendre(min(attente, ATTENTE_MAX_SECONDES))
                continue
            return contexte, reponse
        raise AssertionError("inaccessible : la boucle rend ou lève")  # pragma: no cover

    @staticmethod
    def _decoder(contexte: str, reponse: httpx.Response) -> object:
        """JSON décodé d'une réponse 2xx ; `None` si elle est sans contenu."""
        statut = reponse.status_code
        if 300 <= statut < 400:
            raise UsineErreur(f"{contexte} : statut HTTP {statut} (redirection non suivie)")
        if not 200 <= statut < 300:
            precision = {401: " (authentification refusée)", 403: " (accès refusé)"}.get(statut, "")
            raise UsineErreur(f"{contexte} : statut HTTP {statut}{precision}")
        if statut == 204 or not reponse.content.strip():
            return None
        try:
            donnees: object = reponse.json()
        except ValueError:
            raise UsineErreur(f"{contexte} : statut HTTP {statut}, réponse non JSON") from None
        return donnees

    def fermer(self) -> None:
        """Ferme les connexions HTTP."""
        self._client.close()

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
        return f"TransportJira({self._url_site!r}, {self._authentification!r})"
