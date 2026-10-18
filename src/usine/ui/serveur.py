"""Application FastAPI de l'UI web : pages statiques, vues JSON du cadre (AD-25, Story 7.13).

Seul module qui crée l'application. Il ne reçoit ses services que de `ui/cli.py`, racine de
composition (AD-1) : ici, la lecture du manifeste du Passage affiché, `lire_manifeste(repli)`.
Chaque écran est une page HTML de `statique/`, sans moteur de gabarits ; le script `cadre.js`
charge `/api/cadre` (Passage publié, mode, bandeau de repli). Polices, CSS et script sont
servis ici : aucune requête ne sort (NFR-12). Le serveur n'écoute que `127.0.0.1` (voir `cli`).

Le mode vit dans le processus serveur et ne change jamais seul (AD-19) : il est fixé au
démarrage par `USINE_MODE_REPLI` et ne change que par `POST /api/mode`, sur clic du Pilote.
Seules deux routes `POST` changent un état (Chaîne, mode) ; une troisième, la question à
l'Agent, appelle le LLM : aucune ne touche un Passage ni Jira.
"""

import html
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Literal, Protocol, get_args
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from usine.contrats.erreurs import UsineErreur
from usine.contrats.passage import ManifestePassage
from usine.ui import agent as agent_textes
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
from usine.ui.chaine import MOTIF_MODE_EN_COURS, GestionChaine, LancementRefuse
from usine.ui.detail import LectureDetail, vue_detail, vue_detail_erreur, vue_detail_message
from usine.ui.ecrans import (
    MODE_REPLI_SANS_LLM,
    SERVICES_ABSENTS,
    GardeSession,
    LectureEcransAgent,
    ServicesEcrans,
    SessionIndisponible,
    vue_agent,
    vue_agent_erreur,
    vue_avant_apres,
    vue_avant_apres_erreur,
    vue_outillage,
    vue_outillage_erreur,
    vue_pseudonymisation,
    vue_pseudonymisation_erreur,
    vue_pseudonymisation_message,
    vue_reponse_agent,
)
from usine.ui.vues import (
    DemandeMode,
    DemandeQuestion,
    NomLivrable,
    Periode,
    VueAgent,
    VueAvantApres,
    VueCadre,
    VueCarte,
    VueChaine,
    VueDetail,
    VueLien,
    VueOutillage,
    VuePseudonymisation,
    VueReponseAgent,
    vue_cadre,
)

REPERTOIRE_STATIQUE = Path(__file__).resolve().with_name("statique")
"""Pages HTML, feuille de style, script et polices servis en local."""

HOTE = "127.0.0.1"
"""Seule adresse d'écoute : l'interface n'est jamais joignable depuis le réseau (AD-25)."""

HOTES_AUTORISES = (HOTE, "localhost")
"""Seuls en-têtes `Host` acceptés (quel que soit le port) : une page tierce qui ferait pointer
son nom de domaine sur `127.0.0.1` (DNS rebinding) reçoit 400 sur toutes les routes."""

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


class LectureEcrans(LectureVueCarte, LectureDetail, LectureEcransAgent, Protocol):
    """Lectures de la `Consultation` que les écrans Carte et Détail utilisent."""


LireConsultation = Callable[[bool], LectureEcrans | None]
"""`Consultation` du Passage affiché dans le mode donné (`True` : Mode repli), `None` s'il n'y
en a pas ; lève `UsineErreur` (ou `OSError`) si la lecture est impossible."""

LIENS_CARTE = VueLien(libelle="← Carte météo", url="/")
LIEN_CHAINE = VueLien(libelle="Lancer la Chaîne", url="/chaine")
SEULEMENT_REPLI = "Réponses enregistrées : Mode repli seulement."


class _Mode:
    """Mode courant du processus serveur : fixé au démarrage, changé par `POST /api/mode` seul."""

    def __init__(self, repli: bool) -> None:
        self.repli = repli


def _meme_origine(request: Request) -> None:
    """Refuse une écriture venue d'une autre origine (une page web tierce ouverte sur le poste).

    Le `Host` est déjà limité à `HOTES_AUTORISES` ; un `Origin` présent doit nommer ce même
    hôte et ce même port (`null`, autre port ou autre nom : 403).
    """
    origine = request.headers.get("origin")
    if origine is None:
        return
    parties = urlsplit(origine)
    if parties.hostname not in HOTES_AUTORISES or parties.netloc != request.headers.get("host"):
        raise HTTPException(status_code=403, detail="Origine refusée.")


