"""Lancement de la Chaîne et suivi de sa progression pour l'UI web (Story 7.15, AD-8, AD-25).

`GestionChaine` vit dans le processus serveur : elle démarre `usine rapport` en sous-processus
(une Chaîne à la fois), retient le processus et le fichier d'erreurs, et construit la vue
`VueChaine` à chaque sondage du navigateur. La progression se lit dans
`sorties/progression/<passage_id>.jsonl` en ouvrir-lire-fermer (`progression.lire_progression`) ;
aucun fichier ne reste ouvert entre deux sondages. Elle ne touche ni Passage ni Jira : c'est
`usine rapport` qui publie.
"""

import subprocess
import threading
from datetime import UTC
from pathlib import Path
from typing import IO

from usine.contrats.erreurs import UsineErreur
from usine.contrats.format import formater_date, formater_entier
from usine.contrats.passage import Etape, EvenementProgression, ManifestePassage, StatutEtape
from usine.ui import lancement, progression
from usine.ui.lancement import Lanceur
from usine.ui.textes import INTERVALLE_SONDAGE, LANCEMENT_REPLI, LIGNES_ERREUR_MAX
from usine.ui.vues import (
    EtatEtape,
    StatutChaine,
    VueBandeauChaine,
    VueBouton,
    VueChaine,
    VueDernierPassage,
    VueEtape,
    VueLien,
    VueLigneJournal,
)

DESCRIPTIONS: dict[Etape, str] = {
    Etape.extraction: "Lecture des tickets du projet",
    Etape.instantanes: "Instantanés quotidiens des états de tickets",
    Etape.kpi: "Calcul des KPI de chaque Entité",
    Etape.meteo: "Météo de chaque Entité, d'après les Règles déclenchantes",
    Etape.prevision: "Prévision de fermeture des Anomalies",
    Etape.classification: "Classification des Anomalies",
    Etape.repartition_causes: "Répartition des causes",
    Etape.explications: "Explications citées de la Météo",
    Etape.narration: "Narration du Rapport",
    Etape.rendu: "Rapport quotidien et Comité de pilotage",
}
"""Description de chaque étape, affichée en légende (DESIGN.md, Lancement de la Chaîne)."""

LIBELLE_LANCER = "Lancer la Chaîne"
LIBELLE_EN_COURS = "Chaîne en cours…"
LIBELLE_RELANCER = "Relancer la Chaîne"
LIBELLE_PASSER_REPLI = "Passer en Mode repli"
LIBELLE_REVENIR_REEL = "Revenir au Mode réel"
MOTIF_LANCEMENT_EN_COURS = "Une Chaîne est en cours : le lancement redevient possible à sa fin."
MOTIF_MODE_EN_COURS = "Le mode ne peut pas changer tant qu'une Chaîne tourne."
MOTIF_RACINE = "La racine du projet est introuvable : la Chaîne ne peut pas être lancée."
MESSAGE_SUCCES = "Chaîne terminée : Passage publié."
JOURNAL_ATTENTE = "En attente d'un lancement."
JOURNAL_VIDE = "Aucun événement de progression pour l'instant."
AUCUN_PASSAGE_LANCE = "Aucun Passage affiché : lancer la Chaîne pour en publier un."
AUCUN_PASSAGE_REPLI = "Aucun Passage enregistré à afficher en Mode repli."

_TERMINES = frozenset(
    {StatutEtape.reussie.value, StatutEtape.sautee.value, StatutEtape.echouee.value}
)
_ETATS: dict[str, EtatEtape] = {
    StatutEtape.en_cours.value: "en_cours",
    StatutEtape.reussie.value: "reussie",
    StatutEtape.sautee.value: "sautee",
    StatutEtape.echouee.value: "echouee",
}


class LancementRefuse(UsineErreur):
    """Lancement impossible : Chaîne déjà en cours, Mode repli ou racine absente."""


def _sans_marques(texte: str) -> str:
    """Texte de constante Markdown (`code`) affiché tel quel dans une page sans Markdown."""
    return texte.replace("`", "")


