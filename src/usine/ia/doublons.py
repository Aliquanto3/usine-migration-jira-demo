"""Tâche `doublons` [BONUS] : paires d'Anomalies ouvertes probablement en doublon (FR-36).

Deux temps. Un pré-filtre déterministe local retient, par Entité, les paires d'Anomalies
ouvertes dont les textes (titre et description, hors clés de ticket) partagent assez de mots
(`SEUIL_SIMILARITE`, indice de Jaccard), au plus `MAX_PAIRES` : le coût reste borné et aucun
texte ne part vers le LLM pour les paires sans rapport. Chaque paire retenue fait ensuite un
appel par la passerelle (ordre AD-12) ; le prompt `prompts/doublons.md` reçoit les deux
Anomalies entre délimiteurs (données, pas instructions) et le fournisseur rend un score de 0
à 1. Le contrôle déterministe retire de la justification toute phrase citant une autre clé
de ticket (`corrige`) ; sinon `conforme`.

Sont publiées les paires de score au moins `SCORE_MIN`, triées par score décroissant. Le
résultat n'est qu'une liste à revoir par le Pilote : aucune fusion, aucune écriture dans Jira.
Plafond de coût du Passage atteint : la détection s'arrête, les paires restantes sont absentes.
Un échec isolé du fournisseur laisse la paire sans score, consignée au journal ; seuls
`MAX_ECHECS_CONSECUTIFS` échecs d'affilée (fournisseur injoignable) font échouer la tâche.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
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
from usine.contrats.tickets import rang_cle
from usine.contrats.trace import EntreeTrace
from usine.contrats.versions import version_prompt
from usine.ia.classification import anomalies
from usine.ia.controles import decouper_phrases, retirer_citations_hors
from usine.ia.explication import _donnee, rendre_prompt
from usine.ia.passerelle import ContexteAppel, Controle, Passerelle, PlafondCoutAtteint
from usine.ports.consultation import Consultation

SEUIL_SIMILARITE = 0.3
"""Indice de Jaccard minimal des mots de deux Anomalies pour qu'elles soient comparées."""

MAX_PAIRES = 50
"""Paires envoyées au fournisseur au plus par détection (les plus proches d'abord)."""

SCORE_MIN = 0.5
"""Score minimal d'une paire publiée."""

MAX_ECHECS_CONSECUTIFS = 3
"""Échecs du fournisseur d'affilée au-delà desquels la détection échoue."""

MAX_JETONS_SORTIE = 256
"""Plafond de jetons de sortie d'une comparaison."""

journal = logging.getLogger(__name__)

_CLE_TICKET = re.compile(r"\b[A-Z][A-Z0-9]*-\d+\b")
_MOT = re.compile(r"[a-z0-9]{3,}")
_MOTS_VIDES = frozenset(
    {
        "les", "des", "une", "aux", "est", "sont", "dans", "pour", "par", "sur", "avec", "sans",
        "que", "qui", "pas", "plus", "mais", "ont", "ces", "cette", "son", "ses", "leur",
        "leurs", "elle", "elles", "ils", "nous", "vous", "tout", "tous", "toute", "toutes",
        "entre", "depuis", "lors", "the", "and", "for", "with",
    }
)  # fmt: skip

type Ligne = dict[str, Any]
"""Ligne de `SCHEMA_TICKET_TEXTE`."""


def lire_prompt() -> bytes:
    """Octets de `ia/prompts/doublons.md` (source de `version_prompt`)."""
    return (resources.files("usine.ia") / "prompts" / "doublons.md").read_bytes()


@dataclass(frozen=True)
class ContexteDoublons:
    """Contexte du Passage commun aux comparaisons."""

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


def mots(titre: str | None, description: str | None) -> frozenset[str]:
    """Mots significatifs d'une Anomalie : minuscules sans accent, clés de ticket écartées."""
    texte = _CLE_TICKET.sub(" ", f"{titre or ''} {description or ''}")
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")
    return frozenset(_MOT.findall(texte.lower())) - _MOTS_VIDES


def similarite(a: frozenset[str], b: frozenset[str]) -> float:
    """Indice de Jaccard de deux ensembles de mots (0 si les deux sont vides)."""
    union = len(a | b)
    return len(a & b) / union if union else 0.0


def candidats(lignes: list[Ligne]) -> list[tuple[Ligne, Ligne]]:
    """Paires d'Anomalies d'une même Entité assez proches, les plus proches d'abord.

    `lignes` : lignes de `SCHEMA_TICKET_TEXTE` triées par `rang_cle`, de sorte que chaque
    paire porte sa plus petite clé en premier. Au plus `MAX_PAIRES`, départagées par les clés.
    """
    par_entite: dict[str | None, list[tuple[Ligne, frozenset[str]]]] = {}
    for ligne in lignes:
        par_entite.setdefault(ligne["entite"], []).append(
            (ligne, mots(ligne["titre"], ligne["description"]))
        )
    proches: list[tuple[float, Ligne, Ligne]] = []
    for groupe in par_entite.values():
        for (ligne_a, mots_a), (ligne_b, mots_b) in combinations(groupe, 2):
            indice = similarite(mots_a, mots_b)
            if indice >= SEUIL_SIMILARITE:
                proches.append((indice, ligne_a, ligne_b))
    proches.sort(key=lambda p: (-p[0], rang_cle(p[1]["cle_ticket"]), rang_cle(p[2]["cle_ticket"])))
    return [(a, b) for _, a, b in proches[:MAX_PAIRES]]


