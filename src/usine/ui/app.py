"""Page Streamlit de la démo : bandeau Mode repli, navigation latérale et écrans.

La carte météo est l'écran par défaut ; chaque autre écran (détail d'une Entité, lancement et
suivi de la Chaîne, avant / après, Agent, outillage) est à un clic, depuis la navigation
latérale ou, pour le détail, depuis le bouton de chaque Entité sous la carte.

La page lit le dernier Passage publié via `Consultation` seulement, et la progression d'un
Passage lancé dans `sorties/progression/`. Elle n'écrit rien sous `sorties/` et n'exécute
jamais la Chaîne dans son propre processus : `usine rapport` tourne dans un sous-processus.
La racine est `USINE_RACINE` si elle est définie, sinon le répertoire courant. Racine, Mode
repli et `Consultation` viennent des services de `ui/cli.py` (racine de composition).
"""

import subprocess
from pathlib import Path
from typing import IO, Protocol

import streamlit as st

from usine.contrats.erreurs import UsineErreur
from usine.contrats.passage import Etape, EvenementProgression, StatutEtape
from usine.ui import carte, detail, lancement, navigation, progression
from usine.ui.cli import consultation_dernier_passage, mode_repli, racine_ui
from usine.ui.liens import echapper_markdown
from usine.ui.navigation import Ecran

# Pas de chaîne isolée au niveau du module : la « magie » Streamlit l'afficherait.
INTERVALLE_SONDAGE = 1.0  # secondes entre deux lectures de la progression, Chaîne en cours
LIGNES_ERREUR_MAX = 20  # dernières lignes de l'erreur standard affichées en cas d'échec

_PROCESSUS = "processus"
_AVANT = "fichiers_avant"
_FICHIER = "fichier_progression"
_RACINE = "racine_lancement"
_ERREUR = "erreur_chaine"
_FIN_VUE = "fin_vue"
_FICHIER_ERREURS = "fichier_erreurs"
_ECHEC_LANCEMENT = "echec_lancement"


def afficher_bandeau(racine: Path) -> None:
    """Bandeau permanent en tête de page quand `USINE_MODE_REPLI=1` (jamais automatique)."""
    try:
        repli = mode_repli(racine)
    except UsineErreur as exc:
        st.error(str(exc))
        return
    if repli:
        st.warning(
            "**Mode repli** : la démo tourne sans Jira ni LLM réels ; aucun lien Jira n'est"
            " proposé.",
            icon="⚠️",
        )


class _Lecture(carte.LectureCarte, detail.LectureDetail, Protocol):
    """Lectures de la `Consultation` utilisées par la carte et par le détail."""


def _lecture(racine: Path) -> _Lecture | None:
    """`Consultation` du dernier Passage publié, ou `None` après un message explicite."""
    if not racine.is_dir():
        st.error(
            f"Racine introuvable : {racine} (variable USINE_RACINE ou répertoire courant) ;"
            " aucun Passage ne peut être lu ni lancé"
        )
        return None
    try:
        consultation = consultation_dernier_passage(racine)
    except UsineErreur as exc:
        st.error(f"Lecture du dernier Passage impossible : {exc}")
        return None
    if consultation is None:
        st.info("Aucun Passage publié : lancer la Chaîne pour produire une carte météo.")
    return consultation


def afficher_carte(racine: Path) -> None:
    """Carte météo du dernier Passage publié : tableau, légende et un bouton Détail par Entité."""
    st.subheader("Carte météo du dernier Passage")
    consultation = _lecture(racine)
    if consultation is None:
        return
    try:
        date_arrete = carte.date_carte(consultation)
        lignes = carte.lignes_carte(consultation)
        entites = [meteo.entite for meteo in consultation.meteo()]
    except UsineErreur as exc:
        st.error(f"Lecture du dernier Passage impossible : {exc}")
        return
    st.caption(f"Date d'arrêté : {date_arrete}")
    if not lignes:
        st.info("Ce Passage ne contient aucune Météo.")
        return
    st.markdown(carte.tableau_markdown(lignes))
    st.caption(carte.LEGENDE)
    colonnes = st.columns(len(entites))
    for colonne, entite in zip(colonnes, entites, strict=True):
        colonne.button(
            f"Détail {echapper_markdown(entite)}",
            key=f"detail_{entite}",
            on_click=navigation.ouvrir_detail,
            args=(st.session_state, entite),
        )


def _bloc(titre: str, contenu: str) -> None:
    """Sous-titre d'un bloc du détail, puis son contenu Markdown."""
    st.markdown(f"#### {titre}")
    st.markdown(contenu)


