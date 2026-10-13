"""Contrôle rapide pour les agents : ruff, format, mypy, import-linter, sans pytest.

Imprime une ligne courte si tout passe, sinon les seules erreurs utiles (tronquées), sur stderr.
Code de sortie : 0 si tout passe, 2 sinon (un hook Claude Code renvoie alors stderr à l'agent).
Usage : uv run python outils/controle_rapide.py [--racine <dépôt>]
Mode hook (agent `dev-story`) : `--hook` lit le JSON du hook sur stdin
et contrôle les worktrees de lane en cours de travail ; il bloque au plus deux fois par sous-agent.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

CONTROLES: tuple[tuple[str, list[str]], ...] = (
    ("ruff", ["ruff", "check", ".", "--output-format", "concise", "--quiet"]),
    ("format", ["ruff", "format", "--check", "--quiet", "."]),
    ("mypy", ["mypy", "--no-error-summary"]),
    ("lint-imports", ["lint-imports", "--no-cache"]),
)
LIGNES_MAX = 15


def _erreurs(nom: str, sortie: str) -> list[str]:
    lignes = [ligne for ligne in sortie.splitlines() if ligne.strip()]
    if nom == "lint-imports":
        lignes = [ligne for ligne in lignes if "BROKEN" in ligne or "->" in ligne] or lignes
    return lignes


def _git(racine: Path, *args: str) -> str:
    resultat = subprocess.run(
        ["git", "-C", str(racine), *args], capture_output=True, text=True, check=False
    )
    return resultat.stdout


def _cibles_du_hook(racine: Path, message: str = "") -> list[Path]:
    """Worktrees de lane en cours de travail (fichiers modifiés ou commits absents de main).

    Si le dernier message de l'agent nomme un ou plusieurs de ces worktrees, seuls ceux-là sont
    contrôlés : des agents parallèles ne se bloquent pas sur le travail des autres.
    """
    worktrees = [
        Path(ligne.removeprefix("worktree ").strip())
        for ligne in _git(racine, "worktree", "list", "--porcelain").splitlines()
        if ligne.startswith("worktree ")
    ]
    principal = worktrees[0] if worktrees else racine
    cibles = [
        wt
        for wt in worktrees[1:]
        if _git(wt, "status", "--porcelain", "--untracked-files=no").strip()
        or _git(wt, "rev-list", "main..HEAD").strip()
    ]
    nommees = [wt for wt in cibles if wt.name in message]
    return nommees or cibles or [principal]


def _hook(racine: Path) -> int:
    """Mode hook SubagentStop : bloque au plus deux fois par sous-agent, pour éviter une boucle."""
    try:
        entree = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        entree = {}
    compteur = Path(tempfile.gettempdir()) / f"controle_rapide_{entree.get('agent_id', 'inconnu')}"
    blocages = int(compteur.read_text()) if compteur.exists() else 0
    if blocages >= 2:
        print("Contrôle rapide : deux blocages déjà faits, arrêt laissé à l'agent.")
        return 0
    code = 0
    for cible in _cibles_du_hook(racine, str(entree.get("last_assistant_message", ""))):
        code = max(code, _controler(cible))
    if code:
        compteur.write_text(str(blocages + 1))
    return code


def main() -> int:
    for flux in (sys.stdout, sys.stderr):
        flux.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--racine", type=Path, default=Path.cwd())
    analyseur.add_argument("--hook", action="store_true", help="mode hook SubagentStop")
    options = analyseur.parse_args()
    if options.hook:
        return _hook(options.racine)
    return _controler(options.racine)


def _controler(racine: Path) -> int:
    echecs: list[str] = []
    for nom, commande in CONTROLES:
        resultat = subprocess.run(
            ["uv", "run", "--no-sync", *commande],
            cwd=racine,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if resultat.returncode != 0:
            lignes = _erreurs(nom, resultat.stdout + resultat.stderr)
            reste = len(lignes) - LIGNES_MAX
            echecs.append(f"[{nom}] {len(lignes)} ligne(s) d'erreur")
            echecs.extend(lignes[:LIGNES_MAX])
            if reste > 0:
                echecs.append(f"… {reste} ligne(s) de plus")
    if echecs:
        print(
            f"Contrôle rapide en échec dans {racine}, à corriger avant de conclure :",
            file=sys.stderr,
        )
        print("\n".join(echecs), file=sys.stderr)
        return 2
    print(f"Contrôle rapide OK dans {racine} (ruff, format, mypy, lint-imports).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
