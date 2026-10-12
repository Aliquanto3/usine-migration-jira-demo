"""Lecture du dump MongoDB du Public Jira Dataset et écriture des `SerieStock` (FR-51).

Hors CI (AD-20) : exige un `mongod` local où le dump a été restauré (voir `README.md`).

    uv run python -m evaluation.zenodo.chargement --uri mongodb://127.0.0.1:27017 \\
        --base JiraReposAnon --collection Apache --sortie series.parquet
"""

import argparse
import sys
from collections.abc import Iterator, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from evaluation.zenodo.conversion import PRIORITES_MAXIMALES, convertir_en_series
from usine.contrats.erreurs import UsineErreur

PROJECTION = {
    "_id": 1,
    "key": 1,
    "fields.project": 1,
    "fields.priority": 1,
    "fields.created": 1,
    "fields.resolutiondate": 1,
    "fields.status": 1,
    "changelog.histories": 1,
}
"""Champs lus : ce qu'il faut à la conversion, et `_id` pour nommer un ticket sans clé."""


def lire_tickets(
    client: MongoClient[dict[str, Any]], base: str, collection: str
) -> Iterator[dict[str, Any]]:
    """Tickets de `base.collection`, réduits à `PROJECTION` (la conversion ignore leur ordre)."""
    yield from client[base][collection].find({}, PROJECTION)


def main(arguments: Sequence[str] | None = None) -> int:
    """Convertit une collection du dump en `SerieStock` Parquet ; code de sortie."""
    parseur = argparse.ArgumentParser(prog="python -m evaluation.zenodo.chargement")
    parseur.add_argument("--uri", default="mongodb://127.0.0.1:27017")
    parseur.add_argument("--base", required=True, help="base du dump (ex. JiraReposAnon)")
    parseur.add_argument("--collection", required=True, help="dépôt Jira (ex. Apache)")
    parseur.add_argument("--sortie", required=True, type=Path, help="fichier Parquet produit")
    parseur.add_argument("--depot", help="préfixe des séries (défaut : la collection)")
    parseur.add_argument("--fin", type=date.fromisoformat, help="dernier Jour ouvré AAAA-MM-JJ")
    parseur.add_argument(
        "--priorite",
        action="append",
        help=f"priorité maximale, répétable (défaut : {', '.join(sorted(PRIORITES_MAXIMALES))})",
    )
    options = parseur.parse_args(arguments)
    client: MongoClient[dict[str, Any]] = MongoClient(options.uri, tz_aware=True)
    try:
        series = convertir_en_series(
            lire_tickets(client, options.base, options.collection),
            depot=options.depot or options.collection,
            priorites=frozenset(options.priorite or PRIORITES_MAXIMALES),
            fin=options.fin,
        )
    except (UsineErreur, PyMongoError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    finally:
        client.close()
    if series.is_empty():
        print(
            f"Erreur : aucune série produite pour {options.base}.{options.collection} ;"
            " vérifier --collection, --priorite et --fin.",
            file=sys.stderr,
        )
        return 1
    options.sortie.parent.mkdir(parents=True, exist_ok=True)
    series.write_parquet(options.sortie)
    nb_series = series.get_column("serie").n_unique()
    print(f"{nb_series} série(s), {series.height} ligne(s) écrites dans {options.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
