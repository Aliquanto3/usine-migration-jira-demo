"""Écrit le Corpus de textes : provisoire par gabarits, ou produit par LLM (Stories 1.2, 1.9).

Le Corpus est produit une fois, puis versionné dans `donnees/corpus/textes.json` ; la
génération du Journal le relit sans aucun appel LLM. Avec un fournisseur, seul
`FournisseurLLM.generer_structure` est appelé (AD-24), sans SDK de fournisseur importé ici.

Corpus provisoire, sans appel :
`uv run python outils/generer_corpus.py --provisoire [--config ...] [--sortie ...]
[--version-corpus ...]`.

Corpus définitif par LLM (Story 1.9), d'abord estimé puis produit :
`uv run python outils/generer_corpus.py --fournisseur mistral --modele mistral-medium-latest
--estimer`, puis la même commande sans `--estimer`. La clé du fournisseur
(`MISTRAL_API_KEY` ou `ANTHROPIC_API_KEY` ; `local` : aucune, `LLAMA_API_KEY` facultative) se lit
dans l'environnement ou `.env`.

Avant tout appel, dans cet ordre : le modèle doit figurer au registre des prix ; il doit
différer du modèle de classification de `config/llm.yaml` (AD-19) ; le coût estimé majoré
(jetons d'entrée ≈ longueur du prompt / 3 + 500 pour le schéma, 2 000 jetons de sortie par
appel) ne doit pas dépasser `--plafond-eur` (2,00 € par défaut). La production fait
`(nombre de Domaines + 1) × 8 + 1` appels, soit 57 pour les 6 Domaines du Programme ; sur
`mistral:mistral-medium-latest` (offre gratuite « Experiment »), le coût réel est nul et le
coût estimé de l'ordre de 0,25 €. Le bilan affiche les jetons réels et leur coût estimé.
"""

import argparse
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml
from pydantic import ValidationError

from usine.composition import (
    BilanCorpus,
    construire_fournisseur,
    estimer_corpus,
    generer_corpus,
    generer_corpus_llm,
    verifier_modele_corpus_candidat,
)
from usine.contrats.config import ConfigProgramme
from usine.contrats.erreurs import UsineErreur
from usine.contrats.versions import version_modele
from usine.ports.fournisseur_llm import FournisseurLLM

RACINE_DEPOT = Path(__file__).resolve().parents[1]
CONFIG_PAR_DEFAUT = RACINE_DEPOT / "config" / "programme.yaml"
SORTIE_PAR_DEFAUT = RACINE_DEPOT / "donnees" / "corpus" / "textes.json"
PLAFOND_PAR_DEFAUT_EUR = Decimal("2.00")
"""Plafond du coût estimé majoré d'une production du Corpus, en euros."""


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
            "aucun fournisseur LLM : donner --fournisseur et --modele pour le Corpus par LLM,"
            " ou --provisoire pour le Corpus provisoire par gabarits"
        )
    return generer_corpus(
        None if provisoire else fournisseur,
        domaines_programme(config),
        sortie,
        version_corpus=version_corpus,
    )


def preparer(
    fournisseur: str,
    modele: str,
    *,
    racine: Path,
    config: Path = CONFIG_PAR_DEFAUT,
    plafond_eur: Decimal = PLAFOND_PAR_DEFAUT_EUR,
) -> tuple[str, int, Decimal]:
    """Contrôles sans appel ni fournisseur construit ; renvoie `fournisseur:modele`, le nombre
    d'appels et le coût estimé majoré.

    Ordre : registre des prix, garde-fou de classification (AD-19), plafond.
    """
    choisi = version_modele(fournisseur, modele)
    appels, cout = estimer_corpus(choisi, domaines_programme(config))
    verifier_modele_corpus_candidat(racine, choisi)
    if cout > plafond_eur:
        raise UsineErreur(
            f"coût estimé majoré du Corpus sur {choisi} : {cout:.4f} € pour {appels} appels,"
            f" au-delà du plafond --plafond-eur {plafond_eur} € ; aucun appel émis"
        )
    return choisi, appels, cout


