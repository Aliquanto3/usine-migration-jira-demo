"""Racine de composition : seul lieu qui instancie les adaptateurs et câble les étapes (AD-1).

Elle lit `config/*.yaml` et les secrets (Mode repli), calcule `version_grille` et
`version_donnees`, instancie la `SourceJournal` (avec le manifeste d'injection
`donnees/injection/manifeste_injection.json` s'il existe, pour lire le Journal aux clés Jira ;
sinon aux clés générées), charge le gabarit PowerPoint et construit le
registre des étapes de la Chaîne selon le Palier. En Palier 2, elle câble la passerelle LLM
(fournisseur injecté, cache `donnees/cache_llm.sqlite`) dans les étapes `classification` et
`explications`, et l'étape `repartition_causes` sur `domaine.causes.repartition` ; la
narration reste sautée. Un fournisseur construit depuis `config/llm.yaml` s'accompagne d'un
fournisseur par entrée de `modeles_par_tache` (modèle différent de `modele`) ; un fournisseur
injecté sert toutes les tâches. Sans pseudonymiseur injecté, elle construit le moteur de
la clé `moteur` de `config/pseudonymisation.yaml` (AD-15) sur la clé `USINE_CLE_PSEUDO` et la
table `donnees/pseudonymes.sqlite` : `PseudonymiseurPresidio` (`presidio`, défaut) ou
`PseudonymiseurHmac` sur les motifs des reconnaisseurs (`regex`) ; sans ce fichier,
`PseudonymiseurHmac` sur `MOTIFS_PAR_DEFAUT`. La passerelle reçoit le plafond de coût de
`config/llm.yaml` (s'il existe) et le tarif du registre des prix (0 € pour un modèle absent du
registre, comme une doublure). Un fournisseur construit ici depuis `config/llm.yaml` est fermé
(avec ses fournisseurs par tâche) par `Rapport.fermer`, ou dès l'échec de
`construire_rapport`. Les secrets passent par `charger_secrets` (erreur nommant la variable) ;
l'URL Jira se résout dans `url_jira` seulement.

L'étape `extraction` verse Jira dans `donnees/entrepot.duckdb` (`EtapeExtraction`) quand
`config/jira.yaml` existe, hors Mode repli, et que le secret de lecture de sa plateforme est
présent (`mode: cloud` : `JIRA_TOKEN_LECTURE`, puis `JIRA_EMAIL` exigé ; `mode: dc` :
`JIRA_DC_PAT`) ; l'adaptateur (`SourceJiraCloud` ou `SourceJiraDC`) suit `mode`. Sinon elle
reste un bouchon et le Journal est la seule source.

Quand l'extraction Jira est active et que le manifeste d'injection existe, la source est
`composite` (Story 2.6) : `instantanes` lit `SourceComposite` (Journal, puis événements Jira
de l'entrepôt postérieurs à la fin d'injection) et l'étape `extraction` persiste les
alignements détectés (`DetecteurAlignements`). L'instant d'extraction est alors figé à la
composition : repère, instant de détection et `version_donnees` le partagent, et la Chaîne
le recopie au manifeste du Passage avec le nombre d'alignements. `version_donnees` porte sur
les octets du Journal, suivis de `\n` et du manifeste d'injection s'il existe.

`instantanes` et `meteo` couvrent chaque Jour ouvré depuis `EnteteJournal.ancrage_semaines`,
aussi ancrage des semaines ; `kpi` (KPI et Tendances), chaque Jour ouvré du premier jour où un
ticket existe à la Date d'arrêté, aucun avant. `prevision` est une `EtapePrevision` sur
`prevision_du_passage` : chaque Jour ouvré, la Baseline (`domaine.prevision.baseline`) pour les
Entités rouges et les Risques d'entrée en rouge (`domaine.prevision.risque`) pour les autres,
avec les paramètres H-7 et H-8 de `ConfigChaine.prevision` (défauts du domaine si absents de
`chaine.yaml`), sur la `SerieStock` que construit `domaine.prevision.serie`. `meteo` reçoit
`ConfigChaine.decalage_comparaison` (H-19), qui dimensionne l'historique transmis au domaine.
`rendu` reçoit l'identité des données (source, versions) et
l'instant d'extraction, affichés dans l'onglet Traçabilité.

Les services de l'UI vivent dans `ui/cli.py`, l'écriture du Journal dans
`generateur.journal.ecrire_journal`.

`construire_explicateur` expose à la suite d'évaluation `evals/explication` la vraie tâche
`expliquer`, passerelle comprise, avec un cache en mémoire (jamais le cache de production) ;
`controler_citations` est ré-exporté pour qu'`evals` n'importe pas `usine.ia`.
`construire_classificateur` expose de même à `evals/classification` la vraie tâche `classer`,
sur la même passerelle d'évaluation (`_passerelle_evaluation`). `evals/agent` passe par
`construire_session_agent` (même session que l'UI, `SessionAgent` ré-exporté) sur le lecteur
de `consultation_repertoire`.

`apercu_pseudonymisation` expose à l'UI (vue côte à côte, Story 7.7) le seul `apercu` du
moteur de Pseudonymisation, sur une table en mémoire qui refuse toute écriture.
"""

import json
import secrets
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from functools import partial
from pathlib import Path
from types import MappingProxyType

import polars as pl
from pydantic import BaseModel, SecretStr

