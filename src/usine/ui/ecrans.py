"""Vues JSON des quatre derniers écrans de l'UI web : Agent, Avant / après, Pseudonymisation,
Outillage (Story 7.16, AD-25).

Chaque fonction reçoit des lectures déjà faites (ou des services injectés par `ui/cli.py`,
racine de composition) et rend une vue pydantic locale à `ui/`, aux libellés écrits : le
navigateur n'a ni calcul ni formatage à faire (AD-9). Aucun module d'`ia`, de `ports` ou
d'adaptateur n'est importé ici (AD-1).
"""

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from usine.contrats.config import ConfigDemo
from usine.contrats.erreurs import UsineErreur
from usine.contrats.format import formater_entier
from usine.contrats.llm import ReponseAgent, ReponseAgentEnregistree, StatutControle
from usine.contrats.passage import ManifestePassage
from usine.ui import agent, avant_apres, outillage, pseudonymisation
from usine.ui.carte import LectureCarte
from usine.ui.liens import vue_ticket
from usine.ui.progression import texte_duree
from usine.ui.pseudonymisation import LecturePseudonymisation
from usine.ui.vues import (
    CodeBadge,
    Periode,
    VueAgent,
    VueAvantApres,
    VueCarteTemps,
    VueLien,
    VueOptionPeriode,
    VueOutil,
    VueOutillage,
    VuePseudonymisation,
    VueQuestionEnregistree,
    VueReponseAgent,
    VueSaisie,
    VueTableau,
)


class LectureEcransAgent(LectureCarte, LecturePseudonymisation, Protocol):
    """Lectures de la `Consultation` des quatre écrans (le manifeste et l'URL d'un ticket)."""


SERVICES_ABSENTS = "Écran indisponible : l'interface n'a pas reçu ses services (racine absente)."

LIEN_CHAINE = VueLien(libelle="Lancer la Chaîne", url="/chaine")
LIEN_REPLI = VueLien(libelle="Passer en Mode repli depuis l'écran de lancement", url="/chaine")

ATTENTE_AGENT = "L'Agent consulte le Passage…"
ANNONCE_REPONSE = "Réponse de l'Agent reçue"
TITRE_QUESTIONS_REEL = "Questions enregistrées (suggestions)"
TITRE_QUESTIONS_REPLI = agent.LIBELLE_CHOIX
TITRE_OUTILS = "Outils de l'Agent"
LIBELLE_OUTILS = "Outils appelés :"
AUCUN_OUTIL = "aucun"
BADGE_HORS_PERIMETRE = "Hors périmètre · aucune donnée inventée"
REPONSE_REJETEE = "Réponse rejetée par le contrôle : son texte n'est pas affiché."
MODE_REPLI_SANS_LLM = (
    "Mode repli : l'Agent ne s'adresse à aucun LLM, choisir une question enregistrée."
)

OUTILS_AGENT: tuple[VueOutil, ...] = (
    VueOutil(
        nom="get_meteo",
        description="Météo des Entités, Règles déclenchantes et évolution J-1 / J-5.",
    ),
    VueOutil(
        nom="list_anomalies",
        description="Anomalies ouvertes, filtrées par Entité, Gravité, Phase, domaine ou statut.",
    ),
    VueOutil(nom="get_tendance", description="Tendance hebdomadaire des KPI, par Entité."),
    VueOutil(nom="get_prevision", description="Prévisions de sortie du rouge."),
    VueOutil(nom="get_risques", description="Risques d'entrée en rouge."),
)
"""Outils exposés à l'Agent, tous en lecture seule (liste fixe de l'écran, EXPERIENCE.md)."""


@dataclass(frozen=True)
class ServicesEcrans:
    """Services des quatre écrans, fournis par `ui/cli.py` (AD-1).

    Chaque appel lit la racine au moment de l'affichage : aucune lecture n'est gardée.
    """

    session_agent: Callable[[LectureEcransAgent], agent.Session]
    reponses_repli: Callable[[str], tuple[ReponseAgentEnregistree, ...]]
    questions_suggerees: tuple[str, ...]
    texte_hors_perimetre: str
    apercu_pseudonymisation: Callable[[], Callable[[str], str]]
    config_demo: Callable[[], ConfigDemo | None]
    manifestes_avant_apres: Callable[
        [bool], tuple[ManifestePassage | None, ManifestePassage | None]
    ]
    lire_fiche: Callable[[], str | None]


