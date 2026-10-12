"""Contrôle CI : sur une branche `lane/<n>-*`, chaque fichier modifié appartient à la lane n.

Recopie de la *Carte des lanes* du spine d'architecture (AD-21) : le spine fait foi, et
`tests/depot/test_controle_lanes.py` vérifie que `LANES` lui est identique. Chaque lane écrit
aussi dans `tests/unit/<chemin de ses répertoires source>` et, pour un module `<dir>/<nom>`,
dans le test plat `tests/unit/<dir>/test_<nom>.py`.
"""

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass

SRC = "src/usine/"


@dataclass(frozen=True)
class Lane:
    """Répertoires (ou fichiers) qu'une lane peut modifier, et ses exceptions."""

    nom: str
    chemins: tuple[str, ...]
    exclus: tuple[str, ...] = ()


LANES: dict[int, Lane] = {
    1: Lane("Données", (f"{SRC}generateur", "outils", "config/programme.yaml", "donnees/corpus")),
    2: Lane(
        "Extraction",
        (
            *(
                f"{SRC}adaptateurs/{m}"
                for m in (
                    "jira_http",
                    "jira_cloud",
                    "jira_dc",
                    "journal",
                    "composite",
                    "entrepot_duckdb",
                    "cli",
                )
            ),
            "config/jira.yaml",
            "tests/fixtures/jira_cloud",
            "tests/fixtures/jira_dc",
        ),
    ),
    3: Lane(
        "Calcul",
        (
            f"{SRC}domaine/instantanes",
            f"{SRC}domaine/kpi",
            f"{SRC}domaine/meteo",
            "config/grille_meteo.yaml",
            "tests/fixtures/reference",
        ),
    ),
    4: Lane("Prévision", (f"{SRC}domaine/prevision", "evaluation")),
    5: Lane("Rapport", (f"{SRC}chaine", f"{SRC}consultation", f"{SRC}rendu", "gabarits")),
    6: Lane(
        "Couche LLM",
        (
            f"{SRC}ia",
            f"{SRC}domaine/causes",
            f"{SRC}adaptateurs/llm",
            f"{SRC}adaptateurs/presidio",
            f"{SRC}adaptateurs/pseudonymisation",
            f"{SRC}adaptateurs/stockage_sqlite",
            "config/llm.yaml",
            "config/pseudonymisation.yaml",
            "evals",
        ),
        exclus=(f"{SRC}ia/agent", "evals/agent"),
    ),
    7: Lane(
        "Agent et UI",
        (f"{SRC}ia/agent", f"{SRC}ui", "demo", "config/demo.yaml", "evals/agent"),
    ),
    8: Lane("Portage", ("docs",)),
}

# Suivi BMAD des stories : mis à jour par chaque lane.
TOLERES = ("_bmad-output/implementation-artifacts",)

_BRANCHE = re.compile(r"^lane/(\d+)-.+")


def _couvre(chemin: str, fichier: str) -> bool:
    """Vrai si `fichier` est `chemin`, son module `chemin.py` ou un fichier sous `chemin/`."""
    return fichier in (chemin, f"{chemin}.py") or fichier.startswith(f"{chemin}/")


def _miroir_tests(chemin: str) -> list[str]:
    """Chemins des tests unitaires miroirs d'un chemin.

    Pour un module source `<dir>/<nom>` : `tests/unit/<dir>/<nom>` (répertoire ou module)
    et le test plat `tests/unit/<dir>/test_<nom>.py`.
    """
    if not chemin.startswith(SRC):
        return ["tests/unit/" + chemin]
    relatif = chemin.removeprefix(SRC)
    repertoire, _, nom = relatif.rpartition("/")
    plat = f"{repertoire}/test_{nom}.py" if repertoire else f"test_{nom}.py"
    return ["tests/unit/" + relatif, "tests/unit/" + plat]


def numero_lane(branche: str) -> int | None:
    """Numéro de lane d'une branche `lane/<n>-*`, ou `None` pour toute autre branche."""
    correspondance = _BRANCHE.match(branche)
    return int(correspondance.group(1)) if correspondance else None


def fichiers_hors_lane(numero: int, fichiers: list[str]) -> list[str]:
    """Fichiers modifiés qui sortent des répertoires de la lane `numero`."""
    if numero not in LANES:
        return list(fichiers)
    lane = LANES[numero]
    autorises = [*lane.chemins, *(m for c in lane.chemins for m in _miroir_tests(c)), *TOLERES]
    exclus = [*lane.exclus, *(m for c in lane.exclus for m in _miroir_tests(c))]
    return [
        f
        for f in fichiers
        if not any(_couvre(c, f) for c in autorises) or any(_couvre(c, f) for c in exclus)
    ]


def _fichiers_modifies(base: str) -> list[str]:
    """Fichiers modifiés depuis `base`, non échappés ; un renommage donne ses deux chemins."""
    sortie = subprocess.run(
        [
            "git",
            "-c",
            "core.quotepath=off",
            "diff",
            "--name-only",
            "-z",
            "--no-renames",
            f"{base}...HEAD",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="surrogateescape",
    ).stdout
    return [chemin for chemin in sortie.split("\0") if chemin]


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--branche", required=True)
    parseur.add_argument("--base", default="origin/main")
    args = parseur.parse_args(argv)

    numero = numero_lane(args.branche)
    if numero is None and args.branche.startswith("lane/"):
        print(f"{args.branche} : branche de lane mal formée, attendu lane/<n>-<nom>.")
        return 1
    if numero is None:
        print(f"{args.branche} : pas une branche de lane, contrôle sans objet.")
        return 0
    if numero not in LANES:
        print(f"{args.branche} : lane {numero} inconnue de la carte des lanes.")
        return 1
    fautifs = fichiers_hors_lane(numero, _fichiers_modifies(args.base))
    if fautifs:
        print(f"Lane {numero} ({LANES[numero].nom}) : fichiers hors de la lane (AD-21) :")
        for fichier in fautifs:
            print(f"  {fichier}")
        print("Ouvrir une PR courte sur main pour ces fichiers, puis rebaser la lane.")
        return 1
    print(f"Lane {numero} ({LANES[numero].nom}) : tous les fichiers modifiés sont dans la lane.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