def _ticket(ligne: Ligne) -> str:
    return (
        f"{ligne['cle_ticket']} : {_donnee(ligne['titre'] or '(sans titre)')}\n"
        f"{_donnee(ligne['description'] or '(sans description)')}"
    )


@dataclass(frozen=True)
class _Controleur:
    """Contrôle d'une `ReponseDoublon` : justification sans clé d'un autre ticket."""

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


def detecter_doublons(
    passerelle: Passerelle,
    textes: pl.DataFrame,
    ouvertes: frozenset[str],
    date_arrete: date,
    contexte: ContexteDoublons,
) -> tuple[tuple[SortieDoublon, ...], tuple[EntreeTrace, ...]]:
    """Paires de doublons probables entre les Anomalies de `textes` dont la clé est dans
    `ouvertes`, et la trace de chaque appel.

    Les Anomalies fermées, les Cas de test et les Certifications ne sont jamais comparés.
    """
    lignes = [ligne for ligne in anomalies(textes) if ligne["cle_ticket"] in ouvertes]
    gabarit = contexte.gabarit.decode("utf-8")
    parametres = ParametresAppel(tache=Tache.doublons, max_jetons_sortie=MAX_JETONS_SORTIE)
    sorties: list[SortieDoublon] = []
    traces: list[EntreeTrace] = []
    echecs: list[str] = []
    consecutifs = 0
    for ligne_a, ligne_b in candidats(lignes):
        cle_a, cle_b = ligne_a["cle_ticket"], ligne_b["cle_ticket"]
        cible = f"{cle_a}+{cle_b}"
        prompt = rendre_prompt(
            gabarit,
            {
                "cle_a": cle_a,
                "cle_b": cle_b,
                "ticket_a": _ticket(ligne_a),
                "ticket_b": _ticket(ligne_b),
            },
            Tache.doublons,
        )
        appel = ContexteAppel(
            passage_id=contexte.passage_id,
            date_arrete=date_arrete,
            cible=cible,
            version_prompt=contexte.version_prompt,
            version_grille=contexte.version_grille,
            version_donnees=contexte.version_donnees,
            entite=ligne_a["entite"],
        )
        try:
            resultat = passerelle.executer_structure(
                prompt, ReponseDoublon, parametres, appel, _Controleur(cle_a, cle_b)
            )
        except PlafondCoutAtteint:
            journal.warning("doublons : plafond de coût atteint, détection arrêtée à %s", cible)
            break
        except UsineErreur as exc:
            traces.extend(passerelle.vider_traces_echec(Tache.doublons))
            consecutifs += 1
            echecs.append(cible)
            if consecutifs >= MAX_ECHECS_CONSECUTIFS:
                raise UsineErreur(
                    f"doublons : {consecutifs} échecs consécutifs du fournisseur LLM"
                    f" (dernier sur {cible} : {exc})"
                ) from exc
            journal.warning("doublons de %s en échec, sans score : %s", cible, exc)
            continue
        consecutifs = 0
        traces.append(resultat.trace)
        if resultat.sortie.score >= SCORE_MIN:
            sorties.append(resultat.sortie)
    if echecs:
        journal.warning("%d paire(s) sans score après échec : %s", len(echecs), ", ".join(echecs))
    sorties.sort(key=lambda s: (-s.score, rang_cle(s.cle_a), rang_cle(s.cle_b)))
    return tuple(sorties), tuple(traces)


class DetecteurDoublons:
    """Détection de doublons sur un Passage publié, lu via la Consultation ; n'écrit rien."""

    def __init__(self, passerelle: Passerelle, gabarit: bytes | None = None) -> None:
        self._passerelle = passerelle
        self._gabarit = gabarit if gabarit is not None else lire_prompt()

    @property
    def version_prompt(self) -> str:
        """`version_prompt` du gabarit envoyé."""
        return version_prompt(self._gabarit)

    def detecter(
        self, consultation: Consultation
    ) -> tuple[tuple[SortieDoublon, ...], tuple[EntreeTrace, ...]]:
        """Doublons probables des Anomalies ouvertes à la Date d'arrêté du Passage lu."""
        manifeste = consultation.manifeste()
        ouvertes = frozenset(
            a.cle_ticket for a in consultation.anomalies(manifeste.date_arrete).anomalies
        )
        contexte = ContexteDoublons(
            passage_id=manifeste.passage_id,
            version_donnees=manifeste.version_donnees,
            version_grille=manifeste.version_grille,
            gabarit=self._gabarit,
        )
        return detecter_doublons(
            self._passerelle,
            consultation.textes_tickets(),
            ouvertes,
            manifeste.date_arrete,
            contexte,
        )