from usine.adaptateurs.composite import DetecteurAlignements, SourceComposite
from usine.adaptateurs.entrepot_duckdb import CHEMIN_ENTREPOT, EtapeExtraction
from usine.adaptateurs.jira_cloud import SourceJiraCloud
from usine.adaptateurs.jira_dc import SourceJiraDC
from usine.adaptateurs.jira_http import construire_client_lecture
from usine.adaptateurs.journal import (
    CHEMIN_MANIFESTE_INJECTION,
    SourceJournal,
    charger_manifeste,
)
from usine.adaptateurs.pseudonymisation import (
    MOTIFS_PAR_DEFAUT,
    PseudonymiseurHmac,
    TablePseudonymes,
    verifier_cle,
)
from usine.adaptateurs.stockage_sqlite import CacheLLMSqlite, TablePseudonymesSqlite
from usine.chaine.ecrivain import EcrivainPassage
from usine.chaine.etapes import (
    EtapeBouchon,
    EtapeInstantanes,
    EtapeKpi,
    EtapeMeteo,
    EtapePrevision,
    EtapeSautee,
    prevision_du_passage,
)
from usine.chaine.execution import executer_passage
from usine.chaine.verrou import verrou_exclusif
from usine.config import Secrets, charger_secrets, charger_yaml, verifier_modele_corpus
from usine.consultation.passage import ConsultationPassage
from usine.contrats.calendrier import est_jour_ouvre
from usine.contrats.config import (
    ConfigChaine,
    ConfigJira,
    ConfigLLM,
    ConfigProgramme,
    ConfigPseudonymisation,
    ConfigUsine,
    GrilleMeteo,
)
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import (
    MessageAgent,
    OutilAgent,
    ParametresAppel,
    ReponseAgentBrute,
    ReponseStructuree,
    SortieClassification,
    SortieExplication,
    Tache,
)
from usine.contrats.meteo import MeteoEntite
from usine.contrats.passage import (
    CHEMIN_CACHE_LLM,
    CHEMIN_JOURNAL,
    CHEMIN_PSEUDONYMES,
    CHEMIN_VERROU,
    REPERTOIRE_SORTIES,
    SOUS_REPERTOIRE_PASSAGES,
    DonneesPassage,
    Etape,
    ManifestePassage,
)
from usine.contrats.trace import EntreeTrace
from usine.contrats.versions import version_donnees, version_grille
from usine.domaine.causes.repartition import repartition
from usine.domaine.meteo import verifier_grille
from usine.domaine.prevision.baseline import ParametresBaseline
from usine.domaine.prevision.risque import ParametresRisque
from usine.generateur.corpus import (
    CHEMIN_CORPUS,
    MAX_JETONS_CASE,
    MODELE_GABARITS,
    VERSION_CORPUS_LLM,
    VERSION_CORPUS_PROVISOIRE,
    charger_corpus,
    ecrire_corpus,
    produire_corpus,
    prompts_corpus,
)
from usine.generateur.journal import ecrire_journal, generer
from usine.generateur.textes import corpus_provisoire
from usine.ia.agent.session import SessionAgent as SessionAgent
from usine.ia.classification import (
    PART_PLAFOND_CLASSIFICATION,
    ContexteClassification,
    EtapeClassification,
    classer,
)
from usine.ia.classification import lire_prompt as lire_prompt_classification
from usine.ia.controles import controler_citations as controler_citations
from usine.ia.etape import EtapeExplications, EtapeNarration
from usine.ia.explication import ContexteExplication, expliquer, lire_prompt
from usine.ia.passerelle import Passerelle
from usine.ia.repartition import EtapeRepartitionCauses
from usine.ports.cache_llm import CacheLLM
from usine.ports.consultation import Consultation
from usine.ports.etape import Etape as PortEtape
from usine.ports.fournisseur_llm import FournisseurLLM
from usine.ports.pseudonymiseur import Pseudonymiseur
from usine.rendu.etape import EtapeRendu

CHEMIN_GABARIT = Path("gabarits") / "rapport.pptx"
"""Gabarit neutre du PowerPoint, relatif à la racine."""

ETAPES_LLM = frozenset(
    {Etape.classification, Etape.repartition_causes, Etape.explications, Etape.narration}
)
"""Étapes de la couche LLM, sautées en Palier 1."""


@dataclass(frozen=True)
class Rapport:
    """Tout ce qu'il faut pour exécuter un Passage : configuration, registre, données."""

    configuration: ConfigUsine
    registre: Mapping[Etape, PortEtape]
    donnees: DonneesPassage
    racine_sorties: Path
    chemin_verrou: Path
    url_jira: str | None = None
    """URL du site Jira pour `url_ticket` ; `None` en Mode repli ou sans `config/jira.yaml`."""
    horodatage_extraction: datetime | None = None
    """Instant d'extraction figé à la composition (source `composite`) ; sinon `None`."""
    fermeture: Callable[[], None] | None = None
    """Fermeture des fournisseurs LLM construits par la composition ; `None` si injecté."""

    def fermer(self) -> None:
        """Ferme les fournisseurs LLM construits par la composition (aucun effet sinon)."""
        if self.fermeture is not None:
            self.fermeture()

    def fabrique_consultation(self, date_arrete: date) -> Callable[[Path], Consultation]:
        """Fabrique de la `Consultation` d'un Passage de ce rapport à la Date d'arrêté."""
        return partial(
            ConsultationPassage,
            racine_passages=self.racine_sorties / SOUS_REPERTOIRE_PASSAGES,
            url_jira=self.url_jira,
            date_arrete=date_arrete,
        )


def _octets(chemin: Path, quoi: str) -> bytes:
    try:
        return chemin.read_bytes()
    except FileNotFoundError as exc:
        raise UsineErreur(f"{chemin} : {quoi} introuvable") from exc
    except OSError as exc:
        raise UsineErreur(f"{chemin} : {quoi} illisible ({exc.strerror or exc})") from exc


def _maintenant() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class _ParametresPseudonymisation:
    """Clé et moteur de Pseudonymisation, vérifiés avant tout Passage."""

    cle: bytes
    motifs: Mapping[str, str]
    """Motifs de `PseudonymiseurHmac` (moteur `regex`)."""
    presidio: ConfigPseudonymisation | None = None
    """Configuration de `PseudonymiseurPresidio` ; `None` pour le moteur `regex`."""


def _moteur_pseudonymisation(
    repertoire_config: Path,
) -> tuple[Mapping[str, str], ConfigPseudonymisation | None]:
    """Moteur de `config/pseudonymisation.yaml` : motifs du moteur `regex`, ou configuration
    du moteur `presidio` ; sans ce fichier, `MOTIFS_PAR_DEFAUT` (moteur `regex`)."""
    chemin = repertoire_config / "pseudonymisation.yaml"
    if not chemin.exists():
        return MOTIFS_PAR_DEFAUT, None
    config = charger_yaml(chemin, ConfigPseudonymisation)
    if config.moteur == "regex":
        return _motifs_pseudonymisation(repertoire_config), None
    if not config.reconnaisseurs and not config.entites_presidio:
        raise UsineErreur(
            f"{chemin}, clés « reconnaisseurs » et « entites_presidio », valeurs vides : rien à"
            " pseudonymiser ; déclarer au moins un reconnaisseur ou une entité"
        )
    return {}, config


def _tarif_registre(version_modele: str, jetons_entree: int, jetons_sortie: int) -> Decimal:
    """Coût estimé du registre des prix ; 0 € pour un modèle absent du registre (doublures)."""
    # Import différé : le paquet `adaptateurs.llm` charge `pydantic_ai` (Palier 2 seulement).
    from usine.adaptateurs.llm import REGISTRE, cout_estime_eur

    if version_modele not in REGISTRE:
        return Decimal(0)
    return cout_estime_eur(version_modele, jetons_entree, jetons_sortie)


