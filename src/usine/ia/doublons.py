"""Tâche `doublons` : paires d'Anomalies ouvertes probablement en doublon, avec un score (FR-36).

Bonus (Story 6.11). Sélection déterministe des paires candidates (même Entité, recouvrement
lexical du titre et de la description), puis un appel par paire à la passerelle (ordre AD-12) :
le LLM donne un score et une justification, jamais un calcul. Le contrôle déterministe retire
de la justification toute phrase citant une autre clé que celles de la paire. Seules les paires
au score d'au moins `SEUIL_PUBLICATION` sont publiées, triées par score décroissant.

Les paires ne sont qu'à revoir par le Pilote : aucune fusion, aucune écriture dans Jira (ce
module ne reçoit ni port d'écriture ni client Jira). Plafond de coût du Passage atteint : la
détection s'arrête avec les paires déjà évaluées. Un échec isolé du fournisseur laisse la
paire sans score ; `MAX_ECHECS_CONSECUTIFS` échecs d'affilée font échouer la tâche.
"""

import logging
import re
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from importlib import resources
from itertools import combinations
from typing import Any

import polars as pl

from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import (
    ParametresAppel,
    ReponseDoublon,
    SortieDoublon,
    StatutControle,
    Tache,
)
from usine.contrats.tickets import STATUTS_FERMES, rang_cle
from usine.contrats.trace import EntreeTrace
from usine.contrats.versions import version_prompt
from usine.ia.classification import anomalies, rendre_prompt
from usine.ia.controles import decouper_phrases, retirer_citations_hors
from usine.ia.passerelle import ContexteAppel, Controle, Passerelle, PlafondCoutAtteint

SEUIL_CANDIDAT = 0.25
"""Recouvrement lexical (Jaccard) minimal pour qu'une paire soit soumise au LLM."""

SEUIL_PUBLICATION = 0.5
"""Score minimal d'une paire publiée."""

MAX_PAIRES = 50
"""Paires soumises au LLM par Passage, les plus proches d'abord (bornes de coût)."""

MAX_ECHECS_CONSECUTIFS = 3
"""Échecs du fournisseur d'affilée au-delà desquels la détection échoue."""

MAX_JETONS_SORTIE = 256
"""Plafond de jetons de sortie d'une paire."""

DELIMITEUR = "```"
"""Délimiteur du bloc de données ; neutralisé dans les textes des tickets."""

journal = logging.getLogger(__name__)

_MOT = re.compile(r"\w{3,}")

_Paire = tuple[float, dict[str, Any], dict[str, Any]]


def lire_prompt() -> bytes:
    """Octets de `ia/prompts/doublons.md` (source de `version_prompt`)."""
    return (resources.files("usine.ia") / "prompts" / "doublons.md").read_bytes()


@dataclass(frozen=True)
class ContexteDoublons:
    """Contexte du Passage commun aux appels de la détection."""

    passage_id: str
    version_donnees: str
    version_grille: str
    """Tracée seulement (AD-16) : la Grille n'entre ni dans le prompt ni dans le cache."""
    gabarit: bytes
    """Octets du gabarit envoyé (source de `version_prompt`)."""

    @property
    def version_prompt(self) -> str:
        """`version_prompt` du gabarit envoyé."""
        return version_prompt(self.gabarit)


def cles_ouvertes(etats: pl.DataFrame) -> frozenset[str]:
    """Clés des Anomalies ouvertes d'une table `SCHEMA_TICKET_ETAT` (statut non fermé)."""
    fermes = [statut.value for statut in STATUTS_FERMES]
    ouvertes = etats.filter(
        (pl.col("type_ticket").cast(pl.Utf8) == "anomalie")
        & ~pl.col("statut").cast(pl.Utf8).is_in(fermes)
    )
    return frozenset(ouvertes["cle_ticket"].to_list())


def _mots(ligne: dict[str, Any]) -> frozenset[str]:
    texte = f"{ligne['titre'] or ''} {ligne['description'] or ''}".lower()
    return frozenset(_MOT.findall(texte))


def paires_candidates(textes: pl.DataFrame, ouvertes: Collection[str]) -> list[_Paire]:
    """Paires d'Anomalies ouvertes d'une même Entité au recouvrement lexical suffisant.

    Triées par recouvrement décroissant puis par clés, bornées à `MAX_PAIRES`. Chaque paire est
    `(recouvrement, ligne_a, ligne_b)` avec `cle_a` avant `cle_b` dans l'ordre des clés.
    """
    lignes = [ligne for ligne in anomalies(textes) if ligne["cle_ticket"] in ouvertes]
    mots = {ligne["cle_ticket"]: _mots(ligne) for ligne in lignes}
    candidates: list[_Paire] = []
    for a, b in combinations(lignes, 2):
        if a["entite"] != b["entite"]:
            continue
        union = mots[a["cle_ticket"]] | mots[b["cle_ticket"]]
        if not union:
            continue
        recouvrement = len(mots[a["cle_ticket"]] & mots[b["cle_ticket"]]) / len(union)
        if recouvrement >= SEUIL_CANDIDAT:
            candidates.append((recouvrement, a, b))
    candidates.sort(
        key=lambda c: (-c[0], rang_cle(c[1]["cle_ticket"]), rang_cle(c[2]["cle_ticket"]))
    )
    return candidates[:MAX_PAIRES]


