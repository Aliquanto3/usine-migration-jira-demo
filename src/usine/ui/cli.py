"""Sous-application `usine ui` et services de l'interface web (racine de composition, AD-1).

Module `cli` de la lane L7 : il démarre le serveur web et lui fournit la racine (`USINE_RACINE`), le
Mode repli, la `Consultation` du dernier Passage publié ou du Passage enregistré du Mode repli
(`demo/repli/passage/`), la configuration de la démo (`config/demo.yaml`), les manifestes
mesurés par l'avant / après, l'aperçu de la Pseudonymisation (vue côte à côte) et la session
de l'Agent (`session_agent`) ou ses réponses enregistrées du Mode repli (`reponses_repli`).
La page n'importe ni `ports`, ni `config`, ni `adaptateurs` : elle passe par ces services.
"""

import os
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, cast

import typer
import uvicorn
from fastapi import FastAPI

from usine import composition
from usine.config import charger_secrets, charger_yaml
from usine.consultation.passage import ConsultationPassage
from usine.contrats.config import ConfigDemo
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import ReponseAgentEnregistree
from usine.contrats.passage import FICHIERS_PASSAGE, REPERTOIRE_PASSAGES, ManifestePassage
from usine.ia.agent.repli import QUESTIONS_DEMO, REPERTOIRE_REPONSES, charger_reponses
from usine.ia.agent.session import SANS_REPONSE, SessionAgent
from usine.ports.consultation import Consultation
from usine.ui.avant_apres import FICHIER_CONFIG
from usine.ui.chaine import GestionChaine
from usine.ui.ecrans import LectureEcransAgent, ServicesEcrans
from usine.ui.outillage import lire_fiche
from usine.ui.serveur import HOTE, LireConsultation, LireManifeste, creer_application
from usine.ui.textes import REPERTOIRE_REPLI as REPERTOIRE_REPLI
from usine.ui.textes import REPLI_ABSENT

app = typer.Typer(help="Interface web de la démo (FastAPI, 127.0.0.1).")

PORT = 8000
"""Port local par défaut de l'interface web."""

VARIABLE_HOTE = "USINE_UI_HOTE"
"""Variable d'environnement réservée au conteneur (Dockerfile) : adresse d'écoute du serveur."""

HOTE_CONTENEUR = "0.0.0.0"
"""Seule autre adresse d'écoute permise : la publication de port d'un conteneur n'atteint pas
127.0.0.1 du conteneur. Le contrôle du `Host` et de l'`Origin` reste celui de `HOTE`."""


def hote_ecoute() -> str:
    """Adresse d'écoute : `HOTE` (127.0.0.1) sauf `USINE_UI_HOTE=0.0.0.0` (conteneur seulement).

    Lue dans l'environnement du processus, jamais dans `.env`. Toute autre valeur lève une
    `UsineErreur` qui nomme la variable.
    """
    valeur = os.environ.get(VARIABLE_HOTE, "").strip()
    if valeur in ("", HOTE):
        return HOTE
    if valeur == HOTE_CONTENEUR:
        return HOTE_CONTENEUR
    raise UsineErreur(
        f"{VARIABLE_HOTE}={valeur!r} refusée (valeurs permises : {HOTE} ou {HOTE_CONTENEUR})"
    )


def racine_ui() -> Path:
    """`USINE_RACINE` (environnement ou `.env` du répertoire courant), sinon le répertoire courant.

    Une variable illisible lève une `UsineErreur` qui la nomme.
    """
    courant = Path.cwd()
    racine = (charger_secrets(courant).usine_racine or "").strip()
    return Path(racine) if racine else courant


def mode_repli(racine: Path) -> bool:
    """Mode repli demandé par `USINE_MODE_REPLI` (environnement ou `racine/.env`), jamais déduit.

    Une valeur illisible lève une `UsineErreur` qui nomme la variable.
    """
    return charger_secrets(racine).usine_mode_repli


