"""CLI de la suite d'évaluation de l'Explication sourcée (SM-3).

    uv run python -m evals.explication executer [--reel] [--sortie REPERTOIRE]
    uv run python -m evals.explication noter evals/explication/resultats/<horodatage>.json

Sans `--reel`, les réponses enregistrées des cas sont rejouées, sans réseau ni secret.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from evals.explication.cas import REPERTOIRE_CAS, charger_cas
from evals.explication.suite import (
    CHEMIN_HISTORIQUE,
    REPERTOIRE_RESULTATS,
    ecrire_resultat,
    executer_suite,
    noter,
)
from usine.contrats.erreurs import UsineErreur


def _analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(
        prog="python -m evals.explication",
        description="Suite d'évaluation de l'Explication sourcée (SM-3).",
    )
    commandes = analyseur.add_subparsers(dest="commande", required=True)
    executer = commandes.add_parser("executer", help="exécute les 10 cas et publie le taux")
    executer.add_argument(
        "--reel",
        action="store_true",
        help="appelle le vrai fournisseur (config/llm.yaml, clé, USINE_CLE_PSEUDO ; coût)",
    )
    executer.add_argument("--cas", type=Path, default=REPERTOIRE_CAS, help="répertoire des cas")
    executer.add_argument(
        "--sortie", type=Path, default=REPERTOIRE_RESULTATS, help="répertoire des résultats"
    )
    executer.add_argument(
        "--racine",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="racine du dépôt (mode réel)",
    )
    noter_ = commandes.add_parser("noter", help="enregistre la moyenne humaine d'un résultat")
    noter_.add_argument("resultat", type=Path, help="fichier de résultat noté")
    noter_.add_argument(
        "--historique", type=Path, default=CHEMIN_HISTORIQUE, help="historique JSON Lines"
    )
    return analyseur


def main(arguments: Sequence[str] | None = None) -> int:
    """Point d'entrée ; renvoie le code de sortie (1 sur `UsineErreur`)."""
    options = _analyseur().parse_args(arguments)
    try:
        if options.commande == "executer":
            resultat = executer_suite(charger_cas(options.cas), options.racine, reel=options.reel)
            chemin = ecrire_resultat(resultat, options.sortie)
            print(
                f"Résultat écrit : {chemin}\n"
                f"Taux de Citations valides : {resultat['taux_citations_valides']:.1%}"
                f" ({resultat['phrases_valides']}/{resultat['phrases_total']} phrases),"
                f" {resultat['phrases_retirees_passerelle']} phrase(s) retirée(s) par la"
                f" passerelle\nversion_prompt {resultat['version_prompt']},"
                f" version_modele {resultat['version_modele']}"
            )
        else:
            entree = noter(options.resultat, options.historique)
            print(
                f"Historique complété : {options.historique}\n"
                f"Moyenne humaine {entree['moyenne_humaine']:.2f}/5, taux de Citations valides"
                f" {entree['taux_citations_valides']:.1%} ; SM-3 atteint :"
                f" {'oui' if entree['sm3_atteint'] else 'non'}"
            )
    except UsineErreur as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
