"""Page Streamlit de la démo : bandeau Mode repli, navigation latérale et écrans.

La carte météo est l'écran par défaut ; chaque autre écran (détail d'une Entité, lancement et
suivi de la Chaîne, avant / après, Agent, outillage) est à un clic, depuis la navigation
latérale ou, pour le détail, depuis le bouton de chaque Entité sous la carte.

La page lit le dernier Passage publié via `Consultation` seulement, et la progression d'un
Passage lancé dans `sorties/progression/`. Elle n'écrit rien sous `sorties/` et n'exécute
jamais la Chaîne dans son propre processus : `usine rapport` tourne dans un sous-processus.
La racine est `USINE_RACINE` si elle est définie, sinon le répertoire courant. Racine, Mode
repli, `Consultation`, configuration de la démo (`config/demo.yaml`) et manifestes de l'avant
/ après viennent des services de `ui/cli.py` (racine de composition). L'écran outillage affiche
en lecture seule la fiche `docs/fiche-outillage.md` (Story 8.1), lue sous la même racine.

Comparaison des Paliers (Story 7.7) : sur un Passage Palier 2, un sélecteur de Palier du détail
lit l'Explication sourcée et la narration de la Prévision avec le filtre `palier` de
`Consultation` ; en Palier 1, aucune sortie LLM n'est lue. L'écran Pseudonymisation montre côte
à côte une description de ticket et son aperçu pseudonymisé (`ui/cli.apercu_pseudonymisation`),
calculé localement sans rien écrire.

Mode repli (activation toujours manuelle, H-30) : `USINE_MODE_REPLI` l'impose, sinon la bascule
latérale « Mode repli » le décide. Actif, il affiche un bandeau permanent en tête de page ; la
carte, le détail et l'avant / après lisent alors le Passage enregistré `demo/repli/passage/`
via `Consultation`, sans lien Jira, et le lancement de la Chaîne est désactivé.
"""

import subprocess
from pathlib import Path
from typing import IO, Literal, Protocol

import streamlit as st

from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import ReponseAgent, StatutControle
from usine.contrats.passage import Etape, EvenementProgression, ManifestePassage, StatutEtape
from usine.ui import (
    agent,
    avant_apres,
    carte,
    detail,
    lancement,
    navigation,
    outillage,
    progression,
    pseudonymisation,
)
from usine.ui.cli import (
    REPERTOIRE_REPLI,
    apercu_pseudonymisation,
    config_demo,
    consultation_dernier_passage,
    consultation_repli,
    manifestes_avant_apres,
    mode_repli,
    racine_ui,
    reponses_repli,
    session_agent,
)
from usine.ui.liens import echapper_markdown, lien_ticket
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


_DOSSIER_REPLI = f"{REPERTOIRE_REPLI.as_posix()}/"

# Bandeau permanent du Mode repli, premier élément de la zone principale.
BANDEAU_REPLI = (
    f"**Mode repli** : la démo lit le Passage enregistré `{_DOSSIER_REPLI}`, sans Jira ni LLM"
    " réels ; les liens Jira sont inactifs."
)

# Aide de la bascule latérale du Mode repli.
AIDE_REPLI = (
    f"Activation manuelle : l'UI lit le Passage enregistré {_DOSSIER_REPLI} et le lancement est"
    " désactivé."
)

# Mode repli sans copie versionnée : erreur explicite, jamais de repli silencieux.
REPLI_ABSENT = (
    f"Mode repli : Passage enregistré introuvable (`{_DOSSIER_REPLI}manifeste.json` absent) ;"
    f" restaurer `{_DOSSIER_REPLI}` depuis le dépôt ou désactiver le Mode repli."
)

# Écran Lancement en Mode repli : bouton visible mais désactivé.
LANCEMENT_REPLI = (
    "Mode repli : le lancement de la Chaîne est désactivé. L'UI lit le Passage enregistré"
    f" `{_DOSSIER_REPLI}` ; désactiver le Mode repli pour lancer la Chaîne."
)


