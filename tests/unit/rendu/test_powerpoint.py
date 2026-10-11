"""PowerPoint du Rapport : slide « Carte météo » sur le gabarit neutre (Story 0.6)."""

import io
from datetime import UTC, datetime
from pathlib import Path

import pytest
import time_machine
from pptx import Presentation

from tests.unit.chaine.environnement import DATE_ARRETE, RACINE_DEPOT
from usine.consultation.passage import ConsultationPassage
from usine.contrats.erreurs import UsineErreur
from usine.rendu.powerpoint import rendre_powerpoint

NOM = f"rapport-{DATE_ARRETE.isoformat()}.pptx"
GABARIT = RACINE_DEPOT / "gabarits" / "rapport.pptx"
LIBELLES = {"vert": "Vert", "jaune": "Jaune", "orange": "Orange", "rouge": "Rouge"}


def _contenu(octets: bytes) -> tuple[list[str], list[list[str]]]:
    presentation = Presentation(io.BytesIO(octets))
    assert len(presentation.slides) == 1
    textes: list[str] = []
    tableau: list[list[str]] = []
    for forme in presentation.slides[0].shapes:
        if forme.has_text_frame:
            textes.append(forme.text_frame.text)
        if forme.has_table:
            tableau = [[cellule.text for cellule in ligne.cells] for ligne in forme.table.rows]
    return textes, tableau


def test_gabarit_neutre() -> None:
    presentation = Presentation(str(GABARIT))
    assert (presentation.slide_width, presentation.slide_height) == (12_192_000, 6_858_000)
    assert len(presentation.slides) == 0
    assert presentation.core_properties.author == "Usine de migration (démonstrateur)"


def test_slide_carte_meteo(passage: Path) -> None:
    textes, tableau = _contenu((passage / NOM).read_bytes())
    assert any("09/10/2026" in texte for texte in textes)
    meteos = ConsultationPassage(passage).meteo()
    assert tableau[0] == ["Entité", "Météo"]
    assert tableau[1:] == [[m.entite, LIBELLES[m.couleur.value]] for m in meteos]


def test_proprietes_fixes(passage: Path) -> None:
    proprietes = Presentation(str(passage / NOM)).core_properties
    minuit = datetime(2026, 10, 9, tzinfo=UTC).replace(tzinfo=None)  # relu sans fuseau
    assert (proprietes.created, proprietes.modified) == (minuit, minuit)
    assert proprietes.author == "Usine de migration (démonstrateur)"
    assert proprietes.title == "Rapport quotidien du 09/10/2026"


def test_rendu_deterministe(passage: Path) -> None:
    consultation = ConsultationPassage(passage)
    gabarit = GABARIT.read_bytes()
    with time_machine.travel(datetime(2026, 10, 12, 8, tzinfo=UTC), tick=False):
        premier = rendre_powerpoint(consultation, gabarit, DATE_ARRETE)
    with time_machine.travel(datetime(2026, 11, 3, 17, 45, tzinfo=UTC), tick=False):
        second = rendre_powerpoint(consultation, gabarit, DATE_ARRETE)
    assert premier == second


def test_sans_meteo(tmp_path: Path) -> None:
    """Passage sans Météo : titre daté et tableau réduit à ses en-têtes."""
    octets = rendre_powerpoint(ConsultationPassage(tmp_path), GABARIT.read_bytes(), DATE_ARRETE)
    textes, tableau = _contenu(octets)
    assert any("09/10/2026" in texte for texte in textes)
    assert tableau == [["Entité", "Météo"]]


def test_gabarit_illisible(passage: Path) -> None:
    with pytest.raises(UsineErreur, match="gabarit"):
        rendre_powerpoint(ConsultationPassage(passage), b"pas un pptx", DATE_ARRETE)


def test_couleurs_des_cellules(passage_jaune_rouge: ConsultationPassage) -> None:
    """Teinte et texte de la cellule Météo : texte foncé sur le jaune, blanc sur le rouge."""
    octets = rendre_powerpoint(passage_jaune_rouge, GABARIT.read_bytes(), DATE_ARRETE)
    slide = Presentation(io.BytesIO(octets)).slides[0]
    tableau = next(forme.table for forme in slide.shapes if forme.has_table)
    attendus = {1: ("Jaune", "F9A825", "212121"), 2: ("Rouge", "C62828", "FFFFFF")}
    for ligne, (libelle, teinte, texte) in attendus.items():
        cellule = tableau.cell(ligne, 1)
        assert cellule.text == libelle
        assert str(cellule.fill.fore_color.rgb) == teinte
        assert str(cellule.text_frame.paragraphs[0].runs[0].font.color.rgb) == texte