# --- Agent ---


class SessionIndisponible(UsineErreur):
    """La session de l'Agent ne peut pas être construite (configuration, clé, fournisseur)."""


class GardeSession:
    """Garde la session de l'Agent tant que le Passage publié ne change pas (FR-39).

    Une question à la fois : le verrou serialise les appels au fournisseur.
    """

    def __init__(self, fabrique: Callable[[LectureEcransAgent], agent.Session]) -> None:
        self._fabrique = fabrique
        self._verrou = threading.Lock()
        self._session: agent.Session | None = None

    def repondre(self, consultation: LectureEcransAgent, question: str) -> ReponseAgent:
        """Réponse contrôlée de la session du Passage de `consultation` (rebâtie si changé)."""
        with self._verrou:
            passage_id = consultation.manifeste().passage_id
            if self._session is not None and self._session.passage_id != passage_id:
                self._session.fermer()  # nouveau Passage publié : nouvelle session
                self._session = None
            if self._session is None:
                try:
                    self._session = self._fabrique(consultation)
                except UsineErreur as exc:
                    raise SessionIndisponible(
                        f"Agent indisponible : la session ne peut être construite ({exc})"
                    ) from exc
            return self._session.repondre(question)


def vue_reponse_agent(
    reponse: ReponseAgent,
    texte_hors_perimetre: str,
    enregistree: ReponseAgentEnregistree | None = None,
) -> VueReponseAgent:
    """Réponse avec son badge de contrôle et ses outils ; le texte d'un rejet n'est pas envoyé."""
    rejetee = reponse.statut_controle is StatutControle.rejete
    hors_perimetre = not rejetee and agent.est_hors_perimetre(reponse.texte, texte_hors_perimetre)
    code: CodeBadge = "hors_perimetre" if hors_perimetre else reponse.statut_controle.value
    return VueReponseAgent(
        question=reponse.question,
        texte=None if rejetee else reponse.texte,
        texte_masque=REPONSE_REJETEE if rejetee else None,
        badge=BADGE_HORS_PERIMETRE if hors_perimetre else agent.texte_statut(reponse),
        badge_code=code,
        libelle_outils=LIBELLE_OUTILS,
        outils=list(reponse.outils_appeles),
        aucun_outil=AUCUN_OUTIL,
        mention_repli=None if enregistree is None else agent.mention_repli(enregistree),
        annonce=ANNONCE_REPONSE,
    )


def _vue_agent(repli: bool, **champs: object) -> VueAgent:
    base: dict[str, object] = {
        "mode": "repli" if repli else "reel",
        "erreur": None,
        "message": None,
        "lien_message": None,
        "legende": None,
        "message_repli": None,
        "saisie": None,
        "titre_questions": TITRE_QUESTIONS_REPLI if repli else TITRE_QUESTIONS_REEL,
        "questions": [],
        "titre_outils": TITRE_OUTILS,
        "outils": list(OUTILS_AGENT),
        "attente": ATTENTE_AGENT,
        "lien_repli": None,
    }
    return VueAgent.model_validate(base | champs)


def vue_agent_erreur(repli: bool, erreur: str) -> VueAgent:
    """Écran Agent avec une lecture impossible (bandeau d'erreur)."""
    return _vue_agent(
        repli,
        erreur=erreur,
        message_repli=agent.MESSAGE_REPLI if repli else None,
        lien_repli=None if repli else LIEN_REPLI,
    )


