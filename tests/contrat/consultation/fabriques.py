"""Fabriques des adaptateurs de `Consultation` soumis à la suite de contrat.

`passage_publie` : `ConsultationPassage` sur un Passage publié par `lancer_rapport` (Journal
graine 42 du 2026-10-12, Date d'arrêté 2026-10-09), dans un répertoire temporaire supprimé à
la fin de la session. Le Passage est publié une fois ; chaque cas reçoit un lecteur neuf.
Une copie plus tardive du Passage, au manifeste réécrit avec `classification_initiale`, sert
au filtre de FR-44.

`passage_mode_repli` : le même Passage lu en Mode repli (`url_jira=None`).

`passage_palier_2` : copie du Passage sous une racine de Passages distincte (avec sa copie
`classification_initiale`), manifeste en Palier 2, complétée de `previsions.json`,
`trace/previsions.jsonl`, `llm/*.json` et `repartition_causes.parquet` écrits par les modèles
de contrats pour ENT-B (Risque d'entrée en rouge : ENT-A).
"""

import atexit
import functools
import json
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import polars as pl

from usine.composition import generer_journal, lancer_rapport
from usine.config import charger_yaml
from usine.consultation.passage import ConsultationPassage
from usine.contrats.config import ConfigJira, ConfigProgramme
from usine.contrats.llm import (
    SCHEMA_REPARTITION_CAUSES,
    SortieClassification,
    SortieExplication,
    SortieNarration,
)
from usine.contrats.meteo import CodeIndicateur
from usine.contrats.passage import EnveloppeFichier, ManifestePassage
from usine.contrats.prevision import (
    ContenuPrevisions,
    FacteurExplicatif,
    MethodePrevision,
    Prevision,
    RisqueEntreeRouge,
    StatutPrevision,
)
from usine.contrats.tickets import CauseRacine
from usine.contrats.trace import EntreeTrace, TypeTrace
from usine.contrats.versions import CLE_VERSION, CONTRATS_VERSION
from usine.ports import Consultation

RACINE_DEPOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class CasConsultation:
    """Consultation d'un Passage d'essai publié, et une Entité qu'il contient."""

    consultation: Consultation
    entite: str
    passage_classification_initiale: str
    """`passage_id` du dernier Passage publié, qui a fait la classification initiale."""
    url_attendue: bool
    """`url_ticket` rend une URL (sinon `None`, Mode repli)."""
    avec_sorties: bool = False
    """Le Passage porte Prévisions, Risque, trace et sorties LLM pour `entite`."""


PASSAGE_CLASSIFICATION_INITIALE = "20261012T093000Z-c0ffef"
"""Copie plus tardive du Passage d'essai, marquée `classification_initiale`."""


@functools.cache
def _passage_publie() -> tuple[Path, Path]:
    """Publie le Passage d'essai une fois ; renvoie (racine, répertoire du Passage)."""
    racine = Path(tempfile.mkdtemp(prefix="contrat-consultation-"))
    atexit.register(shutil.rmtree, racine, ignore_errors=True)
    for repertoire in ("config", "gabarits"):
        shutil.copytree(RACINE_DEPOT / repertoire, racine / repertoire)
    # Programme réduit figé (2 Entités) : garde la durée et les attendus de l'essai.
    shutil.copyfile(
        RACINE_DEPOT / "tests/unit/generateur/programme_reduit.yaml",
        racine / "config" / "programme.yaml",
    )
    programme = charger_yaml(racine / "config" / "programme.yaml", ConfigProgramme)
    generer_journal(programme, 42, date(2026, 10, 12), racine)
    lance = lancer_rapport(
        racine,
        date(2026, 10, 9),
        lambda: datetime(2026, 10, 12, 7, 30, tzinfo=UTC),
        lambda: "c0ffee",
    )
    copie = lance.repertoire.parent / PASSAGE_CLASSIFICATION_INITIALE
    shutil.copytree(lance.repertoire, copie)
    manifeste = json.loads((copie / "manifeste.json").read_text(encoding="utf-8"))
    manifeste |= {
        "passage_id": PASSAGE_CLASSIFICATION_INITIALE,
        "horodatage_fin": "2026-10-12T09:30:00Z",
        "classification_initiale": True,
    }
    (copie / "manifeste.json").write_text(json.dumps(manifeste), encoding="utf-8")
    return racine, lance.repertoire


def _url_jira(racine: Path) -> str:
    return charger_yaml(racine / "config" / "jira.yaml", ConfigJira).url_site


def passage_publie() -> CasConsultation:
    """`ConsultationPassage` sur le Passage publié, avec l'URL Jira du dépôt."""
    racine, repertoire = _passage_publie()
    consultation = ConsultationPassage(
        repertoire, racine_passages=racine / "sorties" / "passages", url_jira=_url_jira(racine)
    )
    return CasConsultation(
        consultation, "ENT-A", PASSAGE_CLASSIFICATION_INITIALE, url_attendue=True
    )


def passage_mode_repli() -> CasConsultation:
    """`ConsultationPassage` sur le même Passage, en Mode repli (`url_jira=None`)."""
    racine, repertoire = _passage_publie()
    consultation = ConsultationPassage(
        repertoire, racine_passages=racine / "sorties" / "passages", url_jira=None
    )
    return CasConsultation(
        consultation, "ENT-A", PASSAGE_CLASSIFICATION_INITIALE, url_attendue=False
    )


def _ecrire_json[T](chemin: Path, manifeste: ManifestePassage, contenu: T) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    enveloppe = EnveloppeFichier[T](
        passage_id=manifeste.passage_id, date_arrete=manifeste.date_arrete, contenu=contenu
    )
    chemin.write_text(enveloppe.model_dump_json(), encoding="utf-8")