def _motifs_pseudonymisation(repertoire_config: Path) -> Mapping[str, str]:
    """Motifs de `config/pseudonymisation.yaml` s'il existe, sinon `MOTIFS_PAR_DEFAUT`.

    Plusieurs reconnaisseurs d'un même type de jeton sont combinés en une alternative.
    """
    chemin = repertoire_config / "pseudonymisation.yaml"
    if not chemin.exists():
        return MOTIFS_PAR_DEFAUT
    config = charger_yaml(chemin, ConfigPseudonymisation)
    if not config.reconnaisseurs:
        raise UsineErreur(
            f"{chemin}, clé « reconnaisseurs », valeur vide : aucun motif de Pseudonymisation ;"
            " déclarer au moins un reconnaisseur ou supprimer le fichier"
        )
    par_type: dict[str, list[str]] = {}
    for reconnaisseur in config.reconnaisseurs:
        par_type.setdefault(reconnaisseur.type_jeton, []).append(reconnaisseur.motif)
    return {
        type_jeton: motifs[0] if len(motifs) == 1 else "|".join(f"(?:{m})" for m in motifs)
        for type_jeton, motifs in par_type.items()
    }


def _verifier_llm(
    fournisseur: FournisseurLLM | None,
    pseudonymiseur: Pseudonymiseur | None,
    secrets_usine: Secrets,
    repertoire_config: Path,
) -> _ParametresPseudonymisation | None:
    """Palier 2 : refuse, avant tout Passage, l'absence de fournisseur LLM ou de clé.

    Sans pseudonymiseur injecté, renvoie la clé `USINE_CLE_PSEUDO` et le moteur de
    Pseudonymisation ; sinon `None`.
    """
    if fournisseur is None:
        raise UsineErreur(
            "config/chaine.yaml, clé « palier », valeur 2 : aucun fournisseur LLM injecté ;"
            " repasser en palier 1 ou fournir un fournisseur LLM"
        )
    if pseudonymiseur is not None:
        return None
    cle = secrets_usine.usine_cle_pseudo
    if cle is None or not cle.get_secret_value().strip():
        raise UsineErreur(
            "config/chaine.yaml, clé « palier », valeur 2 : variable d'environnement"
            " USINE_CLE_PSEUDO absente ou vide ; aucun appel LLM sans Pseudonymisation"
        )
    octets_cle = cle.get_secret_value().encode("utf-8")
    verifier_cle(octets_cle)
    motifs, presidio = _moteur_pseudonymisation(repertoire_config)
    return _ParametresPseudonymisation(octets_cle, motifs, presidio)


def construire_fournisseur(
    racine: Path,
    secrets_usine: Secrets | None = None,
    *,
    fournisseur: str | None = None,
    modele: str | None = None,
) -> FournisseurLLM:
    """`FournisseurLLM` choisi par `config/llm.yaml`, avec la clé de son fournisseur (H-23).

    `fournisseur: anthropic` lit `ANTHROPIC_API_KEY`, `fournisseur: mistral` lit
    `MISTRAL_API_KEY` ; un fichier absent, un fournisseur inconnu, un modèle hors du registre
    des quotas et des prix ou une clé absente lèvent une `UsineErreur`.

    `fournisseur` et `modele`, donnés ensemble, remplacent ceux de `config/llm.yaml` (outil de
    production du Corpus, Story 1.9) ; sans ce fichier, la configuration minimale suffit.
    """
    # Import différé : `pydantic_ai` et les SDK ne se chargent qu'en Palier 2 (outils sans SDK).
    from usine.adaptateurs.llm import construire_fournisseur_llm

    if (fournisseur is None) != (modele is None):
        raise UsineErreur("surcharge du fournisseur LLM : `fournisseur` et `modele` vont ensemble")
    config = _config_llm(racine, controler_corpus=fournisseur is None)
    if fournisseur is not None and modele is not None:
        surcharge = {
            "fournisseur": fournisseur,
            "modele": modele,
            "modeles_par_tache": MappingProxyType({}),
        }
        config = (
            ConfigLLM(fournisseur=fournisseur, modele=modele, plafond_cout_passage_eur=Decimal(2))
            if config is None
            else config.model_copy(update=surcharge)
        )
    if config is None:
        chemin = racine / "config" / "llm.yaml"
        raise UsineErreur(f"{chemin} : fichier absent ; aucun fournisseur LLM configuré")
    secrets_usine = secrets_usine if secrets_usine is not None else charger_secrets(racine)
    cles = {"anthropic": secrets_usine.anthropic_api_key, "mistral": secrets_usine.mistral_api_key}
    cle = cles.get(config.fournisseur)
    return construire_fournisseur_llm(config, cle.get_secret_value() if cle is not None else "")


def construire_fournisseurs_par_tache(
    racine: Path, secrets_usine: Secrets | None = None
) -> dict[Tache, FournisseurLLM]:
    """Un `FournisseurLLM` par entrée de `modeles_par_tache` de `config/llm.yaml`.

    Même fournisseur et même clé que `construire_fournisseur` ; une tâche dont le modèle est
    celui de `modele` n'a pas de fournisseur dédié. Un modèle hors du registre des quotas et des
    prix lève une `UsineErreur` dès la construction, sans appel réseau.
    """
    from usine.adaptateurs.llm import construire_fournisseur_llm

    config = _config_llm(racine)
    if config is None or not config.modeles_par_tache:
        return {}
    secrets_usine = secrets_usine if secrets_usine is not None else charger_secrets(racine)
    cles = {"anthropic": secrets_usine.anthropic_api_key, "mistral": secrets_usine.mistral_api_key}
    cle = cles.get(config.fournisseur)
    construits: dict[Tache, FournisseurLLM] = {}
    try:
        for tache, modele in config.modeles_par_tache.items():
            if modele == config.modele:
                continue
            construits[tache] = construire_fournisseur_llm(
                config.model_copy(update={"modele": modele}),
                cle.get_secret_value() if cle is not None else "",
            )
    except BaseException:
        _fermer_tous(construits.values())
        raise
    return construits


def _fermer_tous(fournisseurs: Iterable[FournisseurLLM]) -> None:
    """Ferme chaque fournisseur qui expose `fermer` (les doublures n'en ont pas toujours)."""
    for fournisseur in fournisseurs:
        fermer = getattr(fournisseur, "fermer", None)
        if fermer is not None:
            fermer()


class _CacheMemoire:
    """Cache LLM en mémoire, propre à un explicateur d'évaluation (port `CacheLLM`)."""

    def __init__(self) -> None:
        self._valeurs: dict[str, str] = {}

    def lire(self, cle: str) -> str | None:
        """Valeur enregistrée sous `cle`, ou `None`."""
        return self._valeurs.get(cle)

    def ecrire(self, cle: str, brut: str) -> None:
        """Enregistre (ou remplace) la valeur sous `cle`."""
        self._valeurs[cle] = brut


VERSION_DONNEES_EVALUATION = "evaluation-explication"
"""`version_donnees` tracée par les appels de la suite d'évaluation (cas versionnés)."""


