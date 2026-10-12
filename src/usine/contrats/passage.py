"""Passage : étapes, progression, manifeste, enveloppes de fichiers (AD-7, AD-8, AD-22)."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Self, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from usine.contrats.calendrier import Horodatage
from usine.contrats.config import ConfigUsine
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import SortieClassification, SortieExplication, SortieNarration
from usine.contrats.meteo import MeteoEntite
from usine.contrats.modele import (
    MOTIF_PASSAGE_ID_TEXTE,
    Enregistrement,
    PassageId,
    VersionContrats,
)
from usine.contrats.prevision import ContenuPrevisions
from usine.contrats.trace import EntreeTrace
from usine.contrats.versions import CLE_VERSION, CONTRATS_VERSION, verifier_version


class Etape(StrEnum):
    """Étapes de la Chaîne, dans leur ordre d'exécution (AD-8)."""

    extraction = "extraction"
    instantanes = "instantanes"
    kpi = "kpi"
    meteo = "meteo"
    prevision = "prevision"
    classification = "classification"
    repartition_causes = "repartition_causes"
    explications = "explications"
    narration = "narration"
    rendu = "rendu"


class StatutEtape(StrEnum):
    """État d'une étape ; en Palier 1, les étapes LLM sont `sautee`."""

    en_cours = "en_cours"
    reussie = "reussie"
    sautee = "sautee"
    echouee = "echouee"


class EvenementProgression(Enregistrement):
    """Ligne de `sorties/progression/<passage_id>.jsonl`, hors du Passage."""

    passage_id: PassageId
    etape: Etape
    statut: StatutEtape
    horodatage: Horodatage
    message: str = ""


class ExecutionEtape(Enregistrement):
    """Exécution d'une étape, consignée au manifeste ; la durée s'en déduit."""

    etape: Etape
    statut: StatutEtape
    horodatage_debut: Horodatage
    horodatage_fin: Horodatage

    @model_validator(mode="after")
    def _intervalle(self) -> Self:
        if self.horodatage_fin < self.horodatage_debut:
            raise ValueError(f"étape {self.etape} : fin antérieure au début")
        if self.statut not in (StatutEtape.reussie, StatutEtape.sautee):
            raise ValueError(f"étape {self.etape} : statut final « {self.statut} » au manifeste")
        return self

    @property
    def duree(self) -> timedelta:
        """Durée de l'étape."""
        return self.horodatage_fin - self.horodatage_debut


class ManifestePassage(Enregistrement):
    """Manifeste d'un Passage publié (`manifeste.json`)."""

    contrats_version: VersionContrats = CONTRATS_VERSION
    passage_id: PassageId
    date_arrete: date
    palier: Literal[1, 2]
    source: str = Field(min_length=1)
    """Source des événements (`journal`, `composite`…)."""
    horodatage_debut: Horodatage
    horodatage_fin: Horodatage
    horodatage_extraction: Horodatage | None = None
    version_grille: str = Field(min_length=1)
    version_donnees: str = Field(min_length=1)
    classification_initiale: bool = False
    cout_llm_eur: Decimal = Field(ge=0)
    nb_alignements: int = Field(ge=0)
    nb_tickets: int = Field(ge=0)
    etapes: tuple[ExecutionEtape, ...]

    @model_validator(mode="after")
    def _coherence(self) -> Self:
        if self.horodatage_fin < self.horodatage_debut:
            raise ValueError("fin du Passage antérieure à son début")
        ordre = list(Etape)
        rangs = [ordre.index(execution.etape) for execution in self.etapes]
        if rangs != sorted(set(rangs)):
            raise ValueError("étapes du manifeste en double ou hors de l'ordre d'AD-8")
        return self


FICHIERS_PASSAGE: Mapping[str, str] = MappingProxyType(
    {
        "manifeste": "manifeste.json",
        "tickets_etats": "tickets_etats.parquet",
        "tickets_textes": "tickets_textes.parquet",
        "instantanes": "instantanes.parquet",
        "kpi": "kpi.parquet",
        "indicateurs": "indicateurs.parquet",
        "meteo": "meteo.json",
        "tendances": "tendances.parquet",
        "previsions": "previsions.json",
        "classification": "llm/classification.json",
        "explications": "llm/explications.json",
        "narrations": "llm/narrations.json",
        "repartition_causes": "repartition_causes.parquet",
        "trace_llm": "trace/llm.jsonl",
        "trace_previsions": "trace/previsions.jsonl",
        "rapport_xlsx": "rapport-{date_arrete}.xlsx",
        "rapport_pptx": "rapport-{date_arrete}.pptx",
    }
)
"""Nom logique → chemin relatif dans le Passage (`{date_arrete}` au format AAAA-MM-JJ)."""


CONTENUS_JSON: Mapping[str, type] = MappingProxyType(
    {
        "meteo": tuple[MeteoEntite, ...],
        "previsions": ContenuPrevisions,
        "classification": tuple[SortieClassification, ...],
        "explications": tuple[SortieExplication, ...],
        "narrations": tuple[SortieNarration, ...],
    }
)
"""Type du contenu de chaque fichier JSON enveloppé (`EnveloppeFichier`) d'un Passage.

Le manifeste n'y figure pas : il est son propre modèle (`ManifestePassage`), sans enveloppe.
"""


