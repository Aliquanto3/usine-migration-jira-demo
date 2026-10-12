"""Modèles de configuration validant les fichiers `config/*.yaml` (AD-19).

Amorce de la Story 0.1, complétée par la Story 0.2. Contrats 1.1.0 : Scénarios de démo de
`ConfigProgramme`, paramètres de Prévision et décalage de comparaison de `ConfigChaine`, tous
optionnels (un YAML v1.0 se valide toujours).
"""

import re
from collections.abc import Mapping
from decimal import Decimal
from fractions import Fraction
from types import MappingProxyType
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from usine.contrats.llm import MOTIF_TYPE_JETON, Tache
from usine.contrats.meteo import CodeIndicateur, Couleur, Operateur
from usine.contrats.modele import MappingFige
from usine.contrats.tickets import (
    DOMAINES_CANONIQUES,
    Champ,
    Phase,
    StatutCertification,
    TypeTicket,
)


def _entier_exact(valeur: object) -> object:
    """Refuse tout ce qui n'est pas un `int` (ni `bool`, ni `float`).

    `strict=True` ne suffit pas pour un `Literal[1, 2]` : Pydantic y accepte `True` et `2.0`,
    égaux à 1 et 2.
    """
    if type(valeur) is not int:
        raise ValueError(f"entier attendu, pas {type(valeur).__name__}")
    return valeur


EntierPositif = Annotated[int, BeforeValidator(_entier_exact), Field(ge=1)]
"""Entier ≥ 1, ni `bool` ni `float` (paramètres en Jours ouvrés de la Chaîne)."""


class ConfigBaseline(BaseModel):
    """Paramètres H-7 de la Baseline (FR-20), en Jours ouvrés (contrats 1.1.0).

    Mêmes champs et mêmes défauts que `domaine.prevision.baseline.ParametresBaseline`, que la
    composition construira à partir d'eux.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    fenetre_velocite: EntierPositif = 10
    """Jours ouvrés de la vélocité nette."""
    horizon: EntierPositif = 10
    """Horizon de la Prévision de sortie du rouge."""
    fenetre_fourchette: EntierPositif = 5
    """Jours ouvrés des vélocités glissantes de la fourchette."""
    profondeur_fourchette: EntierPositif = 20
    """Jours ouvrés d'historique parcourus pour la fourchette."""


class ConfigRisque(BaseModel):
    """Paramètres H-8 du Risque d'entrée en rouge (FR-21), en Jours ouvrés (contrats 1.1.0).

    Mêmes champs et mêmes défauts que `domaine.prevision.risque.ParametresRisque`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    fenetre: EntierPositif = 10
    """Jours ouvrés de la tendance projetée."""
    horizon: EntierPositif = 5
    """Horizon de projection (« la semaine prochaine »)."""


class ConfigPrevision(BaseModel):
    """Paramètres des Prévisions de la Chaîne (contrats 1.1.0)."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    baseline: ConfigBaseline = Field(default_factory=ConfigBaseline)
    """Paramètres de la Baseline (H-7)."""
    risque: ConfigRisque = Field(default_factory=ConfigRisque)
    """Paramètres du Risque d'entrée en rouge (H-8)."""


class ConfigChaine(BaseModel):
    """Configuration de la Chaîne de reporting (`config/chaine.yaml`).

    `prevision` et `decalage_comparaison` (contrats 1.1.0) sont optionnels : un `chaine.yaml`
    v1.0 (`palier` seul) prend les défauts H-7, H-8 et H-19.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    palier: Annotated[Literal[1, 2], BeforeValidator(_entier_exact)]
    prevision: ConfigPrevision = Field(default_factory=ConfigPrevision)
    """Paramètres de la Baseline et du Risque d'entrée en rouge (H-7, H-8)."""
    decalage_comparaison: EntierPositif = 5
    """Décalage en Jours ouvrés de la comparaison de Météo et d'IND-8 (J-5, H-19)."""


