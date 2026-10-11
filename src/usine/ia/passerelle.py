"""Passerelle LLM : seul appelant du `FournisseurLLM`, dans l'ordre imposé par AD-12.

Ordre, sans exception : Pseudonymisation de toute l'entrée → cache → `FournisseurLLM` →
contrôle propre à la tâche → ré-identification locale → `EntreeTrace`. Rien n'atteint le
fournisseur ni le cache sans être pseudonymisé ; la trace ne contient que des textes
pseudonymisés (entrée, et sortie contrôlée avant ré-identification).

Le cache est reçu par injection : `CacheLLM` est un `Protocol` à types primitifs que
l'adaptateur SQLite satisfait structurellement (la couche `ia` n'importe pas `adaptateurs`).
La valeur stockée est une `EnveloppeCache` JSON : réponse brute et `version_modele` reçu.
"""

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from usine.contrats.llm import ParametresAppel, StatutControle
from usine.contrats.trace import EntreeTrace, TypeTrace
from usine.ports.fournisseur_llm import FournisseurLLM
from usine.ports.pseudonymiseur import Pseudonymiseur

journal = logging.getLogger(__name__)


@runtime_checkable
class CacheLLM(Protocol):
    """Cache des réponses brutes du fournisseur, avant contrôle (AD-12)."""

    def lire(self, cle: str) -> str | None:
        """Réponse brute enregistrée sous `cle`, ou `None`."""
        ...

    def ecrire(self, cle: str, brut: str) -> None:
        """Enregistre (ou remplace) la réponse brute sous `cle`."""
        ...


class EnveloppeCache(BaseModel):
    """Valeur stockée en cache : réponse brute avant contrôle et modèle qui l'a produite."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    brut: str
    version_modele: str = Field(min_length=1)


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

    `version_donnees` n'y entre pas : elle figure seulement dans la trace.
    """
    return json.dumps(
        {
            "tache": parametres.tache.value,
            "cible": contexte.cible,
            "date_arrete": contexte.date_arrete.isoformat(),
            "version_prompt": contexte.version_prompt,
            "version_modele": version_modele,
            "empreinte_entree": empreinte(entree),
            "tentative": parametres.tentative,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _reidentifier(valeur: object, pseudonymiseur: Pseudonymiseur) -> object:
    """Ré-identifie chaque chaîne d'une structure `model_dump` (listes, tuples, dicts)."""
    if isinstance(valeur, str):
        return pseudonymiseur.reidentifier(valeur)
    if isinstance(valeur, dict):
        return {cle: _reidentifier(v, pseudonymiseur) for cle, v in valeur.items()}
    if isinstance(valeur, list | tuple):
        return [_reidentifier(v, pseudonymiseur) for v in valeur]
    return valeur


class Passerelle:
    """Passerelle LLM ; seule à appeler le fournisseur et à accéder au cache."""

    def __init__(
        self,
        fournisseur: FournisseurLLM,
        pseudonymiseur: Pseudonymiseur,
        cache: CacheLLM,
        horloge: Callable[[], datetime],
    ) -> None:
        self._fournisseur = fournisseur
        self._pseudonymiseur = pseudonymiseur
        self._cache = cache
        self._horloge = horloge

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
            appel = self._fournisseur.generer_structure(entree, schema, parametres)
            enveloppe = EnveloppeCache(brut=appel.brut, version_modele=appel.version_modele)
            self._cache.ecrire(cle, enveloppe.model_dump_json())
            reponse = appel.sortie
            jetons_entree, jetons_sortie = appel.jetons_entree, appel.jetons_sortie
            version_reponse = appel.version_modele

        controle = controler(reponse)
        donnees = _reidentifier(controle.sortie.model_dump(), self._pseudonymiseur)
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
        )
        return ResultatAppel(sortie, controle.statut, controle.phrases_retirees, trace)
