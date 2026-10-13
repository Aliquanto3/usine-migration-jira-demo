"""Tâche `doublons` : paires d'Anomalies ouvertes probablement en doublon (FR-36, bonus).

Deux temps, pour que le modèle ne calcule aucun chiffre (AD-14) : un tri local retient les
paires d'Anomalies ouvertes dont les textes se ressemblent (similarité de Jaccard sur les mots,
sans accent ni mot vide, au moins `SEUIL_CANDIDAT`, au plus `MAX_PAIRES` paires les plus
proches) ; puis un appel par paire, par la passerelle (ordre AD-12, textes pseudonymisés),
demande au modèle si les deux Anomalies décrivent le même défaut. Seules les paires confirmées
sont publiées, en `SortieDoublon` dont le `score` est la similarité locale. Le contrôle
déterministe retire de la justification toute phrase citant une autre clé de ticket (`corrige`).

Le résultat est une liste à revoir par le Pilote : aucune fusion, aucune écriture dans Jira.
Plafond de coût du Passage atteint : les paires restantes ne sont pas demandées. Un échec isolé
du fournisseur laisse la paire de côté ; `MAX_ECHECS_CONSECUTIFS` échecs d'affilée font échouer
la détection.
"""

import logging
import re
import unicodedata
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from importlib import resources
from itertools import combinations

import polars as pl

from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import (
    ParametresAppel,
    ReponseDoublons,
    SortieDoublon,
    StatutControle,
    Tache,
)
from usine.contrats.tickets import TypeTicket, rang_cle
from usine.contrats.trace import EntreeTrace
from usine.contrats.versions import version_prompt
from usine.ia.controles import decouper_phrases, retirer_citations_hors
from usine.ia.explication import _donnee, rendre_prompt
from usine.ia.passerelle import ContexteAppel, Controle, Passerelle, PlafondCoutAtteint
from usine.ports.consultation import Consultation

SEUIL_CANDIDAT = 0.5
"""Similarité minimale (0 à 1) d'une paire soumise au modèle."""

MAX_PAIRES = 50
"""Paires soumises au modèle au plus, les plus proches d'abord : borne le coût d'une détection."""

MAX_ECHECS_CONSECUTIFS = 3
"""Échecs du fournisseur d'affilée au-delà desquels la détection échoue."""

MAX_JETONS_SORTIE = 256
"""Plafond de jetons de sortie d'un avis sur une paire."""

journal = logging.getLogger(__name__)

_MOT = re.compile(r"[a-z0-9]{3,}")
_MOTS_VIDES = frozenset(
    [
        "les",
        "des",
        "une",
        "the",
        "and",
        "que",
        "qui",
        "pour",
        "par",
        "sur",
        "dans",
        "avec",
        "sans",
        "est",
        "sont",
        "pas",
        "aux",
        "ces",
        "ses",
        "son",
        "leur",
        "lors",
        "plus",
        "mais",
        "donc",
        "ainsi",
        "cette",
        "entre",
        "vers",
        "apres",
        "avant",
        "sous",
        "tout",
        "tous",
    ]
)


def lire_prompt() -> bytes:
    """Octets de `ia/prompts/doublons.md` (source de `version_prompt`)."""
    return (resources.files("usine.ia") / "prompts" / "doublons.md").read_bytes()


@dataclass(frozen=True)
class ContexteDoublons:
    """Contexte du Passage commun aux avis sur les paires."""

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

    @property
    def texte_gabarit(self) -> str:
        """Gabarit décodé en UTF-8."""
        return self.gabarit.decode("utf-8")


@dataclass(frozen=True)
class AnomalieTexte:
    """Anomalie ouverte telle que comparée : clé, Entité, titre et description."""

    cle: str
    entite: str | None
    titre: str
    description: str

    @property
    def mots(self) -> frozenset[str]:
        """Mots du titre et de la description : minuscules, sans accent, sans mot vide."""
        decomposes = unicodedata.normalize("NFKD", f"{self.titre} {self.description}")
        sans_accent = "".join(c for c in decomposes if not unicodedata.combining(c))
        return frozenset(_MOT.findall(sans_accent.lower())) - _MOTS_VIDES

    def bloc(self) -> str:
        """Clé, titre et description, sans délimiteur de bloc de données."""
        return (
            f"{self.cle} : {_donnee(self.titre or '(sans titre)')}\n"
            f"{_donnee(self.description or '(sans description)')}"
        )


@dataclass(frozen=True)
class PaireCandidate:
    """Paire d'Anomalies ouvertes assez proches pour être soumise au modèle."""

    a: AnomalieTexte
    b: AnomalieTexte
    score: float


def similarite(mots_a: Collection[str], mots_b: Collection[str]) -> float:
    """Similarité de Jaccard de deux ensembles de mots, de 0 à 1, arrondie à 3 décimales."""
    a, b = frozenset(mots_a), frozenset(mots_b)
    union = len(a | b)
    return round(len(a & b) / union, 3) if union else 0.0


