"""Préchauffage du cache de classification (Story 6.10) : « cache de classification initialisé ».

La première classification du stock (environ 3 100 Anomalies, un appel chacune, débit de
50 requêtes par minute) dure plus d'une heure : elle se fait hors Passage, par tranches
bornées dans le temps et relançables, avant le Passage Palier 2 mesuré. Chaque tranche
reprend où la précédente s'est arrêtée (les Anomalies déjà classées sont servies par le
cache, sans appel). Exige `palier: 2` dans `config/chaine.yaml` de la racine.

Usage : `uv run python outils/prechauffer_cache.py --date-arrete AAAA-MM-JJ
[--duree-max 540] [--racine .]`. Code de sortie : 0 stock couvert, 3 stock restant
(relancer), 2 erreur.
"""

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from usine.composition import prechauffer_classification
from usine.contrats.erreurs import UsineErreur


def _analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(
        prog="prechauffer_cache", description="Préchauffage du cache de classification."
    )
    analyseur.add_argument("--date-arrete", type=date.fromisoformat, required=True)
    analyseur.add_argument("--duree-max", type=float, default=540.0, help="secondes")
    analyseur.add_argument("--racine", type=Path, default=Path("."))
    return analyseur


def main(arguments: Sequence[str] | None = None) -> int:
    """Point d'entrée ; code de sortie 0, 2 ou 3."""
    args = _analyseur().parse_args(arguments)
    try:
        bilan = prechauffer_classification(args.racine, args.date_arrete, args.duree_max)
    except UsineErreur as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2
    print(
        f"Classées : {bilan.classees}/{bilan.anomalies} Anomalies ; {bilan.appels} appels frais,"
        f" coût estimé {bilan.cout_eur:.4f} €"
    )
    return 0 if bilan.classees >= bilan.anomalies else 3


if __name__ == "__main__":
    sys.exit(main())
