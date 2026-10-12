"""Cas versionnés de la suite d'évaluation de l'Explication sourcée (SM-3).

Un cas est un fichier `cas/cas-NN.json` : Météo de l'Entité à la Date d'arrêté, textes des
tickets en cause, KPI et Causes racines facultatifs, et réponses enregistrées du fournisseur
(rejouées dans l'ordre, une par appel : appel initial, puis régénération éventuelle).
"""

from pathlib import Path

import polars as pl
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from usine.contrats.calcul import SCHEMA_KPI
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import SCHEMA_REPARTITION_CAUSES, ReponseExplication
from usine.contrats.meteo import MeteoEntite
from usine.contrats.schemas import valider
from usine.contrats.tickets import SCHEMA_TICKET_TEXTE, CauseRacine, TypeTicket, rang_cle

NOMBRE_CAS = 10
"""Nombre de cas exigé par SM-3."""

REPERTOIRE_CAS = Path(__file__).parent / "cas"
"""Répertoire des cas versionnés."""


class _Modele(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TexteTicket(_Modele):
    """Titre et description d'un ticket à la Date d'arrêté."""

    cle_ticket: str = Field(min_length=1)
    type_ticket: TypeTicket = TypeTicket.anomalie
    titre: str | None = None
    description: str | None = None


class LigneKpi(_Modele):
    """KPI de l'Entité à la Date d'arrêté (`dimension` vide = KPI non ventilé)."""

    code_kpi: str = Field(min_length=1)
    dimension: str = ""
    numerateur: int
    denominateur: int = Field(ge=0)


class LigneCause(_Modele):
    """Anomalies ouvertes classées de l'Entité portant une Cause racine proposée."""

    cause_racine: CauseRacine
    nombre: int = Field(ge=0)
    part: float = Field(ge=0, le=1)


class CasExplication(_Modele):
    """Cas d'évaluation : entrée de la tâche `expliquer` et réponses enregistrées."""

    identifiant: str = Field(min_length=1)
    description: str = Field(min_length=1)
    """Ce que le cas éprouve (couleur, règles, KPI, causes, phrase hors cause…)."""
    meteo: MeteoEntite
    textes: tuple[TexteTicket, ...] = ()
    kpi: tuple[LigneKpi, ...] | None = None
    repartition: tuple[LigneCause, ...] | None = None
    reponses: tuple[ReponseExplication, ...] = ()
    """Réponses du fournisseur rejouées hors réseau, dans l'ordre des appels."""

    @property
    def tickets_en_cause(self) -> tuple[str, ...]:
        """Clés en cause de toutes les Règles déclenchantes, sans doublon, triées."""
        cles = {cle for regle in self.meteo.regles for cle in regle.tickets_en_cause}
        return tuple(sorted(cles, key=rang_cle))

    def table_textes(self) -> pl.DataFrame:
        """Table `SCHEMA_TICKET_TEXTE` des textes du cas."""
        table = pl.DataFrame(
            {
                "cle_ticket": [texte.cle_ticket for texte in self.textes],
                "type_ticket": [texte.type_ticket.value for texte in self.textes],
                "entite": [self.meteo.entite] * len(self.textes),
                "titre": [texte.titre for texte in self.textes],
                "description": [texte.description for texte in self.textes],
            },
            schema=dict(SCHEMA_TICKET_TEXTE.colonnes),
        )
        return valider(table, SCHEMA_TICKET_TEXTE)

    def table_kpi(self) -> pl.DataFrame | None:
        """Table `SCHEMA_KPI` de l'Entité à la Date d'arrêté, ou `None`."""
        if self.kpi is None:
            return None
        table = pl.DataFrame(
            {
                "date": [self.meteo.date_arrete] * len(self.kpi),
                "perimetre": [self.meteo.entite] * len(self.kpi),
                "code_kpi": [ligne.code_kpi for ligne in self.kpi],
                "dimension": [ligne.dimension for ligne in self.kpi],
                "numerateur": [ligne.numerateur for ligne in self.kpi],
                "denominateur": [ligne.denominateur for ligne in self.kpi],
            },
            schema=dict(SCHEMA_KPI.colonnes),
        )
        return valider(table, SCHEMA_KPI)

    def table_repartition(self) -> pl.DataFrame | None:
        """Table `SCHEMA_REPARTITION_CAUSES` de l'Entité, ou `None`."""
        if self.repartition is None:
            return None
        table = pl.DataFrame(
            {
                "date": [self.meteo.date_arrete] * len(self.repartition),
                "entite": [self.meteo.entite] * len(self.repartition),
                "cause_racine": [ligne.cause_racine.value for ligne in self.repartition],
                "nombre": [ligne.nombre for ligne in self.repartition],
                "part": [ligne.part for ligne in self.repartition],
            },
            schema=dict(SCHEMA_REPARTITION_CAUSES.colonnes),
        )
        return valider(table, SCHEMA_REPARTITION_CAUSES)


def lire_cas(chemin: Path) -> CasExplication:
    """Cas du fichier `chemin` ; un fichier illisible ou mal formé lève une `UsineErreur`."""
    try:
        return CasExplication.model_validate_json(chemin.read_bytes())
    except OSError as exc:
        raise UsineErreur(f"{chemin} : cas illisible ({exc.strerror or exc})") from exc
    except ValidationError as exc:
        premiere = exc.errors()[0]
        lieu = ".".join(str(partie) for partie in premiere["loc"]) or "racine"
        raise UsineErreur(
            f"{chemin} : cas mal formé ({exc.error_count()} erreur(s), {lieu} : {premiere['msg']})"
        ) from exc


def charger_cas(repertoire: Path = REPERTOIRE_CAS) -> tuple[CasExplication, ...]:
    """Les `cas-*.json` de `repertoire`, triés par nom : exactement 10, identifiants uniques."""
    chemins = sorted(repertoire.glob("cas-*.json"))
    if len(chemins) != NOMBRE_CAS:
        raise UsineErreur(
            f"{repertoire} : {len(chemins)} fichier(s) cas-*.json, {NOMBRE_CAS} attendus (SM-3)"
        )
    cas = tuple(lire_cas(chemin) for chemin in chemins)
    vus: dict[str, Path] = {}
    for chemin, un_cas in zip(chemins, cas, strict=True):
        if un_cas.identifiant in vus:
            raise UsineErreur(
                f"{chemin} : identifiant « {un_cas.identifiant} » déjà porté par"
                f" {vus[un_cas.identifiant].name}"
            )
        vus[un_cas.identifiant] = chemin
    return cas