def afficher_bandeau(racine: Path, erreur_racine: str | None = None) -> bool:
    """Mode repli effectif, toujours manuel (H-30), et bandeau permanent en tête s'il est actif.

    `USINE_MODE_REPLI` actif force la bascule latérale à l'état activé et la désactive ;
    sinon la bascule décide. Une variable illisible est signalée sous le bandeau, comme
    `erreur_racine` (lecture de `USINE_RACINE`), puis la bascule décide.
    """
    erreurs = [] if erreur_racine is None else [erreur_racine]
    try:
        impose = mode_repli(racine)
    except UsineErreur as exc:
        erreurs.append(str(exc))
        impose = False
    if impose:
        st.session_state[navigation.CLE_REPLI] = True  # avant la bascule : état imposé
    repli = st.sidebar.toggle(
        "Mode repli",
        key=navigation.CLE_REPLI,
        disabled=impose,
        help=AIDE_REPLI + (" Imposé par USINE_MODE_REPLI." if impose else ""),
    )
    if repli:
        st.warning(BANDEAU_REPLI, icon="⚠️")
    for erreur in dict.fromkeys(erreurs):  # une variable illisible n'est nommée qu'une fois
        st.error(erreur)
    return repli


class _Lecture(
    carte.LectureCarte, detail.LectureDetail, pseudonymisation.LecturePseudonymisation, Protocol
):
    """Lectures de la `Consultation` utilisées par la carte, le détail et la Pseudonymisation."""


def _racine_introuvable(racine: Path) -> bool:
    """Vrai, après un message d'erreur, si la racine n'est pas un répertoire."""
    if racine.is_dir():
        return False
    st.error(
        f"Racine introuvable : {racine} (variable USINE_RACINE ou répertoire courant) ;"
        " aucun Passage ne peut être lu ni lancé"
    )
    return True


def _echec_lecture(exc: Exception, repli: bool) -> None:
    """Erreur de lecture qui nomme la source : Passage enregistré en Mode repli, sinon dernier."""
    source = f"du Passage enregistré `{_DOSSIER_REPLI}`" if repli else "du dernier Passage"
    st.error(f"Lecture {source} impossible : {exc}")


def _lecture(racine: Path, repli: bool) -> _Lecture | None:
    """`Consultation` du dernier Passage publié, ou du Passage enregistré en Mode repli.

    `None` après un message explicite ; en Mode repli, jamais de lecture de `sorties/`.
    """
    if _racine_introuvable(racine):
        return None
    try:
        consultation = consultation_repli(racine) if repli else consultation_dernier_passage(racine)
    except UsineErreur as exc:
        _echec_lecture(exc, repli)
        return None
    if consultation is None:
        if repli:
            st.error(REPLI_ABSENT)
        else:
            st.info("Aucun Passage publié : lancer la Chaîne pour produire une carte météo.")
    return consultation


def afficher_carte(racine: Path, repli: bool = False) -> None:
    """Carte météo du dernier Passage publié : tableau, légende et un bouton Détail par Entité."""
    st.subheader("Carte météo du dernier Passage")
    consultation = _lecture(racine, repli)
    if consultation is None:
        return
    try:
        date_arrete = carte.date_carte(consultation)
        lignes = carte.lignes_carte(consultation)
        entites = [meteo.entite for meteo in consultation.meteo()]
    except UsineErreur as exc:
        _echec_lecture(exc, repli)
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


def _palier_affiche(palier_passage: Literal[1, 2]) -> Literal[1, 2]:
    """Palier affiché : le sélecteur n'est offert que pour un Passage Palier 2 (FR-46)."""
    if palier_passage == 1:
        return 1
    choix = st.radio(
        "Palier affiché",
        [2, 1],
        format_func=lambda palier: f"Palier {palier}",
        horizontal=True,
        key=navigation.CLE_PALIER,
        help="Palier 1 : la même Entité sans aucune sortie LLM.",
    )
    return 1 if choix == 1 else 2


