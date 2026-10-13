"""Tâche `doublons` : paires d'Anomalies probablement en doublon, avec un score (FR-36, bonus).

La détection ne fusionne rien et n'écrit rien dans Jira : elle propose des paires que le Pilote
revoit. Deux temps. D'abord une présélection locale et déterministe sur les Anomalies ouvertes :
similarité de Jaccard entre les mots du titre et de la description, au moins
`SEUIL_PRESELECTION`, les `MAX_PAIRES` plus proches retenues (la comparaison ne coûte aucun
appel LLM). Ensuite un appel par paire retenue, par la passerelle (ordre AD-12), avec le prompt
`prompts/doublons.md` : le LLM rend un `score` de 0 à 100. Le contrôle déterministe retire de
la justification toute phrase citant une autre clé que les deux de la paire (`corrige`). Seules
les paires de score au moins `SEUIL_SCORE` sont publiées, triées par score décroissant puis par
clés.

Plafond de coût du Passage atteint (`PlafondCoutAtteint`) : les paires restantes ne sont pas
demandées. Un échec isolé du fournisseur laisse la paire sans score, consigné au journal ;
`MAX_ECHECS_CONSECUTIFS` échecs d'affilée font échouer la tâche. Une Anomalie fermée ou
inconnue n'entre jamais dans une paire.
"""

import logging
import re
import unicodedata
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from importlib import resources
from typing import Any

import polars as pl

from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import (
    ParametresAppel,
    ReponseDoublons,
    SortieDoublons,
    StatutControle,
    Tache,
)
from usine.contrats.tickets import rang_cle
from usine.contrats.trace import EntreeTrace
from usine.ia.classification import anomalies
from usine.ia.controles import decouper_phrases, retirer_citations_hors
from usine.ia.explication import ContexteExplication, _donnee, rendre_prompt
from usine.ia.passerelle import ContexteAppel, Controle, Passerelle, PlafondCoutAtteint

SEUIL_PRESELECTION = 0.3
"""Similarité de Jaccard minimale (0 à 1) pour qu'une paire parte au LLM."""

MAX_PAIRES = 50
"""Paires envoyées au LLM au plus par Passage : borne du coût (NFR-9)."""

SEUIL_SCORE = 70
"""Score minimal (0 à 100) d'une paire publiée."""

MAX_ECHECS_CONSECUTIFS = 3
"""Échecs du fournisseur d'affilée au-delà desquels la tâche échoue (fournisseur injoignable)."""

MAX_JETONS_SORTIE = 256
"""Plafond de jetons de sortie d'une estimation de doublon."""

journal = logging.getLogger(__name__)

_MOT = re.compile(r"[a-z0-9]{3,}")
_MOTS_VIDES = frozenset(
    [
        "les",
        "des",
        "une",
        "aux",
        "que",
        "qui",
        "par",
        "pour",
        "dans",
        "sur",
        "avec",
        "sans",
        "est",
        "sont",
        "pas",
        "plus",
        "mais",
        "donc",
        "elle",
        "ils",
        "nous",
        "vous",
        "ces",
        "ses",
        "son",
        "leur",
        "leurs",
        "the",
        "and",
    ]
)


def lire_prompt() -> bytes:
    """Octets de `ia/prompts/doublons.md` (source de `version_prompt`)."""
    return (resources.files("usine.ia") / "prompts" / "doublons.md").read_bytes()


class ContexteDoublons(ContexteExplication):
    """Contexte du Passage commun aux estimations de doublons."""


def mots(titre: str | None, description: str | None) -> frozenset[str]:
    """Mots significatifs (minuscules, sans accent, 3 caractères au moins) d'une Anomalie."""
    texte = unicodedata.normalize("NFKD", f"{titre or ''} {description or ''}".lower())
    sans_accent = "".join(c for c in texte if not unicodedata.combining(c))
    return frozenset(m for m in _MOT.findall(sans_accent) if m not in _MOTS_VIDES)


def similarite(a: frozenset[str], b: frozenset[str]) -> float:
    """Similarité de Jaccard de deux ensembles de mots (0 si l'un est vide)."""
    union = len(a | b)
    return len(a & b) / union if union else 0.0


@dataclass(frozen=True)
class Candidate:
    """Paire présélectionnée : deux lignes de `TicketTexte` et leur similarité."""

    ligne_a: dict[str, Any]
    ligne_b: dict[str, Any]
    similarite: float