@dataclass(frozen=True)
class Explicateur:
    """Tâche `expliquer` câblée sur une passerelle, pour la suite d'évaluation.

    Appelable `(meteo, textes, kpi, repartition) -> (SortieExplication, traces)` : une trace
    par appel (appel initial, régénération éventuelle).
    """

    passerelle: Passerelle
    contexte: ContexteExplication
    version_modele: str
    """`version_modele` du fournisseur de la tâche `explication`."""
    fermeture: Callable[[], None] | None = None

    @property
    def version_prompt(self) -> str:
        """`version_prompt` du gabarit `explication` envoyé."""
        return self.contexte.version_prompt

    def __call__(
        self,
        meteo: MeteoEntite,
        textes: pl.DataFrame,
        kpi: pl.DataFrame | None = None,
        repartition: pl.DataFrame | None = None,
    ) -> tuple[SortieExplication, tuple[EntreeTrace, ...]]:
        """Explication sourcée de `meteo` par la vraie tâche `expliquer`, et ses traces."""
        return expliquer(
            self.passerelle, meteo, textes, self.contexte, kpi=kpi, repartition=repartition
        )

    def fermer(self) -> None:
        """Ferme les fournisseurs construits depuis `config/llm.yaml` (aucun effet sinon)."""
        if self.fermeture is not None:
            self.fermeture()


@dataclass(frozen=True)
class _PasserelleEvaluation:
    """Passerelle d'une suite d'évaluation et ses fournisseurs (cache en mémoire)."""

    passerelle: Passerelle
    fournisseur: FournisseurLLM
    par_tache: Mapping[Tache, FournisseurLLM]
    fermeture: Callable[[], None] | None

    def version_modele(self, tache: Tache) -> str:
        """`version_modele` du fournisseur qui sert `tache`."""
        return self.par_tache.get(tache, self.fournisseur).version_modele


def _passerelle_evaluation(
    racine: Path,
    fournisseur: FournisseurLLM | None,
    pseudonymiseur: Pseudonymiseur | None,
) -> _PasserelleEvaluation:
    """Passerelle des suites d'évaluation `evals/explication` et `evals/classification`.

    `fournisseur=None` : mode réel, comme un Passage Palier 2 : fournisseur (et fournisseurs
    par tâche) de `config/llm.yaml` avec la clé de son fournisseur, plafond de coût de ce
    fichier et, sans pseudonymiseur injecté, moteur de Pseudonymisation sur
    `USINE_CLE_PSEUDO`. Un fournisseur injecté sert toutes les tâches, sans plafond. Le cache
    est toujours en mémoire : le cache de production n'est ni lu ni écrit.
    """
    secrets_usine: Secrets | None = None
    config_llm: ConfigLLM | None = None
    fermeture: Callable[[], None] | None = None
    par_tache: Mapping[Tache, FournisseurLLM] = {}
    if fournisseur is None:
        secrets_usine = charger_secrets(racine)
        config_llm = _config_llm(racine)
        fournisseur = construire_fournisseur(racine, secrets_usine)
        try:
            par_tache = construire_fournisseurs_par_tache(racine, secrets_usine)
        except BaseException:
            _fermer_tous([fournisseur])
            raise
        fermeture = partial(_fermer_tous, [fournisseur, *par_tache.values()])
    try:
        if pseudonymiseur is None:
            if secrets_usine is None:
                secrets_usine = charger_secrets(racine)
            parametres = _verifier_llm(fournisseur, None, secrets_usine, racine / "config")
            if parametres is None:  # pragma: no cover - renvoyé sans pseudonymiseur injecté
                raise UsineErreur("USINE_CLE_PSEUDO absente ou vide")
            pseudonymiseur = _pseudonymiseur(racine, parametres)
        cache: CacheLLM = _CacheMemoire()
        passerelle = Passerelle(
            fournisseur,
            pseudonymiseur,
            cache,
            _maintenant,
            tarif=_tarif_registre,
            plafond_cout_passage_eur=(
                None if config_llm is None else config_llm.plafond_cout_passage_eur
            ),
            fournisseurs_par_tache=par_tache,
        )
    except BaseException:
        if fermeture is not None:
            fermeture()
        raise
    return _PasserelleEvaluation(passerelle, fournisseur, par_tache, fermeture)


def construire_explicateur(
    racine: Path,
    fournisseur: FournisseurLLM | None = None,
    pseudonymiseur: Pseudonymiseur | None = None,
) -> Explicateur:
    """`Explicateur` de la suite d'évaluation `evals/explication`.

    Passerelle de `_passerelle_evaluation` : mode réel sans `fournisseur` (configuration,
    secrets, plafond de coût), doublures injectées sinon ; cache toujours en mémoire.
    """
    evaluation = _passerelle_evaluation(racine, fournisseur, pseudonymiseur)
    contexte = ContexteExplication(
        passage_id=f"{_maintenant():%Y%m%dT%H%M%SZ}-{_suffixe()}",
        version_donnees=VERSION_DONNEES_EVALUATION,
        gabarit=lire_prompt(),
    )
    version = evaluation.version_modele(Tache.explication)
    return Explicateur(evaluation.passerelle, contexte, version, evaluation.fermeture)


VERSION_DONNEES_CLASSIFICATION = "evaluation-classification"
"""`version_donnees` (et `version_grille`, tracée seulement) des appels de la suite
d'évaluation de la classification."""


@dataclass(frozen=True)
class Classificateur:
    """Tâche `classer` câblée sur une passerelle, pour la suite d'évaluation.

    Appelable `(textes) -> (sorties, traces)` : une `SortieClassification` par Anomalie
    classée (une Anomalie refusée par le plafond de coût est absente) et une trace par appel.
    """

    passerelle: Passerelle
    contexte: ContexteClassification
    version_modele: str
    """`version_modele` du fournisseur de la tâche `classification`."""
    fermeture: Callable[[], None] | None = None

    @property
    def version_prompt(self) -> str:
        """`version_prompt` du gabarit `classification` envoyé."""
        return self.contexte.version_prompt

    def __call__(
        self, textes: pl.DataFrame, date_arrete: date | None = None
    ) -> tuple[tuple[SortieClassification, ...], tuple[EntreeTrace, ...]]:
        """Cause racine proposée de chaque Anomalie de `textes` par la vraie tâche `classer`.

        `date_arrete` n'est que tracée (ni prompt ni clé de cache) ; défaut : aujourd'hui.
        """
        jour = date_arrete if date_arrete is not None else _maintenant().date()
        return classer(self.passerelle, textes, jour, self.contexte)

    def fermer(self) -> None:
        """Ferme les fournisseurs construits depuis `config/llm.yaml` (aucun effet sinon)."""
        if self.fermeture is not None:
            self.fermeture()