class GestionChaine:
    """Une Chaîne à la fois, lancée depuis le serveur ; l'état vit dans ce processus."""

    def __init__(self, racine: Path | None, popen: Lanceur = subprocess.Popen) -> None:
        self._racine = racine
        self._popen = popen
        self._verrou = threading.Lock()
        self._processus: subprocess.Popen[bytes] | None = None
        self._erreurs: IO[bytes] | None = None
        self._texte_erreur: str | None = None
        self._avant: frozenset[Path] = frozenset()
        self._fichier: Path | None = None
        self._echec_lancement: str | None = None

    # --- état ---

    def _en_cours(self) -> bool:
        return self._processus is not None and self._processus.poll() is None

    def en_cours(self) -> bool:
        """Vrai si la Chaîne lancée par ce serveur tourne encore."""
        with self._verrou:
            return self._en_cours()

    def _motif_lancement(self, repli: bool) -> str | None:
        if self._en_cours():
            return MOTIF_LANCEMENT_EN_COURS
        if repli:
            return _sans_marques(LANCEMENT_REPLI)
        if self._racine is None or not self._racine.is_dir():
            return MOTIF_RACINE
        return None

    # --- action ---

    def lancer(self, repli: bool) -> None:
        """Démarre `usine rapport`.

        `LancementRefuse` si une Chaîne tourne, en Mode repli ou sans racine. Un démarrage qui
        échoue (`OSError`) est consigné et affiché par la vue, sans lever.
        """
        with self._verrou:
            motif = self._motif_lancement(repli)
            if motif is not None or self._racine is None:
                raise LancementRefuse(motif or MOTIF_RACINE)
            if self._erreurs is not None:
                self._erreurs.close()
                self._erreurs = None
            self._fichier = None
            self._texte_erreur = None
            self._echec_lancement = None
            erreurs: IO[bytes] | None = None
            try:
                self._avant = progression.fichiers_progression(self._racine)
                erreurs = lancement.fichier_erreurs()
                self._processus = lancement.lancer_chaine(
                    self._racine, popen=self._popen, erreurs=erreurs
                )
            except OSError as exc:
                if erreurs is not None:
                    erreurs.close()
                self._processus = None
                self._echec_lancement = f"Lancement de la Chaîne impossible : {exc}"
                return
            self._erreurs = erreurs

    # --- vue ---

    def _evenements(self) -> tuple[EvenementProgression, ...]:
        if self._fichier is None and self._racine is not None:
            self._fichier = progression.fichier_nouveau(self._avant, self._racine)
        return progression.lire_progression(self._fichier) if self._fichier is not None else ()

    def _erreur_standard(self) -> str:
        """Erreur standard du sous-processus terminé, lue une seule fois (fichier alors fermé)."""
        if self._texte_erreur is None:
            erreurs, self._erreurs = self._erreurs, None
            self._texte_erreur = "" if erreurs is None else lancement.lire_erreurs(erreurs)
        return self._texte_erreur

    def vue(self, repli: bool, manifeste: ManifestePassage | None) -> VueChaine:
        """Vue de l'écran pour le mode courant et le Passage affiché `manifeste`."""
        with self._verrou:
            return self._vue(repli, manifeste)

    def _vue(self, repli: bool, manifeste: ManifestePassage | None) -> VueChaine:
        code = None if self._processus is None else self._processus.poll()
        statut: StatutChaine = "attente"
        if self._processus is not None:
            statut = "en_cours" if code is None else ("terminee" if code == 0 else "echec")
        erreur = self._echec_lancement
        try:
            evenements = self._evenements()
        except (UsineErreur, OSError) as exc:  # progression illisible : signalée, sondage maintenu
            erreur = str(exc)
            evenements = ()
        suivis = progression.suivi_des_etapes(evenements)
        etapes = [
            VueEtape(
                numero=rang,
                nom=suivi.etape.value,
                description=DESCRIPTIONS[suivi.etape],
                etat=_ETATS.get(suivi.etat, "en_attente"),
                libelle_etat=progression.LIBELLES_ETATS[suivi.etat],
                duree=None if suivi.duree is None else progression.texte_duree(suivi.duree),
            )
            for rang, suivi in enumerate(suivis, start=1)
        ]
        terminees = sum(1 for suivi in suivis if suivi.etat in _TERMINES)
        motif_lancement = self._motif_lancement(repli)
        en_cours = statut == "en_cours"
        if en_cours:
            libelle_lancement = LIBELLE_EN_COURS
        elif statut in ("terminee", "echec"):
            libelle_lancement = LIBELLE_RELANCER
        else:
            libelle_lancement = LIBELLE_LANCER
        return VueChaine(
            statut=statut,
            en_cours=en_cours,
            intervalle_ms=round(INTERVALLE_SONDAGE * 1000),
            bouton_lancement=VueBouton(
                libelle=libelle_lancement,
                bloque=motif_lancement is not None,
                motif=motif_lancement,
            ),
            bouton_mode=VueBouton(
                libelle=LIBELLE_REVENIR_REEL if repli else LIBELLE_PASSER_REPLI,
                bloque=en_cours,
                motif=MOTIF_MODE_EN_COURS if en_cours else None,
            ),
            mode_cible="reel" if repli else "repli",
            etapes=etapes,
            terminees=terminees,
            total=len(etapes),
            compteur=f"{terminees} / {len(etapes)}",
            annonce=_annonce(statut, evenements),
            journal=_journal(evenements),
            journal_vide=JOURNAL_ATTENTE if statut == "attente" else JOURNAL_VIDE,
            bandeau=self._bandeau(code, evenements),
            erreur=erreur,
            dernier_passage=None if manifeste is None else vue_dernier_passage(manifeste),
            message_dernier_passage=AUCUN_PASSAGE_REPLI if repli else AUCUN_PASSAGE_LANCE,
        )

    def _bandeau(
        self, code: int | None, evenements: tuple[EvenementProgression, ...]
    ) -> VueBandeauChaine | None:
        if code is None:
            return None
        message = self._erreur_standard()  # lu et fermé dans les deux issues
        if code == 0:
            return VueBandeauChaine(
                variante="succes",
                texte=MESSAGE_SUCCES,
                lignes=[],
                complement=None,
                lien=VueLien(libelle="Voir la carte météo", url="/"),
            )
        lignes = message.splitlines()[-LIGNES_ERREUR_MAX:] or ["aucun message"]
        return VueBandeauChaine(
            variante="erreur",
            texte=f"Échec de la Chaîne {_lieu_echec(evenements)} (code {code}).",
            lignes=lignes,
            complement=progression.AUCUN_RAPPORT,
            lien=None,
        )