def preselectionner(
    textes: pl.DataFrame, ouvertes: Collection[str], max_paires: int = MAX_PAIRES
) -> tuple[Candidate, ...]:
    """Paires d'Anomalies ouvertes assez proches, les plus proches d'abord (`max_paires` au plus).

    Chaque paire range ses deux Anomalies dans l'ordre des clés ; à similarité égale, l'ordre
    des clés départage.
    """
    autorisees = frozenset(ouvertes)
    lignes = [ligne for ligne in anomalies(textes) if ligne["cle_ticket"] in autorisees]
    ensembles = [mots(ligne["titre"], ligne["description"]) for ligne in lignes]
    retenues: list[Candidate] = []
    for i, ligne_a in enumerate(lignes):
        for j in range(i + 1, len(lignes)):
            score = similarite(ensembles[i], ensembles[j])
            if score >= SEUIL_PRESELECTION:
                retenues.append(Candidate(ligne_a, lignes[j], score))
    retenues.sort(
        key=lambda c: (
            -c.similarite,
            rang_cle(c.ligne_a["cle_ticket"]),
            rang_cle(c.ligne_b["cle_ticket"]),
        )
    )
    return tuple(retenues[:max_paires])


def _ticket(ligne: dict[str, Any]) -> str:
    return (
        f"{ligne['cle_ticket']} : {_donnee(ligne['titre'] or '(sans titre)')}\n"
        f"{_donnee(ligne['description'] or '(sans description)')}"
    )


@dataclass(frozen=True)
class _Controleur:
    """Contrôle d'une `ReponseDoublons` : justification sans clé d'un autre ticket."""

    cle_a: str
    cle_b: str

    def __call__(self, reponse: ReponseDoublons) -> Controle[SortieDoublons]:
        justification = retirer_citations_hors(reponse.justification, (self.cle_a, self.cle_b))
        retirees = len(decouper_phrases(reponse.justification)) - len(
            decouper_phrases(justification)
        )
        if retirees:
            statut = StatutControle.corrige
        else:
            statut = StatutControle.conforme
            justification = reponse.justification
        sortie = SortieDoublons(
            cle_a=self.cle_a,
            cle_b=self.cle_b,
            score=reponse.score,
            justification=justification,
            statut_controle=statut,
        )
        return Controle(sortie, statut, retirees)


def detecter_doublons(
    passerelle: Passerelle,
    textes: pl.DataFrame,
    ouvertes: Collection[str],
    date_arrete: date,
    version_grille: str,
    contexte: ContexteDoublons,
    plafond_eur: Decimal | None = None,
) -> tuple[tuple[SortieDoublons, ...], tuple[EntreeTrace, ...]]:
    """Paires de doublons probables parmi les Anomalies `ouvertes` de `textes`, et leurs traces.

    `ouvertes` : clés des Anomalies ouvertes à la Date d'arrêté ; les autres sont ignorées.
    Seules les paires de score au moins `SEUIL_SCORE` sont rendues, mais chaque appel laisse sa
    trace. Aucune écriture : le résultat est une liste de suggestions pour le Pilote.
    """
    sorties: list[SortieDoublons] = []
    traces: list[EntreeTrace] = []
    consecutifs = 0
    parametres = ParametresAppel(tache=Tache.doublons, max_jetons_sortie=MAX_JETONS_SORTIE)
    for candidate in preselectionner(textes, ouvertes):
        cle_a = candidate.ligne_a["cle_ticket"]
        cle_b = candidate.ligne_b["cle_ticket"]
        prompt = rendre_prompt(
            contexte.texte_gabarit,
            {
                "cle_a": cle_a,
                "cle_b": cle_b,
                "ticket_a": _ticket(candidate.ligne_a),
                "ticket_b": _ticket(candidate.ligne_b),
            },
            Tache.doublons,
        )
        appel = ContexteAppel(
            passage_id=contexte.passage_id,
            date_arrete=date_arrete,
            cible=f"{cle_a}|{cle_b}",
            version_prompt=contexte.version_prompt,
            version_grille=version_grille,
            version_donnees=contexte.version_donnees,
            entite=candidate.ligne_a["entite"],
        )
        try:
            resultat = passerelle.executer_structure(
                prompt,
                ReponseDoublons,
                parametres,
                appel,
                _Controleur(cle_a, cle_b),
                plafond_eur=plafond_eur,
            )
        except PlafondCoutAtteint:
            journal.warning("doublons : plafond de coût atteint, paires restantes non demandées")
            break
        except UsineErreur as exc:
            traces.extend(passerelle.vider_traces_echec(Tache.doublons))
            consecutifs += 1
            if consecutifs >= MAX_ECHECS_CONSECUTIFS:
                raise UsineErreur(
                    f"doublons : {consecutifs} échecs consécutifs du fournisseur LLM"
                    f" (dernier sur {cle_a}|{cle_b} : {exc})"
                ) from exc
            journal.warning("doublons : paire %s|%s en échec, sans score : %s", cle_a, cle_b, exc)
            continue
        consecutifs = 0
        traces.append(resultat.trace)
        if resultat.sortie.score >= SEUIL_SCORE:
            sorties.append(resultat.sortie)
    sorties.sort(key=lambda s: (-s.score, rang_cle(s.cle_a), rang_cle(s.cle_b)))
    return tuple(sorties), tuple(traces)