class _ModeleConfig(BaseModel):
    """Base des modèles de configuration : gelés, clés inconnues refusées.

    Pas de `strict=True` : les dates et décimaux arrivent du YAML sous forme de texte.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


# --- Programme (`config/programme.yaml`, FR-1) ---


class PeriodePhase(_ModeleConfig):
    """Phase d'une Vague, en semaines du Programme (1 = semaine de l'ancrage)."""

    phase: Phase
    semaine_debut: int = Field(ge=1)
    semaine_fin: int = Field(ge=1)

    @model_validator(mode="after")
    def _ordre(self) -> Self:
        if self.semaine_fin < self.semaine_debut:
            raise ValueError("semaine de fin antérieure à la semaine de début")
        return self


class VagueProgramme(_ModeleConfig):
    """Vague de migration et son calendrier de Phases."""

    code: str = Field(min_length=1)
    libelle: str = Field(min_length=1)
    phases: tuple[PeriodePhase, ...]


class EntiteProgramme(_ModeleConfig):
    """Entité pilotée ; elle appartient à une seule Vague."""

    code: str = Field(pattern=r"^ENT-[A-Z0-9]+$")
    libelle: str = Field(min_length=1)
    vague: str = Field(min_length=1)


class VolumetrieProgramme(_ModeleConfig):
    """Volumétrie cible du générateur."""

    anomalies_min: int = Field(ge=0)
    anomalies_max: int = Field(ge=0)
    entrees_semaine_min: int = Field(ge=0)
    entrees_semaine_max: int = Field(ge=0)

    @model_validator(mode="after")
    def _bornes(self) -> Self:
        if self.anomalies_max < self.anomalies_min:
            raise ValueError("anomalies_max inférieur à anomalies_min")
        if self.entrees_semaine_max < self.entrees_semaine_min:
            raise ValueError("entrees_semaine_max inférieur à entrees_semaine_min")
        return self


SemaineScenario = Annotated[int, Field(strict=True, ge=1)]
"""Semaine du Programme d'un Scénario (1 = semaine de l'ancrage)."""
NombreScenario = Annotated[int, Field(strict=True, ge=0)]
"""Nombre entier ≥ 0 d'un Scénario."""
PoidsScenario = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
"""Poids d'une Entité dans le tirage des créations (Entité normale : 1)."""
TauxScenario = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
"""Part ou taux dans [0, 1]."""
DureeBloquantes = Annotated[int, Field(strict=True, ge=4, le=10)]
"""Jours ouvrés entre la création et la fermeture d'une bloquante scriptée : au moins 4 (ses
quatre transitions sur des Jours ouvrés distincts), au plus 10 (IND-2 ≤ 10 JO)."""


class ConfigScenarioSortie(_ModeleConfig):
    """Scénario A, « sortie de crise » (FR-3), miroir de `generateur.scenarios.ScenarioSortie`.

    Tous les champs sont requis : les valeurs de la démo vivent dans `config/programme.yaml`.
    Les bloquantes de A sont scriptées (contrats 1.2) : `bloquantes_bascule` le premier Jour
    ouvré de `semaine_vague`, puis `bloquantes_par_semaine` (la dernière valeur se répète),
    chacune fermée `duree_bloquantes` Jours ouvrés après sa création.
    """

    entite: str = Field(pattern=r"^ENT-[A-Z0-9]+$")
    semaine_vague: SemaineScenario
    bloquantes_bascule: NombreScenario
    bloquantes_par_semaine: tuple[NombreScenario, ...] = Field(min_length=1)
    duree_bloquantes: DureeBloquantes
    poids_vague: PoidsScenario
    poids_decrue: PoidsScenario
    statut_certification: StatutCertification
    semaine_certification: SemaineScenario


class ConfigScenarioEnlisement(_ModeleConfig):
    """Scénario B, « enlisement » (FR-3), miroir de `generateur.scenarios.ScenarioEnlisement`.

    Les bloquantes de B sont scriptées (contrats 1.2), comme celles de A : aucune bloquante
    n'est tirée, `part_majeures` porte seule la gravité des créations enlisées.
    """

    entite: str = Field(pattern=r"^ENT-[A-Z0-9]+$")
    semaine_debut: SemaineScenario
    bloquantes_bascule: NombreScenario
    bloquantes_par_semaine: tuple[NombreScenario, ...] = Field(min_length=1)
    duree_bloquantes: DureeBloquantes
    poids: PoidsScenario
    part_majeures: TauxScenario
    statut_certification: StatutCertification
    semaine_certification: SemaineScenario