def construire_classificateur(
    racine: Path,
    fournisseur: FournisseurLLM | None = None,
    pseudonymiseur: Pseudonymiseur | None = None,
) -> Classificateur:
    """`Classificateur` de la suite d'évaluation `evals/classification`.

    Même passerelle que `construire_explicateur` (`_passerelle_evaluation`) ; la version de
    modèle publiée est celle du fournisseur de la tâche `classification`. Aucune part de
    plafond propre : seul le plafond de coût du Passage de `config/llm.yaml` s'applique.
    """
    evaluation = _passerelle_evaluation(racine, fournisseur, pseudonymiseur)
    contexte = ContexteClassification(
        passage_id=f"{_maintenant():%Y%m%dT%H%M%SZ}-{_suffixe()}",
        version_donnees=VERSION_DONNEES_CLASSIFICATION,
        version_grille=VERSION_DONNEES_CLASSIFICATION,
        gabarit=lire_prompt_classification(),
    )
    version = evaluation.version_modele(Tache.classification)
    return Classificateur(evaluation.passerelle, contexte, version, evaluation.fermeture)


def consultation_repertoire(repertoire: Path) -> Consultation:
    """`Consultation` du Passage de `repertoire`, sans URL Jira (suite `evals/agent`).

    `evals` ne peut pas importer `usine.consultation` : la composition construit le lecteur.
    """
    return ConsultationPassage(repertoire, racine_passages=repertoire, url_jira=None)


def construire_session_agent(
    racine: Path,
    consultation: Consultation,
    fournisseur: FournisseurLLM | None = None,
    pseudonymiseur: Pseudonymiseur | None = None,
) -> SessionAgent:
    """`SessionAgent` sur le Passage de `consultation` (FR-39, FR-40).

    Passerelle de `_passerelle_evaluation` : mode réel sans `fournisseur` (configuration,
    secrets, plafond de coût), doublures injectées sinon ; cache en mémoire. Les traces vont
    dans `racine/sorties/agent/<AAAA-MM-JJ>/<session>.jsonl`.
    """
    evaluation = _passerelle_evaluation(racine, fournisseur, pseudonymiseur)
    try:
        return SessionAgent(
            evaluation.passerelle,
            consultation,
            racine,
            _maintenant,
            f"{_maintenant():%Y%m%dT%H%M%SZ}-{_suffixe()}",
            evaluation.fermeture,
        )
    except BaseException:
        if evaluation.fermeture is not None:
            evaluation.fermeture()
        raise


def _config_llm(racine: Path, *, controler_corpus: bool = True) -> ConfigLLM | None:
    """`config/llm.yaml` validé, ou `None` s'il n'existe pas.

    Garde-fou AD-19 : refusé si son modèle de classification est le `modele_corpus` du Corpus
    versionné (`donnees/corpus/textes.json`) ; Corpus absent ou provisoire, accepté.
    `controler_corpus=False` (production d'un nouveau Corpus) saute ce contrôle : un Corpus
    versionné fautif ne doit pas empêcher de le régénérer.
    """
    chemin = racine / "config" / "llm.yaml"
    if not chemin.exists():
        return None
    config = charger_yaml(chemin, ConfigLLM)
    if not controler_corpus:
        return config
    modele_corpus = _modele_corpus(racine / CHEMIN_CORPUS)
    if modele_corpus is not None and modele_corpus != MODELE_GABARITS:
        try:
            verifier_modele_corpus(config, modele_corpus)
        except UsineErreur as exc:
            raise UsineErreur(f"{chemin} et {racine / CHEMIN_CORPUS} : {exc}") from exc
    return config


def _modele_corpus(chemin: Path) -> str | None:
    """Seule clé `modele_corpus` du Corpus de `chemin`, ou `None` s'il est absent."""
    if not chemin.exists():
        return None
    try:
        donnees = json.loads(chemin.read_bytes())
    except (OSError, ValueError) as exc:
        raise UsineErreur(f"{chemin} : Corpus de textes illisible ({exc})") from exc
    modele = donnees.get("modele_corpus") if isinstance(donnees, dict) else None
    if not isinstance(modele, str):
        raise UsineErreur(f"{chemin} : clé « modele_corpus » absente ou non textuelle")
    return modele


def _config_jira(racine: Path) -> ConfigJira | None:
    """`config/jira.yaml` validé, ou `None` s'il n'existe pas."""
    chemin = racine / "config" / "jira.yaml"
    return charger_yaml(chemin, ConfigJira) if chemin.exists() else None


def url_jira(racine: Path) -> str | None:
    """URL du site Jira pour `url_ticket` (AD-11), seule résolution du dépôt.

    `None` en Mode repli (`USINE_MODE_REPLI`, environnement ou `racine/.env`) ou sans
    `config/jira.yaml`.
    """
    if charger_secrets(racine).usine_mode_repli:
        return None
    return _url_jira(False, _config_jira(racine))


def _url_jira(mode_repli: bool, jira: ConfigJira | None) -> str | None:
    """URL Jira déduite de valeurs déjà chargées : `None` en Mode repli ou sans configuration."""
    return None if mode_repli or jira is None else jira.url_site


def _secret_present(valeur: SecretStr | None) -> bool:
    return valeur is not None and bool(valeur.get_secret_value().strip())


def _jira_actif(jira: ConfigJira | None, secrets_usine: Secrets) -> ConfigJira | None:
    """`jira` si l'extraction Jira est active, sinon `None`.

    Inactive sans `config/jira.yaml`, en Mode repli (pas d'extraction automatique) ou sans le
    secret de lecture de la plateforme.
    """
    if jira is None or secrets_usine.usine_mode_repli:
        return None
    secret = secrets_usine.jira_token_lecture if jira.mode == "cloud" else secrets_usine.jira_dc_pat
    return jira if _secret_present(secret) else None


def _figee(instant: datetime) -> Callable[[], datetime]:
    """Horloge qui rend toujours `instant`."""
    return lambda: instant


def _etape_extraction(
    racine: Path,
    jira: ConfigJira,
    secrets_usine: Secrets,
    horloge: Callable[[], datetime],
    composite: tuple[SourceJournal, datetime] | None = None,
) -> EtapeExtraction:
    """Étape `extraction` : Jira (`mode` de `config/jira.yaml`) vers l'entrepôt.

    En Cloud, `JIRA_TOKEN_LECTURE` sans `JIRA_EMAIL` lève une `UsineErreur` qui nomme
    `JIRA_EMAIL`. Le client Jira est fermé après l'étape. Avec `composite` (Journal lu aux
    clés Jira, instant d'extraction figé), le repère est cet instant et l'étape persiste les
    alignements détectés à cet instant ; la source Jira garde `horloge` (fenêtre `updated`).
    """
    client = construire_client_lecture(
        jira,
        email=secrets_usine.jira_email,
        jeton_lecture=secrets_usine.jira_token_lecture,
        pat=secrets_usine.jira_dc_pat,
    )
    source = (
        SourceJiraCloud(client, jira, horloge)
        if jira.mode == "cloud"
        else SourceJiraDC(client, jira, horloge)
    )
    marge = timedelta(minutes=jira.marge_extraction_minutes)
    if composite is None:
        return EtapeExtraction(source, racine / CHEMIN_ENTREPOT, marge, horloge, client.fermer)
    journal, instant = composite
    return EtapeExtraction(
        source,
        racine / CHEMIN_ENTREPOT,
        marge,
        _figee(instant),
        client.fermer,
        aligner=DetecteurAlignements(journal),
    )


