"""Tâche `doublons` : paires d'Anomalies ouvertes probablement en doublon (FR-36, bonus).

Tâche locale : aucun appel au fournisseur LLM, donc ni passerelle, ni cache, ni coût. Les
titres et descriptions des Anomalies ouvertes sont pseudonymisés (aperçu, sans écrire la table
de correspondance), ramenés à des jetons sans casse ni accents, puis comparés deux à deux par
l'indice de Jaccard des ensembles de jetons. Les paires au score d'au moins `seuil` sont
rendues par score décroissant, plafonnées à `limite`.

Le résultat n'est qu'une liste de suggestions à revoir par le Pilote : aucune fusion, aucune
écriture dans Jira, aucune fermeture de ticket.
"""

import re
import unicodedata
from collections.abc import Callable, Collection
from datetime import date
from itertools import combinations

import polars as pl

from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import PaireDoublon, SortieDoublons, StatutControle
from usine.contrats.tickets import TypeTicket, rang_cle

SEUIL_DEFAUT = 0.6
"""Score minimal d'une paire rendue."""

LIMITE_DEFAUT = 50
"""Nombre maximal de paires rendues."""

LONGUEUR_MIN_JETON = 3
"""Les mots plus courts (articles, prépositions) ne comptent pas dans la similarité."""

_MOT = re.compile(r"[a-z0-9_]+")


def _jetons(texte: str) -> frozenset[str]:
    sans_accents = unicodedata.normalize("NFKD", texte.lower()).encode("ascii", "ignore")
    return frozenset(
        m for m in _MOT.findall(sans_accents.decode("ascii")) if len(m) >= LONGUEUR_MIN_JETON
    )


def score_similarite(a: frozenset[str], b: frozenset[str]) -> float:
    """Indice de Jaccard de deux ensembles de jetons ; 0 si l'un des deux est vide."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def detecter_doublons(
    textes: pl.DataFrame,
    ouvertes: Collection[str],
    date_arrete: date,
    pseudonymiser: Callable[[str], str],
    *,
    seuil: float = SEUIL_DEFAUT,
    limite: int = LIMITE_DEFAUT,
) -> SortieDoublons:
    """Paires d'Anomalies ouvertes de `textes` dont la similarité atteint `seuil`.

    `ouvertes` : clés des Anomalies ouvertes à la Date d'arrêté ; les autres tickets de
    `textes` sont ignorés. `pseudonymiser` s'applique à chaque texte avant toute comparaison.
    Tri : score décroissant, puis rang des clés ; `limite` borne le nombre de paires.
    """
    if not 0 <= seuil <= 1:
        raise UsineErreur(f"seuil de doublons hors de [0, 1] : {seuil}")
    if limite <= 0:
        raise UsineErreur(f"limite de doublons non positive : {limite}")
    lignes = textes.filter(
        (pl.col("type_ticket") == TypeTicket.anomalie.value)
        & pl.col("cle_ticket").is_in(list(ouvertes))
    )
    jetons = {
        ligne["cle_ticket"]: _jetons(
            pseudonymiser(f"{ligne['titre'] or ''}\n{ligne['description'] or ''}")
        )
        for ligne in lignes.iter_rows(named=True)
    }
    cles = sorted(jetons, key=rang_cle)
    paires = [
        PaireDoublon(cle_a=a, cle_b=b, score=round(score, 4))
        for a, b in combinations(cles, 2)
        if (score := score_similarite(jetons[a], jetons[b])) >= seuil and score > 0
    ]
    paires.sort(key=lambda p: -p.score)
    return SortieDoublons(
        date_arrete=date_arrete,
        seuil=seuil,
        paires=tuple(paires[:limite]),
        statut_controle=StatutControle.conforme,
    )