def est_du_type(valeur: object, type_contenu: type) -> bool:
    """Vrai si `valeur` est du type de contenu annoncé (`X` ou `tuple[X, ...]`)."""
    if get_origin(type_contenu) is tuple:
        (element, _points) = get_args(type_contenu)
        return isinstance(valeur, tuple) and all(isinstance(v, element) for v in valeur)
    return isinstance(valeur, type_contenu)


def chemin_fichier_passage(nom: str, date_arrete: date) -> str:
    """Chemin relatif du fichier `nom` de `FICHIERS_PASSAGE` pour une Date d'arrêté."""
    if nom not in FICHIERS_PASSAGE:
        raise UsineErreur(f"fichier de Passage inconnu : {nom!r}")
    return FICHIERS_PASSAGE[nom].format(date_arrete=date_arrete.isoformat())


_EXCLUSION_ENVELOPPE = frozenset({"passage_id"})

EXCLUSIONS_REJEU: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "manifeste": frozenset(
            {
                "passage_id",
                "horodatage_debut",
                "horodatage_fin",
                "horodatage_extraction",
                "version_donnees",
                "etapes[].horodatage_debut",
                "etapes[].horodatage_fin",
                "classification_initiale",
                "cout_llm_eur",
            }
        ),
        "meteo": _EXCLUSION_ENVELOPPE,
        "previsions": _EXCLUSION_ENVELOPPE,
        "classification": _EXCLUSION_ENVELOPPE,
        "explications": _EXCLUSION_ENVELOPPE,
        "narrations": _EXCLUSION_ENVELOPPE,
        "trace_llm": frozenset(
            {
                "horodatage",
                "passage_id",
                "version_donnees",
                "depuis_cache",
                "jetons_entree",
                "jetons_sortie",
                "cout_estime_eur",
            }
        ),
        "trace_previsions": frozenset({"horodatage", "passage_id", "version_donnees"}),
        "rapport_xlsx": frozenset({"Traçabilité!B5", "Traçabilité!B8"}),
        "rapport_pptx": frozenset(
            {"Annexe méthode!Horodatage d'extraction", "Annexe méthode!Version des données"}
        ),
    }
)
"""Champs ignorés par la comparaison du Rejeu, par fichier (AD-7).

Clé : nom logique de `FICHIERS_PASSAGE`. Valeur : chemins de champ depuis la racine de
l'enregistrement (la ligne d'un JSONL, l'enveloppe d'un JSON, l'objet du manifeste) ; `[]`
désigne chaque élément d'une liste (`etapes[].horodatage_debut`). Un champ exclu dans un
fichier reste comparé dans tous les autres. Les tables Parquet n'ont aucune exclusion.

Les rendus sont repérés `<onglet ou slide>!<repère>` : adresse de cellule pour l'Excel
(`Traçabilité!B5`), libellé de ligne pour le PowerPoint (`Annexe méthode!Version des données`,
stable quel que soit le nombre d'Indicateurs). Ce sont les cellules qui affichent
`horodatage_extraction` et `version_donnees`, exclus au manifeste (contrats 1.2).
"""

# --- Chemins de `donnees/` et `sorties/`, relatifs à la racine du dépôt ---

REPERTOIRE_DONNEES = Path("donnees")
"""Données locales, ignorées par git sauf `donnees/corpus/`."""

CHEMIN_JOURNAL = REPERTOIRE_DONNEES / "journal.jsonl"
"""Journal d'événements lu par la Chaîne, écrit par `usine donnees generer`."""

CHEMIN_VERITE_TERRAIN = REPERTOIRE_DONNEES / "verite_terrain.json"
"""Vérité terrain des Causes racines, écrite à côté du Journal."""

CHEMIN_VERROU = REPERTOIRE_DONNEES / ".verrou-passage"
"""Verrou exclusif d'un Passage (AD-6)."""

CHEMIN_CACHE_LLM = REPERTOIRE_DONNEES / "cache_llm.sqlite"
"""Cache des réponses LLM (WAL, AD-12) ; seule la passerelle y accède."""

CHEMIN_PSEUDONYMES = REPERTOIRE_DONNEES / "pseudonymes.sqlite"
"""Table jeton → valeur de la Pseudonymisation (WAL, AD-15) ; hors git."""

REPERTOIRE_SORTIES = Path("sorties")
"""Racine des sorties : Passages, échecs, progression."""

SOUS_REPERTOIRE_PASSAGES = "passages"
"""Passages sous `sorties/` : `<date_arrete>/<passage_id>/` publiés, `.en-cours-<id>/`."""

SOUS_REPERTOIRE_ECHECS = "echecs"
"""Passages en échec sous `sorties/` : `<passage_id>/`."""

SOUS_REPERTOIRE_PROGRESSION = "progression"
"""Progression sous `sorties/` : `<passage_id>.jsonl`, hors du Passage (AD-8)."""