def consultation_dernier_passage(racine: Path) -> Consultation | None:
    """`Consultation` du dernier Passage publié sous `racine/sorties/passages/`, ou `None`.

    L'URL Jira vient de `composition.url_jira` : `None` en Mode repli.
    """
    racine_passages = racine / REPERTOIRE_PASSAGES
    lecteur = ConsultationPassage(racine_passages, racine_passages=racine_passages)
    manifeste = lecteur.dernier_passage()
    if manifeste is None:
        return None
    return ConsultationPassage(
        racine_passages / manifeste.date_arrete.isoformat() / manifeste.passage_id,
        racine_passages=racine_passages,
        url_jira=composition.url_jira(racine),
        date_arrete=manifeste.date_arrete,
    )


def consultation_repli(racine: Path) -> Consultation | None:
    """`Consultation` du Passage enregistré `racine/demo/repli/passage/`, sans URL Jira.

    `None` si son `manifeste.json` est absent : jamais de repli vers `sorties/passages/`.
    """
    repertoire = racine / REPERTOIRE_REPLI
    if not (repertoire / FICHIERS_PASSAGE["manifeste"]).exists():
        return None
    return ConsultationPassage(repertoire, racine_passages=repertoire, url_jira=None)


def config_demo(racine: Path) -> ConfigDemo | None:
    """`racine/config/demo.yaml` validé par `ConfigDemo`, ou `None` si le fichier est absent.

    Un fichier invalide lève l'`UsineErreur` de `charger_yaml` (fichier, clé et valeur).
    """
    chemin = racine / FICHIER_CONFIG
    if not chemin.exists():
        return None
    return charger_yaml(chemin, ConfigDemo)


def manifestes_avant_apres(
    racine: Path,
) -> tuple[ManifestePassage | None, ManifestePassage | None]:
    """Derniers manifestes publiés sous `racine/sorties/passages/`, ou `None` pour chacun.

    Le premier est le dernier Passage sans classification initiale (mesure de l'avant /
    après), le second le dernier Passage tous Passages confondus.
    """
    racine_passages = racine / REPERTOIRE_PASSAGES
    lecteur = ConsultationPassage(racine_passages, racine_passages=racine_passages)
    return (
        lecteur.dernier_passage(sans_classification_initiale=True),
        lecteur.dernier_passage(),
    )


def manifestes_mesures(
    racine: Path, repli: bool
) -> tuple[ManifestePassage | None, ManifestePassage | None]:
    """Manifestes de l'avant / après dans le mode donné : (mesuré, dernier).

    Mode réel : `manifestes_avant_apres`. Mode repli : le Passage enregistré, mesuré seulement
    s'il est sans classification initiale ; copie absente : `UsineErreur` (`REPLI_ABSENT`).
    """
    if not repli:
        return manifestes_avant_apres(racine)
    consultation = consultation_repli(racine)
    if consultation is None:
        raise UsineErreur(REPLI_ABSENT)
    manifeste = consultation.manifeste()
    return (None if manifeste.classification_initiale else manifeste), manifeste


def apercu_pseudonymisation(racine: Path) -> Callable[[str], str]:
    """`Pseudonymiseur.apercu` construit par la composition (AD-15) : local, sans écriture.

    `USINE_CLE_PSEUDO` absente ou invalide lève une `UsineErreur` qui nomme la variable.
    """
    return composition.apercu_pseudonymisation(racine)


def session_agent(racine: Path, consultation: Consultation) -> SessionAgent:
    """`SessionAgent` de la composition sur le Passage de `consultation` (FR-39, FR-40).

    Fournisseur, plafond et Pseudonymisation de `config/llm.yaml` et des secrets ; une
    configuration ou une clé absente lève une `UsineErreur` qui la nomme.
    """
    return composition.construire_session_agent(racine, consultation)


def reponses_repli(racine: Path, passage_id: str) -> tuple[ReponseAgentEnregistree, ...]:
    """Réponses enregistrées de l'Agent (`racine/demo/repli/agent/*.json`) sur `passage_id`.

    Aucune réponse, fichier illisible ou `passage_id` différent : `UsineErreur` explicite.
    """
    return charger_reponses(racine / REPERTOIRE_REPONSES, passage_id)


