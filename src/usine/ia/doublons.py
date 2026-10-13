"""Tâche `doublons` : paires d'Anomalies ouvertes probablement en doublon (FR-36, AD-2, AD-12).

Pour chaque Entité, un préfiltre déterministe retient les paires d'Anomalies ouvertes dont les
textes se ressemblent (similarité de Jaccard des mots, au moins `SEUIL_SIMILARITE`, au plus
`MAX_PAIRES_PAR_ENTITE` paires). Un seul appel par Entité, par la passerelle (ordre AD-12),
demande au fournisseur de scorer ces candidates ; le prompt `prompts/doublons.md` les reçoit
entre délimiteurs (données, pas instructions). Le contrôle déterministe écarte toute paire
absente des candidates, en double ou au score hors de 0 à 1 (`corrige`) ; seules les paires au
score d'au moins `SEUIL_SCORE` sont publiées. Le résultat n'est qu'une liste à revoir par le
Pilote : aucune fusion, aucune écriture dans Jira. Plafond de coût du Passage atteint : l'Entité
reste sans paire, sans faire échouer le Passage.
"""

import logging
import math
import re
from collections import defaultdict
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from importlib import resources
from typing import Any

import polars as pl

from usine.contrats.llm import (
    PaireDoublonBrute,
    ParametresAppel,
    ReponseDoublons,
    SortieDoublon,
    StatutControle,
    Tache,
)
from usine.contrats.tickets import TypeTicket, rang_cle
from usine.contrats.trace import EntreeTrace
from usine.ia.explication import ContexteExplication, _donnee, rendre_prompt
from usine.ia.passerelle import ContexteAppel, Controle, Passerelle, PlafondCoutAtteint

SEUIL_SIMILARITE = 0.25
"""Similarité de Jaccard minimale des mots de deux Anomalies pour former une paire candidate."""

MAX_PAIRES_PAR_ENTITE = 15
"""Paires candidates envoyées au fournisseur pour une Entité (les plus semblables d'abord)."""

SEUIL_SCORE = 0.5
"""Score minimal d'une paire publiée."""

MAX_JETONS_SORTIE = 1024
"""Plafond de jetons de sortie d'un appel de détection."""

journal = logging.getLogger(__name__)

_MOT = re.compile(r"\w{3,}")

Paire = tuple[str, str]


def lire_prompt() -> bytes:
    """Octets de `ia/prompts/doublons.md` (source de `version_prompt`)."""
    return (resources.files("usine.ia") / "prompts" / "doublons.md").read_bytes()


class ContexteDoublons(ContexteExplication):
    """Contexte du Passage commun aux détections (identifiant, données, gabarit envoyé)."""


def _mots(titre: str | None, description: str | None) -> frozenset[str]:
    return frozenset(_MOT.findall(f"{titre or ''} {description or ''}".lower()))


def _ordonnee(cle_a: str, cle_b: str) -> Paire:
    return (cle_a, cle_b) if rang_cle(cle_a) <= rang_cle(cle_b) else (cle_b, cle_a)


def paires_candidates(lignes: list[dict[str, Any]]) -> list[Paire]:
    """Paires candidates des Anomalies de `lignes` (une seule Entité), les plus semblables
    d'abord, bornées à `MAX_PAIRES_PAR_ENTITE` ; clés de chaque paire en ordre croissant."""
    mots = {ligne["cle_ticket"]: _mots(ligne["titre"], ligne["description"]) for ligne in lignes}
    cles = sorted(mots, key=rang_cle)
    candidates: list[tuple[float, Paire]] = []
    for rang, cle_a in enumerate(cles):
        for cle_b in cles[rang + 1 :]:
            union = mots[cle_a] | mots[cle_b]
            if not union:
                continue
            similarite = len(mots[cle_a] & mots[cle_b]) / len(union)
            if similarite >= SEUIL_SIMILARITE:
                candidates.append((similarite, (cle_a, cle_b)))
    candidates.sort(key=lambda c: (-c[0], rang_cle(c[1][0]), rang_cle(c[1][1])))
    return [paire for _, paire in candidates[:MAX_PAIRES_PAR_ENTITE]]