def afficher_detail(racine: Path) -> None:
    """Détail d'une Entité (Palier 1) : Météo, Règles, KPI clés, Prévision, Risque, Explication."""
    st.subheader(Ecran.detail.value)
    consultation = _lecture(racine)
    if consultation is None:
        return
    try:
        meteos = {meteo.entite: meteo for meteo in consultation.meteo()}
    except UsineErreur as exc:
        st.error(f"Lecture du dernier Passage impossible : {exc}")
        return
    if not meteos:
        st.info("Ce Passage ne contient aucune Météo.")
        return
    if st.session_state.get(navigation.CLE_ENTITE) not in meteos:
        st.session_state.pop(navigation.CLE_ENTITE, None)  # Entité absente de ce Passage
    entite = st.selectbox("Entité", list(meteos), key=navigation.CLE_ENTITE)
    meteo = meteos[entite]
    try:
        manifeste = consultation.manifeste()
        regles = detail.lignes_regles(meteo, consultation.url_ticket)
        kpi = detail.lignes_kpi(consultation.kpi(entite=entite))
        calculees = detail.previsions_calculees(manifeste)
        previsions = consultation.previsions(entite=entite)
        risques = consultation.risques(entite=entite)
    except UsineErreur as exc:
        st.error(f"Lecture du dernier Passage impossible : {exc}")
        return
    st.markdown(f"**Météo** : {carte.libelle_meteo(meteo.couleur)}")
    _bloc("Règles déclenchantes", carte.tableau_markdown(regles) or detail.AUCUNE_REGLE)
    _bloc("KPI clés", carte.tableau_markdown(kpi) or detail.AUCUN_KPI)
    _bloc("Prévision de sortie du rouge", detail.texte_prevision(meteo, previsions, calculees))
    _bloc("Risque d'entrée en rouge", detail.texte_risques(meteo, risques, calculees))
    _bloc("Explication", detail.texte_explication(manifeste.palier))


def afficher_a_venir(ecran: Ecran) -> None:
    """Emplacement nommé d'un écran livré par une story suivante."""
    st.subheader(ecran.value)
    st.info(f"Écran livré par la Story {navigation.STORY_A_VENIR[ecran]}.")


def _en_cours() -> bool:
    """Vrai si un processus de la Chaîne lancé par cette session tourne encore."""
    processus: subprocess.Popen[bytes] | None = st.session_state.get(_PROCESSUS)
    return processus is not None and processus.poll() is None


def _lancer(racine: Path) -> None:
    """Rappel du bouton : note les fichiers de progression présents, puis lance la Chaîne.

    Ne relance rien si la Chaîne tourne déjà (onglet périmé, double clic).
    """
    if _en_cours():
        return
    ancien: IO[bytes] | None = st.session_state.get(_FICHIER_ERREURS)
    if ancien is not None:
        ancien.close()
    st.session_state[_FICHIER_ERREURS] = None
    st.session_state[_AVANT] = progression.fichiers_progression(racine)
    st.session_state[_FICHIER] = None
    st.session_state[_RACINE] = racine
    st.session_state[_ERREUR] = None
    st.session_state[_FIN_VUE] = False
    st.session_state[_ECHEC_LANCEMENT] = None
    erreurs: IO[bytes] | None = None
    try:
        erreurs = lancement.fichier_erreurs()
        processus = lancement.lancer_chaine(racine, erreurs=erreurs)
    except OSError as exc:
        if erreurs is not None:
            erreurs.close()
        st.session_state[_PROCESSUS] = None
        st.session_state[_ECHEC_LANCEMENT] = f"Lancement de la Chaîne impossible : {exc}"
        return
    st.session_state[_FICHIER_ERREURS] = erreurs
    st.session_state[_PROCESSUS] = processus


def _erreur() -> str:
    """Erreur standard du sous-processus terminé, lue une seule fois (fichier alors fermé)."""
    if st.session_state.get(_ERREUR) is None:
        erreurs: IO[bytes] | None = st.session_state.get(_FICHIER_ERREURS)
        st.session_state[_FICHIER_ERREURS] = None
        st.session_state[_ERREUR] = "" if erreurs is None else lancement.lire_erreurs(erreurs)
    texte: str = st.session_state[_ERREUR]
    return texte


def _evenements() -> tuple[EvenementProgression, ...]:
    """Événements du Passage lancé, relus en ouvrir-lire-fermer ; lève `UsineErreur`."""
    fichier: Path | None = st.session_state.get(_FICHIER)
    if fichier is None:
        fichier = progression.fichier_nouveau(st.session_state[_AVANT], st.session_state[_RACINE])
        st.session_state[_FICHIER] = fichier
    return progression.lire_progression(fichier) if fichier is not None else ()


def _evenements_ou_erreur() -> tuple[EvenementProgression, ...]:
    """Événements du Passage lancé ; une progression illisible est signalée, sans arrêt."""
    try:
        return _evenements()
    except UsineErreur as exc:
        st.error(str(exc))
        return ()


