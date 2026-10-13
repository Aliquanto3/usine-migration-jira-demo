"""CLI de la suite d'évaluation de l'Agent (SM-4, FR-42).

    uv run python -m evals.agent executer [--reel] [--sortie REPERTOIRE]

Sans `--reel`, le tour enregistré de chaque question est rejoué, sans réseau ni secret.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from evals.agent.questions import CHEMIN_QUESTIONS, charger_questions
from evals.agent.suite import (
    CHEMIN_HISTORIQUE,
    REPERTOIRE_RESULTATS,
    ajouter_historique,
    executer_suite,
)
from evals.explication.suite import ecrire_resultat
from usine.contrats.erreurs import UsineErreur


def _analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(
        prog="python -m evals.agent",
        description="Suite d'évaluation de l'Agent (SM-4).",
    )
    commandes = analyseur.add_subparsers(dest="commande", required=True)
    executer = commandes.add_parser("executer", help="pose les 15 questions et publie le score")
    executer.add_argument(
        "--reel",
        action="store_true",
        help="appelle le vrai fournisseur (config/llm.yaml, clé, USINE_CLE_PSEUDO ; coût)",
    )
    executer.add_argument(
        "--questions", type=Path, default=CHEMIN_QUESTIONS, help="fichier des questions"
    )
    executer.add_argument(
        "--racine",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="racine du dépôt (configuration en mode réel, traces sous sorties/agent/)",
    )
    executer.add_argument(
        "--passage", type=Path, default=None, help="Passage interrogé (défaut : demo/repli/passage)"
    )
    executer.add_argument(
        "--sortie", type=Path, default=REPERTOIRE_RESULTATS, help="répertoire des résultats"
    )
    executer.add_argument(
        "--historique", type=Path, default=CHEMIN_HISTORIQUE, help="historique JSON Lines"
    )
    return analyseur


def main(arguments: Sequence[str] | None = None) -> int:
    """Point d'entrée ; renvoie le code de sortie (1 sur `UsineErreur`)."""
    options = _analyseur().parse_args(arguments)
    try:
        resultat = executer_suite(
            charger_questions(options.questions),
            options.racine,
            options.passage,
            reel=options.reel,
        )
        chemin = ecrire_resultat(resultat, options.sortie)
        ajouter_historique(resultat, chemin, options.historique)
    except UsineErreur as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    print(
        f"Résultat écrit : {chemin}\n"
        f"Score : {resultat['score']}/{resultat['nombre_questions']}\n"
        f"Chiffres inventés : {resultat['chiffres_inventes']},"
        f" tickets inventés : {resultat['tickets_inventes']}\n"
        f"Refus sur les {resultat['nombre_repondables']} questions répondables :"
        f" {resultat['refus_repondables']}\n"
        f"SM-4 atteint : {'oui' if resultat['sm4_atteint'] else 'non'}"
        f" (score d'au moins 13, aucun chiffre inventé, au plus 1 refus)\n"
        f"version_prompt {resultat['version_prompt']}, version_modele"
        f" {resultat['version_modele']}, coût estimé {resultat['cout_estime_eur']} €"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