def vue_agent(
    *,
    repli: bool,
    consultation: LectureEcransAgent | None,
    services: ServicesEcrans,
) -> VueAgent:
    """Écran Agent : saisie (Mode réel) ou questions enregistrées (Mode repli)."""
    if repli:
        questions: list[VueQuestionEnregistree] = []
        erreur = None
        if consultation is not None:
            try:
                enregistrees = services.reponses_repli(consultation.manifeste().passage_id)
            except UsineErreur as exc:
                erreur = f"{agent.REFUS_REPLI} : {exc}"
            else:
                questions = [
                    VueQuestionEnregistree(rang=rang, question=e.reponse.question)
                    for rang, e in enumerate(enregistrees)
                ]
        return _vue_agent(
            True, message_repli=agent.MESSAGE_REPLI, questions=questions, erreur=erreur
        )
    if consultation is None:
        return _vue_agent(False, message=agent.AUCUN_PASSAGE, lien_message=LIEN_CHAINE)
    suggestions = [
        VueQuestionEnregistree(rang=rang, question=question)
        for rang, question in enumerate(services.questions_suggerees)
    ]
    saisie = VueSaisie(
        libelle=agent.LIBELLE_QUESTION,
        valeur_defaut=agent.QUESTION_DEMO,
        bouton="Envoyer",
    )
    return _vue_agent(False, legende=agent.LEGENDE, saisie=saisie, questions=suggestions)


# --- Avant / après ---

LIBELLE_PERIODE = "Période"
PERIODES: tuple[VueOptionPeriode, ...] = (
    VueOptionPeriode(valeur="rapport", libelle="Par Rapport quotidien"),
    VueOptionPeriode(
        valeur="cumul", libelle=f"Cumulé sur {avant_apres.NB_RAPPORTS_CUMUL} Rapports"
    ),
)


def _vue_avant_apres(**champs: object) -> VueAvantApres:
    base: dict[str, object] = {
        "erreur": None,
        "message": None,
        "lien_message": None,
        "avertissements": [],
        "manuel": None,
        "chaine": None,
        "libelle_periode": LIBELLE_PERIODE,
        "periodes": list(PERIODES),
        "periode": "rapport",
        "tableau": None,
        "legende": None,
    }
    return VueAvantApres.model_validate(base | champs)


def vue_avant_apres_erreur(erreur: str) -> VueAvantApres:
    """Écran Avant / après avec une lecture impossible."""
    return _vue_avant_apres(erreur=erreur)


def _carte_manuel(minutes: int) -> VueCarteTemps:
    cumul = minutes * avant_apres.NB_RAPPORTS_CUMUL
    return VueCarteTemps(
        titre="Reporting manuel",
        etiquette="déclaré",
        valeurs={
            "rapport": f"{formater_entier(minutes)} min",
            "cumul": f"{formater_entier(cumul)} min",
        },
    )


def _carte_chaine(duree: timedelta) -> VueCarteTemps:
    return VueCarteTemps(
        titre="Chaîne",
        etiquette="mesuré",
        valeurs={
            "rapport": texte_duree(duree),
            "cumul": texte_duree(duree * avant_apres.NB_RAPPORTS_CUMUL),
        },
    )


def _tableau(manuel: VueCarteTemps | None, chaine: VueCarteTemps | None) -> VueTableau:
    colonnes = ["Rapport"]
    cartes = [carte for carte in (manuel, chaine) if carte is not None]
    colonnes += [
        "Reporting manuel (déclaré)" if carte is manuel else "Chaîne (mesuré)" for carte in cartes
    ]
    lignes = [
        [option.libelle, *(carte.valeurs[option.valeur] for carte in cartes)] for option in PERIODES
    ]
    return VueTableau(colonnes=colonnes, lignes=lignes)


def vue_avant_apres(
    *,
    minutes: int | None,
    mesure: ManifestePassage | None,
    dernier: ManifestePassage | None,
    periode: Periode = "rapport",
) -> VueAvantApres:
    """Écran Avant / après : valeurs des fonctions de `avant_apres`, aucun écart ni ratio.

    `minutes` à `None` : configuration absente. `mesure` à `None` : aucun Passage sans
    classification initiale (`dernier` précise s'il y a un Passage publié ou non).
    """
    avertissements: list[str] = []
    if minutes is None:
        avertissements.append(avant_apres.CONFIG_ABSENTE)
    if mesure is None:
        if dernier is None:
            return _vue_avant_apres(
                message=avant_apres.AUCUN_PASSAGE, lien_message=LIEN_CHAINE, periode=periode
            )
        avertissements.append(avant_apres.SEULE_CLASSIFICATION_INITIALE)
    manuel = None if minutes is None else _carte_manuel(minutes)
    chaine = None if mesure is None else _carte_chaine(avant_apres.duree_mesuree(mesure))
    return _vue_avant_apres(
        avertissements=avertissements,
        manuel=manuel,
        chaine=chaine,
        periode=periode,
        tableau=None if manuel is None and chaine is None else _tableau(manuel, chaine),
        legende=None if mesure is None else avant_apres.legende(mesure),
    )