@dataclass(frozen=True)
class _Controleur:
    """Contrôle d'une `ReponseDoublons` : paires candidates, sans doublon, score de 0 à 1."""

    candidates: frozenset[Paire]

    def __call__(self, reponse: ReponseDoublons) -> Controle[ReponseDoublons]:
        retenues: dict[Paire, PaireDoublonBrute] = {}
        ecartees = 0
        for brute in reponse.paires:
            paire = _ordonnee(brute.cle_a, brute.cle_b)
            if (
                paire not in self.candidates
                or paire in retenues
                or not math.isfinite(brute.score)
                or not 0.0 <= brute.score <= 1.0
            ):
                ecartees += 1
                continue
            retenues[paire] = PaireDoublonBrute(
                cle_a=paire[0],
                cle_b=paire[1],
                score=brute.score,
                justification=brute.justification.strip(),
            )
        paires = tuple(
            sorted(
                (p for p in retenues.values() if p.score >= SEUIL_SCORE),
                key=lambda p: (-p.score, rang_cle(p.cle_a), rang_cle(p.cle_b)),
            )
        )
        statut = StatutControle.corrige if ecartees else StatutControle.conforme
        return Controle(ReponseDoublons(paires=paires), statut, ecartees)


def _bloc_paires(paires: list[Paire], lignes: dict[str, dict[str, Any]]) -> str:
    morceaux = []
    for rang, (cle_a, cle_b) in enumerate(paires, start=1):
        detail = "\n".join(
            f"{nom} = {cle} : {_donnee(lignes[cle]['titre'] or '(sans titre)')}\n"
            f"{_donnee(lignes[cle]['description'] or '(sans description)')}"
            for nom, cle in (("A", cle_a), ("B", cle_b))
        )
        morceaux.append(f"### Paire {rang} : {cle_a} / {cle_b}\n{detail}")
    return "\n\n".join(morceaux)


def detecter_doublons(
    passerelle: Passerelle,
    textes: pl.DataFrame,
    date_arrete: date,
    contexte: ContexteDoublons,
    version_grille: str,
    ouvertes: Collection[str] | None = None,
) -> tuple[tuple[SortieDoublon, ...], tuple[EntreeTrace, ...]]:
    """Paires d'Anomalies en doublon probable, par Entité, et trace de chaque appel.

    `ouvertes` : clés des Anomalies ouvertes (`None` : toutes les Anomalies de `textes`). Les
    paires sont triées par Entité, puis par score décroissant. Une Entité sans paire candidate
    ne déclenche aucun appel. Un échec du fournisseur est propagé (`UsineErreur`).
    """
    anomalies = textes.filter(pl.col("type_ticket") == TypeTicket.anomalie.value)
    par_entite: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ligne in anomalies.iter_rows(named=True):
        if ouvertes is None or ligne["cle_ticket"] in ouvertes:
            par_entite[ligne["entite"]].append(ligne)
    parametres = ParametresAppel(tache=Tache.doublons, max_jetons_sortie=MAX_JETONS_SORTIE)
    sorties: list[SortieDoublon] = []
    traces: list[EntreeTrace] = []
    for entite in sorted(par_entite):
        lignes = par_entite[entite]
        candidates = paires_candidates(lignes)
        if not candidates:
            continue
        par_cle = {ligne["cle_ticket"]: ligne for ligne in lignes}
        prompt = rendre_prompt(
            contexte.texte_gabarit,
            {"entite": entite, "paires": _bloc_paires(candidates, par_cle)},
            Tache.doublons,
        )
        appel = ContexteAppel(
            passage_id=contexte.passage_id,
            date_arrete=date_arrete,
            cible=entite,
            version_prompt=contexte.version_prompt,
            version_grille=version_grille,
            version_donnees=contexte.version_donnees,
            entite=entite,
        )
        try:
            resultat = passerelle.executer_structure(
                prompt, ReponseDoublons, parametres, appel, _Controleur(frozenset(candidates))
            )
        except PlafondCoutAtteint:
            journal.warning("doublons de %s non demandés : plafond de coût", entite)
            continue
        traces.append(resultat.trace)
        sorties.extend(
            SortieDoublon(
                date_arrete=date_arrete,
                entite=entite,
                cle_a=paire.cle_a,
                cle_b=paire.cle_b,
                score=paire.score,
                justification=paire.justification,
                statut_controle=resultat.statut,
            )
            for paire in resultat.sortie.paires
        )
    return tuple(sorties), tuple(traces)
