"""Vues JSON du cadre commun de l'UI web (AD-25), modèles locaux à `ui/`, pas des contrats.

Le navigateur affiche ces valeurs sans les calculer ni les formater (AD-9) : les libellés
arrivent déjà écrits. Les vues des écrans (carte, détail, …) s'ajoutent ici dans les Stories
7.14 à 7.16.
"""

from typing import Literal

from markdown_it import MarkdownIt
from pydantic import BaseModel, ConfigDict

from usine.contrats.format import formater_date
from usine.contrats.passage import ManifestePassage
from usine.ui.textes import BANDEAU_REPLI

LIBELLE_MODE_REEL = "Mode réel"
LIBELLE_MODE_REPLI = "Mode repli"

_MARKDOWN = MarkdownIt("commonmark")


class VueCadre(BaseModel):
    """Ce que l'en-tête, la pastille de mode et les bandeaux du cadre affichent."""

    model_config = ConfigDict(frozen=True)

    mode: Literal["reel", "repli"]
    libelle_mode: str
    bandeau_repli_html: str | None
    """`app.BANDEAU_REPLI` rendu en HTML en ligne (`<strong>`, `<code>`), texte constant."""
    passage_publie: str | None
    """« Passage publié · JJ/MM/AAAA HH:MM », ou `None` s'il n'y a pas de Passage affiché."""
    erreur: str | None
    """Lecture impossible (manifeste, racine) : détail affiché dans le bandeau d'erreur."""


def libelle_passage(manifeste: ManifestePassage) -> str:
    """« Passage publié · JJ/MM/AAAA HH:MM », date et heure (UTC) de fin du Passage."""
    fin = manifeste.horodatage_fin
    return f"Passage publié · {formater_date(fin.date())} {fin:%H:%M}"


def vue_cadre(*, repli: bool, manifeste: ManifestePassage | None, erreur: str | None) -> VueCadre:
    """Vue du cadre pour le mode courant et le Passage affiché (aucune bascule automatique)."""
    return VueCadre(
        mode="repli" if repli else "reel",
        libelle_mode=LIBELLE_MODE_REPLI if repli else LIBELLE_MODE_REEL,
        bandeau_repli_html=_MARKDOWN.renderInline(BANDEAU_REPLI) if repli else None,
        passage_publie=None if manifeste is None else libelle_passage(manifeste),
        erreur=erreur,
    )