def afficher_detail(racine: Path, repli: bool = False) -> None:
    """Détail d'une Entité : Météo, Règles, KPI clés, Prévision, Risque, Explication sourcée.

    Sur un Passage Palier 2, le sélecteur de Palier choisit le filtre `palier` des lectures
    LLM (Explication, narration) ; en Palier 1, aucune sortie LLM n'est lue.
    """
    st.subheader(Ecran.detail.value)
    consultation = _lecture(racine, repli)
    if consultation is None:
        return
    try:
        manifeste = consultation.manifeste()
        meteos = {meteo.entite: meteo for meteo in consultation.meteo()}
    except UsineErreur as exc:
        _echec_lecture(exc, repli)
        return
    if not meteos:
        st.info("Ce Passage ne contient aucune Météo.")
        return
    if st.session_state.get(navigation.CLE_ENTITE) not in meteos:
        st.session_state.pop(navigation.CLE_ENTITE, None)  # Entité absente de ce Passage
    entite = st.selectbox("Entité", list(meteos), key=navigation.CLE_ENTITE)
    palier = _palier_affiche(manifeste.palier)
    meteo = meteos[entite]
    try:
        regles = detail.lignes_regles(meteo, consultation.url_ticket)
        kpi = detail.lignes_kpi(consultation.kpi(entite=entite))
        calculees = detail.previsions_calculees(manifeste)
        previsions = consultation.previsions(entite=entite)
        risques = consultation.risques(entite=entite)
        narrations = consultation.narrations(entite=entite, palier=palier)
        explications = consultation.explications(entite=entite, palier=palier)
        prevision = detail.texte_prevision(meteo, previsions, calculees, narrations)
        explication = detail.texte_explication(palier, explications, consultation.url_ticket)
    except UsineErreur as exc:
        _echec_lecture(exc, repli)
        return
    st.markdown(f"**Météo** : {carte.libelle_meteo(meteo.couleur)}")
    _bloc("Règles déclenchantes", carte.tableau_markdown(regles) or detail.AUCUNE_REGLE)
    _bloc("KPI clés", carte.tableau_markdown(kpi) or detail.AUCUN_KPI)
    _bloc("Prévision de sortie du rouge", prevision)
    _bloc("Risque d'entrée en rouge", detail.texte_risques(meteo, risques, calculees))
    _bloc("Explication", explication)


def _moteur_indisponible(exc: ImportError | OSError) -> str:
    """Message d'une ligne qui nomme la cause : moteur Presidio ou modèle spaCy introuvable."""
    lignes = str(exc).strip().splitlines()
    cause = f"{type(exc).__name__} : {lignes[0]}" if lignes else type(exc).__name__
    return f"Moteur de Pseudonymisation indisponible (Presidio ou modèle spaCy) : {cause}"


def afficher_pseudonymisation(racine: Path, repli: bool = False) -> None:
    """Description d'un ticket et sa version pseudonymisée, côte à côte (FR-31, AD-15).

    L'aperçu vient de `ui/cli.apercu_pseudonymisation` : local, sans LLM ni écriture.
    """
    st.subheader(Ecran.pseudonymisation.value)
    consultation = _lecture(racine, repli)
    if consultation is None:
        return
    try:
        textes = pseudonymisation.descriptions(consultation.textes_tickets())
    except UsineErreur as exc:
        _echec_lecture(exc, repli)
        return
    if not textes:
        st.info(pseudonymisation.AUCUNE_DESCRIPTION)
        return
    if st.session_state.get(navigation.CLE_TICKET_APERCU) not in textes:
        st.session_state.pop(navigation.CLE_TICKET_APERCU, None)  # ticket absent du Passage
    cle = st.selectbox("Ticket", list(textes), key=navigation.CLE_TICKET_APERCU)
    original = textes[cle]
    try:
        version = apercu_pseudonymisation(racine)(original)
    except UsineErreur as exc:
        st.error(f"Aperçu de la Pseudonymisation impossible : {exc}")
        return
    except (ImportError, OSError) as exc:  # Presidio ou modèle spaCy indisponible
        st.error(_moteur_indisponible(exc))
        return
    st.markdown(f"Ticket : {lien_ticket(cle, consultation.url_ticket(cle))}")
    st.caption(pseudonymisation.LEGENDE)
    gauche, droite = st.columns(2)
    with gauche:
        st.markdown(f"#### {pseudonymisation.TITRE_ORIGINAL}")
        st.text(original)
    with droite:
        st.markdown(f"#### {pseudonymisation.TITRE_PSEUDONYMISE}")
        st.text(version)


