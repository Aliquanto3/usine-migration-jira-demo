"""Balayage SM-7 : aucun identifiant fictif injecté ne part vers le fournisseur LLM.

Cherche chaque identifiant de `identifiants_injectes.json` (écrit par `usine donnees generer`
à côté du Journal), tel quel et sans ses espaces (IBAN), dans :

- les traces LLM d'un Passage (`trace/llm.jsonl` : entrées pseudonymisées, donc les requêtes
  émises vers le fournisseur, et sorties avant ré-identification) ;
- le cache LLM (`donnees/cache_llm.sqlite` : réponses brutes du fournisseur), s'il est donné.

Le Rapport lui-même n'est pas balayé : la ré-identification locale y remet légitimement les
valeurs. Le balayage compte aussi les jetons de Pseudonymisation trouvés, preuve que des
identifiants ont bien été remplacés.

Usage : `uv run python outils/balayer_sm7.py --passage <répertoire du Passage>
--identifiants <identifiants_injectes.json> [--cache <cache_llm.sqlite>]`.
Code de sortie : 0 aucun identifiant trouvé, 1 fuite, 2 usage ou fichier illisible.
"""

import argparse
import json
import re
import sqlite3
import sys
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from usine.contrats.llm import CANDIDAT_JETON

CHEMIN_TRACES_LLM = Path("trace") / "llm.jsonl"
"""Traces LLM d'un Passage, relatives à son répertoire."""


class FichierIllisible(Exception):
    """Fichier d'entrée absent ou mal formé."""


@dataclass(frozen=True)
class Fuite:
    """Identifiant injecté retrouvé dans une source balayée."""

    source: str
    type: str
    valeur: str


@dataclass(frozen=True)
class Bilan:
    """Résultat du balayage."""

    textes: int
    identifiants: int
    jetons: int
    fuites: tuple[Fuite, ...]


def charger_identifiants(chemin: Path) -> list[tuple[str, str]]:
    """Paires `(type, valeur)` de `identifiants_injectes.json`."""
    try:
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
        paires = [(str(i["type"]), str(i["valeur"])) for i in donnees]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, KeyError) as exc:
        raise FichierIllisible(f"{chemin} : liste d'identifiants illisible ({exc})") from None
    if not paires:
        raise FichierIllisible(f"{chemin} : aucun identifiant injecté")
    return paires


def variantes(valeur: str) -> set[str]:
    """La valeur et, si elle en a, la même sans espaces (IBAN recopié d'un bloc)."""
    return {valeur, valeur.replace(" ", "")} - {""}


def textes_traces(passage: Path) -> Iterator[tuple[str, str]]:
    """`(source, texte)` de chaque ligne des traces LLM du Passage."""
    chemin = passage / CHEMIN_TRACES_LLM
    try:
        lignes = chemin.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise FichierIllisible(f"{chemin} : traces LLM illisibles ({exc})") from None
    for numero, ligne in enumerate(lignes, start=1):
        if ligne.strip():
            yield f"{chemin}:{numero}", ligne


def textes_cache(chemin: Path) -> Iterator[tuple[str, str]]:
    """`(source, texte)` de chaque réponse du cache LLM SQLite, ouvert en lecture seule."""
    if not chemin.is_file():
        raise FichierIllisible(f"{chemin} : cache LLM absent")
    try:
        with sqlite3.connect(f"{chemin.resolve().as_uri()}?mode=ro", uri=True) as connexion:
            lignes = connexion.execute("SELECT cle, brut FROM cache_llm").fetchall()
    except sqlite3.Error as exc:
        raise FichierIllisible(f"{chemin} : cache LLM illisible ({exc})") from None
    for cle, brut in lignes:
        yield f"{chemin}#{cle}", str(brut)


def balayer(textes: Iterable[tuple[str, str]], identifiants: Sequence[tuple[str, str]]) -> Bilan:
    """Cherche chaque variante de chaque identifiant dans chaque texte."""
    par_variante = {v: (type_, valeur) for type_, valeur in identifiants for v in variantes(valeur)}
    # Une seule expression, variantes les plus longues d'abord ; `lookahead` pour les
    # chevauchements (une variante contenue dans une autre est aussi signalée).
    motif = re.compile(
        "(?=(" + "|".join(re.escape(v) for v in sorted(par_variante, key=len, reverse=True)) + "))"
    )
    fuites: list[Fuite] = []
    nb_textes = jetons = 0
    for source, texte in textes:
        nb_textes += 1
        jetons += len(CANDIDAT_JETON.findall(texte))
        for trouve in motif.finditer(texte):
            fuites.append(Fuite(source, *par_variante[trouve.group(1)]))
    return Bilan(nb_textes, len(identifiants), jetons, tuple(dict.fromkeys(fuites)))


def _analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(
        prog="balayer_sm7", description="Balayage SM-7 des traces et du cache LLM."
    )
    analyseur.add_argument("--passage", type=Path, required=True)
    analyseur.add_argument("--identifiants", type=Path, required=True)
    analyseur.add_argument("--cache", type=Path)
    return analyseur


def main(arguments: Sequence[str] | None = None) -> int:
    """Point d'entrée ; code de sortie 0, 1 ou 2."""
    args = _analyseur().parse_args(arguments)
    try:
        identifiants = charger_identifiants(args.identifiants)
        textes = list(textes_traces(args.passage))
        if args.cache is not None:
            textes += textes_cache(args.cache)
    except FichierIllisible as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2
    bilan = balayer(textes, identifiants)
    print(
        f"SM-7 : {bilan.textes} textes balayés, {bilan.identifiants} identifiants injectés,"
        f" {bilan.jetons} jetons de Pseudonymisation, {len(bilan.fuites)} fuite(s)"
    )
    for fuite in bilan.fuites:
        print(f"  FUITE {fuite.type} dans {fuite.source}")
    return 1 if bilan.fuites else 0


if __name__ == "__main__":
    sys.exit(main())
