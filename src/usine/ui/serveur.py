"""Application FastAPI de l'UI web : pages statiques, vues JSON du cadre (AD-25, Story 7.13).

Seul module qui crée l'application. Il ne reçoit ses services que de `ui/cli.py`, racine de
composition (AD-1) : ici, la lecture du manifeste du Passage affiché, `lire_manifeste(repli)`.
Chaque écran est une page HTML de `statique/`, sans moteur de gabarits ; le script `cadre.js`
charge `/api/cadre` (Passage publié, mode, bandeau de repli). Polices, CSS et script sont
servis ici : aucune requête ne sort (NFR-12). Le serveur n'écoute que `127.0.0.1` (voir `cli`).

Le mode vit dans le processus serveur et ne change jamais seul (AD-19) : il est fixé au
démarrage par `USINE_MODE_REPLI`.
"""

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from usine.contrats.erreurs import UsineErreur
from usine.contrats.passage import ManifestePassage
from usine.ui.vues import VueCadre, vue_cadre

REPERTOIRE_STATIQUE = Path(__file__).resolve().with_name("statique")
"""Pages HTML, feuille de style, script et polices servis en local."""

HOTE = "127.0.0.1"
"""Seule adresse d'écoute : l'interface n'est jamais joignable depuis le réseau (AD-25)."""

PAGES: dict[str, str] = {
    "/": "carte-meteo.html",
    "/entites/{entite}": "detail-entite.html",
    "/chaine": "chaine.html",
    "/agent": "agent.html",
    "/avant-apres": "avant-apres.html",
    "/pseudonymisation": "pseudonymisation.html",
    "/outillage": "outillage.html",
}
"""Route de chaque écran (EXPERIENCE.md, Information Architecture) et sa page statique."""

LireManifeste = Callable[[bool], ManifestePassage | None]
"""Manifeste du Passage affiché dans le mode donné (`True` : Mode repli), `None` s'il n'y en a pas ;
lève `UsineErreur` (ou `OSError`) si la lecture est impossible."""


def creer_application(*, repli: bool, lire_manifeste: LireManifeste) -> FastAPI:
    """Application des sept écrans ; `repli` est le mode imposé au démarrage (AD-19)."""
    application = FastAPI(
        title="Usine de migration", docs_url=None, redoc_url=None, openapi_url=None
    )
    application.mount("/statique", StaticFiles(directory=REPERTOIRE_STATIQUE), name="statique")

    def cadre() -> VueCadre:
        try:
            return vue_cadre(repli=repli, manifeste=lire_manifeste(repli), erreur=None)
        except UsineErreur as exc:
            return vue_cadre(repli=repli, manifeste=None, erreur=str(exc))
        except OSError as exc:  # répertoire illisible : bandeau d'erreur, pas une 500
            erreur = f"Lecture du Passage impossible : {exc}"
            return vue_cadre(repli=repli, manifeste=None, erreur=erreur)

    application.add_api_route("/api/cadre", cadre, response_model=VueCadre)

    for route, fichier in PAGES.items():
        application.add_api_route(
            route, _page(REPERTOIRE_STATIQUE / fichier), include_in_schema=False
        )
    return application


def _page(chemin: Path) -> Callable[..., FileResponse]:
    def servir() -> FileResponse:
        return FileResponse(chemin, media_type="text/html; charset=utf-8")

    return servir
