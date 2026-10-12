"""Passerelle LLM : seul appelant du `FournisseurLLM`, dans l'ordre imposé par AD-12.

Ordre, sans exception : Pseudonymisation de toute l'entrée → cache → `FournisseurLLM` →
contrôle propre à la tâche → ré-identification locale → `EntreeTrace`. Rien n'atteint le
fournisseur ni le cache sans être pseudonymisé ; la trace ne contient que des textes
pseudonymisés (entrée, et sortie contrôlée avant ré-identification). Seuls les jetons présents
dans l'entrée pseudonymisée de l'appel sont ré-identifiés ; tout autre jeton reste tel quel.

Le cache est reçu par injection, par le port `CacheLLM` (implémenté par
`adaptateurs/stockage_sqlite`). La valeur stockée est une `contrats.llm.EnveloppeCache` JSON :
réponse brute et `version_modele` reçu. Les jetons suivent la grammaire de `contrats.llm`.

Coût (NFR-9) : chaque appel frais porte dans sa trace le coût estimé que donne le tarif injecté
(`Callable[[version_modele, jetons_entree, jetons_sortie], Decimal]`, fourni par la
composition : `ia` n'importe pas `adaptateurs`) ; un succès en cache coûte 0 €. La passerelle
cumule ces coûts par `passage_id` ; une fois le cumul au plafond ou au-delà, tout appel frais
lève `PlafondCoutAtteint` avant le fournisseur, tandis que le cache reste servi. L'appel qui
franchit le plafond passe : seuls les suivants sont refusés. Chaque tâche choisit son repli.
"""

import hashlib
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ValidationError

from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import (
    CANDIDAT_JETON,
    EnveloppeCache,
    ParametresAppel,
    StatutControle,
    Tache,
    variantes_jeton,
)
from usine.contrats.trace import EntreeTrace, TypeTrace
from usine.ports.cache_llm import CacheLLM
from usine.ports.fournisseur_llm import FournisseurLLM
from usine.ports.pseudonymiseur import Pseudonymiseur

journal = logging.getLogger(__name__)

Tarif = Callable[[str, int, int], Decimal]
"""Coût estimé d'un appel, en euros : `(version_modele, jetons_entree, jetons_sortie)`."""


def tarif_nul(version_modele: str, jetons_entree: int, jetons_sortie: int) -> Decimal:
    """Tarif par défaut : tout appel est estimé à 0 €."""
    return Decimal(0)


class PlafondCoutAtteint(UsineErreur):
    """Plafond de coût du Passage atteint : aucun appel frais au fournisseur (NFR-9)."""


@dataclass(frozen=True)
class ContexteAppel:
    """Contexte d'un appel : identité du Passage, cible et versions tracées."""

    passage_id: str
    date_arrete: date
    cible: str
    """Clé de ticket (classification) ou Entité (explication, narration)."""
    version_prompt: str
    version_grille: str
    version_donnees: str
    entite: str | None = None


@dataclass(frozen=True)
class Controle[S: BaseModel]:
    """Sortie d'un contrôle propre à la tâche, encore pseudonymisée."""

    sortie: S
    statut: StatutControle
    phrases_retirees: int = 0


@dataclass(frozen=True)
class ResultatAppel[S: BaseModel]:
    """Résultat d'un appel : sortie contrôlée et ré-identifiée, et sa trace."""

    sortie: S
    statut: StatutControle
    phrases_retirees: int
    trace: EntreeTrace


