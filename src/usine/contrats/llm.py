"""Contrats de la couche LLM : appels, réponses du fournisseur, sorties contrôlées (AD-12, AD-13).

Le LLM lit, classe et rédige ; il ne calcule jamais un chiffre. Chaque sortie porte son
`statut_controle`, fixé par le contrôle déterministe de la passerelle. Le schéma demandé au
fournisseur est, pour chaque tâche, un `Reponse<Tache>` de ce module ; la sortie publiée reste
`Sortie<Tache>`. La grammaire des jetons de Pseudonymisation (AD-15) est définie ici une seule
fois, pour les adaptateurs, la passerelle et les doublures.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Literal, Self

import polars as pl
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from usine.contrats.calendrier import Horodatage
from usine.contrats.modele import Enregistrement, MappingFige, PassageId, VersionContrats
from usine.contrats.schemas import SchemaTable, enum_polars
from usine.contrats.tickets import CauseRacine
from usine.contrats.versions import CONTRATS_VERSION


class Tache(StrEnum):
    """Tâches LLM figées."""

    classification = "classification"
    explication = "explication"
    narration = "narration"
    agent = "agent"


class StatutControle(StrEnum):
    """Résultat du contrôle déterministe d'une sortie LLM."""

    non_controle = "non_controle"
    conforme = "conforme"
    corrige = "corrige"
    """Conforme après retrait de phrases fautives."""
    rejete = "rejete"
    """Remplacée par un libellé explicite (« explication indisponible », Prévision brute)."""


# --- Grammaire des jetons de Pseudonymisation (AD-15) ---

LONGUEUR_EMPREINTE_JETON = 6
"""Caractères hexadécimaux du HMAC-SHA256 gardés dans un jeton `<TYPE>_<6 hex>`."""

MOTIF_TYPE_JETON = r"[A-Z](?:[A-Z_]*[A-Z])?"
"""Type d'un jeton : majuscules et `_`, sans `_` en tête ni en fin (`COMPTE`, `ID_CLIENT`)."""

_TYPE_JETON = re.compile(MOTIF_TYPE_JETON)

CANDIDAT_JETON = re.compile(
    rf"(?<![A-Z_])([A-Z][A-Z_]*)_([0-9a-f]{{{LONGUEUR_EMPREINTE_JETON}}})(?![0-9a-f])"
)
"""Jeton candidat, même collé à des lettres ou précédé d'un préfixe `MAJUSCULES_`.

Le groupe 1 peut porter un préfixe en plus du type (`ID_COMPTE`), le groupe 2 est
l'empreinte : `variantes_jeton` donne les jetons possibles.
"""


def est_type_jeton(type_jeton: str) -> bool:
    """Vrai si `type_jeton` suit `MOTIF_TYPE_JETON` (`COMPTE` oui, `compte` ou `_X` non)."""
    return _TYPE_JETON.fullmatch(type_jeton) is not None


def variantes_jeton(candidat: re.Match[str]) -> tuple[str, ...]:
    """Jetons possibles d'un candidat de `CANDIDAT_JETON`, du plus long au plus court.

    `ID_COMPTE_abc123` → `ID_COMPTE_abc123`, puis `COMPTE_abc123`. Une variante dont le type
    ne suit pas `MOTIF_TYPE_JETON` n'est jamais un jeton.
    """
    parties = candidat.group(1).split("_")
    empreinte = candidat.group(2)
    return tuple(
        f"{'_'.join(parties[rang:])}_{empreinte}"
        for rang in range(len(parties))
        if parties[rang] and est_type_jeton("_".join(parties[rang:]))
    )


# --- Appels au fournisseur (AD-13) ---


class ParametresAppel(Enregistrement):
    """Paramètres d'un appel au fournisseur."""

    tache: Tache
    max_jetons_sortie: int = Field(gt=0)
    temperature: float = Field(default=0.0, ge=0.0)
    tentative: int = Field(default=0, ge=0)


class ReponseStructuree[T: BaseModel](BaseModel):
    """Réponse de `FournisseurLLM.generer_structure` : sortie validée et texte brut."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sortie: T
    brut: str
    """Réponse brute, stockée en cache avant contrôle."""
    jetons_entree: int = Field(ge=0)
    jetons_sortie: int = Field(ge=0)
    version_modele: str = Field(min_length=1)


class AppelOutil(Enregistrement):
    """Appel d'outil demandé par le modèle, au cours d'une conversation d'Agent."""

    id_appel: str = Field(min_length=1)
    nom_outil: str = Field(min_length=1)
    arguments: MappingFige[str, JsonValue]


