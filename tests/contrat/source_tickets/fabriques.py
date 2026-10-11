"""Fabriques des adaptateurs de `SourceTickets` soumis à la suite de contrat.

Chaque lane ajoute ici la fabrique de son adaptateur (Journal, Jira Cloud, Jira DC).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from tests.doublures import SourceEnMemoire
from usine.config import charger_yaml
from usine.contrats.config import ConfigProgramme
from usine.contrats.evenements import Evenement, NatureEvenement, SourceEvenement
from usine.contrats.tickets import Champ, TypeTicket
from usine.generateur.journal import generer
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
        Path(__file__).resolve().parents[3] / "config" / "programme.yaml", ConfigProgramme
    )
    attendus = generer(config, 42, date(2026, 10, 12)).evenements
    return CasSourceTickets(SourceEnMemoire(attendus), attendus)


FABRIQUES: list[tuple[str, Callable[[], CasSourceTickets]]] = [
    ("source_en_memoire", fabrique_source_en_memoire),
    ("journal_genere", fabrique_journal_genere),
]
