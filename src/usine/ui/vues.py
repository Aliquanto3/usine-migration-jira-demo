"""Vues JSON du cadre commun de l'UI web (AD-25), modèles locaux à `ui/`, pas des contrats.

Le navigateur affiche ces valeurs sans les calculer ni les formater (AD-9) : les libellés
arrivent déjà écrits. Les vues des écrans (carte, détail, …) s'ajoutent ici dans les Stories
7.14 à 7.16.
"""

from datetime import UTC
from typing import Literal

from markdown_it import MarkdownIt
from pydantic import BaseModel, ConfigDict

from usine.contrats.format import formater_date
from usine.contrats.passage import ManifestePassage
from usine.ui.textes import BANDEAU_REPLI

LIBELLE_MODE_REEL = "Mode réel"
LIBELLE_MODE_REPLI = "Mode repli"

_MARKDOWN = MarkdownIt("commonmark", {"html": False})  # aucun HTML brut ne traverse


class VueCadre(BaseModel):
    """Ce que l'en-tête, la pastille de mode et les bandeaux du cadre affichent."""

    model_config = ConfigDict(frozen=True)

    mode: Literal["reel", "repli"]
    libelle_mode: str
    bandeau_repli_html: str | None
    """`app.BANDEAU_REPLI` rendu en HTML en ligne (`<strong>`, `<code>`), texte constant."""
    passage_publie: str | None
    """« Passage publié · JJ/MM/AAAA HH:MM UTC », ou `None` s'il n'y a pas de Passage affiché."""
    erreur: str | None
    """Lecture impossible (manifeste, racine) : détail affiché dans le bandeau d'erreur."""


def libelle_passage(manifeste: ManifestePassage) -> str:
    """« Passage publié · JJ/MM/AAAA HH:MM UTC », fin du Passage (convention de `rendu.commun`)."""
    fin = manifeste.horodatage_fin.astimezone(UTC)
    return f"Passage publié · {formater_date(fin.date())} {fin:%H:%M} UTC"


def vue_cadre(*, repli: bool, manifeste: ManifestePassage | None, erreur: str | None) -> VueCadre:
    """Vue du cadre pour le mode courant et le Passage affiché (aucune bascule automatique)."""
    return VueCadre(
        mode="repli" if repli else "reel",
        libelle_mode=LIBELLE_MODE_REPLI if repli else LIBELLE_MODE_REEL,
        bandeau_repli_html=_MARKDOWN.renderInline(BANDEAU_REPLI) if repli else None,
        passage_publie=None if manifeste is None else libelle_passage(manifeste),
        erreur=erreur,
    )


# --- Carte météo, détail d'une Entité et livrables (Story 7.14) ---
# Valeurs déjà formatées : le navigateur les affiche telles quelles (AD-9, AD-25).

NomCouleur = Literal["vert", "jaune", "orange", "rouge"]
NomLivrable = Literal["rapport_xlsx", "rapport_pptx"]


class _Vue(BaseModel):
    model_config = ConfigDict(frozen=True)


class VueTicket(_Vue):
    """Clé de ticket : lien Jira (`url`) ou texte simple (`url` à `None`, Mode repli, FR-29)."""

    cle: str
    url: str | None
    nom_accessible: str | None
    """« DEMO-1 (nouvel onglet) » quand `url` est connue, sinon `None`."""


class VueLien(_Vue):
    """Lien interne vers un autre écran."""

    libelle: str
    url: str


class VueMeteo(_Vue):
    """Pastille météo : nom de la couleur (teinte de la feuille de style) et libellé écrit."""

    couleur: NomCouleur
    libelle: str


class VueTableau(_Vue):
    """Tableau de cellules en texte simple."""

    colonnes: list[str]
    lignes: list[list[str]]


class VueComptage(_Vue):
    """Tuile de comptage : nombre d'Entités de la couleur."""

    meteo: VueMeteo
    nombre: int


class VueOptionFiltre(_Vue):
    """Option du filtre météo ; `valeur` vaut `toutes` ou le nom de la couleur."""

    valeur: str
    libelle: str
    message_vide: str