def creer_application(
    *,
    repli: bool,
    lire_manifeste: LireManifeste,
    lire_consultation: LireConsultation,
    chaine: GestionChaine | None = None,
    services: ServicesEcrans | None = None,
) -> FastAPI:
    """Application des sept écrans ; `repli` est le mode imposé au démarrage (AD-19).

    `chaine` gère le lancement de `usine rapport` (fourni par `ui/cli.py`) ; sans elle, la
    Chaîne ne peut pas être lancée (racine absente). `services` fournit les lectures et la
    session de l'Agent des écrans Agent, Avant / après, Pseudonymisation et Outillage.
    """
    application = FastAPI(
        title="Usine de migration", docs_url=None, redoc_url=None, openapi_url=None
    )
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=list(HOTES_AUTORISES))
    application.mount("/statique", StaticFiles(directory=REPERTOIRE_STATIQUE), name="statique")
    mode = _Mode(repli)
    ecriture = threading.Lock()  # bascule du mode et lancement : jamais l'un pendant l'autre
    gestion = chaine if chaine is not None else GestionChaine(None)

    def cadre() -> VueCadre:
        repli = mode.repli
        try:
            return vue_cadre(repli=repli, manifeste=lire_manifeste(repli), erreur=None)
        except UsineErreur as exc:
            return vue_cadre(repli=repli, manifeste=None, erreur=str(exc))
        except OSError as exc:  # répertoire illisible : bandeau d'erreur, pas une 500
            erreur = f"Lecture du Passage impossible : {exc}"
            return vue_cadre(repli=repli, manifeste=None, erreur=erreur)

    application.add_api_route("/api/cadre", cadre, response_model=VueCadre)

    def changer_mode(demande: DemandeMode, request: Request) -> VueCadre:
        """Bascule explicite du mode (AD-19) ; refusée tant qu'une Chaîne tourne."""
        _meme_origine(request)
        with ecriture:
            if gestion.en_cours():
                raise HTTPException(status_code=409, detail=MOTIF_MODE_EN_COURS)
            mode.repli = demande.mode == "repli"
        return cadre()

    application.add_api_route("/api/mode", changer_mode, methods=["POST"], response_model=VueCadre)

    def vue_chaine() -> VueChaine:
        try:
            manifeste = lire_manifeste(mode.repli)
        except (UsineErreur, OSError):  # le bandeau d'erreur du cadre nomme la cause
            manifeste = None
        return gestion.vue(mode.repli, manifeste)

    application.add_api_route("/api/chaine", vue_chaine, response_model=VueChaine)

    def lancer_chaine(request: Request) -> VueChaine:
        """Démarre `usine rapport` ; une Chaîne à la fois (409 sinon)."""
        _meme_origine(request)
        with ecriture:
            try:
                gestion.lancer(mode.repli)
            except LancementRefuse as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        return vue_chaine()

    application.add_api_route(
        "/api/chaine", lancer_chaine, methods=["POST"], response_model=VueChaine, status_code=202
    )

    def lire() -> LectureEcrans | None:
        return lire_consultation(mode.repli)

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

    _ajouter_ecrans(application, mode, lire, services)

    for route, fichier in PAGES.items():
        application.add_api_route(
            route, _page(REPERTOIRE_STATIQUE / fichier), include_in_schema=False
        )
    return application