def _annonce(statut: StatutChaine, evenements: tuple[EvenementProgression, ...]) -> str:
    """Texte de la région `status` : étape courante, fin ou échec, sinon rien."""
    if statut == "terminee":
        return MESSAGE_SUCCES
    if statut == "echec":
        return f"Échec de la Chaîne {_lieu_echec(evenements)}."
    if statut == "attente":
        return ""
    courante = _etape_courante(evenements)
    if courante is not None:
        rang = list(Etape).index(courante) + 1
        return f"Étape {rang} sur {len(Etape)} : {courante.value}"
    return "" if evenements else LIBELLE_EN_COURS


def _etape_courante(evenements: tuple[EvenementProgression, ...]) -> Etape | None:
    """Dernière étape `en_cours` non encore terminée."""
    courante: Etape | None = None
    for evenement in evenements:
        if evenement.statut is StatutEtape.en_cours:
            courante = evenement.etape
        elif evenement.etape is courante:
            courante = None
    return courante


def _lieu_echec(evenements: tuple[EvenementProgression, ...]) -> str:
    """`à l'étape « X »` ou `hors d'une étape`, selon la progression."""
    etape = progression.etape_en_echec(evenements)
    return "hors d'une étape" if etape is None else f"à l'étape « {etape.value} »"


def _journal(evenements: tuple[EvenementProgression, ...]) -> list[VueLigneJournal]:
    """Lignes horodatées (UTC), la plus récente en premier."""
    lignes: list[VueLigneJournal] = []
    for evenement in reversed(evenements):
        texte = f"{evenement.etape.value} : {progression.LIBELLES_ETATS[evenement.statut]}"
        if evenement.message:
            texte += f" · {evenement.message}"
        horodatage = f"{evenement.horodatage.astimezone(UTC):%H:%M:%S}"
        lignes.append(VueLigneJournal(horodatage=horodatage, texte=texte))
    return lignes


def vue_dernier_passage(manifeste: ManifestePassage) -> VueDernierPassage:
    """Encart « Dernier Passage » : date, durée, tickets extraits et identifiant, du manifeste."""
    duree = progression.texte_duree(manifeste.horodatage_fin - manifeste.horodatage_debut)
    return VueDernierPassage(
        lignes=[
            f"Date d'arrêté {formater_date(manifeste.date_arrete)} · durée {duree}",
            f"{formater_entier(manifeste.nb_tickets)} tickets extraits",
            f"Passage {manifeste.passage_id}",
        ]
    )