def _temps_manuel(racine: Path) -> int | None:
    """Temps manuel déclaré dans `config/demo.yaml`, ou `None` après un message explicite."""
    try:
        config = config_demo(racine)
    except UsineErreur as exc:
        st.error(f"Configuration de la démo invalide : {exc}")
        return None
    if config is None:
        st.warning(avant_apres.CONFIG_ABSENTE)
        return None
    return config.temps_manuel_minutes_par_rapport


def _passage_repli(racine: Path) -> ManifestePassage | None:
    """Manifeste du Passage enregistré, s'il est sans classification initiale ; sinon `None`."""
    try:
        consultation = consultation_repli(racine)
        manifeste = None if consultation is None else consultation.manifeste()
    except (UsineErreur, OSError) as exc:
        _echec_lecture(exc, repli=True)
        return None
    if manifeste is None:
        st.error(REPLI_ABSENT)
        return None
    if manifeste.classification_initiale:
        st.warning(avant_apres.SEULE_CLASSIFICATION_INITIALE)
        return None
    return manifeste


def _passage_mesure(racine: Path, repli: bool) -> ManifestePassage | None:
    """Dernier Passage publié sans classification initiale, ou `None` après un message.

    En Mode repli : le Passage enregistré (`_passage_repli`).
    """
    if repli:
        return _passage_repli(racine)
    try:
        mesure, dernier = manifestes_avant_apres(racine)
    except (UsineErreur, OSError) as exc:
        st.error(f"Lecture des Passages publiés impossible : {exc}")
        return None
    if mesure is None:
        if dernier is None:
            st.info(avant_apres.AUCUN_PASSAGE)
        else:
            st.warning(avant_apres.SEULE_CLASSIFICATION_INITIALE)
    return mesure


def afficher_avant_apres(racine: Path, repli: bool = False) -> None:
    """Temps de reporting manuel déclaré et temps mesuré de la Chaîne, par Rapport et cumulé."""
    st.subheader(Ecran.avant_apres.value)
    if _racine_introuvable(racine):
        return
    minutes = _temps_manuel(racine)
    manifeste = _passage_mesure(racine, repli)
    if minutes is None or manifeste is None:
        return
    st.markdown(avant_apres.tableau_avant_apres(minutes, avant_apres.duree_mesuree(manifeste)))
    st.caption(avant_apres.legende(manifeste))


def afficher_outillage(racine: Path) -> None:
    """Fiche outillage de la Story 8.1, lue sous la racine et affichée telle quelle."""
    st.subheader(Ecran.outillage.value)
    if _racine_introuvable(racine):
        return
    try:
        fiche = outillage.lire_fiche(racine)
    except (OSError, UnicodeDecodeError) as exc:
        st.error(f"Lecture de la fiche outillage impossible : {exc}")
        return
    if fiche is None:
        st.warning(outillage.FICHE_ABSENTE)
        return
    st.caption(outillage.LEGENDE)
    st.markdown(fiche)


def afficher_agent(racine: Path, repli: bool = False) -> None:
    """Écran Agent, en lecture seule : question, réponse contrôlée, statut, outils appelés.

    La session vient de `ui/cli.session_agent`, gardée dans `session_state` tant que le dernier
    Passage publié ne change pas ; en Mode repli, aucun LLM n'est appelé : les réponses
    enregistrées sont rejouées (`_afficher_agent_repli`).
    """
    st.subheader(Ecran.agent.value)
    if repli:
        _afficher_agent_repli(racine)
        return
    if _racine_introuvable(racine):
        return
    try:
        consultation = consultation_dernier_passage(racine)
        passage_id = None if consultation is None else consultation.manifeste().passage_id
    except UsineErreur as exc:
        _echec_lecture(exc, repli)
        return
    if consultation is None:
        st.info(agent.AUCUN_PASSAGE)
        return
    st.caption(agent.LEGENDE)
    with st.form("formulaire_agent"):
        question = st.text_input(
            agent.LIBELLE_QUESTION,
            value=agent.QUESTION_DEMO,
            key=navigation.CLE_QUESTION_AGENT,
        )
        envoyee = st.form_submit_button(agent.LIBELLE_ENVOYER)
    if not envoyee or not question.strip():
        return
    session: agent.Session | None = st.session_state.get(navigation.CLE_SESSION_AGENT)
    if session is not None and session.passage_id != passage_id:
        session.fermer()  # nouveau Passage publié : nouvelle session
        session = None
    if session is None:
        st.session_state.pop(navigation.CLE_SESSION_AGENT, None)
        try:
            session = session_agent(racine, consultation)
        except UsineErreur as exc:
            st.error(f"Agent indisponible : la session ne peut être construite ({exc})")
            return
        st.session_state[navigation.CLE_SESSION_AGENT] = session
    try:
        reponse = session.repondre(question.strip())
    except Exception as exc:  # fournisseur, trace ou validation : message explicite
        st.error(f"Réponse de l'Agent impossible : {exc}")
        return
    _afficher_reponse(reponse)


