"""PowerPoint du Rapport quotidien : une slide « Carte météo » (Story 0.6, amorce de FR-27).

La slide est construite sur le gabarit neutre `gabarits/rapport.pptx` (disposition « Title
Only ») : un titre avec la Date d'arrêté et un tableau Entité × Météo, une ligne par Entité
dans l'ordre de `consultation.meteo()`.
"""

import io
from datetime import date

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.presentation import Presentation as Presentation_
from pptx.util import Emu, Pt

from usine.contrats.erreurs import UsineErreur
from usine.contrats.format import formater_date
from usine.ports.consultation import Consultation
from usine.rendu.commun import (
    AUTEUR,
    LIBELLES_COULEURS,
    TEINTES_COULEURS,
    TEXTES_COULEURS,
    archive_deterministe,
    horodatage_fixe,
    titre_document,
)

DISPOSITION = "Title Only"
"""Disposition du gabarit utilisée pour la slide."""

MARGE = Emu(457_200)
"""Marge latérale du tableau (1,27 cm)."""

HAUT_TABLEAU = Emu(1_600_200)
"""Position verticale du tableau, sous le titre."""

HAUTEUR_LIGNE = Emu(370_840)


def _rvb(hexadecimal: str) -> RGBColor:
    rvb: RGBColor = RGBColor.from_string(hexadecimal)  # type: ignore[no-untyped-call]
    return rvb


def _gabarit(octets: bytes) -> Presentation_:
    try:
        return Presentation(io.BytesIO(octets))
    except Exception as exc:
        raise UsineErreur(f"gabarit PowerPoint illisible ({type(exc).__name__} : {exc})") from exc


def rendre_powerpoint(consultation: Consultation, gabarit: bytes, date_arrete: date) -> bytes:
    """Octets de la présentation du Passage à la Date d'arrêté, déterministes.

    Sans Météo à cette date, le tableau ne porte que sa ligne d'en-têtes.
    """
    meteos = consultation.meteo(date_arrete)
    presentation = _gabarit(gabarit)
    if len(presentation.slides) != 0:
        raise UsineErreur(
            f"gabarit PowerPoint : {len(presentation.slides)} slide(s), aucune attendue"
        )
    disposition = presentation.slide_layouts.get_by_name(DISPOSITION)
    if disposition is None:
        raise UsineErreur(f"gabarit PowerPoint : disposition « {DISPOSITION} » absente")
    slide = presentation.slides.add_slide(disposition)
    titre = slide.shapes.title
    if titre is None:
        raise UsineErreur(f"gabarit PowerPoint : disposition « {DISPOSITION} » sans titre")
    titre.text = f"Carte météo du {formater_date(date_arrete)}"

    largeur = presentation.slide_width - 2 * MARGE
    forme = slide.shapes.add_table(
        len(meteos) + 1,
        2,
        MARGE,
        HAUT_TABLEAU,
        Emu(largeur),
        Emu(HAUTEUR_LIGNE * (len(meteos) + 1)),
    )
    tableau = forme.table
    tableau.columns[0].width = Emu(largeur // 2)
    tableau.columns[1].width = Emu(largeur - largeur // 2)
    tableau.cell(0, 0).text = "Entité"
    tableau.cell(0, 1).text = "Météo"
    for ligne, meteo in enumerate(meteos, start=1):
        tableau.cell(ligne, 0).text = meteo.entite
        cellule = tableau.cell(ligne, 1)
        cellule.text = LIBELLES_COULEURS[meteo.couleur]
        cellule.fill.solid()
        cellule.fill.fore_color.rgb = _rvb(TEINTES_COULEURS[meteo.couleur])
        police = cellule.text_frame.paragraphs[0].runs[0].font
        police.bold = True
        police.size = Pt(16)
        police.color.rgb = _rvb(TEXTES_COULEURS[meteo.couleur])

    proprietes = presentation.core_properties
    proprietes.author = AUTEUR
    proprietes.last_modified_by = AUTEUR
    proprietes.title = titre_document(date_arrete)
    proprietes.revision = 1
    proprietes.created = horodatage_fixe(date_arrete)
    proprietes.modified = horodatage_fixe(date_arrete)
    proprietes.last_printed = horodatage_fixe(date_arrete)
    tampon = io.BytesIO()
    presentation.save(tampon)
    return archive_deterministe(tampon.getvalue(), date_arrete)
