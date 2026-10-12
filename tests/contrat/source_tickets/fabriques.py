"""Fabriques des adaptateurs de `SourceTickets` soumis à la suite de contrat.

Chaque lane ajoute ici la fabrique de son adaptateur (Journal, Jira Cloud, Jira DC).
"""

import atexit
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from tests.doublures import SourceEnMemoire
from tests.unit.adaptateurs.jira_cloud.outils import (
    evenements_attendus as evenements_attendus_cloud,
)
from tests.unit.adaptateurs.jira_cloud.outils import source_fixtures
from tests.unit.adaptateurs.jira_dc.outils import (
    evenements_attendus as evenements_attendus_dc,
)
from tests.unit.adaptateurs.jira_dc.outils import source_fixtures_dc
from tests.unit.adaptateurs.journal.outils import cle_jira, manifeste_pour
from usine.adaptateurs.journal import SourceJournal
from usine.config import charger_yaml
from usine.contrats.config import ConfigProgramme
from usine.contrats.evenements import Evenement, NatureEvenement, SourceEvenement
from usine.contrats.tickets import Champ, TypeTicket
from usine.generateur.journal import generer, serialiser_journal
from usine.ports import SourceTickets


@dataclass(frozen=True)
class CasSourceTickets:
    """Adaptateur à éprouver et événements qu'il doit rendre."""

    source: SourceTickets
    evenements_attendus: tuple[Evenement, ...]


T0 = datetime(2026, 10, 5, 8, 0, tzinfo=UTC)


def _evenement(
    rang: int,
    cle: str,
    type_ticket: TypeTicket,
    decalage_heures: int,
    nature: NatureEvenement,
    champ: Champ | None = None,
    de: str | None = None,
    vers: str | None = None,
) -> Evenement:
    return Evenement(
        id_evenement=f"J-{rang}",
        cle_ticket=cle,
        type_ticket=type_ticket,
        horodatage=T0 + timedelta(hours=decalage_heures),
        nature=nature,
        champ=champ,
        de=de,
        vers=vers,
        source=SourceEvenement.journal,
    )


def evenements_essai() -> tuple[Evenement, ...]:
    """Petit flux couvrant création, attributs initiaux, transition et Cas de test."""
    anomalie, test = TypeTicket.anomalie, TypeTicket.cas_de_test
    creation, modif = NatureEvenement.creation, NatureEvenement.modification_champ
    return (
        _evenement(1, "DEMO-1", anomalie, 0, creation),
        _evenement(2, "DEMO-1", anomalie, 0, modif, Champ.statut, None, "nouvelle"),
        _evenement(3, "DEMO-1", anomalie, 0, modif, Champ.gravite, None, "bloquante"),
        _evenement(4, "DEMO-1", anomalie, 0, modif, Champ.entite, None, "ENT-A"),
        _evenement(5, "DEMO-2", test, 3, creation),
        _evenement(6, "DEMO-2", test, 3, modif, Champ.statut_test, None, "non_execute"),
        _evenement(
            7,
            "DEMO-1",
            anomalie,
            26,
            NatureEvenement.transition,
            Champ.statut,
            "nouvelle",
            "en_correction",
        ),
        _evenement(8, "DEMO-2", test, 50, modif, Champ.statut_test, "non_execute", "ko"),
        _evenement(
            9,
            "DEMO-1",
            anomalie,
            75,
            NatureEvenement.transition,
            Champ.statut,
            "en_correction",
            "fermee",
        ),
    )


def fabrique_source_en_memoire() -> CasSourceTickets:
    """Doublure en mémoire, alimentée dans le désordre."""
    attendus = evenements_essai()
    return CasSourceTickets(SourceEnMemoire(reversed(attendus)), attendus)


def fabrique_journal_genere() -> CasSourceTickets:
    """Doublure en mémoire sur le Journal du mini-générateur (Story 0.3), graine 42."""
    config = charger_yaml(
        Path(__file__).resolve().parents[3] / "tests/unit/generateur/programme_reduit.yaml",
        ConfigProgramme,
    )
    attendus = generer(config, 42, date(2026, 10, 12)).evenements
    return CasSourceTickets(SourceEnMemoire(attendus), attendus)


def fabrique_journal() -> CasSourceTickets:
    """`SourceJournal` sur le Journal sérialisé du mini-générateur, graine 42."""
    config = charger_yaml(
        Path(__file__).resolve().parents[3] / "tests/unit/generateur/programme_reduit.yaml",
        ConfigProgramme,
    )
    generation = generer(config, 42, date(2026, 10, 12))
    repertoire = Path(tempfile.mkdtemp(prefix="usine-journal-"))
    atexit.register(shutil.rmtree, repertoire, True)
    chemin = repertoire / "journal.jsonl"
    chemin.write_bytes(serialiser_journal(generation))
    return CasSourceTickets(SourceJournal(chemin), generation.evenements)


def fabrique_journal_correspondance() -> CasSourceTickets:
    """`SourceJournal` du mini-générateur lu aux clés Jira (`DEMO-n` → `DEMO-(n+100000)`)."""
    config = charger_yaml(
        Path(__file__).resolve().parents[3] / "tests/unit/generateur/programme_reduit.yaml",
        ConfigProgramme,
    )
    generation = generer(config, 42, date(2026, 10, 12))
    repertoire = Path(tempfile.mkdtemp(prefix="usine-journal-"))
    atexit.register(shutil.rmtree, repertoire, True)
    chemin = repertoire / "journal.jsonl"
    chemin.write_bytes(serialiser_journal(generation))
    manifeste = manifeste_pour(generation.entete, generation.evenements)
    attendus = tuple(
        e.model_copy(update={"cle_ticket": cle_jira(e.cle_ticket)}) for e in generation.evenements
    )
    return CasSourceTickets(SourceJournal(chemin, manifeste), attendus)


def fabrique_jira_cloud() -> CasSourceTickets:
    """`SourceJiraCloud` sur les fixtures `tests/fixtures/jira_cloud/source_*`, sans réseau."""
    return CasSourceTickets(source_fixtures(), evenements_attendus_cloud())


def fabrique_jira_dc() -> CasSourceTickets:
    """`SourceJiraDC` sur les fixtures `tests/fixtures/jira_dc/source_*`, sans réseau."""
    return CasSourceTickets(source_fixtures_dc(), evenements_attendus_dc())


FABRIQUES: list[tuple[str, Callable[[], CasSourceTickets]]] = [
    ("source_en_memoire", fabrique_source_en_memoire),
    ("journal_genere", fabrique_journal_genere),
    ("journal", fabrique_journal),
    ("journal_correspondance", fabrique_journal_correspondance),
    ("jira_cloud", fabrique_jira_cloud),
    ("jira_dc", fabrique_jira_dc),
]