def lecture_manifeste(racine: Path) -> LireManifeste:
    """Service du serveur : manifeste du Passage affiché (dernier Passage publié ou repli).

    En Mode repli, la copie `demo/repli/passage/` absente est une erreur explicite
    (`REPLI_ABSENT`), jamais un repli silencieux vers `sorties/passages/`.
    """

    def lire(repli: bool) -> ManifestePassage | None:
        if not repli:  # manifeste seul : ni `.env` ni `config/jira.yaml` relus (URL Jira inutile)
            racine_passages = racine / REPERTOIRE_PASSAGES
            lecteur = ConsultationPassage(racine_passages, racine_passages=racine_passages)
            return lecteur.dernier_passage()
        consultation = consultation_repli(racine)
        if consultation is None:
            raise UsineErreur(REPLI_ABSENT)
        return consultation.manifeste()

    return lire


def lecture_consultation(racine: Path) -> LireConsultation:
    """Service du serveur : `Consultation` du Passage affiché (dernier Passage publié ou repli).

    En Mode repli, la copie `demo/repli/passage/` absente est une erreur explicite
    (`REPLI_ABSENT`), jamais un repli silencieux vers `sorties/passages/`.
    """

    def lire(repli: bool) -> Consultation | None:
        if not repli:
            return consultation_dernier_passage(racine)
        consultation = consultation_repli(racine)
        if consultation is None:
            raise UsineErreur(REPLI_ABSENT)
        return consultation

    return lire


def services_ecrans(racine: Path) -> ServicesEcrans:
    """Services des écrans Agent, Avant / après, Pseudonymisation et Outillage sur `racine`."""

    def fabrique(consultation: LectureEcransAgent) -> SessionAgent:
        return session_agent(racine, cast("Consultation", consultation))

    return ServicesEcrans(
        session_agent=fabrique,
        reponses_repli=lambda passage_id: reponses_repli(racine, passage_id),
        questions_suggerees=QUESTIONS_DEMO,
        texte_hors_perimetre=SANS_REPONSE,
        apercu_pseudonymisation=lambda: apercu_pseudonymisation(racine),
        config_demo=lambda: config_demo(racine),
        manifestes_avant_apres=lambda repli: manifestes_mesures(racine, repli),
        lire_fiche=lambda: lire_fiche(racine),
    )


def application_web(racine: Path, repli: bool) -> FastAPI:
    """Application FastAPI de l'UI web sur `racine`, dans le mode imposé au démarrage."""
    return creer_application(
        repli=repli,
        lire_manifeste=lecture_manifeste(racine),
        lire_consultation=lecture_consultation(racine),
        chaine=GestionChaine(racine),
        services=services_ecrans(racine),
    )


@app.callback(invoke_without_command=True)
def ui(
    port: Annotated[int, typer.Option("--port", help="Port local de l'interface web.")] = PORT,
) -> None:
    """Démarre l'interface web sur 127.0.0.1 ; racine : `USINE_RACINE` ou répertoire courant."""
    try:
        racine = racine_ui()
        repli = mode_repli(racine)
        hote = hote_ecoute()
    except UsineErreur as exc:
        typer.echo(f"Erreur : {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(
        f"Interface web : http://{HOTE}:{port}/"
        + (" (Mode repli)" if repli else "")
        + (
            f" (écoute sur {hote} dans le conteneur ; publier avec -p {HOTE}:{port}:{port})"
            if hote != HOTE
            else ""
        )
    )
    try:
        uvicorn.run(application_web(racine, repli), host=hote, port=port, log_level="warning")
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        typer.echo(f"Erreur : démarrage du serveur impossible ({exc})", err=True)
        raise typer.Exit(1) from exc
    except SystemExit as exc:  # uvicorn journalise l'échec du bind puis sort (code 3)
        if exc.code in (0, None):
            return
        typer.echo(
            f"Erreur : démarrage du serveur impossible sur {hote}:{port} (port occupé ?)",
            err=True,
        )
        raise typer.Exit(1) from exc
