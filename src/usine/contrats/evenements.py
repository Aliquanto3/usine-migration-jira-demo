"""Événement canonique, en-tête du Journal et manifeste d'injection (AD-3, AD-4).

Toutes les sources (Journal, Jira Cloud, Jira Data Center) produisent des `Evenement` ; une
création est suivie, au même horodatage, d'un `modification_champ` par attribut initial.
"""

from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import date
from enum import StrEnum
from typing import Annotated, Self

import polars as pl
from pydantic import AfterValidator, Field, model_validator

from usine.contrats.calendrier import Horodatage, verifier_lundi
from usine.contrats.erreurs import UsineErreur
from usine.contrats.modele import Enregistrement, VersionContrats
from usine.contrats.schemas import SchemaTable, enum_polars, valider
from usine.contrats.tickets import (
    CHAMPS_PAR_TYPE,
    DOMAINES_CANONIQUES,
    MOTIF_CLE_TICKET,
    Champ,
    TypeTicket,
)
from usine.contrats.versions import CONTRATS_VERSION

CleTicket = Annotated[str, Field(pattern=f"^{MOTIF_CLE_TICKET}$")]
"""Clé de ticket (`DEMO-123`)."""


class NatureEvenement(StrEnum):
    """Nature d'un `Evenement`."""

    creation = "creation"
    transition = "transition"
    modification_champ = "modification_champ"
    alignement = "alignement"


class SourceEvenement(StrEnum):
    """Origine d'un `Evenement`."""

    journal = "journal"
    jira_cloud = "jira_cloud"
    jira_dc = "jira_dc"


class Evenement(Enregistrement):
    """Événement canonique d'un ticket ; `de` et `vers` sont des valeurs canoniques.

    Un `modification_champ` sur `statut` ne porte que la valeur initiale, au même horodatage
    que la création ; tout changement de statut ultérieur est une `transition`. Un événement
    dont `de` et `vers` sont renseignés et égaux est sans effet, donc refusé.
    """

    id_evenement: str = Field(min_length=1)
    cle_ticket: CleTicket
    type_ticket: TypeTicket
    horodatage: Horodatage
    nature: NatureEvenement
    champ: Champ | None = None
    de: str | None = None
    vers: str | None = None
    source: SourceEvenement

    @model_validator(mode="after")
    def _coherence(self) -> Self:
        if self.nature is NatureEvenement.creation:
            if self.champ is not None or self.de is not None or self.vers is not None:
                raise ValueError("une création ne porte ni champ, ni « de », ni « vers »")
            return self
        if self.champ is None:
            raise ValueError(f"un événement « {self.nature} » exige un champ")
        if self.nature is NatureEvenement.transition:
            if self.champ is not Champ.statut:
                raise ValueError(
                    f"une transition porte sur le champ « statut », pas « {self.champ} »"
                )
            if self.vers is None:
                raise ValueError("une transition exige « vers »")
            if self.vers == self.de:
                raise ValueError(f"transition sans effet : « de » = « vers » = {self.vers!r}")
        if self.de is not None and self.de == self.vers:
            raise ValueError(
                f"événement « {self.nature} » sans effet : « de » = « vers » = {self.vers!r}"
            )
        if self.champ not in CHAMPS_PAR_TYPE[self.type_ticket]:
            raise ValueError(f"champ « {self.champ} » sans objet pour « {self.type_ticket} »")
        domaine = DOMAINES_CANONIQUES[self.champ]
        if domaine is not None:
            for nom, valeur in (("de", self.de), ("vers", self.vers)):
                if valeur is not None and valeur not in domaine:
                    raise ValueError(
                        f"« {nom} » = {valeur!r} hors du domaine canonique de « {self.champ} »"
                    )
        return self


def _lundi(d: date) -> date:
    try:
        return verifier_lundi(d)
    except UsineErreur as exc:
        raise ValueError(str(exc)) from exc