def empreinte(texte: str) -> str:
    """SHA-256 (64 hex) du texte encodé en UTF-8."""
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def cle_cache(
    parametres: ParametresAppel, contexte: ContexteAppel, version_modele: str, entree: str
) -> str:
    """Clé de cache stable (JSON trié) ; `entree` est l'entrée déjà pseudonymisée.

    `version_donnees` n'y entre pas : elle figure seulement dans la trace. La Date d'arrêté
    n'entre pas dans la clé d'une classification : un ticket inchangé garde sa Classification
    d'un jour à l'autre.
    """
    champs: dict[str, object] = {
        "tache": parametres.tache.value,
        "cible": contexte.cible,
        "version_prompt": contexte.version_prompt,
        "version_modele": version_modele,
        "empreinte_entree": empreinte(entree),
        "tentative": parametres.tentative,
    }
    if parametres.tache is not Tache.classification:
        champs["date_arrete"] = contexte.date_arrete.isoformat()
    return json.dumps(
        champs,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


_MASQUE = re.compile("\x00([0-9]+)\x00")


def jetons_de(texte: str) -> frozenset[str]:
    """Jetons (et variantes) présents dans `texte`, selon la grammaire de `contrats.llm`."""
    return frozenset(v for m in CANDIDAT_JETON.finditer(texte) for v in variantes_jeton(m))


def _reidentifier_texte(
    texte: str, pseudonymiseur: Pseudonymiseur, autorises: frozenset[str]
) -> str:
    """Ré-identifie `texte` ; un jeton absent de l'entrée de cet appel reste un jeton.

    Un jeton recopié ou inventé par le modèle depuis un autre appel ne doit pas faire entrer
    la valeur d'un autre enregistrement : il est masqué pendant la ré-identification.
    """
    masques: list[str] = []

    def masquer(candidat: re.Match[str]) -> str:
        if autorises.intersection(variantes_jeton(candidat)):
            return candidat.group(0)
        masques.append(candidat.group(0))
        return f"\x00{len(masques) - 1}\x00"

    resultat = pseudonymiseur.reidentifier(CANDIDAT_JETON.sub(masquer, texte))
    return _MASQUE.sub(lambda m: masques[int(m.group(1))], resultat)


def _reidentifier(
    valeur: object, pseudonymiseur: Pseudonymiseur, autorises: frozenset[str]
) -> object:
    """Ré-identifie chaque chaîne d'une structure `model_dump` (listes, tuples, dicts)."""
    if isinstance(valeur, str):
        return _reidentifier_texte(valeur, pseudonymiseur, autorises)
    if isinstance(valeur, dict):
        return {cle: _reidentifier(v, pseudonymiseur, autorises) for cle, v in valeur.items()}
    if isinstance(valeur, list | tuple):
        return [_reidentifier(v, pseudonymiseur, autorises) for v in valeur]
    return valeur


class Passerelle:
    """Passerelle LLM ; seule à appeler le fournisseur et à accéder au cache."""

    def __init__(
        self,
        fournisseur: FournisseurLLM,
        pseudonymiseur: Pseudonymiseur,
        cache: CacheLLM,
        horloge: Callable[[], datetime],
        tarif: Tarif = tarif_nul,
        plafond_cout_passage_eur: Decimal | None = None,
    ) -> None:
        """`plafond_cout_passage_eur` : `None` pour aucun plafond."""
        self._fournisseur = fournisseur
        self._pseudonymiseur = pseudonymiseur
        self._cache = cache
        self._horloge = horloge
        self._tarif = tarif
        self._plafond = plafond_cout_passage_eur
        self._cumul: dict[str, Decimal] = {}

    def cout_cumule_eur(self, passage_id: str) -> Decimal:
        """Coût estimé cumulé des appels frais du Passage `passage_id`."""
        return self._cumul.get(passage_id, Decimal(0))

    @property
    def version_modele(self) -> str:
        """Version de modèle du fournisseur (`fournisseur:modele`)."""
        return self._fournisseur.version_modele

    def executer_structure[T: BaseModel, S: BaseModel](
        self,
        prompt: str,
        schema: type[T],
        parametres: ParametresAppel,
        contexte: ContexteAppel,
        controler: Callable[[T], Controle[S]],
    ) -> ResultatAppel[S]:
        """Exécute un appel structuré dans l'ordre d'AD-12 et renvoie sortie et trace.

        La clé de cache porte le `version_modele` du fournisseur, connu avant l'appel ; la trace
        porte celui de la `ReponseStructuree` reçue, gardé dans l'`EnveloppeCache` pour un succès
        en cache.
        """
        entree = self._pseudonymiseur.pseudonymiser(prompt)
        version_modele = self._fournisseur.version_modele
        cle = cle_cache(parametres, contexte, version_modele, entree)

        reponse: T | None = None
        version_reponse = version_modele
        jetons_entree = jetons_sortie = 0
        cout = Decimal(0)
        stocke = self._cache.lire(cle)
        if stocke is not None:
            try:
                enveloppe = EnveloppeCache.model_validate_json(stocke)
                reponse = schema.model_validate_json(enveloppe.brut)
                version_reponse = enveloppe.version_modele
            except ValidationError as exc:
                journal.warning(
                    "réponse en cache illisible pour %s (%s), nouvel appel au fournisseur",
                    contexte.cible,
                    exc.error_count(),
                )
        depuis_cache = reponse is not None
        if reponse is None:
            cumul = self.cout_cumule_eur(contexte.passage_id)
            if self._plafond is not None and cumul >= self._plafond:
                journal.warning(
                    "plafond de coût du Passage %s atteint (%s € ≥ %s €) : %s sans appel",
                    contexte.passage_id,
                    cumul,
                    self._plafond,
                    contexte.cible,
                )
                raise PlafondCoutAtteint(
                    f"plafond de coût du Passage atteint ({cumul} € pour un plafond de"
                    f" {self._plafond} €, config/llm.yaml, clé « plafond_cout_passage_eur »)"
                )
            appel = self._fournisseur.generer_structure(entree, schema, parametres)
            enveloppe = EnveloppeCache(brut=appel.brut, version_modele=appel.version_modele)
            self._cache.ecrire(cle, enveloppe.model_dump_json())
            reponse = appel.sortie
            jetons_entree, jetons_sortie = appel.jetons_entree, appel.jetons_sortie
            version_reponse = appel.version_modele
            cout = self._tarif(version_reponse, jetons_entree, jetons_sortie)
            self._cumul[contexte.passage_id] = cumul + cout

        controle = controler(reponse)
        donnees = _reidentifier(
            controle.sortie.model_dump(), self._pseudonymiseur, jetons_de(entree)
        )
        sortie = type(controle.sortie).model_validate(donnees)

        trace = EntreeTrace(
            type_trace=TypeTrace.llm,
            horodatage=self._horloge(),
            passage_id=contexte.passage_id,
            date_arrete=contexte.date_arrete,
            entite=contexte.entite,
            tache=parametres.tache,
            cible=contexte.cible,
            fournisseur=version_reponse.split(":", 1)[0],
            version_prompt=contexte.version_prompt,
            version_modele=version_reponse,
            version_grille=contexte.version_grille,
            version_donnees=contexte.version_donnees,
            entree_pseudonymisee=entree,
            sortie=controle.sortie.model_dump_json(),
            statut_controle=controle.statut,
            phrases_retirees=controle.phrases_retirees,
            depuis_cache=depuis_cache,
            jetons_entree=jetons_entree,
            jetons_sortie=jetons_sortie,
            cout_estime_eur=cout,
        )
        return ResultatAppel(sortie, controle.statut, controle.phrases_retirees, trace)
