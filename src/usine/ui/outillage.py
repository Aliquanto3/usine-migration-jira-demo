"""Écran « Ce qu'il faut pour le faire en vrai » : fiche outillage de la Story 8.1 (sans Streamlit).

La fiche vit dans `docs/fiche-outillage.md`, sous la racine de l'UI ; elle est lue en UTF-8
(BOM toléré) à chaque affichage et rendue telle quelle, en lecture seule. Aucun texte de la
fiche n'est recopié ici : seuls le chemin du fichier et les messages de l'écran le sont.
"""

from pathlib import Path

FICHIER_FICHE = Path("docs/fiche-outillage.md")
"""Fiche outillage, relative à la racine de l'UI."""

FICHE_ABSENTE = (
    f"Fiche absente : `{FICHIER_FICHE.as_posix()}` (Story 8.1) ; l'outillage à demander ne peut"
    " pas être affiché."
)
"""Avertissement affiché quand la fiche n'existe pas sous la racine."""

LEGENDE = f"Fiche `{FICHIER_FICHE.as_posix()}` (Story 8.1), affichée en lecture seule."
"""Légende de l'écran, qui cite le fichier source."""


def lire_fiche(racine: Path) -> str | None:
    """Contenu de la fiche, ou `None` si elle n'existe pas.

    Laisse remonter `OSError` (droits, répertoire) et `UnicodeDecodeError` (octets non UTF-8).
    """
    try:
        return (racine / FICHIER_FICHE).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return None
