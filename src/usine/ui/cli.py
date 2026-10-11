"""Sous-application `usine ui` : démarre l'interface de démo Streamlit."""

import subprocess
import sys
from pathlib import Path

import typer

CHEMIN_APP = Path(__file__).resolve().with_name("app.py")
"""Page Streamlit lancée par `usine ui`."""

app = typer.Typer(help="Interface de démo Streamlit.")


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
