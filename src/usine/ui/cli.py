"""Sous-application `usine ui` et services de la page Streamlit (racine de composition, AD-1).

Module `cli` de la lane L7 : il démarre la page et lui fournit la racine (`USINE_RACINE`), le
Mode repli, la `Consultation` du dernier Passage publié ou du Passage enregistré du Mode repli
(`demo/repli/passage/`), la configuration de la démo (`config/demo.yaml`), les manifestes
mesurés par l'avant / après, l'aperçu de la Pseudonymisation (vue côte à côte) et la session
de l'Agent (`session_agent`) ou ses réponses enregistrées du Mode repli (`reponses_repli`).
La page n'importe ni `ports`, ni `config`, ni `adaptateurs` : elle passe par ces services.
"""

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

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
from usine.ia.agent.repli import REPERTOIRE_REPONSES, charger_reponses
from usine.ia.agent.session import SessionAgent
from usine.ports.consultation import Consultation
from usine.ui.avant_apres import FICHIER_CONFIG
from usine.ui.chaine import GestionChaine
from usine.ui.serveur import HOTE, LireConsultation, LireManifeste, creer_application
from usine.ui.textes import REPERTOIRE_REPLI as REPERTOIRE_REPLI
from usine.ui.textes import REPLI_ABSENT

CHEMIN_APP = Path(__file__).resolve().with_name("app.py")
"""Page Streamlit lancée par `usine ui`."""

app = typer.Typer(help="Interface web de la démo (FastAPI, 127.0.0.1).")

PORT = 8000
"""Port local par défaut de l'interface web."""


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


def commande_streamlit() -> list[str]:
    """`python -m streamlit run <usine/ui/app.py>` avec l'interpréteur courant."""
    return [sys.executable, "-m", "streamlit", "run", str(CHEMIN_APP)]


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


def application_web(racine: Path, repli: bool) -> FastAPI:
    """Application FastAPI de l'UI web sur `racine`, dans le mode imposé au démarrage."""
    return creer_application(
        repli=repli,
        lire_manifeste=lecture_manifeste(racine),
        lire_consultation=lecture_consultation(racine),
        chaine=GestionChaine(racine),
    )


def _lancer_streamlit() -> int:
    try:
        return subprocess.run(commande_streamlit(), check=False).returncode
    except KeyboardInterrupt:
        return 0
    except OSError as exc:
        typer.echo(f"Erreur : lancement de Streamlit impossible ({exc})", err=True)
        return 1


@app.callback(invoke_without_command=True)
def ui(
    streamlit: Annotated[
        bool, typer.Option("--streamlit", help="Ancienne interface Streamlit (retirée en 7.17).")
    ] = False,
    port: Annotated[int, typer.Option("--port", help="Port local de l'interface web.")] = PORT,
) -> None:
    """Démarre l'interface web sur 127.0.0.1 ; racine : `USINE_RACINE` ou répertoire courant."""
    if streamlit:
        raise typer.Exit(_lancer_streamlit())
    try:
        racine = racine_ui()
        repli = mode_repli(racine)
    except UsineErreur as exc:
        typer.echo(f"Erreur : {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"Interface web : http://{HOTE}:{port}/" + (" (Mode repli)" if repli else ""))
    try:
        uvicorn.run(application_web(racine, repli), host=HOTE, port=port, log_level="warning")
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        typer.echo(f"Erreur : démarrage du serveur impossible ({exc})", err=True)
        raise typer.Exit(1) from exc
    except SystemExit as exc:  # uvicorn journalise l'échec du bind puis sort (code 3)
        if exc.code in (0, None):
            return
        typer.echo(
            f"Erreur : démarrage du serveur impossible sur {HOTE}:{port} (port occupé ?)",
            err=True,
        )
        raise typer.Exit(1) from exc