def _ajouter_ecrans(
    application: FastAPI,
    mode: _Mode,
    lire: Callable[[], LectureEcrans | None],
    services: ServicesEcrans | None,
) -> None:
    """Routes des écrans Agent, Avant / après, Pseudonymisation et Outillage (Story 7.16)."""
    garde = None if services is None else GardeSession(services.session_agent)

    def refus_lecture(exc: UsineErreur | OSError) -> str:
        return (
            str(exc) if isinstance(exc, UsineErreur) else f"Lecture du Passage impossible : {exc}"
        )

    def vue_ecran_agent() -> VueAgent:
        repli = mode.repli
        if services is None:
            return vue_agent_erreur(repli, SERVICES_ABSENTS)
        try:
            return vue_agent(repli=repli, consultation=lire(), services=services)
        except (UsineErreur, OSError) as exc:
            return vue_agent_erreur(repli, refus_lecture(exc))

    application.add_api_route("/api/agent", vue_ecran_agent, response_model=VueAgent)

    def poser_question(demande: DemandeQuestion, request: Request) -> VueReponseAgent:
        """Question à l'Agent, par la session existante ; Mode réel seulement (AD-24)."""
        _meme_origine(request)
        if services is None or garde is None:
            raise HTTPException(status_code=503, detail=SERVICES_ABSENTS)
        if mode.repli:
            raise HTTPException(status_code=409, detail=MODE_REPLI_SANS_LLM)
        try:
            consultation = lire()
        except (UsineErreur, OSError) as exc:
            raise HTTPException(status_code=503, detail=refus_lecture(exc)) from exc
        if consultation is None:
            raise HTTPException(status_code=409, detail=agent_textes.AUCUN_PASSAGE)
        try:
            reponse = garde.repondre(consultation, demande.question)
        except SessionIndisponible as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:  # fournisseur, trace ou validation : message explicite
            detail = f"Réponse de l'Agent impossible : {exc}"
            raise HTTPException(status_code=502, detail=detail) from exc
        return vue_reponse_agent(reponse, services.texte_hors_perimetre)

    application.add_api_route(
        "/api/agent/question", poser_question, methods=["POST"], response_model=VueReponseAgent
    )

    def rejouer(rang: int) -> VueReponseAgent:
        """Réponse enregistrée rejouée sans LLM ; Mode repli seulement (FR-45)."""
        if services is None:
            raise HTTPException(status_code=503, detail=SERVICES_ABSENTS)
        if not mode.repli:
            raise HTTPException(status_code=409, detail=SEULEMENT_REPLI)
        try:
            consultation = lire()
            if consultation is None:
                raise HTTPException(status_code=409, detail=agent_textes.AUCUN_PASSAGE)
            enregistrees = services.reponses_repli(consultation.manifeste().passage_id)
        except UsineErreur as exc:
            detail = f"{agent_textes.REFUS_REPLI} : {exc}"
            raise HTTPException(status_code=409, detail=detail) from exc
        except OSError as exc:
            raise HTTPException(status_code=503, detail=refus_lecture(exc)) from exc
        if not 0 <= rang < len(enregistrees):
            raise HTTPException(status_code=404, detail="Question enregistrée inconnue.")
        enregistree = enregistrees[rang]
        return vue_reponse_agent(enregistree.reponse, services.texte_hors_perimetre, enregistree)

    application.add_api_route(
        "/api/agent/enregistrees/{rang}", rejouer, response_model=VueReponseAgent
    )

    def avant_apres(periode: Literal["rapport", "cumul"] = "rapport") -> VueAvantApres:
        if services is None:
            return vue_avant_apres_erreur(SERVICES_ABSENTS)
        choix: Periode = periode
        try:
            try:
                config = services.config_demo()
            except UsineErreur as exc:
                return vue_avant_apres_erreur(f"Configuration de la démo invalide : {exc}")
            mesure, dernier = services.manifestes_avant_apres(mode.repli)
        except (UsineErreur, OSError) as exc:
            return vue_avant_apres_erreur(refus_lecture(exc))
        minutes = None if config is None else config.temps_manuel_minutes_par_rapport
        return vue_avant_apres(minutes=minutes, mesure=mesure, dernier=dernier, periode=choix)

    application.add_api_route("/api/avant-apres", avant_apres, response_model=VueAvantApres)

    def pseudonymisation(ticket: str | None = None) -> VuePseudonymisation:
        if services is None:
            return vue_pseudonymisation_erreur(SERVICES_ABSENTS)
        try:
            consultation = lire()
            if consultation is None:
                return vue_pseudonymisation_message(AUCUN_PASSAGE, LIEN_CHAINE)
            return vue_pseudonymisation(consultation, services.apercu_pseudonymisation, ticket)
        except (UsineErreur, OSError) as exc:
            return vue_pseudonymisation_erreur(refus_lecture(exc))

    application.add_api_route(
        "/api/pseudonymisation", pseudonymisation, response_model=VuePseudonymisation
    )

    def vue_fiche() -> VueOutillage:
        if services is None:
            return vue_outillage_erreur(SERVICES_ABSENTS)
        try:
            return vue_outillage(services.lire_fiche())
        except (OSError, UnicodeDecodeError) as exc:
            return vue_outillage_erreur(f"Lecture de la fiche outillage impossible : {exc}")

    application.add_api_route("/api/outillage", vue_fiche, response_model=VueOutillage)


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
