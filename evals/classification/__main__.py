"""CLI de la suite d'évaluation de la classification des Causes racines (SM-9).

    uv run python -m evals.classification executer [--reel]
        [--source manuels|generateur|toutes] [--donnees REPERTOIRE] [--reponses RESULTAT]
        [--sortie REPERTOIRE] [--historique FICHIER]

Sans `--reel`, les réponses enregistrées sont rejouées, sans réseau ni secret : celles des
tickets manuels, et pour la source générateur les `propositions` du résultat `--reponses`.
Source par défaut : `toutes` avec `--reel` ou `--reponses`, sinon `manuels`. Le mode réel
ajoute une ligne à l'historique.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from evals.classification.suite import (
    CHEMIN_HISTORIQUE,
    REPERTOIRE_RESULTATS,
    ajouter_historique,
    ecrire_resultat,
    executer_suite,
    lire_reponses,
)
from evals.classification.tickets import (
    CHEMIN_CORPUS,
    CHEMIN_TICKETS_MANUELS,
    charger_source_generateur,
    charger_tickets_manuels,
)
from usine.contrats.erreurs import UsineErreur
from usine.contrats.passage import REPERTOIRE_DONNEES

RACINE = Path(__file__).resolve().parents[2]


def _analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(
        prog="python -m evals.classification",
        description="Suite d'évaluation de la classification des Causes racines (SM-9).",
    )
    commandes = analyseur.add_subparsers(dest="commande", required=True)
    executer = commandes.add_parser("executer", help="classe les sources et publie les F1")
    executer.add_argument(
        "--reel",
        action="store_true",
        help="appelle le vrai fournisseur (config/llm.yaml, clé, USINE_CLE_PSEUDO ; coût)",
    )
    executer.add_argument(
        "--source",
        choices=("manuels", "generateur", "toutes"),
        default=None,
        help="source évaluée (défaut : toutes avec --reel ou --reponses, sinon manuels)",
    )
    executer.add_argument(
        "--donnees",
        type=Path,
        default=None,
        help="répertoire du Journal et de la vérité terrain (défaut : donnees/ de la racine)",
    )
    executer.add_argument(
        "--reponses", type=Path, default=None, help="résultat antérieur rejoué (générateur)"
    )
    executer.add_argument(
        "--tickets", type=Path, default=CHEMIN_TICKETS_MANUELS, help="tickets manuels"
    )
    executer.add_argument(
        "--sortie", type=Path, default=REPERTOIRE_RESULTATS, help="répertoire des résultats"
    )
    executer.add_argument(
        "--historique",
        type=Path,
        default=CHEMIN_HISTORIQUE,
        help="historique JSON Lines (mode réel)",
    )
    executer.add_argument("--racine", type=Path, default=RACINE, help="racine du dépôt")
    return analyseur


def _format(valeur: float | None) -> str:
    return "—" if valeur is None else f"{valeur:.3f}"


def main(arguments: Sequence[str] | None = None) -> int:
    """Point d'entrée ; renvoie le code de sortie (1 sur `UsineErreur`)."""
    options = _analyseur().parse_args(arguments)
    source = options.source or (
        "toutes" if options.reel or options.reponses is not None else "manuels"
    )
    try:
        manuels = (
            charger_tickets_manuels(options.tickets) if source in ("manuels", "toutes") else None
        )
        generateur = None
        reponses = None
        if source in ("generateur", "toutes"):
            donnees = options.donnees or options.racine / REPERTOIRE_DONNEES
            generateur = charger_source_generateur(donnees, options.racine / CHEMIN_CORPUS)
            if options.reponses is not None:
                reponses = lire_reponses(options.reponses)
        resultat = executer_suite(
            options.racine,
            manuels=manuels,
            generateur=generateur,
            reponses=None if options.reel else reponses,
            reel=options.reel,
        )
        chemin = ecrire_resultat(resultat, options.sortie)
        lignes = [f"Résultat écrit : {chemin}"]
        for nom, bloc in resultat["sources"].items():
            lignes.append(
                f"{nom} : F1 macro {_format(bloc['f1_macro'])}, exactitude"
                f" {bloc['exactitude']:.1%} ({bloc['corrects']}/{bloc['nombre']}),"
                f" {len(bloc['non_classes'])} non classée(s)"
            )
        sm9 = resultat["sm9_atteint"]
        lignes.append(
            f"version_prompt {resultat['version_prompt']}, version_modele"
            f" {resultat['version_modele']} ; SM-9 atteint :"
            f" {'—' if sm9 is None else 'oui' if sm9 else 'non'}"
        )
        if options.reel:
            ajouter_historique(resultat, chemin, options.historique)
            lignes.append(f"Historique complété : {options.historique}")
        print("\n".join(lignes))
    except UsineErreur as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