def construire_rapport(
    racine: Path,
    fournisseur: FournisseurLLM | None = None,
    pseudonymiseur: Pseudonymiseur | None = None,
    horloge: Callable[[], datetime] = _maintenant,
) -> Rapport:
    """Charge la configuration et le Journal de `racine`, puis construit le registre.

    En Palier 2, `fournisseur` est obligatoire ; sans `pseudonymiseur`, `PseudonymiseurHmac`
    est construit et exige `USINE_CLE_PSEUDO`. Toute absence lève une `UsineErreur` avant tout
    Passage. `horloge` date les traces LLM, les traces de Prévision et l'extraction Jira
    (repère, restriction `updated`). En source `composite`, l'instant d'extraction est lu une
    seule fois, ici : repère, détection des alignements, `version_donnees` et l'onglet
    Traçabilité du Rapport le partagent.

    Un fournisseur construit ici depuis `config/llm.yaml` est fermé si la construction échoue
    ensuite ; sinon `Rapport.fermer` le ferme.
    """
    chaine = charger_yaml(racine / "config" / "chaine.yaml", ConfigChaine)
    secrets_usine = charger_secrets(racine)
    config_llm = _config_llm(racine)
    fermeture: Callable[[], None] | None = None
    par_tache: dict[Tache, FournisseurLLM] = {}
    if chaine.palier == 2 and fournisseur is None and config_llm is not None:
        fournisseur = construire_fournisseur(racine, secrets_usine)
        construits: list[FournisseurLLM] = [fournisseur]
        fermeture = partial(_fermer_tous, construits)
        try:
            par_tache = construire_fournisseurs_par_tache(racine, secrets_usine)
        except BaseException:
            fermeture()
            raise
        construits.extend(par_tache.values())
    try:
        return _assembler_rapport(
            racine,
            chaine,
            config_llm,
            secrets_usine,
            fournisseur,
            pseudonymiseur,
            horloge,
            fermeture,
            par_tache,
        )
    except BaseException:
        if fermeture is not None:
            fermeture()
        raise


def _assembler_rapport(
    racine: Path,
    chaine: ConfigChaine,
    config_llm: ConfigLLM | None,
    secrets_usine: Secrets,
    fournisseur: FournisseurLLM | None,
    pseudonymiseur: Pseudonymiseur | None,
    horloge: Callable[[], datetime],
    fermeture: Callable[[], None] | None,
    fournisseurs_par_tache: Mapping[Tache, FournisseurLLM],
) -> Rapport:
    """Suite de `construire_rapport`, une fois le fournisseur LLM connu."""
    repertoire_config = racine / "config"
    pseudonymisation = (
        _verifier_llm(fournisseur, pseudonymiseur, secrets_usine, repertoire_config)
        if chaine.palier == 2
        else None
    )
    programme = charger_yaml(repertoire_config / "programme.yaml", ConfigProgramme)
    chemin_grille = repertoire_config / "grille_meteo.yaml"
    grille = verifier_grille(charger_yaml(chemin_grille, GrilleMeteo), str(chemin_grille))
    jira = _config_jira(racine)
    configuration = ConfigUsine(
        chaine=chaine, programme=programme, grille_meteo=grille, jira=jira, llm=config_llm
    )
    gabarit = _octets(racine / CHEMIN_GABARIT, "gabarit PowerPoint")
    empreinte_grille = version_grille(_octets(chemin_grille, "Grille de météo"))

    chemin_journal = racine / CHEMIN_JOURNAL
    chemin_manifeste = racine / CHEMIN_MANIFESTE_INJECTION
    manifeste = charger_manifeste(chemin_manifeste) if chemin_manifeste.exists() else None
    source = SourceJournal(chemin_journal, manifeste)
    jira_actif = _jira_actif(jira, secrets_usine)
    # Source composite : extraction Jira active et Journal lu aux clés Jira.
    horodatage_extraction = horloge() if jira_actif is not None and manifeste is not None else None
    octets_donnees = _octets(chemin_journal, "Journal")
    if manifeste is not None:
        octets_donnees += b"\n" + _octets(chemin_manifeste, "manifeste d'injection")
    empreinte_donnees = version_donnees(octets_donnees, horodatage_extraction)
    premier_jour = source.entete.ancrage_semaines
    entites = [entite.code for entite in programme.entites]
    donnees = DonneesPassage(
        "journal" if horodatage_extraction is None else "composite",
        empreinte_grille,
        empreinte_donnees,
    )

    registre: dict[Etape, PortEtape] = {
        Etape.extraction: EtapeBouchon(),
        Etape.instantanes: EtapeInstantanes(source, premier_jour),
        Etape.kpi: EtapeKpi(entites, premier_jour),
        Etape.meteo: EtapeMeteo(
            grille,
            empreinte_grille,
            entites,
            premier_jour,
            programme,
            decalage=chaine.decalage_comparaison,
        ),
        Etape.prevision: EtapePrevision(
            prevision_du_passage(
                grille,
                entites,
                premier_jour,
                baseline=ParametresBaseline(**chaine.prevision.baseline.model_dump()),
                risque=ParametresRisque(**chaine.prevision.risque.model_dump()),
            ),
            empreinte_donnees,
            horloge,
        ),
        Etape.rendu: EtapeRendu(gabarit, donnees, horodatage_extraction),
    }
    registre.update({etape: EtapeSautee() for etape in ETAPES_LLM})
    if chaine.palier == 2:
        if fournisseur is None:  # pragma: no cover - vérifié par `_verifier_llm`
            raise UsineErreur("Palier 2 sans fournisseur LLM")
        if pseudonymiseur is None:
            if pseudonymisation is None:  # pragma: no cover - vérifié par `_verifier_llm`
                raise UsineErreur("Palier 2 sans USINE_CLE_PSEUDO")
            pseudonymiseur = _pseudonymiseur(racine, pseudonymisation)
        passerelle = Passerelle(
            fournisseur,
            pseudonymiseur,
            CacheLLMSqlite(racine / CHEMIN_CACHE_LLM),
            horloge,
            tarif=_tarif_registre,
            plafond_cout_passage_eur=(
                None if config_llm is None else config_llm.plafond_cout_passage_eur
            ),
            fournisseurs_par_tache=fournisseurs_par_tache,
        )
        plafond = None if config_llm is None else config_llm.plafond_cout_passage_eur
        registre[Etape.classification] = EtapeClassification(
            passerelle,
            empreinte_donnees,
            empreinte_grille,
            plafond_eur=None if plafond is None else plafond * PART_PLAFOND_CLASSIFICATION,
        )
        registre[Etape.repartition_causes] = EtapeRepartitionCauses(repartition)
        registre[Etape.explications] = EtapeExplications(passerelle, empreinte_donnees)
        registre[Etape.narration] = EtapeNarration(passerelle, empreinte_donnees)
    # En dernier : le client Jira n'est ouvert qu'une fois tout le reste validé.
    if jira_actif is not None:
        composite = None if horodatage_extraction is None else (source, horodatage_extraction)
        extraction = _etape_extraction(racine, jira_actif, secrets_usine, horloge, composite)
        registre[Etape.extraction] = extraction
        if composite is not None:
            registre[Etape.instantanes] = EtapeInstantanes(
                SourceComposite(source, extraction.evenements_extraits), premier_jour
            )
    return Rapport(
        configuration=configuration,
        registre=MappingProxyType({etape: registre[etape] for etape in Etape}),
        donnees=donnees,
        racine_sorties=racine / REPERTOIRE_SORTIES,
        chemin_verrou=racine / CHEMIN_VERROU,
        url_jira=_url_jira(secrets_usine.usine_mode_repli, jira),
        horodatage_extraction=horodatage_extraction,
        fermeture=fermeture,
    )