def _completer_palier_2(repertoire: Path, entite: str) -> None:
    """Passe le manifeste en Palier 2 et écrit Prévisions, trace et sorties LLM de `entite`."""
    chemin_manifeste = repertoire / "manifeste.json"
    donnees = json.loads(chemin_manifeste.read_text(encoding="utf-8"))
    donnees["palier"] = 2
    chemin_manifeste.write_text(json.dumps(donnees), encoding="utf-8")
    manifeste = ManifestePassage.model_validate(donnees)
    jour = manifeste.date_arrete
    grille = manifeste.version_grille
    # Anomalie ouverte de l'Entité, lue avant d'écrire la classification.
    ouvertes = ConsultationPassage(repertoire).anomalies(entite=entite).anomalies
    if not ouvertes:  # pragma: no cover - garde de la fixture
        raise AssertionError(f"aucune Anomalie ouverte {entite} dans le Passage d'essai")
    cle = ouvertes[0].cle_ticket
    prevision = Prevision(
        date_arrete=jour,
        entite=entite,
        methode=MethodePrevision.baseline,
        statut=StatutPrevision.sortie_projetee,
        date_sortie_estimee=jour + timedelta(days=14),
        probabilite_numerateur=3,
        probabilite_denominateur=4,
        horizon_jours_ouvres=20,
        facteurs=(
            FacteurExplicatif(
                nom="stock", libelle="Stock de bloquantes", numerateur=12, denominateur=1
            ),
        ),
        version_grille=grille,
    )
    risque = RisqueEntreeRouge(
        date_arrete=jour,
        entite="ENT-A",
        indicateur=CodeIndicateur.ind_1,
        date_franchissement_estimee=jour + timedelta(days=7),
        horizon_jours_ouvres=20,
        numerateur=4,
        denominateur=1,
        seuil_numerateur=5,
        seuil_denominateur=1,
        version_grille=grille,
    )
    _ecrire_json(
        repertoire / "previsions.json",
        manifeste,
        ContenuPrevisions(previsions=(prevision,), risques=(risque,)),
    )
    trace = EntreeTrace(
        type_trace=TypeTrace.prevision,
        horodatage=manifeste.horodatage_fin,
        passage_id=manifeste.passage_id,
        date_arrete=jour,
        entite=entite,
        version_grille=grille,
        version_donnees=manifeste.version_donnees,
        entree_pseudonymisee="entrée",
        sortie="sortie",
    )
    (repertoire / "trace").mkdir(exist_ok=True)
    (repertoire / "trace" / "previsions.jsonl").write_text(
        trace.model_dump_json() + "\n", encoding="utf-8"
    )
    _ecrire_json(
        repertoire / "llm" / "explications.json",
        manifeste,
        (
            SortieExplication(
                date_arrete=jour,
                entite=entite,
                texte="Texte.",
                citations=(cle,),
                brouillon_commentaire="Brouillon.",
            ),
        ),
    )
    _ecrire_json(
        repertoire / "llm" / "narrations.json",
        manifeste,
        (SortieNarration(date_arrete=jour, entite=entite, texte="Narration."),),
    )
    _ecrire_json(
        repertoire / "llm" / "classification.json",
        manifeste,
        (SortieClassification(cle_ticket=cle, cause_racine=CauseRacine.parametrage),),
    )
    pl.DataFrame(
        {
            "date": [jour],
            "entite": [entite],
            "cause_racine": ["parametrage"],
            "nombre": [1],
            "part": [1.0],
        },
        schema=dict(SCHEMA_REPARTITION_CAUSES.colonnes),
    ).write_parquet(
        repertoire / "repartition_causes.parquet", metadata={CLE_VERSION: CONTRATS_VERSION}
    )


@functools.cache
def _passage_palier_2() -> tuple[Path, Path]:
    """Copie du Passage d'essai sous une racine de Passages distincte, complétée en Palier 2.

    La copie marquée `classification_initiale` l'accompagne, intacte.
    """
    _, repertoire = _passage_publie()
    racine_passages = Path(tempfile.mkdtemp(prefix="contrat-consultation-p2-")) / "passages"
    atexit.register(shutil.rmtree, racine_passages.parent, ignore_errors=True)
    cible_date = racine_passages / repertoire.parent.name
    cible = cible_date / repertoire.name
    shutil.copytree(repertoire, cible)
    shutil.copytree(
        repertoire.parent / PASSAGE_CLASSIFICATION_INITIALE,
        cible_date / PASSAGE_CLASSIFICATION_INITIALE,
    )
    # ENT-B (Scénario B, enlisée) a des Anomalies ouvertes à la Date d'arrêté ; sur le
    # Programme réduit, ENT-A n'en a plus (Story 4.5 : les bloquantes scriptées de B prennent
    # les créations de chaque semaine).
    _completer_palier_2(cible, "ENT-B")
    return racine_passages, cible


def passage_palier_2() -> CasConsultation:
    """`ConsultationPassage` sur un Passage Palier 2 complet (Prévisions, trace, sorties LLM)."""
    racine, _ = _passage_publie()
    racine_passages, repertoire = _passage_palier_2()
    consultation = ConsultationPassage(
        repertoire, racine_passages=racine_passages, url_jira=_url_jira(racine)
    )
    return CasConsultation(
        consultation,
        "ENT-B",
        PASSAGE_CLASSIFICATION_INITIALE,
        url_attendue=True,
        avec_sorties=True,
    )


FABRIQUES: list[tuple[str, Callable[[], CasConsultation]]] = [
    ("passage_publie", passage_publie),
    ("passage_mode_repli", passage_mode_repli),
    ("passage_palier_2", passage_palier_2),
]