class VueFiltre(_Vue):
    """Filtre météo de la carte et textes de la région `role="status"`."""

    libelle: str
    options: list[VueOptionFiltre]
    annonce_une: str
    annonce_plusieurs: str
    """Contient `{n}`, remplacé par le nombre de lignes affichées."""


class VueLigneCarte(_Vue):
    """Une Entité de la carte."""

    entite: str
    meteo: VueMeteo
    tendance: str
    regle_principale: str
    tickets: list[VueTicket]
    suite: str | None
    """« +N » : tickets en cause non listés ; `None` s'il n'y en a pas."""
    url_detail: str
    libelle_detail: str


class VueLivrable(_Vue):
    """Livrable du Passage affiché ; `url` vaut `None` s'il est absent (aucun lien)."""

    nom: NomLivrable
    libelle: str
    fichier: str
    description: str
    """Type et taille (« Excel (.xlsx) · 96 Ko ») ; vide si le livrable est absent."""
    url: str | None
    absent: str | None


class VueCarte(_Vue):
    """Écran Carte météo."""

    erreur: str | None
    message: str | None
    """Remplace la carte (aucun Passage, aucune Météo)."""
    lien_message: VueLien | None
    sous_titre: str | None
    comptages: list[VueComptage]
    filtre: VueFiltre | None
    legende: str | None
    lignes: list[VueLigneCarte]
    livrables: list[VueLivrable]
    vide: str = "—"
    """Contenu d'une cellule sans valeur (aucun ticket)."""


class VueRegle(_Vue):
    """Règle déclenchante et tous ses tickets en cause."""

    regle: str
    tickets: list[VueTicket]
    """Tickets affichés d'emblée."""
    tickets_suite: list[VueTicket]
    """Tickets dépliés par le bouton `libelle_suite`."""
    libelle_suite: str | None
    """« +N » ; `None` si `tickets_suite` est vide."""


class VueLigneKpi(_Vue):
    libelle: str
    valeur: str


class VueBloc(_Vue):
    """Paragraphe d'un bloc de texte : titre, texte, liste, sous-liste titrée et note."""

    titre: str | None = None
    texte: str | None = None
    items: list[str] = []
    sous_titre: str | None = None
    sous_items: list[str] = []
    note: str | None = None


class VueSection(_Vue):
    """Prévision ou Risque : message à la place du contenu, blocs ou tableau."""

    titre: str
    message: str | None
    blocs: list[VueBloc]
    tableau: VueTableau | None


class VueSegmentTexte(_Vue):
    """Morceau du texte d'une Explication : texte brut ou clé de ticket citée."""

    texte: str
    ticket: VueTicket | None


class VueExplication(_Vue):
    segments: list[VueSegmentTexte]
    citations: list[VueTicket]
    titre_citations: str
    phrases_retirees: str | None
    statut: str
    statut_code: str
    """Valeur de `StatutControle` (teinte du badge)."""


class VueExplications(_Vue):
    titre: str
    message: str | None
    explications: list[VueExplication]


class VueOptionPalier(_Vue):
    valeur: Literal[1, 2]
    libelle: str
    actif: bool


class VueSegmentPalier(_Vue):
    """Segment Palier 1 / Palier 2 (Passage de Palier 2 seulement) et sa légende."""

    options: list[VueOptionPalier]
    legende: str


class VueDetail(_Vue):
    """Écran Détail d'une Entité."""

    erreur: str | None
    message: str | None
    """Remplace le détail (aucun Passage, aucune Météo, Entité absente)."""
    lien_message: VueLien | None
    entite: str | None
    entites: list[VueLien]
    """Entités du Passage dans l'ordre de la carte ; `libelle` est l'Entité."""
    lien_carte: VueLien
    palier: Literal[1, 2]
    segment_palier: VueSegmentPalier | None
    meteo: VueMeteo | None
    regles: list[VueRegle]
    aucune_regle: str | None
    kpi: list[VueLigneKpi]
    aucun_kpi: str | None
    prevision: VueSection | None
    risque: VueSection | None
    explication: VueExplications | None
    vide: str = "—"
    """Contenu d'une cellule sans valeur (aucun ticket)."""