class ConfigScenarioMenace(_ModeleConfig):
    """Scénario C, « menace » (FR-3), miroir de `generateur.scenarios.ScenarioMenace`."""

    entite: str = Field(pattern=r"^ENT-[A-Z0-9]+$")
    cas_de_test_par_semaine: Annotated[int, Field(strict=True, ge=1)]
    taux_ko_initial: TauxScenario
    semaine_hausse: SemaineScenario
    taux_ko_hausse: tuple[TauxScenario, ...] = Field(min_length=1)
    semaine_certification: SemaineScenario


ConfigScenario = ConfigScenarioSortie | ConfigScenarioEnlisement | ConfigScenarioMenace
"""Un Scénario de démo configuré."""


class ConfigScenarios(_ModeleConfig):
    """Scénarios de démo A, B et C (FR-3, contrats 1.1.0) ; absent ou `null` : désactivé.

    Contrôlés au chargement : Entités distinctes, connues du Programme (`ConfigProgramme`),
    semaines ≥ 1. Une semaine au-delà de `nb_semaines` n'est pas refusée : le générateur
    ignore ce Scénario, comme un Scénario par défaut, ce qui garde valide une copie raccourcie
    du Programme livré.
    """

    sortie: ConfigScenarioSortie | None = None
    """Scénario A."""
    enlisement: ConfigScenarioEnlisement | None = None
    """Scénario B."""
    menace: ConfigScenarioMenace | None = None
    """Scénario C."""

    def actifs(self) -> tuple[tuple[str, ConfigScenario], ...]:
        """Scénarios non désactivés, nommés par leur clé, dans l'ordre A, B, C."""
        candidats: tuple[tuple[str, ConfigScenario | None], ...] = (
            ("sortie", self.sortie),
            ("enlisement", self.enlisement),
            ("menace", self.menace),
        )
        return tuple((nom, s) for nom, s in candidats if s is not None)

    @model_validator(mode="after")
    def _entites_distinctes(self) -> Self:
        entites = [scenario.entite for _, scenario in self.actifs()]
        doublons = sorted({e for e in entites if entites.count(e) > 1})
        if doublons:
            raise ValueError(f"Entité portée par plusieurs Scénarios : {', '.join(doublons)}")
        return self


class ConfigProgramme(_ModeleConfig):
    """Programme fictif : Entités, Vagues, Domaines, Phases, volumétrie, Scénarios de démo."""

    nom: str = Field(min_length=1)
    graine: int
    nb_semaines: int = Field(default=8, ge=1)
    entites: tuple[EntiteProgramme, ...] = Field(min_length=1)
    vagues: tuple[VagueProgramme, ...] = Field(min_length=1)
    domaines: tuple[str, ...] = Field(min_length=1)
    volumetrie: VolumetrieProgramme
    scenarios: ConfigScenarios | None = None
    """Scénarios de démo (contrats 1.1.0) ; clé absente : Scénarios par défaut du générateur."""

    @model_validator(mode="after")
    def _references(self) -> Self:
        for nom, codes in (
            ("Entité", [e.code for e in self.entites]),
            ("Vague", [v.code for v in self.vagues]),
            ("Domaine", list(self.domaines)),
        ):
            doublons = sorted({c for c in codes if codes.count(c) > 1})
            if doublons:
                raise ValueError(f"{nom} en double : {', '.join(doublons)}")
        vagues = {v.code for v in self.vagues}
        for entite in self.entites:
            if entite.vague not in vagues:
                raise ValueError(f"Entité {entite.code} : Vague inconnue {entite.vague!r}")
        for vague in self.vagues:
            for periode in vague.phases:
                if periode.semaine_fin > self.nb_semaines:
                    raise ValueError(
                        f"Vague {vague.code} : Phase {periode.phase} au-delà de la semaine"
                        f" {self.nb_semaines}"
                    )
        if self.scenarios is not None:
            entites = {e.code for e in self.entites}
            for nom, scenario in self.scenarios.actifs():
                if scenario.entite not in entites:
                    raise ValueError(f"scenarios.{nom} : Entité inconnue {scenario.entite!r}")
        return self


