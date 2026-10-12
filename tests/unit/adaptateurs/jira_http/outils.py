"""Outils des tests du transport Jira : serveur simulé (`httpx.MockTransport`) et configuration."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from usine.config import charger_yaml
from usine.contrats.config import ConfigJira

RACINE = Path(__file__).resolve().parents[4]
FIXTURES = RACINE / "tests" / "fixtures"
URL_SITE = "https://jira.example.invalid"


def fixture(nom: str) -> dict[str, Any]:
    """Réponse enregistrée `tests/fixtures/<nom>`."""
    donnees: dict[str, Any] = json.loads((FIXTURES / nom).read_text(encoding="utf-8"))
    return donnees


def config_jira(mode: str = "cloud", **modifications: Any) -> ConfigJira:
    """`config/jira.yaml` du dépôt, mode et clés éventuellement remplacés."""
    config = charger_yaml(RACINE / "config" / "jira.yaml", ConfigJira)
    return config.model_copy(update={"mode": mode, "url_site": URL_SITE, **modifications})


class ServeurSimule:
    """Rend des réponses dans l'ordre et enregistre les requêtes reçues."""

    def __init__(self, *reponses: httpx.Response | Callable[[httpx.Request], httpx.Response]):
        self._reponses = list(reponses)
        self.requetes: list[httpx.Request] = []

    def __call__(self, requete: httpx.Request) -> httpx.Response:
        self.requetes.append(requete)
        if not self._reponses:
            raise AssertionError(f"requête inattendue : {requete.method} {requete.url}")
        reponse = self._reponses.pop(0)
        return reponse(requete) if callable(reponse) else reponse

    @property
    def transport(self) -> httpx.MockTransport:
        """Transport httpx à passer au client."""
        return httpx.MockTransport(self)


class Attentes:
    """Remplace `time.sleep` : enregistre les attentes sans attendre."""

    def __init__(self) -> None:
        self.durees: list[float] = []

    def __call__(self, duree: float) -> None:
        self.durees.append(duree)


def corps_json(requete: httpx.Request) -> Any:
    """Corps JSON d'une requête enregistrée."""
    return json.loads(requete.content)
