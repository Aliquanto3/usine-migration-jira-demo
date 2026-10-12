"""Fabriques des adaptateurs de `Consultation` soumis à la suite de contrat.

`passage_publie` : `ConsultationPassage` sur un Passage publié par `lancer_rapport` (Journal
graine 42 du 2026-10-12, Date d'arrêté 2026-10-09), dans un répertoire temporaire supprimé à
la fin de la session. Le Passage est publié une fois ; chaque cas reçoit un lecteur neuf.
Une copie plus tardive du Passage, au manifeste réécrit avec `classification_initiale`, sert
au filtre de FR-44.
"""

import atexit
import functools
import json
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from usine.composition import generer_journal, lancer_rapport
from usine.config import charger_yaml
from usine.consultation.passage import ConsultationPassage
from usine.contrats.config import ConfigJira, ConfigProgramme
from usine.ports import Consultation

RACINE_DEPOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class CasConsultation:
    """Consultation d'un Passage d'essai publié, et une Entité qu'il contient."""

    consultation: Consultation
    entite: str
    passage_classification_initiale: str
    """`passage_id` du dernier Passage publié, qui a fait la classification initiale."""


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


def passage_publie() -> CasConsultation:
    """`ConsultationPassage` sur le Passage publié, avec l'URL Jira du dépôt."""
    racine, repertoire = _passage_publie()
    jira = charger_yaml(racine / "config" / "jira.yaml", ConfigJira)
    consultation = ConsultationPassage(
        repertoire, racine_passages=racine / "sorties" / "passages", url_jira=jira.url_site
    )
    return CasConsultation(consultation, "ENT-A", PASSAGE_CLASSIFICATION_INITIALE)


FABRIQUES: list[tuple[str, Callable[[], CasConsultation]]] = [
    ("passage_publie", passage_publie),
]