# --- Grille de météo (`config/grille_meteo.yaml`, FR-15 ; addendum D) ---

_MOTIF_SEUIL = re.compile(r"\s*(>=|>)\s*([+-]?\d+(?:\.\d+)?)\s*")


def _analyser_seuil(valeur: object) -> object:
    """Analyse un seuil `">= 0.20"` en `(Operateur, Fraction)` exact."""
    if isinstance(valeur, tuple):
        return valeur
    correspondance = _MOTIF_SEUIL.fullmatch(valeur) if isinstance(valeur, str) else None
    if correspondance is None:
        raise ValueError(f"seuil illisible {valeur!r} (attendu : « >= 0.20 » ou « > 5 »)")
    return (Operateur(correspondance.group(1)), Fraction(correspondance.group(2)))


SeuilGrille = Annotated[tuple[Operateur, Fraction], BeforeValidator(_analyser_seuil)]
"""Seuil d'une règle : opérateur et valeur exacte."""


class GardeFous(_ModeleConfig):
    """Garde-fous de volume en deçà desquels un indicateur est non évaluable."""

    ind4_min_tests_executes: int = Field(ge=0)
    ind7_min_entrees_fenetre_glissante: int = Field(ge=0)


class RegleIndicateur(_ModeleConfig):
    """Règle d'un Indicateur de météo : seuils par couleur.

    La cohérence entre couleurs (FR-18) est vérifiée au chargement de la Grille (Story 3.4).
    """

    libelle: str = Field(min_length=1)
    active: bool = True
    seuils: MappingFige[Couleur, SeuilGrille]

    @field_validator("seuils")
    @classmethod
    def _sans_vert(
        cls, seuils: Mapping[Couleur, tuple[Operateur, Fraction]]
    ) -> Mapping[Couleur, tuple[Operateur, Fraction]]:
        if not seuils:
            raise ValueError("au moins un seuil attendu")
        if Couleur.vert in seuils:
            raise ValueError("pas de seuil vert : vert = aucune règle déclenchée")
        return seuils


class GrilleMeteo(_ModeleConfig):
    """Grille de météo : règles, seuils et garde-fous."""

    version: int = Field(ge=1)
    couleurs: tuple[Couleur, ...] = tuple(Couleur)
    """Ordre de gravité croissante, rappelé pour le lecteur du YAML."""
    regle_agregation: Literal["pire_couleur"]
    garde_fous: GardeFous
    indicateurs: MappingFige[CodeIndicateur, RegleIndicateur] = Field(min_length=1)

    @field_validator("couleurs")
    @classmethod
    def _ordre_des_couleurs(cls, couleurs: tuple[Couleur, ...]) -> tuple[Couleur, ...]:
        if couleurs != tuple(Couleur):
            attendu = ", ".join(couleur.value for couleur in Couleur)
            raise ValueError(f"couleurs attendues dans l'ordre de gravité : {attendu}")
        return couleurs


# --- Jira (`config/jira.yaml`, AD-5, AD-6, AD-23) ---