class MessageAgent(Enregistrement):
    """Message d'une conversation d'Agent."""

    role: Literal["systeme", "utilisateur", "assistant", "outil"]
    contenu: str
    appels_outils: tuple[AppelOutil, ...] = ()
    """Appels demandés par l'assistant dans ce message."""
    id_appel: str | None = None
    """Pour un message `outil` : l'appel dont il porte le résultat."""

    @model_validator(mode="after")
    def _role(self) -> Self:
        if self.appels_outils and self.role != "assistant":
            raise ValueError("seul un message « assistant » demande des appels d'outils")
        if (self.role == "outil") != (self.id_appel is not None):
            raise ValueError("un message « outil » et lui seul porte un « id_appel »")
        return self


@dataclass(frozen=True)
class OutilAgent:
    """Outil passé au fournisseur, déjà enveloppé par la passerelle (Pseudonymisation, trace).

    `executer` reçoit les arguments JSON de l'appel et renvoie le résultat pseudonymisé.
    """

    nom: str
    description: str
    arguments: type[BaseModel]
    executer: Callable[[Mapping[str, JsonValue]], str]


class ReponseAgentBrute(Enregistrement):
    """Réponse de `FournisseurLLM.executer_agent` : texte final et conversation complète."""

    texte: str
    messages: tuple[MessageAgent, ...]
    jetons_entree: int = Field(ge=0)
    jetons_sortie: int = Field(ge=0)
    version_modele: str = Field(min_length=1)


class EnveloppeCache(Enregistrement):
    """Valeur stockée par le port `CacheLLM` (AD-12), sérialisée en JSON.

    La réponse brute du fournisseur, avant contrôle, et le `version_modele` qui l'a produite.
    """

    brut: str
    version_modele: str = Field(min_length=1)


class ReponseExplication(Enregistrement):
    """Schéma demandé au fournisseur pour la tâche `explication` ; publiée : `SortieExplication`."""

    texte: str
    brouillon_commentaire: str = ""


class SortieClassification(Enregistrement):
    """Cause racine proposée pour une Anomalie (FR-35) ; jamais écrite dans Jira."""

    cle_ticket: str = Field(min_length=1)
    cause_racine: CauseRacine
    justification: str = ""
    statut_controle: StatutControle = StatutControle.non_controle


SCHEMA_REPARTITION_CAUSES = SchemaTable(
    "SCHEMA_REPARTITION_CAUSES",
    {
        "date": pl.Date(),
        "entite": pl.Utf8(),
        "cause_racine": enum_polars(CauseRacine),
        "nombre": pl.Int64(),
    },
    non_nulles=frozenset({"date", "entite", "cause_racine", "nombre"}),
)
"""`RepartitionCauses` : Anomalies ouvertes par Cause racine proposée et par Entité."""


class SortieExplication(Enregistrement):
    """Explication sourcée d'une Entité rouge ou orange (FR-32, FR-33)."""

    date_arrete: date
    entite: str = Field(min_length=1)
    texte: str
    citations: tuple[str, ...]
    brouillon_commentaire: str
    phrases_retirees: int = Field(default=0, ge=0)
    statut_controle: StatutControle = StatutControle.non_controle


class SortieNarration(Enregistrement):
    """Narration d'une Prévision (FR-24), sans chiffre propre."""

    date_arrete: date
    entite: str = Field(min_length=1)
    texte: str
    statut_controle: StatutControle = StatutControle.non_controle


class ReponseAgent(Enregistrement):
    """Réponse contrôlée de l'Agent à une question du Pilote (FR-39, FR-40)."""

    question: str
    texte: str
    outils_appeles: tuple[str, ...] = ()
    tickets_cites: tuple[str, ...] = ()
    statut_controle: StatutControle = StatutControle.non_controle


class ReponseAgentEnregistree(Enregistrement):
    """Réponse de l'Agent enregistrée pour le Mode repli (`demo/repli/agent/*.json`)."""

    contrats_version: VersionContrats = CONTRATS_VERSION
    passage_id: PassageId
    horodatage: Horodatage
    reponse: ReponseAgent