def paires_candidates(
    textes: pl.DataFrame,
    ouvertes: Collection[str],
    seuil: float = SEUIL_CANDIDAT,
    maximum: int = MAX_PAIRES,
) -> tuple[PaireCandidate, ...]:
    """Paires d'Anomalies ouvertes de `textes` dont la similarité atteint `seuil`.

    Les Cas de test, les Certifications et les Anomalies fermées (hors `ouvertes`) sont
    écartés. Tri par score décroissant puis par clés ; au plus `maximum` paires. `a` précède
    `b` dans l'ordre des clés.
    """
    retenues = frozenset(ouvertes)
    lignes = textes.filter(pl.col("type_ticket") == TypeTicket.anomalie.value)
    anomalies = sorted(
        (
            AnomalieTexte(
                ligne["cle_ticket"],
                ligne["entite"],
                ligne["titre"] or "",
                ligne["description"] or "",
            )
            for ligne in lignes.iter_rows(named=True)
            if ligne["cle_ticket"] in retenues
        ),
        key=lambda anomalie: rang_cle(anomalie.cle),
    )
    mots = {anomalie.cle: anomalie.mots for anomalie in anomalies}
    paires = []
    for a, b in combinations(anomalies, 2):
        score = similarite(mots[a.cle], mots[b.cle])
        if score >= seuil:
            paires.append(PaireCandidate(a, b, score))
    paires.sort(key=lambda p: (-p.score, rang_cle(p.a.cle), rang_cle(p.b.cle)))
    return tuple(paires[:maximum])


@dataclass(frozen=True)
class _Controleur:
    """Contrôle d'une `ReponseDoublons` : justification sans clé d'un autre ticket."""

    cles: tuple[str, str]

    def __call__(self, reponse: ReponseDoublons) -> Controle[ReponseDoublons]:
        justification = retirer_citations_hors(reponse.justification, self.cles)
        retirees = len(decouper_phrases(reponse.justification)) - len(
            decouper_phrases(justification)
        )
        if retirees:
            statut = StatutControle.corrige
        else:
            statut = StatutControle.conforme
            justification = reponse.justification
        sortie = ReponseDoublons(doublon=reponse.doublon, justification=justification)
        return Controle(sortie, statut, retirees)


def detecter(
    passerelle: Passerelle,
    textes: pl.DataFrame,
    ouvertes: Collection[str],
    date_arrete: date,
    contexte: ContexteDoublons,
    plafond_eur: Decimal | None = None,
) -> tuple[tuple[SortieDoublon, ...], tuple[EntreeTrace, ...]]:
    """Paires d'Anomalies ouvertes confirmées en doublon par le modèle, et une trace par appel.

    Sortie triée par score décroissant puis par clés. Aucune fusion, aucune écriture dans Jira.
    """
    sorties: list[SortieDoublon] = []
    traces: list[EntreeTrace] = []
    consecutifs = 0
    parametres = ParametresAppel(tache=Tache.doublons, max_jetons_sortie=MAX_JETONS_SORTIE)
    for paire in paires_candidates(textes, ouvertes):
        cle_a, cle_b = paire.a.cle, paire.b.cle
        prompt = rendre_prompt(
            contexte.texte_gabarit,
            {
                "cle_a": cle_a,
                "cle_b": cle_b,
                "tickets": f"{paire.a.bloc()}\n\n{paire.b.bloc()}",
            },
            Tache.doublons,
        )
        appel = ContexteAppel(
            passage_id=contexte.passage_id,
            date_arrete=date_arrete,
            cible=f"{cle_a}|{cle_b}",
            version_prompt=contexte.version_prompt,
            version_grille=contexte.version_grille,
            version_donnees=contexte.version_donnees,
            entite=paire.a.entite if paire.a.entite == paire.b.entite else None,
        )
        try:
            resultat = passerelle.executer_structure(
                prompt,
                ReponseDoublons,
                parametres,
                appel,
                _Controleur((cle_a, cle_b)),
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
            journal.warning("doublons : paire %s|%s en échec, écartée : %s", cle_a, cle_b, exc)
            continue
        consecutifs = 0
        traces.append(resultat.trace)
        if resultat.sortie.doublon:
            sorties.append(
                SortieDoublon(
                    cle_a=cle_a,
                    cle_b=cle_b,
                    score=paire.score,
                    justification=resultat.sortie.justification,
                    statut_controle=resultat.statut,
                )
            )
    return tuple(sorties), tuple(traces)


def detecter_doublons(
    passerelle: Passerelle,
    consultation: Consultation,
    date_arrete: date,
    contexte: ContexteDoublons,
    plafond_eur: Decimal | None = None,
) -> tuple[tuple[SortieDoublon, ...], tuple[EntreeTrace, ...]]:
    """`detecter` sur les Anomalies ouvertes à `date_arrete`, lues via la Consultation."""
    ouvertes = [a.cle_ticket for a in consultation.anomalies(date_arrete).anomalies]
    return detecter(
        passerelle, consultation.textes_tickets(), ouvertes, date_arrete, contexte, plafond_eur
    )