def generer_par_llm(
    fournisseur: str,
    modele: str,
    *,
    racine: Path,
    config: Path = CONFIG_PAR_DEFAUT,
    sortie: Path = SORTIE_PAR_DEFAUT,
    version_corpus: str | None = None,
    plafond_eur: Decimal = PLAFOND_PAR_DEFAUT_EUR,
) -> BilanCorpus:
    """Contrôle, construit le fournisseur choisi puis écrit le Corpus ; renvoie son bilan."""
    preparer(fournisseur, modele, racine=racine, config=config, plafond_eur=plafond_eur)
    domaines = domaines_programme(config)
    construit = construire_fournisseur(racine, fournisseur=fournisseur, modele=modele)
    try:
        return generer_corpus_llm(construit, domaines, sortie, version_corpus=version_corpus)
    finally:
        fermer = getattr(construit, "fermer", None)
        if callable(fermer):
            fermer()


def _montant(texte: str) -> Decimal:
    """Montant en euros de `--plafond-eur` : décimal fini, positif ou nul."""
    try:
        valeur = Decimal(texte)
    except InvalidOperation:
        valeur = Decimal("NaN")
    if not valeur.is_finite() or valeur < 0:
        raise argparse.ArgumentTypeError(f"montant en euros invalide : {texte!r}")
    return valeur


def _analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    analyseur.add_argument("--config", type=Path, default=CONFIG_PAR_DEFAUT)
    analyseur.add_argument("--sortie", type=Path, default=SORTIE_PAR_DEFAUT)
    analyseur.add_argument(
        "--provisoire", action="store_true", help="Corpus par gabarits, sans LLM."
    )
    analyseur.add_argument(
        "--fournisseur", help="Fournisseur LLM : anthropic, mistral ou local (sans clé)."
    )
    analyseur.add_argument("--modele", help="Modèle du fournisseur, présent au registre des prix.")
    analyseur.add_argument(
        "--estimer", action="store_true", help="Affiche appels et coût estimé, sans appel."
    )
    analyseur.add_argument(
        "--plafond-eur",
        type=_montant,
        default=PLAFOND_PAR_DEFAUT_EUR,
        help="Plafond du coût estimé majoré, en euros (défaut : 2.00).",
    )
    analyseur.add_argument("--version-corpus", default=None)
    return analyseur


def main(arguments: list[str] | None = None) -> int:
    """Point d'entrée en ligne de commande ; code 1 et message sur `stderr` en cas d'erreur."""
    lus = _analyseur().parse_args(arguments)
    par_llm = lus.fournisseur is not None or lus.modele is not None
    try:
        if lus.provisoire:
            if par_llm or lus.estimer:
                raise UsineErreur("--provisoire exclut --fournisseur, --modele et --estimer")
            chemin = generer(
                None,
                provisoire=True,
                config=lus.config,
                sortie=lus.sortie,
                version_corpus=lus.version_corpus,
            )
            print(f"Corpus écrit : {chemin}")
            return 0
        if lus.fournisseur is None or lus.modele is None:
            raise UsineErreur(
                "--fournisseur et --modele vont ensemble (par exemple --fournisseur mistral"
                " --modele mistral-medium-latest) ; sinon --provisoire pour le Corpus provisoire"
                " par gabarits"
            )
        if lus.estimer:
            choisi, appels, cout = preparer(
                lus.fournisseur,
                lus.modele,
                racine=RACINE_DEPOT,
                config=lus.config,
                plafond_eur=lus.plafond_eur,
            )
            print(
                f"Estimation du Corpus sur {choisi} : {appels} appels, coût estimé majoré"
                f" {cout:.4f} € (plafond {lus.plafond_eur} €) ; aucun appel émis"
            )
            return 0
        bilan = generer_par_llm(
            lus.fournisseur,
            lus.modele,
            racine=RACINE_DEPOT,
            config=lus.config,
            sortie=lus.sortie,
            version_corpus=lus.version_corpus,
            plafond_eur=lus.plafond_eur,
        )
    except UsineErreur as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    print(f"Corpus écrit : {bilan.chemin} (modèle {bilan.modele_corpus})")
    print(
        f"Bilan : {bilan.appels} appels, {bilan.jetons_entree} jetons d'entrée,"
        f" {bilan.jetons_sortie} jetons de sortie, coût estimé réel {bilan.cout_eur:.4f} €"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