def _donnee(texte: str) -> str:
    return texte.replace(DELIMITEUR, "'''")


def _ticket(ligne: dict[str, Any]) -> str:
    return (
        f"{ligne['cle_ticket']} : {_donnee(ligne['titre'] or '(sans titre)')}\n"
        f"{_donnee(ligne['description'] or '(sans description)')}"
    )


@dataclass(frozen=True)
class _Controleur:
    """Contrôle d'une `ReponseDoublon` : justification sans clé étrangère à la paire."""

    cle_a: str
    cle_b: str

    def __call__(self, reponse: ReponseDoublon) -> Controle[SortieDoublon]:
        justification = retirer_citations_hors(reponse.justification, (self.cle_a, self.cle_b))
        retirees = len(decouper_phrases(reponse.justification)) - len(
            decouper_phrases(justification)
        )
        if retirees:
            statut = StatutControle.corrige
        else:
            statut = StatutControle.conforme
            justification = reponse.justification
        sortie = SortieDoublon(
            cle_a=self.cle_a,
            cle_b=self.cle_b,
            score=reponse.score,
            justification=justification,
            statut_controle=statut,
        )
        return Controle(sortie, statut, retirees)


def detecter(
    passerelle: Passerelle,
    textes: pl.DataFrame,
    ouvertes: Collection[str],
    date_arrete: date,
    contexte: ContexteDoublons,
    plafond_eur: Decimal | None = None,
) -> tuple[tuple[SortieDoublon, ...], tuple[EntreeTrace, ...]]:
    """Paires d'Anomalies ouvertes probablement en doublon, avec score, et trace de chaque appel.

    Lecture seule : aucune fusion, aucune écriture dans Jira. Une paire refusée par le plafond
    de coût arrête la détection (les paires restantes sont absentes) ; un échec isolé du
    fournisseur laisse la paire sans score (consigné au journal).
    """
    sorties: list[SortieDoublon] = []
    traces: list[EntreeTrace] = []
    consecutifs = 0
    parametres = ParametresAppel(tache=Tache.doublons, max_jetons_sortie=MAX_JETONS_SORTIE)
    gabarit = contexte.gabarit.decode("utf-8")
    for _, a, b in paires_candidates(textes, ouvertes):
        cle_a, cle_b = a["cle_ticket"], b["cle_ticket"]
        prompt = rendre_prompt(
            gabarit,
            {"cle_a": cle_a, "cle_b": cle_b, "paire": f"{_ticket(a)}\n\n{_ticket(b)}"},
        )
        appel = ContexteAppel(
            passage_id=contexte.passage_id,
            date_arrete=date_arrete,
            cible=f"{cle_a}+{cle_b}",
            version_prompt=contexte.version_prompt,
            version_grille=contexte.version_grille,
            version_donnees=contexte.version_donnees,
            entite=a["entite"],
        )
        try:
            resultat = passerelle.executer_structure(
                prompt,
                ReponseDoublon,
                parametres,
                appel,
                _Controleur(cle_a, cle_b),
                plafond_eur=plafond_eur,
            )
        except PlafondCoutAtteint:
            journal.warning("détection de doublons arrêtée à %s+%s : plafond de coût", cle_a, cle_b)
            break
        except UsineErreur as exc:
            traces.extend(passerelle.vider_traces_echec(Tache.doublons))
            consecutifs += 1
            if consecutifs >= MAX_ECHECS_CONSECUTIFS:
                raise UsineErreur(
                    f"doublons : {consecutifs} échecs consécutifs du fournisseur LLM"
                    f" (dernier sur {cle_a}+{cle_b} : {exc})"
                ) from exc
            journal.warning("paire %s+%s en échec, sans score : %s", cle_a, cle_b, exc)
            continue
        consecutifs = 0
        traces.append(resultat.trace)
        if resultat.sortie.score >= SEUIL_PUBLICATION:
            sorties.append(resultat.sortie)
    sorties.sort(key=lambda s: (-s.score, rang_cle(s.cle_a), rang_cle(s.cle_b)))
    return tuple(sorties), tuple(traces)
