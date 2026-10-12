"""Écran Pseudonymisation : descriptions à comparer, alignement sur `Consultation`."""

import inspect
from pathlib import Path

import polars as pl

from usine.contrats.tickets import SCHEMA_TICKET_TEXTE
from usine.ports.consultation import Consultation
from usine.ui.cli import consultation_repli
from usine.ui.pseudonymisation import LecturePseudonymisation, descriptions


def test_lecture_alignee_sur_consultation() -> None:
    assert inspect.signature(LecturePseudonymisation.textes_tickets) == inspect.signature(
        Consultation.textes_tickets
    )


def _table(lignes: list[tuple[str, str | None]]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "cle_ticket": [cle for cle, _ in lignes],
            "type_ticket": ["anomalie"] * len(lignes),
            "entite": ["ENT-A"] * len(lignes),
            "titre": ["titre"] * len(lignes),
            "description": [description for _, description in lignes],
        },
        schema=dict(SCHEMA_TICKET_TEXTE.colonnes),
    )


def test_descriptions_non_vides_dans_l_ordre() -> None:
    table = _table([("DEMO-2", "deux"), ("DEMO-1", None), ("DEMO-3", "  "), ("DEMO-4", "quatre")])
    assert list(descriptions(table).items()) == [("DEMO-2", "deux"), ("DEMO-4", "quatre")]


def test_aucune_description() -> None:
    assert descriptions(_table([("DEMO-1", None), ("DEMO-2", "")])) == {}
    assert descriptions(_table([])) == {}


def test_copie_du_mode_repli(racine_publiee: Path) -> None:
    consultation = consultation_repli(racine_publiee)
    assert consultation is not None
    textes = descriptions(consultation.textes_tickets())
    assert textes
    assert all(cle.startswith("DEMO-") for cle in textes)