def _pseudonymiseur(racine: Path, parametres: _ParametresPseudonymisation) -> Pseudonymiseur:
    """Moteur de Pseudonymisation de `config/pseudonymisation.yaml` (AD-15)."""
    return _moteur_sur_table(parametres, TablePseudonymesSqlite(racine / CHEMIN_PSEUDONYMES))


def _moteur_sur_table(
    parametres: _ParametresPseudonymisation, table: TablePseudonymes
) -> Pseudonymiseur:
    """`PseudonymiseurHmac` ou `PseudonymiseurPresidio` sur la table de correspondance donnée."""
    if parametres.presidio is None:
        return PseudonymiseurHmac(parametres.cle, parametres.motifs, table)
    # Import différé : Presidio et spaCy ne se chargent que pour ce moteur.
    from usine.adaptateurs.presidio import PseudonymiseurPresidio

    return PseudonymiseurPresidio(parametres.cle, parametres.presidio, table)


class _TableApercu:
    """Table de correspondance vide et en lecture seule : l'aperçu n'écrit rien (FR-31)."""

    def enregistrer(self, correspondances: Mapping[str, str]) -> None:
        """Refuse toute écriture : l'aperçu ne doit jamais enregistrer une correspondance."""
        raise UsineErreur(
            "Aperçu de la Pseudonymisation : table de correspondance en lecture seule"
        )

    def lire(self, jetons: Iterable[str]) -> dict[str, str]:
        """Aucun jeton connu."""
        return {}


def apercu_pseudonymisation(racine: Path) -> Callable[[str], str]:
    """`Pseudonymiseur.apercu` du moteur de `config/pseudonymisation.yaml` (AD-15, FR-31).

    Seule porte de l'UI vers la Pseudonymisation : elle ne voit que l'aperçu. Local, sans
    fournisseur LLM ; la table est en mémoire et refuse toute écriture, si bien que
    `donnees/pseudonymes.sqlite` n'est ni lu ni créé. La clé `USINE_CLE_PSEUDO` vient de
    `charger_secrets` ; absente, vide ou trop courte, une `UsineErreur` nomme la variable.
    """
    cle = charger_secrets(racine).usine_cle_pseudo
    if cle is None or not cle.get_secret_value().strip():
        raise UsineErreur(
            "Variable d'environnement USINE_CLE_PSEUDO absente ou vide : aperçu de la"
            " Pseudonymisation impossible"
        )
    octets_cle = cle.get_secret_value().encode("utf-8")
    verifier_cle(octets_cle)
    motifs, presidio = _moteur_pseudonymisation(racine / "config")
    parametres = _ParametresPseudonymisation(octets_cle, motifs, presidio)
    return _moteur_sur_table(parametres, _TableApercu()).apercu


def _suffixe() -> str:
    return secrets.token_hex(3)


@dataclass(frozen=True)
class PassageLance:
    """Résultat de `lancer_rapport` : manifeste et répertoire publié."""

    manifeste: ManifestePassage
    repertoire: Path


def verifier_date_arrete(jour: date) -> date:
    """Renvoie `jour` s'il est un Jour ouvré ; sinon lève une `UsineErreur` qui le nomme."""
    if not est_jour_ouvre(jour):
        raise UsineErreur(
            f"Date d'arrêté {jour.isoformat()} : ce n'est pas un Jour ouvré (lundi à vendredi)"
        )
    return jour


def lancer_rapport(
    racine: Path,
    date_arrete: date,
    horloge: Callable[[], datetime] = _maintenant,
    alea: Callable[[], str] = _suffixe,
    fournisseur: FournisseurLLM | None = None,
    pseudonymiseur: Pseudonymiseur | None = None,
) -> PassageLance:
    """Prend le verrou, construit le rapport et exécute un Passage ; verrou toujours rendu.

    Le manifeste du Passage reçoit l'instant d'extraction du rapport et le nombre
    d'alignements persistés par l'étape `extraction`. Le client Jira et le fournisseur LLM
    construit par la composition sont fermés, que le Passage réussisse ou échoue.
    """
    verifier_date_arrete(date_arrete)
    with verrou_exclusif(racine / CHEMIN_VERROU):
        rapport = construire_rapport(racine, fournisseur, pseudonymiseur, horloge)
        extraction = rapport.registre[Etape.extraction]
        try:
            ecrivain = EcrivainPassage(rapport.racine_sorties, horloge)
            manifeste = executer_passage(
                rapport.registre,
                rapport.configuration,
                date_arrete,
                ecrivain,
                rapport.fabrique_consultation(date_arrete),
                horloge,
                alea,
                rapport.donnees,
                horodatage_extraction=rapport.horodatage_extraction,
                nb_alignements=(
                    extraction.nb_alignements if isinstance(extraction, EtapeExtraction) else None
                ),
            )
        finally:
            # Client Jira fermé même si le Passage échoue avant l'étape `extraction`.
            try:
                if isinstance(extraction, EtapeExtraction):
                    extraction.fermer()
            finally:
                rapport.fermer()
    repertoire = ecrivain.repertoire_publie
    if repertoire is None:  # pragma: no cover - executer_passage publie ou lève
        raise UsineErreur(f"Passage {manifeste.passage_id} non publié")
    return PassageLance(manifeste, repertoire)


