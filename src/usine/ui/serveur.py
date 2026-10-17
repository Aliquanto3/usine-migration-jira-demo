"""Application FastAPI de l'UI web : pages statiques, vues JSON du cadre (AD-25, Story 7.13).

Seul module qui crée l'application. Il ne reçoit ses services que de `ui/cli.py`, racine de
composition (AD-1) : ici, la lecture du manifeste du Passage affiché, `lire_manifeste(repli)`.
Chaque écran est une page HTML de `statique/`, sans moteur de gabarits ; le script `cadre.js`
charge `/api/cadre` (Passage publié, mode, bandeau de repli). Polices, CSS et script sont
servis ici : aucune requête ne sort (NFR-12). Le serveur n'écoute que `127.0.0.1` (voir `cli`).

Le mode vit dans le processus serveur et ne change jamais seul (AD-19) : il est fixé au
démarrage par `USINE_MODE_REPLI`.
"""

import html
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, get_args

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from usine.contrats.erreurs import UsineErreur
from usine.contrats.passage import ManifestePassage
from usine.ui.carte import (
    AUCUN_PASSAGE,
    MIME_LIVRABLES,
    LectureVueCarte,
    entites_triees,
    nom_fichier_livrable,
    url_detail,
    vue_carte,
    vue_carte_erreur,
    vue_carte_message,
)
from usine.ui.detail import LectureDetail, vue_detail, vue_detail_erreur, vue_detail_message
from usine.ui.vues import (
    NomLivrable,
    VueCadre,
    VueCarte,
    VueDetail,
    VueLien,
    vue_cadre,
)

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


class LectureEcrans(LectureVueCarte, LectureDetail, Protocol):
    """Lectures de la `Consultation` que les écrans Carte et Détail utilisent."""


LireConsultation = Callable[[bool], LectureEcrans | None]
"""`Consultation` du Passage affiché dans le mode donné (`True` : Mode repli), `None` s'il n'y
en a pas ; lève `UsineErreur` (ou `OSError`) si la lecture est impossible."""

LIENS_CARTE = VueLien(libelle="← Carte météo", url="/")
LIEN_CHAINE = VueLien(libelle="Lancer la Chaîne", url="/chaine")


def creer_application(
    *, repli: bool, lire_manifeste: LireManifeste, lire_consultation: LireConsultation
) -> FastAPI:
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

    def lire() -> LectureEcrans | None:
        return lire_consultation(repli)

    def carte() -> VueCarte:
        try:
            consultation = lire()
            if consultation is None:
                return vue_carte_message(AUCUN_PASSAGE, LIEN_CHAINE)
            return vue_carte(consultation)
        except UsineErreur as exc:
            return vue_carte_erreur(str(exc))
        except OSError as exc:
            return vue_carte_erreur(f"Lecture du Passage impossible : {exc}")

    application.add_api_route("/api/carte", carte, response_model=VueCarte)

    def detail(entite: str, palier: str | None = None) -> VueDetail:
        try:
            consultation = lire()
            if consultation is None:
                return vue_detail_message(AUCUN_PASSAGE).model_copy(
                    update={"lien_message": LIEN_CHAINE}
                )
            return vue_detail(consultation, entite, 1 if palier == "1" else 2)
        except UsineErreur as exc:
            return vue_detail_erreur(str(exc))
        except OSError as exc:
            return vue_detail_erreur(f"Lecture du Passage impossible : {exc}")

    application.add_api_route("/api/entites/{entite}", detail, response_model=VueDetail)

    def premiere_entite() -> RedirectResponse:
        """Navigation « Détail d'une Entité » : première Entité du Tableau des Entités."""
        try:
            consultation = lire()
            meteos = entites_triees(consultation.meteo()) if consultation else []
        except (UsineErreur, OSError):
            meteos = []
        cible = url_detail(meteos[0].entite) if meteos else "/"
        return RedirectResponse(cible, status_code=307)

    application.add_api_route("/entites", premiere_entite, include_in_schema=False)

    def livrable(nom: str) -> Response:
        if nom not in get_args(NomLivrable):
            raise HTTPException(status_code=404)
        nom_valide: NomLivrable = "rapport_xlsx" if nom == "rapport_xlsx" else "rapport_pptx"
        fichier = nom
        try:
            consultation = lire()
            if consultation is None:
                return _page_erreur(
                    f"Le livrable {nom} n'est pas disponible : {AUCUN_PASSAGE}", 404
                )
            fichier = nom_fichier_livrable(nom_valide, consultation.manifeste().date_arrete)
            contenu = consultation.livrable(nom_valide)
        except (UsineErreur, OSError) as exc:
            return _page_erreur(f"Lecture du livrable {fichier} impossible : {exc}", 500)
        if contenu is None:
            return _page_erreur(f"Le livrable {fichier} n'a pas été généré pour ce Passage.", 404)
        return Response(
            contenu,
            media_type=MIME_LIVRABLES[nom_valide],
            headers={"Content-Disposition": f'attachment; filename="{fichier}"'},
        )

    application.add_api_route(
        "/livrables/{nom}", livrable, methods=["GET", "HEAD"], include_in_schema=False
    )

    for route, fichier in PAGES.items():
        application.add_api_route(
            route, _page(REPERTOIRE_STATIQUE / fichier), include_in_schema=False
        )
    return application


def _page(chemin: Path) -> Callable[..., FileResponse]:
    def servir() -> FileResponse:
        return FileResponse(chemin, media_type="text/html; charset=utf-8")

    return servir


def _page_erreur(message: str, statut: int) -> HTMLResponse:
    """Page d'erreur d'un téléchargement : nomme le fichier et renvoie à la carte."""
    texte = html.escape(message)
    corps = f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Livrable indisponible · Usine de migration</title>
  <link rel="icon" href="data:,">
  <link rel="stylesheet" href="/statique/cadre.css">
</head>
<body>
  <main class="contenu page-erreur">
    <h1 id="titre-ecran">Livrable indisponible</h1>
    <p class="bandeau bandeau--erreur" role="alert">{texte}</p>
    <p><a href="/">{html.escape(LIENS_CARTE.libelle)}</a></p>
  </main>
</body>
</html>
"""
    return HTMLResponse(corps, status_code=statut)
