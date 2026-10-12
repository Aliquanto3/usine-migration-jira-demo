"""Page Streamlit minimale : bandeau Mode repli, carte météo, lancement et suivi de la Chaîne.

La page lit le dernier Passage publié via `Consultation` seulement, et la progression d'un
Passage lancé dans `sorties/progression/`. Elle n'écrit rien sous `sorties/` et n'exécute
jamais la Chaîne dans son propre processus : `usine rapport` tourne dans un sous-processus.
La racine est `USINE_RACINE` si elle est définie, sinon le répertoire courant. Racine, Mode
repli et `Consultation` viennent des services de `ui/cli.py` (racine de composition).
"""

import subprocess
from pathlib import Path
from typing import IO

import streamlit as st

from usine.contrats.erreurs import UsineErreur
from usine.ui import carte, lancement, progression
from usine.ui.cli import consultation_dernier_passage, mode_repli, racine_ui

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


def afficher_carte(racine: Path) -> None:
    """Carte météo du dernier Passage publié, ou message explicite sans Passage."""
    st.subheader("Carte météo du dernier Passage")
    if not racine.is_dir():
        st.error(
            f"Racine introuvable : {racine} (variable USINE_RACINE ou répertoire courant) ;"
            " aucun Passage ne peut être lu ni lancé"
        )
        return
    try:
        consultation = consultation_dernier_passage(racine)
        if consultation is None:
            st.info("Aucun Passage publié : lancer la Chaîne pour produire une carte météo.")
            return
        date_arrete = carte.date_carte(consultation)
        lignes = carte.lignes_carte(consultation)
    except UsineErreur as exc:
        st.error(f"Lecture du dernier Passage impossible : {exc}")
        return
    st.caption(f"Date d'arrêté : {date_arrete}")
    if lignes:
        st.table(lignes)
    else:
        st.info("Ce Passage ne contient aucune Météo.")


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


def _suivre() -> None:
    """État de chaque étape du Passage lancé, relu à chaque sondage."""
    processus: subprocess.Popen[bytes] = st.session_state[_PROCESSUS]
    racine: Path = st.session_state[_RACINE]
    code = processus.poll()
    fichier: Path | None = st.session_state.get(_FICHIER)
    if fichier is None:
        fichier = progression.fichier_nouveau(st.session_state[_AVANT], racine)
        st.session_state[_FICHIER] = fichier
    try:
        evenements = progression.lire_progression(fichier) if fichier is not None else ()
    except UsineErreur as exc:
        st.error(str(exc))
        evenements = ()
    st.markdown(
        "\n".join(
            f"- **{etape.value}** : {progression.LIBELLES_ETATS[etat]}"
            for etape, etat in progression.etat_des_etapes(evenements)
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
        st.error(f"Échec de la Chaîne (code {code}) : {fin}")
    if not st.session_state.get(_FIN_VUE):
        st.session_state[_FIN_VUE] = True
        st.rerun()  # la page entière relit la carte et cesse de sonder


def afficher_lancement(racine: Path) -> None:
    """Bouton de lancement et suivi de la progression, sans bloquer la page."""
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
    if st.session_state.get(_PROCESSUS) is None:
        return
    st.fragment(run_every=INTERVALLE_SONDAGE if en_cours else None)(_suivre)()


def principal() -> None:
    """Page entière ; le bandeau Mode repli vient en premier, à chaque exécution."""
    st.set_page_config(page_title="Usine de migration", layout="wide")
    try:
        racine = racine_ui()
    except UsineErreur as exc:
        st.error(str(exc))
        return
    afficher_bandeau(racine)
    st.title("Usine de migration")
    afficher_carte(racine)
    afficher_lancement(racine)


principal()