REPERTOIRE_PASSAGES = REPERTOIRE_SORTIES / SOUS_REPERTOIRE_PASSAGES
"""`sorties/passages/`."""

REPERTOIRE_PROGRESSION = REPERTOIRE_SORTIES / SOUS_REPERTOIRE_PROGRESSION
"""`sorties/progression/`."""

PREFIXE_EN_COURS = ".en-cours-"
"""Préfixe du répertoire d'un Passage en construction, sous `sorties/passages/`."""

MOTIF_PASSAGE_ID = re.compile(MOTIF_PASSAGE_ID_TEXTE)
"""`AAAAMMJJTHHMMSSZ-<6 hex>` (à appliquer avec `fullmatch`)."""

_MOTIF_SUFFIXE = re.compile(r"[0-9a-f]{6}")


def former_passage_id(horodatage_debut: datetime, suffixe: str) -> str:
    """Forme un `passage_id` à partir du début du Passage (UTC) et de 6 hex fournis."""
    if horodatage_debut.tzinfo is None or horodatage_debut.utcoffset() is None:
        raise UsineErreur(f"horodatage sans fuseau pour un passage_id : {horodatage_debut!r}")
    if not isinstance(suffixe, str) or _MOTIF_SUFFIXE.fullmatch(suffixe) is None:
        raise UsineErreur(f"suffixe de passage_id invalide : {suffixe!r} (6 hex minuscules)")
    return f"{horodatage_debut.astimezone(UTC):%Y%m%dT%H%M%SZ}-{suffixe}"


class EnveloppeFichier[T](BaseModel):
    """Enveloppe de chaque fichier JSON d'un Passage : version des contrats et contexte."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contrats_version: VersionContrats = CONTRATS_VERSION
    passage_id: PassageId
    date_arrete: date
    contenu: T


def lire_enveloppe[T](texte: str | bytes, type_contenu: type[T]) -> EnveloppeFichier[T]:
    """Relit une enveloppe ; refuse une version majeure de contrats différente (AD-2).

    La version est lue avant toute validation du contenu.
    """
    try:
        donnees = json.loads(texte)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise UsineErreur(f"enveloppe de fichier illisible ({exc})") from exc
    if not isinstance(donnees, dict) or CLE_VERSION not in donnees:
        raise UsineErreur(f"enveloppe de fichier sans « {CLE_VERSION} »")
    version = donnees[CLE_VERSION]
    if not isinstance(version, str):
        raise UsineErreur(f"« {CLE_VERSION} » illisible : {version!r}")
    verifier_version(version)
    modele: type[EnveloppeFichier[T]] = EnveloppeFichier[type_contenu]  # type: ignore[valid-type]
    try:
        return modele.model_validate(donnees)
    except ValidationError as exc:
        raise UsineErreur(
            f"enveloppe de fichier invalide ({exc.error_count()} erreur(s)) : {exc}"
        ) from exc


@dataclass(frozen=True)
class DonneesPassage:
    """Identité des données d'un Passage, calculée par la composition et passée à la Chaîne."""

    source: str
    """Source des événements (`journal`, `composite`…), recopiée au manifeste."""
    version_grille: str
    version_donnees: str


@dataclass(frozen=True)
class ContextePassage[C]:
    """Contexte donné à chaque étape ; le port `Etape` fixe `C` à `Consultation`."""

    date_arrete: date
    passage_id: str
    configuration: ConfigUsine
    consultation: C

    def __post_init__(self) -> None:
        if MOTIF_PASSAGE_ID.fullmatch(self.passage_id) is None:
            raise UsineErreur(f"passage_id invalide : {self.passage_id!r}")

    @property
    def palier(self) -> Literal[1, 2]:
        """Palier du Passage : la seule source est `ConfigChaine.palier` (AD-8)."""
        return self.configuration.chaine.palier


@dataclass(frozen=True)
class ResultatEtape:
    """Résultat d'une étape : sorties nommées (clés de `FICHIERS_PASSAGE`) et traces."""

    statut: StatutEtape
    sorties: Mapping[str, object] = field(default_factory=dict)
    traces: tuple[EntreeTrace, ...] = ()

    def __post_init__(self) -> None:
        if self.statut not in (StatutEtape.reussie, StatutEtape.sautee):
            raise UsineErreur(f"statut d'étape terminée invalide : {self.statut!r}")
        inconnues = sorted(set(self.sorties) - set(FICHIERS_PASSAGE))
        if inconnues:
            raise UsineErreur(f"sortie d'étape hors FICHIERS_PASSAGE : {', '.join(inconnues)}")
        if self.statut is StatutEtape.sautee and self.sorties:
            raise UsineErreur("une étape sautée ne produit aucune sortie")
        for nom, valeur in self.sorties.items():
            attendu = CONTENUS_JSON.get(nom)
            if attendu is not None and not est_du_type(valeur, attendu):
                raise UsineErreur(
                    f"sortie « {nom} » de type {type(valeur).__name__}, attendu {attendu}"
                )
        object.__setattr__(self, "sorties", MappingProxyType(dict(self.sorties)))
        object.__setattr__(self, "traces", tuple(self.traces))