class ConfigJira(_ModeleConfig):
    """Site Jira, adaptateur et correspondance Jira → vocabulaire canonique."""

    url_site: str = Field(pattern=r"^https?://\S+$")
    mode: Literal["cloud", "dc"]
    cle_projet: str = Field(pattern=r"^[A-Z][A-Z0-9]+$")
    marge_extraction_minutes: int = Field(ge=0)
    tentatives_max: int = Field(default=5, ge=1)
    champs: MappingFige[Champ, str]
    """Identifiant Jira de chaque `Champ` (ex. `customfield_10031`), propre à ce `Champ`."""
    types_tickets: MappingFige[str, TypeTicket]
    """Type de ticket Jira → type canonique."""
    valeurs: MappingFige[Champ, MappingFige[str, str]]
    """Pour chaque `Champ` à domaine fermé : valeur Jira → valeur canonique."""

    @model_validator(mode="after")
    def _correspondance(self) -> Self:
        manquants = [champ.value for champ in Champ if champ not in self.champs]
        if manquants:
            raise ValueError(f"champs : Champ sans identifiant Jira : {', '.join(manquants)}")
        types_manquants = [t.value for t in TypeTicket if t not in self.types_tickets.values()]
        if types_manquants:
            raise ValueError(
                f"types_tickets : type canonique sans type Jira : {', '.join(types_manquants)}"
            )
        fermes_manquants = [
            champ.value
            for champ, domaine in DOMAINES_CANONIQUES.items()
            if domaine is not None and champ not in self.valeurs
        ]
        if fermes_manquants:
            raise ValueError(
                "valeurs : Champ à domaine fermé sans correspondance :"
                f" {', '.join(fermes_manquants)}"
            )
        identifiants = list(self.champs.values())
        for champ, identifiant in self.champs.items():
            if not identifiant.strip():
                raise ValueError(f"champs.{champ} : identifiant Jira vide")
        partages = sorted({i for i in identifiants if identifiants.count(i) > 1})
        if partages:
            raise ValueError(
                f"champs : identifiant Jira partagé par plusieurs Champs : {', '.join(partages)}"
            )
        for champ, table in self.valeurs.items():
            domaine = DOMAINES_CANONIQUES[champ]
            if domaine is None:
                raise ValueError(f"valeurs.{champ} : Champ à valeur libre, sans correspondance")
            for valeur_jira, canonique in table.items():
                if canonique not in domaine:
                    raise ValueError(
                        f"valeurs.{champ}.{valeur_jira} : {canonique!r} hors du domaine"
                        f" canonique de « {champ} »"
                    )
        return self


# --- LLM (`config/llm.yaml`, AD-12, AD-13) ---


class ConfigLLM(_ModeleConfig):
    """Fournisseur, modèles, plafond de coût et reprise sur 429."""

    fournisseur: str = Field(min_length=1)
    modele: str = Field(min_length=1)
    modeles_par_tache: MappingFige[Tache, str] = Field(default_factory=lambda: MappingProxyType({}))
    plafond_cout_passage_eur: Decimal = Field(ge=0)
    tentatives_max: int = Field(default=5, ge=1)
    temperature: float = Field(default=0.0, ge=0.0)

    @field_validator("fournisseur")
    @classmethod
    def _sans_deux_points(cls, fournisseur: str) -> str:
        if ":" in fournisseur:
            raise ValueError(f"fournisseur {fournisseur!r} : « : » interdit (version_modele)")
        return fournisseur


# --- Pseudonymisation (`config/pseudonymisation.yaml`, AD-15) ---


class Reconnaisseur(_ModeleConfig):
    """Reconnaisseur maison : expression régulière et type de jeton produit."""

    type_jeton: str = Field(pattern=f"^{MOTIF_TYPE_JETON}$")
    motif: str = Field(min_length=1)
    score: float = Field(default=0.85, gt=0.0, le=1.0)

    @field_validator("motif")
    @classmethod
    def _compilable(cls, motif: str) -> str:
        try:
            re.compile(motif)
        except re.error as exc:
            raise ValueError(f"expression régulière invalide ({exc})") from exc
        return motif


class ConfigPseudonymisation(_ModeleConfig):
    """Moteur de Pseudonymisation et reconnaisseurs maison."""

    langue: str = "fr"
    modele_spacy: str = "fr_core_news_md"
    entites_presidio: tuple[str, ...] = ()
    reconnaisseurs: tuple[Reconnaisseur, ...] = ()


# --- Démo (`config/demo.yaml`, FR-44, FR-45) ---


class ConfigDemo(_ModeleConfig):
    """Paramètres de l'interface de démonstration."""

    temps_manuel_minutes_par_rapport: int = Field(gt=0)
    """Temps de reporting manuel déclaré pour un Rapport quotidien (Q-5)."""
    questions_repli: tuple[str, ...] = ()


# --- Ensemble ---


class ConfigUsine(_ModeleConfig):
    """Configuration complète ; `None` tant que la lane n'a pas livré son YAML."""

    chaine: ConfigChaine
    programme: ConfigProgramme | None = None
    grille_meteo: GrilleMeteo | None = None
    jira: ConfigJira | None = None
    llm: ConfigLLM | None = None
    pseudonymisation: ConfigPseudonymisation | None = None
    demo: ConfigDemo | None = None
