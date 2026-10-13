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
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, JsonValue, ValidationError

from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import (
    CANDIDAT_JETON,
    EnveloppeCache,
    MessageAgent,
    OutilAgent,
    ParametresAppel,
    ReponseAgent,
    ReponseAgentBrute,
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


ECHEC_FACTEUR_TENTATIVES = 3
"""Requêtes supposées facturées pour un appel structuré en échec (tentative et relances de
sortie de Pydantic AI) : majoration du coût imputé au plafond."""

ECHEC_CARACTERES_PAR_JETON = 2
"""Caractères par jeton d'entrée supposés pour un appel en échec (majorant : le français
compte plutôt 3 à 4 caractères par jeton)."""


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


@dataclass(frozen=True)
class OutilSource:
    """Outil de l'Agent avant enveloppe : `executer` rend son résultat brut, en clair.

    Des arguments invalides lèvent une `ValidationError`, rendue au modèle en texte.
    """

    nom: str
    description: str
    arguments: type[BaseModel]
    executer: Callable[[Mapping[str, JsonValue]], str]


@dataclass(frozen=True)
class ResultatAgent:
    """Résultat d'une conversation d'Agent : réponse contrôlée et ré-identifiée, et traces.

    `traces` : une trace par outil exécuté, dans l'ordre d'exécution, puis celle de la réponse.
    """

    sortie: ReponseAgent
    statut: StatutControle
    traces: tuple[EntreeTrace, ...]

    @property
    def depuis_cache(self) -> bool:
        """Vrai si la réponse a été servie du cache, sans appel au fournisseur."""
        return self.traces[-1].depuis_cache


def message_erreur_arguments(nom_outil: str) -> str:
    """Texte rendu au modèle quand il appelle `nom_outil` avec des arguments invalides."""
    return f"erreur : arguments invalides pour {nom_outil}"


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
        fournisseurs_par_tache: Mapping[Tache, FournisseurLLM] | None = None,
    ) -> None:
        """`plafond_cout_passage_eur` : `None` pour aucun plafond.

        `fournisseurs_par_tache` : fournisseur dédié à une tâche (clé `modeles_par_tache` de
        `config/llm.yaml`) ; une tâche absente passe par `fournisseur`. Le cumul de coût et le
        plafond du Passage restent communs à tous les fournisseurs.
        """
        self._fournisseur = fournisseur
        self._fournisseurs_par_tache = dict(fournisseurs_par_tache or {})
        self._pseudonymiseur = pseudonymiseur
        self._cache = cache
        self._horloge = horloge
        self._tarif = tarif
        self._plafond = plafond_cout_passage_eur
        self._cumul: dict[str, Decimal] = {}
        self._traces_echec: list[EntreeTrace] = []

    def cout_cumule_eur(self, passage_id: str) -> Decimal:
        """Coût estimé cumulé des appels frais du Passage `passage_id`."""
        return self._cumul.get(passage_id, Decimal(0))

    def vider_traces_echec(self, tache: Tache | None = None) -> tuple[EntreeTrace, ...]:
        """Traces (`en_echec`) des appels structurés échoués, de la `tache` demandée si donnée
        (les autres restent au tampon : un appelant ne reprend pas l'échec d'une autre tâche).

        L'appelant qui tolère un échec les ajoute à ses traces : le coût majoré, déjà imputé au
        plafond, entre ainsi dans `cout_llm_eur` et dans le balayage SM-7.
        """
        prises = tuple(t for t in self._traces_echec if tache is None or t.tache is tache)
        self._traces_echec = [t for t in self._traces_echec if all(t is not p for p in prises)]
        return prises

    def _tracer_echec(
        self,
        contexte: ContexteAppel,
        parametres: ParametresAppel,
        version_modele: str,
        entree: str,
        cumul: Decimal,
        sur_trace: Callable[[EntreeTrace], None] | None = None,
    ) -> None:
        """Impute le coût majoré d'un appel en échec au Passage et en garde la trace.

        Un échec (par exemple `UnexpectedModelBehavior` après relances de sortie) a pu être
        facturé : trois requêtes supposées. La trace porte la même entrée pseudonymisée qu'un
        succès, une sortie vide et le coût majoré ; elle va à `sur_trace`, sinon au tampon
        que vide `vider_traces_echec`.
        """
        jetons_entree = ECHEC_FACTEUR_TENTATIVES * len(entree) // ECHEC_CARACTERES_PAR_JETON
        jetons_sortie = ECHEC_FACTEUR_TENTATIVES * parametres.max_jetons_sortie
        majore = self._tarif(version_modele, jetons_entree, jetons_sortie)
        self._cumul[contexte.passage_id] = cumul + majore
        journal.warning(
            "appel en échec pour %s : %s € estimés imputés au Passage %s",
            contexte.cible,
            majore,
            contexte.passage_id,
        )
        trace = EntreeTrace(
            type_trace=TypeTrace.llm,
            horodatage=self._horloge(),
            passage_id=contexte.passage_id,
            date_arrete=contexte.date_arrete,
            entite=contexte.entite,
            tache=parametres.tache,
            cible=contexte.cible,
            fournisseur=version_modele.split(":", 1)[0],
            version_prompt=contexte.version_prompt,
            version_modele=version_modele,
            version_grille=contexte.version_grille,
            version_donnees=contexte.version_donnees,
            entree_pseudonymisee=entree,
            sortie="",
            statut_controle=StatutControle.non_controle,
            jetons_entree=jetons_entree,
            jetons_sortie=jetons_sortie,
            cout_estime_eur=majore,
            en_echec=True,
        )
        if sur_trace is not None:
            sur_trace(trace)
        else:
            self._traces_echec.append(trace)

    @property
    def version_modele(self) -> str:
        """Version de modèle du fournisseur (`fournisseur:modele`)."""
        return self._fournisseur.version_modele

    def _verifier_plafond(
        self, contexte: ContexteAppel, parametres: ParametresAppel, plafond_eur: Decimal | None
    ) -> Decimal:
        """Cumul du Passage ; lève `PlafondCoutAtteint` si un plafond est atteint (NFR-9)."""
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
        if plafond_eur is not None and cumul >= plafond_eur:
            journal.warning(
                "part du plafond de coût atteinte, Passage %s (%s € ≥ %s €) : %s sans appel",
                contexte.passage_id,
                cumul,
                plafond_eur,
                contexte.cible,
            )
            raise PlafondCoutAtteint(
                f"part du plafond de coût du Passage atteinte ({cumul} € pour une part de"
                f" {plafond_eur} € réservée à la tâche « {parametres.tache.value} »)"
            )
        return cumul

    def executer_structure[T: BaseModel, S: BaseModel](
        self,
        prompt: str,
        schema: type[T],
        parametres: ParametresAppel,
        contexte: ContexteAppel,
        controler: Callable[[T], Controle[S]],
        plafond_eur: Decimal | None = None,
    ) -> ResultatAppel[S]:
        """Exécute un appel structuré dans l'ordre d'AD-12 et renvoie sortie et trace.

        La clé de cache porte le `version_modele` du fournisseur, connu avant l'appel ; la trace
        porte celui de la `ReponseStructuree` reçue, gardé dans l'`EnveloppeCache` pour un succès
        en cache.

        `plafond_eur` : part du plafond réservée à une tâche ; un appel frais est refusé
        (`PlafondCoutAtteint`) dès que le cumul du Passage atteint le plus petit des deux
        plafonds. Le cache reste servi.
        """
        fournisseur = self._fournisseurs_par_tache.get(parametres.tache, self._fournisseur)
        entree = self._pseudonymiseur.pseudonymiser(prompt)
        version_modele = fournisseur.version_modele
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
            cumul = self._verifier_plafond(contexte, parametres, plafond_eur)
            try:
                appel = fournisseur.generer_structure(entree, schema, parametres)
            except UsineErreur:
                self._tracer_echec(contexte, parametres, version_modele, entree, cumul)
                raise
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

    def executer_agent(
        self,
        messages: Sequence[MessageAgent],
        outils: Sequence[OutilSource],
        parametres: ParametresAppel,
        contexte: ContexteAppel,
        controler: Callable[[ReponseAgentBrute], Controle[ReponseAgent]],
        plafond_eur: Decimal | None = None,
        sur_trace: Callable[[EntreeTrace], None] | None = None,
    ) -> ResultatAgent:
        """Conversation d'Agent dans l'ordre d'AD-12, en texte libre (`output_type=str`).

        Chaque message est pseudonymisé avant le cache et le fournisseur ; chaque outil est
        enveloppé en `OutilAgent` : exécution, erreur d'arguments rendue en texte,
        Pseudonymisation du résultat et trace `tache=agent`, `cible=<nom de l'outil>`. Le
        cache garde la `ReponseAgentBrute` (conversation pseudonymisée) : une réponse en cache
        n'exécute aucun outil. `controler` reçoit la réponse pseudonymisée ; la
        ré-identification n'admet que les jetons de la conversation pseudonymisée.

        `sur_trace` reçoit chaque trace dès sa production (chaque outil, puis la réponse) : une
        exception en cours de conversation ne fait pas perdre les traces déjà produites.
        """
        fournisseur = self._fournisseurs_par_tache.get(parametres.tache, self._fournisseur)
        version_modele = fournisseur.version_modele
        pseudonymises = tuple(
            m.model_copy(update={"contenu": self._pseudonymiseur.pseudonymiser(m.contenu)})
            for m in messages
        )
        entree = json.dumps(
            {
                "messages": [m.model_dump(mode="json") for m in pseudonymises],
                "outils": [outil.nom for outil in outils],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        cle = cle_cache(parametres, contexte, version_modele, entree)
        traces_outils: list[EntreeTrace] = []

        def envelopper(source: OutilSource) -> OutilAgent:
            def executer(arguments: Mapping[str, JsonValue]) -> str:
                try:
                    brut = source.executer(arguments)
                except ValidationError as exc:
                    journal.info(
                        "arguments invalides pour %s (%s erreurs)", source.nom, exc.error_count()
                    )
                    brut = message_erreur_arguments(source.nom)
                resultat = self._pseudonymiseur.pseudonymiser(brut)
                arguments_json = json.dumps(dict(arguments), ensure_ascii=False, sort_keys=True)
                traces_outils.append(
                    EntreeTrace(
                        type_trace=TypeTrace.llm,
                        horodatage=self._horloge(),
                        passage_id=contexte.passage_id,
                        date_arrete=contexte.date_arrete,
                        entite=contexte.entite,
                        tache=parametres.tache,
                        cible=source.nom,
                        fournisseur=version_modele.split(":", 1)[0],
                        version_prompt=contexte.version_prompt,
                        version_modele=version_modele,
                        version_grille=contexte.version_grille,
                        version_donnees=contexte.version_donnees,
                        entree_pseudonymisee=self._pseudonymiseur.pseudonymiser(arguments_json),
                        sortie=resultat,
                        statut_controle=StatutControle.non_controle,
                    )
                )
                if sur_trace is not None:
                    sur_trace(traces_outils[-1])
                return resultat

            return OutilAgent(source.nom, source.description, source.arguments, executer)

        reponse: ReponseAgentBrute | None = None
        jetons_entree = jetons_sortie = 0
        cout = Decimal(0)
        stocke = self._cache.lire(cle)
        if stocke is not None:
            try:
                enveloppe = EnveloppeCache.model_validate_json(stocke)
                reponse = ReponseAgentBrute.model_validate_json(enveloppe.brut)
            except ValidationError as exc:
                journal.warning(
                    "réponse d'Agent en cache illisible (%s), nouvel appel au fournisseur",
                    exc.error_count(),
                )
        depuis_cache = reponse is not None
        if reponse is None:
            cumul = self._verifier_plafond(contexte, parametres, plafond_eur)
            try:
                reponse = fournisseur.executer_agent(
                    pseudonymises, [envelopper(o) for o in outils], parametres
                )
            except UsineErreur:
                self._tracer_echec(contexte, parametres, version_modele, entree, cumul, sur_trace)
                raise
            enveloppe = EnveloppeCache(
                brut=reponse.model_dump_json(), version_modele=reponse.version_modele
            )
            self._cache.ecrire(cle, enveloppe.model_dump_json())
            jetons_entree, jetons_sortie = reponse.jetons_entree, reponse.jetons_sortie
            cout = self._tarif(reponse.version_modele, jetons_entree, jetons_sortie)
            self._cumul[contexte.passage_id] = cumul + cout

        controle = controler(reponse)
        # Jetons de l'entrée et des résultats d'outils ; ceux qu'écrit le modèle n'en font pas
        # partie : un jeton inventé ou recopié d'un autre appel reste un jeton.
        autorises = jetons_de(entree).union(
            *(jetons_de(m.contenu) for m in reponse.messages if m.role == "outil")
        )
        donnees = _reidentifier(controle.sortie.model_dump(), self._pseudonymiseur, autorises)
        sortie = ReponseAgent.model_validate(donnees)
        trace = EntreeTrace(
            type_trace=TypeTrace.llm,
            horodatage=self._horloge(),
            passage_id=contexte.passage_id,
            date_arrete=contexte.date_arrete,
            entite=contexte.entite,
            tache=parametres.tache,
            cible=contexte.cible,
            fournisseur=reponse.version_modele.split(":", 1)[0],
            version_prompt=contexte.version_prompt,
            version_modele=reponse.version_modele,
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
        if sur_trace is not None:
            sur_trace(trace)
        return ResultatAgent(sortie, controle.statut, (*traces_outils, trace))
