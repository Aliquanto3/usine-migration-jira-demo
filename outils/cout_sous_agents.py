"""Coût réel d'un sous-agent Claude Code, en équivalent API, à partir de sa transcription.

Le nombre de tokens affiché à la fin d'un sous-agent mélange des tokens dont le prix varie
de 1 à 100. Ce script somme l'usage de chaque réponse par catégorie (entrée, écriture du
cache, lecture du cache, sortie), puis applique les prix par Mtok.

Transcriptions : `~/.claude/projects/<projet>/<session>/subagents/agent-<id>.jsonl`.
Usage : uv run python outils/cout_sous_agents.py <fichier.jsonl> [...]
        uv run python outils/cout_sous_agents.py --session <dossier de session> [--ids a1 a2]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# $/Mtok : entrée, sortie, lecture du cache (tarifs API d'octobre 2026).
# Haiku : lecture du cache supposée à 0,1 x l'entrée (non publiée dans nos sources).
PRIX: dict[str, tuple[float, float, float]] = {
    "fable": (10.0, 50.0, 0.25),
    "opus": (4.0, 20.0, 0.20),
    "sonnet": (2.0, 10.0, 0.20),
    "haiku": (0.10, 0.50, 0.01),
}
# Écriture du cache : 1,25 x l'entrée (TTL 5 min) ou 2 x (TTL 1 h).
FACTEUR_ECRITURE = {"5m": 1.25, "1h": 2.0}
CLES = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


def usage_par_modele(chemin: Path) -> dict[str, Counter[str]]:
    """Somme l'usage final de chaque réponse (une réponse peut s'étaler sur plusieurs lignes)."""
    dernieres: dict[str, tuple[str, dict[str, int]]] = {}
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        try:
            entree = json.loads(ligne)
        except ValueError:
            continue
        message = entree.get("message") or {}
        usage = message.get("usage")
        if not usage or message.get("role") != "assistant":
            continue
        valeurs = {cle: int(usage.get(cle) or 0) for cle in CLES}
        cle = str(message.get("id"))
        precedent = dernieres.get(cle)
        if precedent is None or valeurs["output_tokens"] >= precedent[1]["output_tokens"]:
            dernieres[cle] = (str(message.get("model", "?")), valeurs)
    totaux: dict[str, Counter[str]] = {}
    for modele, valeurs in dernieres.values():
        total = totaux.setdefault(modele, Counter())
        total["appels"] += 1
        total.update(valeurs)
    return totaux


def cout(modele: str, total: Counter[str], ttl: str) -> float | None:
    famille = next((nom for nom in PRIX if nom in modele), None)
    if famille is None:
        return None
    entree, sortie, lecture = PRIX[famille]
    return (
        total["input_tokens"] * entree
        + total["cache_creation_input_tokens"] * entree * FACTEUR_ECRITURE[ttl]
        + total["cache_read_input_tokens"] * lecture
        + total["output_tokens"] * sortie
    ) / 1e6


def main() -> int:
    for flux in (sys.stdout, sys.stderr):
        flux.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("fichiers", nargs="*", type=Path)
    analyseur.add_argument("--session", type=Path, help="dossier de session (contient subagents/)")
    analyseur.add_argument("--ids", nargs="*", default=[], help="ids d'agents à retenir")
    analyseur.add_argument("--ttl", choices=sorted(FACTEUR_ECRITURE), default="5m")
    options = analyseur.parse_args()
    fichiers = list(options.fichiers)
    if options.session:
        motifs = [f"agent-{i}.jsonl" for i in options.ids] or ["agent-*.jsonl"]
        for motif in motifs:
            fichiers.extend(sorted((options.session / "subagents").glob(motif)))
    if not fichiers:
        analyseur.error("aucune transcription")
    print("agent | modèle | appels | entrée | écriture cache | lecture cache | sortie | coût $")
    for chemin in fichiers:
        for modele, total in usage_par_modele(chemin).items():
            montant = cout(modele, total, options.ttl)
            texte = "?" if montant is None else f"{montant:.2f}"
            print(
                f"{chemin.stem} | {modele} | {total['appels']} | {total['input_tokens']} | "
                f"{total['cache_creation_input_tokens']} | {total['cache_read_input_tokens']} | "
                f"{total['output_tokens']} | {texte}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
