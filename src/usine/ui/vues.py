"""Vues JSON du cadre commun de l'UI web (AD-25), modèles locaux à `ui/`, pas des contrats.

Le navigateur affiche ces valeurs sans les calculer ni les formater (AD-9) : les libellés
arrivent déjà écrits. Les vues des écrans (carte, détail, …) s'ajoutent ici dans les Stories
7.14 à 7.16.
"""

from typing import Literal

from markdown_it import MarkdownIt
from pydantic import BaseModel, ConfigDict, Field, field_validator

from usine.contrats.format import formater_horodatage
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
    """`textes.BANDEAU_REPLI` rendu en HTML en ligne (`<strong>`, `<code>`), texte constant."""
    passage_publie: str | None
    """« Passage publié · JJ/MM/AAAA HH:MM » (heure de Paris), ou `None` sans Passage affiché."""
    erreur: str | None
    """Lecture impossible (manifeste, racine) : détail affiché dans le bandeau d'erreur."""


def libelle_passage(manifeste: ManifestePassage) -> str:
    """« Passage publié · JJ/MM/AAAA HH:MM », fin du Passage en heure de Paris (AD-11)."""
    return f"Passage publié · {formater_horodatage(manifeste.horodatage_fin, secondes=False)}"


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


# --- Lancement de la Chaîne et bouton de mode (Story 7.15) ---

EtatEtape = Literal["en_attente", "en_cours", "reussie", "sautee", "echouee"]
StatutChaine = Literal["attente", "en_cours", "terminee", "echec"]


class VueEtape(_Vue):
    """Une des 10 étapes de la Chaîne et son état."""

    numero: int
    nom: str
    description: str
    etat: EtatEtape
    libelle_etat: str
    duree: str | None
    """Durée de l'étape terminée, déjà formatée (« 0,3 s »)."""


class VueBouton(_Vue):
    """Bouton de l'écran : libellé, blocage (`aria-disabled`) et motif visible sous lui."""

    libelle: str
    bloque: bool
    motif: str | None


class VueBandeauChaine(_Vue):
    """Résultat de la dernière Chaîne : succès (`status`) ou échec (`alert`)."""

    variante: Literal["succes", "erreur"]
    texte: str
    lignes: list[str]
    """Au plus `LIGNES_ERREUR_MAX` dernières lignes de l'erreur standard (échec seulement)."""
    complement: str | None
    lien: VueLien | None


class VueLigneJournal(_Vue):
    """Ligne horodatée du journal de progression (la plus récente en premier)."""

    horodatage: str
    texte: str


class VueDernierPassage(_Vue):
    """Encart « Dernier Passage », lu dans le manifeste du Passage affiché."""

    lignes: list[str]


class VueChaine(_Vue):
    """Ce que l'écran Lancement de la Chaîne affiche à chaque sondage."""

    statut: StatutChaine
    en_cours: bool
    """Vrai tant que le sondage doit continuer."""
    intervalle_ms: int
    bouton_lancement: VueBouton
    bouton_mode: VueBouton
    mode_cible: Literal["reel", "repli"]
    """Mode que le bouton de mode demande."""
    etapes: list[VueEtape]
    terminees: int
    """Étapes terminées (réussies, sautées ou en échec) : `aria-valuenow` de la barre."""
    total: int
    compteur: str
    annonce: str
    """Texte de la région `status` ; vide quand rien de nouveau n'est à annoncer."""
    journal: list[VueLigneJournal]
    journal_vide: str
    bandeau: VueBandeauChaine | None
    erreur: str | None
    """Progression illisible ou lancement impossible (bandeau d'erreur, sondage maintenu)."""
    dernier_passage: VueDernierPassage | None
    message_dernier_passage: str


class DemandeMode(BaseModel):
    """Corps de `POST /api/mode` : le mode demandé (jamais déduit, AD-19)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: Literal["reel", "repli"]


# --- Agent, Avant / après, Pseudonymisation et Outillage (Story 7.16) ---

CodeBadge = Literal["conforme", "corrige", "rejete", "non_controle", "hors_perimetre"]
Periode = Literal["rapport", "cumul"]


class DemandeQuestion(BaseModel):
    """Corps de `POST /api/agent/question` : la question du Pilote, jamais vide."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    question: str = Field(min_length=1, max_length=2000)

    @field_validator("question")
    @classmethod
    def _non_vide(cls, valeur: str) -> str:
        texte = valeur.strip()
        if not texte:
            raise ValueError("la question est vide")
        return texte


class VueOutil(_Vue):
    """Outil de l'Agent (lecture seule) et sa description."""

    nom: str
    description: str


class VueSaisie(_Vue):
    """Saisie de la question (Mode réel seulement)."""

    libelle: str
    valeur_defaut: str
    bouton: str


class VueQuestionEnregistree(_Vue):
    """Question enregistrée : suggestion (Mode réel) ou seul moyen de questionner (Mode repli)."""

    rang: int
    question: str


class VueReponseAgent(_Vue):
    """Réponse contrôlée : `texte` vaut `None` quand le contrôle l'a rejetée (jamais affichée)."""

    question: str
    texte: str | None
    texte_masque: str | None
    badge: str
    badge_code: CodeBadge
    libelle_outils: str
    outils: list[str]
    aucun_outil: str
    mention_repli: str | None
    annonce: str


class VueAgent(_Vue):
    """Écran Agent."""

    mode: Literal["reel", "repli"]
    erreur: str | None
    message: str | None
    """Remplace l'écran (aucun Passage publié)."""
    lien_message: VueLien | None
    legende: str | None
    message_repli: str | None
    saisie: VueSaisie | None
    titre_questions: str
    questions: list[VueQuestionEnregistree]
    titre_outils: str
    outils: list[VueOutil]
    attente: str
    lien_repli: VueLien | None
    """Avec une erreur d'Agent en Mode réel : passer en Mode repli par l'écran de lancement."""


class VueCarteTemps(_Vue):
    """Grande carte « Reporting manuel » ou « Chaîne » : valeur de chaque période."""

    titre: str
    etiquette: str
    valeurs: dict[Periode, str]


class VueOptionPeriode(_Vue):
    valeur: Periode
    libelle: str


class VueAvantApres(_Vue):
    """Écran Avant / après : valeurs reçues telles quelles, aucun écart ni ratio."""

    erreur: str | None
    message: str | None
    lien_message: VueLien | None
    avertissements: list[str]
    manuel: VueCarteTemps | None
    chaine: VueCarteTemps | None
    libelle_periode: str
    periodes: list[VueOptionPeriode]
    periode: Periode
    tableau: VueTableau | None
    legende: str | None


class VuePseudonymisation(_Vue):
    """Écran Pseudonymisation : texte brut, sans surlignage (AD-11)."""

    erreur: str | None
    message: str | None
    lien_message: VueLien | None
    libelle_ticket: str
    tickets: list[str]
    ticket: VueTicket | None
    legende: str | None
    titre_original: str
    titre_pseudonymise: str
    etiquette_pseudonymise: str
    original: str | None
    pseudonymise: str | None


class VueOutillage(_Vue):
    """Écran Outillage : fiche rendue en HTML par le serveur (HTML brut désactivé)."""

    erreur: str | None
    message: str | None
    legende: str | None
    html: str | None