def _afficher_reponse(reponse: ReponseAgent) -> None:
    """Texte de la réponse (avertissement si rejetée), statut de contrôle, outils appelés."""
    if reponse.statut_controle is StatutControle.rejete:
        st.warning(reponse.texte)
    else:
        st.markdown(echapper_markdown(reponse.texte))
    st.caption(agent.texte_statut(reponse))
    st.caption(agent.texte_outils(reponse))


def _afficher_agent_repli(racine: Path) -> None:
    """Mode repli : questions enregistrées en choix fermés, réponse rejouée sans LLM (FR-45).

    Réponses absentes, illisibles ou d'un autre Passage que la copie : refus explicite.
    """
    st.info(agent.MESSAGE_REPLI)
    if _racine_introuvable(racine):
        return
    try:
        consultation = consultation_repli(racine)
        if consultation is None:
            st.error(REPLI_ABSENT)
            return
        enregistrees = reponses_repli(racine, consultation.manifeste().passage_id)
    except UsineErreur as exc:
        st.error(f"{agent.REFUS_REPLI} : {exc}")
        return
    rang = st.radio(
        agent.LIBELLE_CHOIX,
        range(len(enregistrees)),
        format_func=lambda i: enregistrees[i].reponse.question,
        key=navigation.CLE_CHOIX_AGENT,
    )
    if not st.button(agent.LIBELLE_REJOUER) or rang is None:
        return
    enregistree = enregistrees[rang]
    _afficher_reponse(enregistree.reponse)
    st.caption(agent.mention_repli(enregistree))


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


def afficher_lancement(racine: Path, repli: bool = False) -> None:
    """Bouton de lancement et suivi de la progression, sans bloquer la page.

    Une fois la Chaîne terminée : la carte du dernier Passage publié après un succès, sinon
    `progression.AUCUN_RAPPORT` (jamais de rapport partiel). En Mode repli, le bouton reste
    visible mais désactivé : aucun nouveau lancement n'est possible.
    """
    st.subheader("Chaîne de reporting")
    en_cours = _en_cours()
    st.button(
        "Lancer la Chaîne",
        on_click=_lancer,
        args=(racine,),
        disabled=repli or en_cours or not racine.is_dir(),
    )
    if repli:
        st.info(LANCEMENT_REPLI)
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
        afficher_carte(st.session_state.get(_RACINE, racine), repli)
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
    erreur_racine: str | None = None
    try:
        racine = racine_ui()
    except UsineErreur as exc:
        erreur_racine = str(exc)  # affichée sous le bandeau, qui reste en tête
        racine = Path.cwd()  # la page reste utilisable : carte et lancement s'affichent
    ecran = Ecran(st.sidebar.radio("Écran", navigation.libelles_ecrans(), key=navigation.CLE_ECRAN))
    repli = afficher_bandeau(racine, erreur_racine)  # premier élément de la zone principale
    if ecran is not Ecran.lancement:
        afficher_resume()  # avant l'écran : une relance de fin évite de lire la carte deux fois
    st.title("Usine de migration")
    if ecran is Ecran.carte:
        afficher_carte(racine, repli)
    elif ecran is Ecran.detail:
        afficher_detail(racine, repli)
    elif ecran is Ecran.lancement:
        afficher_lancement(racine, repli)
    elif ecran is Ecran.avant_apres:
        afficher_avant_apres(racine, repli)
    elif ecran is Ecran.pseudonymisation:
        afficher_pseudonymisation(racine, repli)
    elif ecran is Ecran.outillage:
        afficher_outillage(racine)
    elif ecran is Ecran.agent:
        afficher_agent(racine, repli)
    else:
        afficher_a_venir(ecran)


principal()