class EnteteJournal(Enregistrement):
    """Première ligne du Journal JSONL : paramètres de génération."""

    contrats_version: VersionContrats = CONTRATS_VERSION
    graine: int
    date_generation: date
    date_injection: date
    ancrage_semaines: Annotated[date, AfterValidator(_lundi)]
    """Lundi de la semaine 1 du Programme (`calendrier.semaine_programme`)."""
    version_corpus: str = Field(min_length=1)
    modele_corpus: str = Field(min_length=1)

    @model_validator(mode="after")
    def _dates(self) -> Self:
        if not self.ancrage_semaines <= self.date_injection <= self.date_generation:
            raise ValueError(
                "ordre attendu : ancrage des semaines ≤ Date d'injection ≤ date de génération"
            )
        return self


class ManifesteInjection(Enregistrement):
    """Manifeste écrit par l'injecteur (`donnees/injection/manifeste_injection.json`)."""

    contrats_version: VersionContrats = CONTRATS_VERSION
    date_injection: date
    debut_injection: Horodatage
    horodatage_fin_injection: Horodatage
    cle_projet: str = Field(pattern=r"^[A-Z][A-Z0-9]+$")
    correspondance_cles: Mapping[CleTicket, CleTicket]
    """Clé générée → clé Jira, appliquée à la lecture du Journal."""

    @model_validator(mode="after")
    def _intervalle(self) -> Self:
        if self.horodatage_fin_injection < self.debut_injection:
            raise ValueError("fin d'injection antérieure à son début")
        prefixe = f"{self.cle_projet}-"
        hors_projet = sorted(
            cle for cle in self.correspondance_cles.values() if not cle.startswith(prefixe)
        )
        if hors_projet:
            raise ValueError(
                f"clés Jira hors du projet {self.cle_projet} : {', '.join(hors_projet)}"
            )
        comptes = Counter(self.correspondance_cles.values())
        doublons = sorted(cle for cle, nombre in comptes.items() if nombre > 1)
        if doublons:
            raise ValueError(
                f"correspondance des clés non injective : {', '.join(doublons)} reçu(es)"
                " par plusieurs clés générées"
            )
        return self


SCHEMA_EVENEMENT = SchemaTable(
    "SCHEMA_EVENEMENT",
    {
        "id_evenement": pl.Utf8(),
        "cle_ticket": pl.Utf8(),
        "type_ticket": enum_polars(TypeTicket),
        "horodatage": pl.Datetime("us", "UTC"),
        "nature": enum_polars(NatureEvenement),
        "champ": enum_polars(Champ),
        "de": pl.Utf8(),
        "vers": pl.Utf8(),
        "source": enum_polars(SourceEvenement),
    },
)
"""Table des `Evenement`, une ligne par événement.

`de` et `vers` restent en texte : leur domaine dépend de `champ`.
"""


def evenements_en_table(evenements: Iterable[Evenement]) -> pl.DataFrame:
    """Range des `Evenement` dans une table `SCHEMA_EVENEMENT`, dans l'ordre reçu."""
    liste = list(evenements)
    colonnes: dict[str, list[object]] = {
        "id_evenement": [e.id_evenement for e in liste],
        "cle_ticket": [e.cle_ticket for e in liste],
        "type_ticket": [e.type_ticket.value for e in liste],
        "horodatage": [e.horodatage for e in liste],
        "nature": [e.nature.value for e in liste],
        "champ": [None if e.champ is None else e.champ.value for e in liste],
        "de": [e.de for e in liste],
        "vers": [e.vers for e in liste],
        "source": [e.source.value for e in liste],
    }
    # Construction par colonnes : une valeur hors d'un `pl.Enum` y lève une erreur, alors que
    # la construction par lignes la remplacerait silencieusement par `null`.
    df = pl.DataFrame(colonnes, schema=dict(SCHEMA_EVENEMENT.colonnes))
    return valider(df, SCHEMA_EVENEMENT)
