"""Écrit le Corpus de textes : provisoire par gabarits, ou produit par LLM (Story 1.2).

Le Corpus est produit une fois, puis versionné dans `donnees/corpus/textes.json` ; la
génération du Journal le relit sans aucun appel LLM. Avec un fournisseur, seul
`FournisseurLLM.generer_structure` est appelé (AD-24), sans SDK de fournisseur importé ici.
Les adaptateurs LLM réels arrivent à la Story 6.1 : d'ici là, la ligne de commande n'écrit que
le Corpus provisoire.

Usage : `uv run python outils/generer_corpus.py --provisoire [--config ...] [--sortie ...]
[--version-corpus ...]`.
"""

import argparse
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from usine.composition import generer_corpus
from usine.contrats.config import ConfigProgramme
from usine.contrats.erreurs import UsineErreur
from usine.ports.fournisseur_llm import FournisseurLLM

RACINE_DEPOT = Path(__file__).resolve().parents[1]
CONFIG_PAR_DEFAUT = RACINE_DEPOT / "config" / "programme.yaml"
SORTIE_PAR_DEFAUT = RACINE_DEPOT / "donnees" / "corpus" / "textes.json"


def domaines_programme(config: Path) -> tuple[str, ...]:
    """Domaines de la configuration du Programme ; une erreur nomme le fichier."""
    try:
        donnees = yaml.safe_load(config.read_text(encoding="utf-8"))
        return ConfigProgramme.model_validate(donnees).domaines
    except (OSError, UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise UsineErreur(f"{config} : configuration du Programme illisible ({exc})") from exc


def generer(
    fournisseur: FournisseurLLM | None,
    *,
    provisoire: bool = False,
    config: Path = CONFIG_PAR_DEFAUT,
    sortie: Path = SORTIE_PAR_DEFAUT,
    version_corpus: str | None = None,
) -> Path:
    """Écrit le Corpus des Domaines de `config` à `sortie` et renvoie ce chemin.

    `provisoire` : Corpus par gabarits, sans appel. Sinon `fournisseur` est obligatoire.
    """
    if not provisoire and fournisseur is None:
        raise UsineErreur(
            "aucun fournisseur LLM : les adaptateurs LLM réels arrivent à la Story 6.1 ;"
            " utiliser --provisoire pour écrire le Corpus provisoire par gabarits"
        )
    return generer_corpus(
        None if provisoire else fournisseur,
        domaines_programme(config),
        sortie,
        version_corpus=version_corpus,
    )


def main(arguments: list[str] | None = None) -> int:
    """Point d'entrée en ligne de commande ; code 1 et message sur `stderr` en cas d'erreur."""
    analyseur = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    analyseur.add_argument("--config", type=Path, default=CONFIG_PAR_DEFAUT)
    analyseur.add_argument("--sortie", type=Path, default=SORTIE_PAR_DEFAUT)
    analyseur.add_argument(
        "--provisoire", action="store_true", help="Corpus par gabarits, sans LLM."
    )
    analyseur.add_argument("--version-corpus", default=None)
    lus = analyseur.parse_args(arguments)
    try:
        chemin = generer(
            None,
            provisoire=lus.provisoire,
            config=lus.config,
            sortie=lus.sortie,
            version_corpus=lus.version_corpus,
        )
    except UsineErreur as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    print(f"Corpus écrit : {chemin}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