def _lieu_echec(evenements: tuple[EvenementProgression, ...]) -> str:
    """`à l'étape « X »` ou `hors d'une étape`, selon la progression."""
    etape = progression.etape_en_echec(evenements)
    return "hors d'une étape" if etape is None else f"à l'étape « {etape.value} »"


def _finir() -> None:
    """Relance unique de la page entière à la fin de la Chaîne : la carte relit le Passage."""
    if not st.session_state.get(_FIN_VUE):
        st.session_state[_FIN_VUE] = True
        st.rerun()  # la page entière relit la carte et cesse de sonder


def _suivre() -> None:
    """État et durée de chaque étape du Passage lancé, relus à chaque sondage."""
    processus: subprocess.Popen[bytes] = st.session_state[_PROCESSUS]
    code = processus.poll()
    evenements = _evenements_ou_erreur()
    st.markdown(
        "\n".join(
            progression.ligne_suivi(suivi) for suivi in progression.suivi_des_etapes(evenements)
        )
    )
    if code is None:
        st.info("Chaîne en cours…")
        return
    message = _erreur() or "aucun message"  # lu et fermé dans les deux issues
    if code == 0:
        st.success("Chaîne terminée : Passage publié.")
    else:
        fin = "\n".join(message.splitlines()[-LIGNES_ERREUR_MAX:])
        st.error(f"Échec de la Chaîne {_lieu_echec(evenements)} (code {code}) : {fin}")
    _finir()


def afficher_lancement(racine: Path) -> None:
    """Bouton de lancement et suivi de la progression, sans bloquer la page.

    Une fois la Chaîne terminée : la carte du dernier Passage publié après un succès, sinon
    `progression.AUCUN_RAPPORT` (jamais de rapport partiel).
    """
    st.subheader("Chaîne de reporting")
    en_cours = _en_cours()
    st.button(
        "Lancer la Chaîne",
        on_click=_lancer,
        args=(racine,),
        disabled=en_cours or not racine.is_dir(),
    )
    echec = st.session_state.get(_ECHEC_LANCEMENT)
    if echec:
        st.error(echec)
    processus: subprocess.Popen[bytes] | None = st.session_state.get(_PROCESSUS)
    if processus is None:
        return
    st.fragment(run_every=INTERVALLE_SONDAGE if en_cours else None)(_suivre)()
    if en_cours:
        return
    if processus.poll() == 0:
        afficher_carte(st.session_state.get(_RACINE, racine))
    else:
        st.info(progression.AUCUN_RAPPORT)


def _resumer() -> None:
    """Résumé latéral du lancement hors de l'écran Lancement, sondé tant que la Chaîne tourne."""
    processus: subprocess.Popen[bytes] = st.session_state[_PROCESSUS]
    code = processus.poll()
    try:
        evenements = _evenements()
    except UsineErreur:
        evenements = ()  # l'écran Lancement nomme l'erreur ; le résumé reste neutre
    if code is None:
        courante: Etape | None = None  # dernière étape `en_cours` non encore terminée
        for evenement in evenements:
            if evenement.statut is StatutEtape.en_cours:
                courante = evenement.etape
            elif evenement.etape is courante:
                courante = None
        if courante is not None:
            st.info(f"Chaîne en cours : étape « {courante.value} »")
        else:
            st.info("Chaîne en cours…")
        return
    _erreur()  # lue une seule fois et fermée, comme sur l'écran Lancement
    if code == 0:
        st.success("Dernier lancement : Passage publié.")
    else:
        st.error(f"Dernier lancement en échec {_lieu_echec(evenements)}.")
    _finir()


def afficher_resume() -> None:
    """Résumé du lancement de cette session dans la barre latérale (hors écran Lancement)."""
    if st.session_state.get(_PROCESSUS) is None:
        return
    with st.sidebar:
        st.fragment(run_every=INTERVALLE_SONDAGE if _en_cours() else None)(_resumer)()


def principal() -> None:
    """Page entière ; le bandeau Mode repli vient en premier, à chaque exécution, sur tout écran."""
    st.set_page_config(page_title="Usine de migration", layout="wide")
    try:
        racine = racine_ui()
    except UsineErreur as exc:
        st.error(str(exc))
        racine = Path.cwd()  # la page reste utilisable : carte et lancement s'affichent
    afficher_bandeau(racine)
    ecran = Ecran(st.sidebar.radio("Écran", navigation.libelles_ecrans(), key=navigation.CLE_ECRAN))
    if ecran is not Ecran.lancement:
        afficher_resume()  # avant l'écran : une relance de fin évite de lire la carte deux fois
    st.title("Usine de migration")
    if ecran is Ecran.carte:
        afficher_carte(racine)
    elif ecran is Ecran.detail:
        afficher_detail(racine)
    elif ecran is Ecran.lancement:
        afficher_lancement(racine)
    else:
        afficher_a_venir(ecran)


principal()