# --- Pseudonymisation ---

LIBELLE_TICKET = "Ticket"
ETIQUETTE_PSEUDONYMISE = "envoyée au LLM"


def _vue_pseudo(**champs: object) -> VuePseudonymisation:
    base: dict[str, object] = {
        "erreur": None,
        "message": None,
        "lien_message": None,
        "libelle_ticket": LIBELLE_TICKET,
        "tickets": [],
        "ticket": None,
        "legende": None,
        "titre_original": pseudonymisation.TITRE_ORIGINAL,
        "titre_pseudonymise": pseudonymisation.TITRE_PSEUDONYMISE,
        "etiquette_pseudonymise": ETIQUETTE_PSEUDONYMISE,
        "original": None,
        "pseudonymise": None,
    }
    return VuePseudonymisation.model_validate(base | champs)


def vue_pseudonymisation_erreur(erreur: str) -> VuePseudonymisation:
    """Écran Pseudonymisation avec une lecture impossible."""
    return _vue_pseudo(erreur=erreur)


def vue_pseudonymisation_message(message: str, lien: VueLien | None = None) -> VuePseudonymisation:
    """Écran Pseudonymisation remplacé par un message (aucun Passage)."""
    return _vue_pseudo(message=message, lien_message=lien)


def vue_pseudonymisation(
    consultation: LectureEcransAgent,
    apercu: Callable[[], Callable[[str], str]],
    ticket: str | None,
) -> VuePseudonymisation:
    """Original et `Pseudonymiseur.apercu` en texte brut, côte à côte (FR-31, AD-15).

    Un moteur absent (Presidio, modèle spaCy) ou une clé absente est nommé dans `erreur`, la
    sélection du ticket restant utilisable.
    """
    textes = pseudonymisation.descriptions(consultation.textes_tickets())
    if not textes:
        return _vue_pseudo(message=pseudonymisation.AUCUNE_DESCRIPTION)
    cles: Sequence[str] = sorted(textes)
    if ticket is not None and ticket not in textes:
        return _vue_pseudo(
            tickets=list(cles),
            erreur=f"Le ticket {ticket} n'a pas de description non vide dans ce Passage.",
        )
    cle = ticket if ticket is not None else cles[0]
    base: dict[str, object] = {
        "tickets": list(cles),
        "ticket": vue_ticket(cle, consultation.url_ticket(cle)),
    }
    try:
        version = apercu()(textes[cle])
    except UsineErreur as exc:
        return _vue_pseudo(**base, erreur=f"Aperçu de la Pseudonymisation impossible : {exc}")
    except Exception as exc:  # Presidio ou modèle spaCy indisponible ou en échec
        return _vue_pseudo(**base, erreur=pseudonymisation.moteur_indisponible(exc))
    return _vue_pseudo(
        **base, legende=pseudonymisation.LEGENDE, original=textes[cle], pseudonymise=version
    )


# --- Outillage ---


def vue_outillage(fiche: str | None) -> VueOutillage:
    """Fiche d'outillage rendue en HTML par le serveur, ou le message de fiche absente."""
    if fiche is None:
        return VueOutillage(erreur=None, message=outillage.FICHE_ABSENTE, legende=None, html=None)
    return VueOutillage(
        erreur=None,
        message=None,
        legende=outillage.LEGENDE,
        html=outillage.rendre_fiche(fiche),
    )


def vue_outillage_erreur(erreur: str) -> VueOutillage:
    """Écran Outillage avec une fiche illisible."""
    return VueOutillage(erreur=erreur, message=None, legende=None, html=None)
