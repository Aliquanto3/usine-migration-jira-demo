"""Écran « Ce qu'il faut pour le faire en vrai » : fiche outillage de la Story 8.1.

La fiche vit dans `docs/fiche-outillage.md`, sous la racine de l'UI ; elle est lue en UTF-8
(BOM toléré) à chaque affichage et rendue telle quelle, en lecture seule. Aucun texte de la
fiche n'est recopié ici : seuls le chemin du fichier et les messages de l'écran le sont.
"""

import re
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.token import Token

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


PASTILLES: dict[str, tuple[str, str]] = {
    "✅": ("oui", "Oui"),
    "⚠": ("surveiller", "À surveiller"),
    "❌": ("non", "Non"),
}
"""Marqueur de la fiche (sans sélecteur de variante) : variante de la pastille et son libellé."""

_MARQUEUR = re.compile("([✅⚠❌])️?")

_MARKDOWN = MarkdownIt("commonmark", {"html": False}).enable("table")
"""Rendu de la fiche : le HTML brut du Markdown n'est jamais interprété."""

LIBELLE_TABLEAU = "Tableau de la fiche, défilant"


def _pastille(marqueur: str) -> Token:
    variante, libelle = PASTILLES[marqueur]
    jeton = Token("html_inline", "", 0)
    jeton.content = f'<span class="pastille pastille--{variante}">{libelle}</span>'
    return jeton


def _pastilles(jetons: list[Token]) -> list[Token]:
    """Remplace chaque marqueur ✅ ⚠️ ❌ d'un texte en ligne par sa pastille de texte."""
    resultat: list[Token] = []
    for jeton in jetons:
        if jeton.type != "text" or not _MARQUEUR.search(jeton.content):
            resultat.append(jeton)
            continue
        morceaux = _MARQUEUR.split(jeton.content)
        for rang, morceau in enumerate(morceaux):
            if rang % 2:
                resultat.append(_pastille(morceau))
            elif morceau:
                texte = Token("text", "", 0)
                texte.content = morceau
                resultat.append(texte)
    return resultat


def rendre_fiche(fiche: str) -> str:
    """Fiche en HTML : cartes par section `##`, tableau défilant, pastilles de texte.

    Le titre `#` de la fiche est celui de l'écran : il n'est pas rendu. Aucun HTML brut de la
    fiche ne traverse ; seules les pastilles et les enveloppes ci-dessous sont du HTML du serveur.
    """
    jetons = _MARKDOWN.parse(fiche)
    sans_titre: list[Token] = []
    rang = 0
    while rang < len(jetons):
        jeton = jetons[rang]
        if jeton.type == "heading_open" and jeton.tag == "h1":
            rang += 3  # ouverture, contenu, fermeture
            continue
        if jeton.type == "inline" and jeton.children:
            jeton.children = _pastilles(jeton.children)
        sans_titre.append(jeton)
        rang += 1
    html = _MARKDOWN.renderer.render(sans_titre, _MARKDOWN.options, {})
    ouverture = (
        f'<div class="table-defile" role="region" tabindex="0" aria-label="{LIBELLE_TABLEAU}">'
        "<table>"
    )
    html = html.replace("<table>", ouverture).replace("</table>", "</table></div>")
    intro, *sections = html.split("<h2>")
    cartes = [intro] if intro.strip() else []
    cartes += [f"<h2>{section}" for section in sections]
    return "".join(f'<section class="carte carte--fiche">{carte}</section>' for carte in cartes)