_RACINE_DEPOT = Path(__file__).resolve().parents[2]
"""Racine du dépôt quand le paquet s'exécute depuis les sources."""


def generer_journal(
    programme: ConfigProgramme, graine: int, date_generation: date, racine: Path
) -> Path:
    """Génère le Journal de `programme` sous `racine/donnees/` et renvoie son chemin.

    Délègue à `generateur.journal.ecrire_journal` (Journal et vérité terrain) ; sert à
    `outils/`, qui ne peut pas importer `generateur` (NFR-2). Les textes viennent du Corpus
    versionné du dépôt (`donnees/corpus/textes.json`, Story 1.9), comme `usine generer` ; à
    défaut de ce fichier (paquet installé hors dépôt), du Corpus provisoire en mémoire.
    """
    chemin_corpus = _RACINE_DEPOT / CHEMIN_CORPUS
    corpus = charger_corpus(chemin_corpus) if chemin_corpus.is_file() else None
    generation = generer(programme, graine, date_generation, corpus=corpus)
    return ecrire_journal(generation, racine / CHEMIN_JOURNAL.parent)


def generer_corpus(
    fournisseur: FournisseurLLM | None,
    domaines: Sequence[str],
    chemin: Path,
    *,
    version_corpus: str | None = None,
) -> Path:
    """Écrit le Corpus de textes des `domaines` à `chemin` et renvoie ce chemin (Story 1.2).

    Sans fournisseur : Corpus provisoire par gabarits (`gabarits-provisoires`). Avec : Corpus
    produit par `FournisseurLLM.generer_structure` seulement (AD-24). Délègue à
    `generateur.corpus`, seul propriétaire du format ; sert à `outils/`, qui ne peut pas
    importer `generateur`.
    """
    if fournisseur is None:
        corpus = corpus_provisoire(
            domaines, version_corpus=version_corpus or VERSION_CORPUS_PROVISOIRE
        )
    else:
        corpus = produire_corpus(
            fournisseur, domaines, version_corpus=version_corpus or VERSION_CORPUS_LLM
        )
    return ecrire_corpus(corpus, chemin)


JETONS_SCHEMA_CORPUS = 500
"""Jetons d'entrée ajoutés à chaque prompt du Corpus pour le schéma de sortie (estimation)."""


@dataclass(frozen=True)
class BilanCorpus:
    """Bilan d'une production du Corpus par LLM : jetons réels et coût estimé réel."""

    chemin: Path
    modele_corpus: str
    appels: int
    jetons_entree: int
    jetons_sortie: int
    cout_eur: Decimal
    """Coût estimé d'après le registre des prix (0 € pour un modèle hors registre)."""


def estimer_corpus(version_modele: str, domaines: Sequence[str]) -> tuple[int, Decimal]:
    """Nombre d'appels et coût estimé majoré, en euros, du Corpus des `domaines` (Story 1.9).

    Majoration : jetons d'entrée ≈ `len(prompt) / 3 + JETONS_SCHEMA_CORPUS`, jetons de sortie
    = `MAX_JETONS_CASE` par appel. Aucun appel ; un modèle hors du registre des prix lève une
    `UsineErreur` qui liste les modèles connus.
    """
    # Import différé : le paquet `adaptateurs.llm` charge `pydantic_ai`.
    from usine.adaptateurs.llm import cout_estime_eur

    prompts = prompts_corpus(domaines)
    entree = sum(-(-len(prompt) // 3) + JETONS_SCHEMA_CORPUS for prompt in prompts)
    sortie = MAX_JETONS_CASE * len(prompts)
    return len(prompts), cout_estime_eur(version_modele, entree, sortie)


def verifier_modele_corpus_candidat(racine: Path, version_modele: str) -> None:
    """Garde-fou AD-19 avant production : `version_modele` doit différer du modèle de
    classification de `racine/config/llm.yaml` (fichier absent : accepté)."""
    config = _config_llm(racine, controler_corpus=False)
    if config is None:
        return
    try:
        verifier_modele_corpus(config, version_modele)
    except UsineErreur as exc:
        raise UsineErreur(f"{racine / 'config' / 'llm.yaml'} : {exc}") from exc


class _FournisseurCompteur:
    """Enveloppe d'un `FournisseurLLM` qui compte les appels et les jetons réels."""

    def __init__(self, fournisseur: FournisseurLLM) -> None:
        self._fournisseur = fournisseur
        self.appels = 0
        self.jetons_entree = 0
        self.jetons_sortie = 0

    @property
    def version_modele(self) -> str:
        return self._fournisseur.version_modele

    def generer_structure[T: BaseModel](
        self, prompt: str, schema: type[T], parametres: ParametresAppel
    ) -> ReponseStructuree[T]:
        reponse = self._fournisseur.generer_structure(prompt, schema, parametres)
        self.appels += 1
        self.jetons_entree += reponse.jetons_entree
        self.jetons_sortie += reponse.jetons_sortie
        return reponse

    def executer_agent(
        self,
        messages: Sequence[MessageAgent],
        outils: Sequence[OutilAgent],
        parametres: ParametresAppel,
    ) -> ReponseAgentBrute:
        reponse = self._fournisseur.executer_agent(messages, outils, parametres)
        self.appels += 1
        self.jetons_entree += reponse.jetons_entree
        self.jetons_sortie += reponse.jetons_sortie
        return reponse


def generer_corpus_llm(
    fournisseur: FournisseurLLM,
    domaines: Sequence[str],
    chemin: Path,
    *,
    version_corpus: str | None = None,
) -> BilanCorpus:
    """Écrit le Corpus produit par `fournisseur` à `chemin` et renvoie son bilan (Story 1.9).

    Même production que `generer_corpus` ; compte en plus les jetons réels et en déduit le coût
    estimé réel d'après le registre des prix.
    """
    compteur = _FournisseurCompteur(fournisseur)
    try:
        ecrit = generer_corpus(compteur, domaines, chemin, version_corpus=version_corpus)
    except UsineErreur as exc:
        raise UsineErreur(
            f"{exc} ; déjà consommés avant l'échec : {compteur.appels} appels,"
            f" {compteur.jetons_entree} jetons d'entrée, {compteur.jetons_sortie} de sortie"
        ) from exc
    cout = _tarif_registre(
        fournisseur.version_modele, compteur.jetons_entree, compteur.jetons_sortie
    )
    return BilanCorpus(
        ecrit,
        fournisseur.version_modele,
        compteur.appels,
        compteur.jetons_entree,
        compteur.jetons_sortie,
        cout,
    )
