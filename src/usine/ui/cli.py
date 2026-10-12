"""Sous-application `usine ui` et services de la page Streamlit (racine de composition, AD-1).

Module `cli` de la lane L7 : il démarre la page et lui fournit la racine (`USINE_RACINE`), le
Mode repli, la `Consultation` du dernier Passage publié ou du Passage enregistré du Mode repli
(`demo/repli/passage/`), la configuration de la démo (`config/demo.yaml`) et les manifestes
mesurés par l'avant / après. La page n'importe ni `ports`, ni `config`, ni `adaptateurs` :
elle passe par ces services.
"""

import subprocess
import sys
from pathlib import Path

import typer

from usine import composition
from usine.config import charger_secrets, charger_yaml
from usine.consultation.passage import ConsultationPassage
from usine.contrats.config import ConfigDemo
from usine.contrats.passage import FICHIERS_PASSAGE, REPERTOIRE_PASSAGES, ManifestePassage
from usine.ports.consultation import Consultation
from usine.ui.avant_apres import FICHIER_CONFIG

CHEMIN_APP = Path(__file__).resolve().with_name("app.py")
"""Page Streamlit lancée par `usine ui`."""

REPERTOIRE_REPLI = Path("demo/repli/passage")
"""Passage publié fictif et versionné, lu par toute l'UI en Mode repli (relatif à la racine).

Régénération, depuis un clone sans secrets Jira et avec `USINE_MODE_REPLI=1` :
`usine donnees generer --graine 42 --date-generation 2026-10-12`, puis
`usine rapport --date-arrete 2026-10-09`, puis copie de
`sorties/passages/2026-10-09/<passage_id>/` vers `demo/repli/passage/`. Régénérée en Story 5.6
sur le Journal des contrats 1.2 (A et B rouges, C orange). `passage_id` actuel :
`20261012T221158Z-96c621`, repris par les réponses enregistrées de l'Agent (Story 7.11).
"""

app = typer.Typer(help="Interface de démo Streamlit.")


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


def commande_streamlit() -> list[str]:
    """`python -m streamlit run <usine/ui/app.py>` avec l'interpréteur courant."""
    return [sys.executable, "-m", "streamlit", "run", str(CHEMIN_APP)]


@app.callback(invoke_without_command=True)
def ui() -> None:
    """Démarre la page Streamlit ; la racine est le répertoire courant (ou `USINE_RACINE`)."""
    try:
        code = subprocess.run(commande_streamlit(), check=False).returncode
    except KeyboardInterrupt:
        code = 0
    except OSError as exc:
        typer.echo(f"Erreur : lancement de Streamlit impossible ({exc})", err=True)
        code = 1
    raise typer.Exit(code)
