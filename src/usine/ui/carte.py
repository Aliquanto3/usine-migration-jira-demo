"""Carte météo du dernier Passage, sans Streamlit : lignes et tableau Markdown, via `Consultation`.

L'UI ne calcule aucun chiffre : elle compare des `Couleur` (ordre de gravité) et formate les
valeurs de `Consultation` avec `contrats.format`.
"""

import re
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from fractions import Fraction
from types import MappingProxyType
from typing import Protocol
from urllib.parse import quote

from usine.contrats.format import formater_date, formater_fraction
from usine.contrats.meteo import (
    LIBELLES_COULEURS,
    Couleur,
    EvolutionMeteo,
    MeteoEntite,
    Operateur,
    RegleDeclenchante,
)
from usine.contrats.passage import ManifestePassage, chemin_fichier_passage
from usine.ui.liens import echapper_markdown, lien_ticket, vue_ticket
from usine.ui.vues import (
    NomLivrable,
    VueCarte,
    VueComptage,
    VueFiltre,
    VueLien,
    VueLigneCarte,
    VueLivrable,
    VueMeteo,
    VueOptionFiltre,
    VueTicket,
)

PASTILLES: Mapping[Couleur, str] = MappingProxyType(
    {Couleur.vert: "🟢", Couleur.jaune: "🟡", Couleur.orange: "🟠", Couleur.rouge: "🔴"}
)
"""Pastille affichée devant chaque couleur."""

AGGRAVATION = "↗"
AMELIORATION = "↘"
STABLE = "→"
INCONNUE = "—"
"""Flèche d'une couleur à J-n inconnue ; aussi la cellule vide de la carte."""

LEGENDE = (
    f"Tendance par rapport à la Météo de J-1 et de J-5 : {AGGRAVATION} aggravation,"
    f" {AMELIORATION} amélioration, {STABLE} stable, {INCONNUE} couleur inconnue à cette date."
    f" Dans les autres colonnes, {INCONNUE} signifie aucune règle ou aucun ticket."
)
"""Légende des flèches, affichée sous la carte."""

TICKETS_MAX = 3
"""Tickets en cause affichés par Entité ; les suivants sont comptés (`+N`)."""

_SYMBOLES: Mapping[Operateur, str] = MappingProxyType(
    {Operateur.superieur_ou_egal: "≥", Operateur.superieur: ">"}
)

_BARRE_NON_ECHAPPEE = re.compile(r"(?<!\\)((?:\\\\)*)\|")


class LectureCarte(Protocol):
    """Lectures de la `Consultation` dont la carte a besoin (alignées sur elle par un test)."""

    def manifeste(self) -> ManifestePassage:
        """Manifeste du Passage lu."""
        ...

    def meteo(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[MeteoEntite, ...]:
        """Météo et Règles déclenchantes (FR-17, FR-43)."""
        ...

    def evolution_meteo(self, date_arrete: date | None = None) -> tuple[EvolutionMeteo, ...]:
        """Météo à J, J-1 et J-5 par Entité (FR-19)."""
        ...

    def url_ticket(self, cle: str) -> str | None:
        """Lien Jira du ticket (FR-29) ; `None` en Mode repli."""
        ...


class LectureVueCarte(LectureCarte, Protocol):
    """Lectures de la vue JSON de la carte : celles de la carte, plus les livrables (1.9.0)."""

    def livrable(self, nom: NomLivrable) -> bytes | None:
        """Contenu du livrable du Passage lu, ou `None` s'il est absent."""
        ...


def date_carte(consultation: LectureCarte) -> str:
    """Date d'arrêté du Passage, au format `JJ/MM/AAAA`."""
    return formater_date(consultation.manifeste().date_arrete)


def libelle_meteo(couleur: Couleur) -> str:
    """Pastille et libellé français : `🔴 Rouge`."""
    return f"{PASTILLES[couleur]} {LIBELLES_COULEURS[couleur]}"


def fleche(avant: Couleur | None, maintenant: Couleur) -> str:
    """`↗` si plus grave qu'avant, `↘` si moins grave, `→` si égale, `—` si inconnue avant."""
    if avant is None:
        return INCONNUE
    if maintenant > avant:
        return AGGRAVATION
    if maintenant < avant:
        return AMELIORATION
    return STABLE


def tendance(evolution: EvolutionMeteo | None) -> str:
    """`J-1 ↗ · J-5 →` ; sans évolution connue de l'Entité, les deux flèches valent `—`."""
    if evolution is None:
        return f"J-1 {INCONNUE} · J-5 {INCONNUE}"
    j1 = fleche(evolution.couleur_j1, evolution.couleur)
    j5 = fleche(evolution.couleur_j5, evolution.couleur)
    return f"J-1 {j1} · J-5 {j5}"


def _valeur(numerateur: int, denominateur: int) -> str:
    if denominateur == 0:
        return "∞"
    return formater_fraction(Fraction(numerateur, denominateur))


def formater_regle(regle: RegleDeclenchante) -> str:
    """`IND-2 : 11 (seuil ≥ 10)`, au format de `rendu.commun.formater_regle`."""
    valeur = _valeur(regle.numerateur, regle.denominateur)
    seuil = _valeur(regle.seuil_numerateur, regle.seuil_denominateur)
    return f"{regle.code.value} : {valeur} (seuil {_SYMBOLES[regle.operateur]} {seuil})"


def regle_principale(meteo: MeteoEntite) -> str:
    """Première Règle (ordre de la Grille), puis `(+N)` s'il y en a d'autres ; `—` si verte."""
    if not meteo.regles:
        return INCONNUE
    texte = formater_regle(meteo.regles[0])
    autres = len(meteo.regles) - 1
    return f"{texte} (+{autres})" if autres else texte


def tickets_principaux(meteo: MeteoEntite, url_ticket: Callable[[str], str | None]) -> str:
    """Tickets en cause de la Règle principale : 3 premiers en liens, puis `+N` ; `—` sinon."""
    if not meteo.regles or not meteo.regles[0].tickets_en_cause:
        return INCONNUE
    cles = meteo.regles[0].tickets_en_cause
    liens = ", ".join(lien_ticket(cle, url_ticket(cle)) for cle in cles[:TICKETS_MAX])
    reste = len(cles) - TICKETS_MAX
    return f"{liens} +{reste}" if reste > 0 else liens


def lignes_carte(consultation: LectureCarte) -> list[dict[str, str]]:
    """Une ligne par Entité : Météo, tendance J-1 / J-5, Règle principale et tickets en cause."""
    evolutions = {evolution.entite: evolution for evolution in consultation.evolution_meteo()}
    return [
        {
            "Entité": echapper_markdown(meteo.entite),
            "Météo": libelle_meteo(meteo.couleur),
            "Tendance": tendance(evolutions.get(meteo.entite)),
            "Règle principale": regle_principale(meteo),
            "Tickets en cause": tickets_principaux(meteo, consultation.url_ticket),
        }
        for meteo in consultation.meteo()
    ]


def _cellule(texte: str) -> str:
    """Cellule sur une seule ligne, chaque `|` non encore échappé l'étant."""
    return _BARRE_NON_ECHAPPEE.sub(r"\1\\|", " ".join(texte.splitlines()))


def tableau_markdown(lignes: Sequence[Mapping[str, str]]) -> str:
    """Tableau Markdown des lignes (colonnes de la première) ; chaîne vide sans ligne."""
    if not lignes:
        return ""
    colonnes = list(lignes[0])
    rangees = [
        "| " + " | ".join(_cellule(colonne) for colonne in colonnes) + " |",
        "|" + "|".join(" --- " for _ in colonnes) + "|",
    ]
    rangees += ["| " + " | ".join(_cellule(ligne[c]) for c in colonnes) + " |" for ligne in lignes]
    return "\n".join(rangees)


# --- Vue JSON de l'écran Carte météo (AD-25) : données structurées, sans Markdown ---

AUCUN_PASSAGE = "Aucun Passage publié : lancer la Chaîne pour produire une carte météo."
AUCUNE_METEO = "Ce Passage ne contient aucune Météo."
LIBELLE_FILTRE = "Filtrer par météo"
ANNONCE_UNE = "1 Entité affichée"
ANNONCE_PLUSIEURS = "{n} Entités affichées"
TOUTES = "toutes"
NON_GENERE = "Non généré pour ce Passage"

LIVRABLES: Mapping[NomLivrable, tuple[str, str]] = MappingProxyType(
    {
        "rapport_xlsx": ("Rapport quotidien", "Excel (.xlsx)"),
        "rapport_pptx": ("Comité de pilotage", "PowerPoint (.pptx)"),
    }
)
"""Libellé et type de chaque livrable proposé sous la carte."""

MIME_LIVRABLES: Mapping[NomLivrable, str] = MappingProxyType(
    {
        "rapport_xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "rapport_pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
)
"""Type MIME de chaque livrable téléchargé."""


def url_detail(entite: str) -> str:
    """URL de l'écran Détail d'une Entité."""
    return f"/entites/{quote(entite, safe='')}"


def vue_meteo(couleur: Couleur) -> VueMeteo:
    """Pastille météo : couleur nommée et libellé français."""
    return VueMeteo.model_validate(
        {"couleur": couleur.value, "libelle": LIBELLES_COULEURS[couleur]}
    )


def entites_triees(meteos: Sequence[MeteoEntite]) -> list[MeteoEntite]:
    """Tableau des Entités : de la Météo la plus grave à la moins grave, puis par Entité."""
    par_entite = sorted(meteos, key=lambda meteo: meteo.entite)
    return sorted(par_entite, key=lambda meteo: meteo.couleur, reverse=True)


def libelle_suite(reste: int) -> str | None:
    """« +N » des tickets en cause non listés ; `None` s'il n'en reste pas."""
    return f"+{reste}" if reste > 0 else None


def taille_lisible(octets: int) -> str:
    """`512 o`, `96 Ko`, `1,2 Mo` ; l'arrondi ne produit jamais « 1024 Ko »."""
    if octets < 1024:
        return f"{octets} o"
    if round(octets / 1024) < 1024:
        return f"{round(octets / 1024)} Ko"
    return f"{octets / (1024 * 1024):.1f} Mo".replace(".", ",")


def nom_fichier_livrable(nom: NomLivrable, date_arrete: date) -> str:
    """Nom du fichier téléchargé : `rapport-2026-10-09.xlsx`."""
    return chemin_fichier_passage(nom, date_arrete)


def vues_livrables(consultation: LectureVueCarte) -> list[VueLivrable]:
    """Livrables du Passage affiché, lus par `Consultation.livrable` (aucun chemin ici)."""
    date_arrete = consultation.manifeste().date_arrete
    vues: list[VueLivrable] = []
    for nom, (libelle, type_fichier) in LIVRABLES.items():
        contenu = consultation.livrable(nom)
        description = "" if contenu is None else f"{type_fichier} · {taille_lisible(len(contenu))}"
        vues.append(
            VueLivrable(
                nom=nom,
                libelle=libelle,
                fichier=nom_fichier_livrable(nom, date_arrete),
                description=description,
                url=None if contenu is None else f"/livrables/{nom}",
                absent=NON_GENERE if contenu is None else None,
            )
        )
    return vues


def vues_tickets(cles: Sequence[str], url_ticket: Callable[[str], str | None]) -> list[VueTicket]:
    """Clés de ticket en données (lien ou texte simple selon `url_ticket`)."""
    return [vue_ticket(cle, url_ticket(cle)) for cle in cles]


def _filtre() -> VueFiltre:
    options = [VueOptionFiltre(valeur=TOUTES, libelle="Toutes", message_vide="")]
    for couleur in sorted(Couleur, reverse=True):
        libelle = LIBELLES_COULEURS[couleur]
        message = f"Aucune Entité en {libelle.lower()} à cette Date d'arrêté."
        options.append(VueOptionFiltre(valeur=couleur.value, libelle=libelle, message_vide=message))
    return VueFiltre(
        libelle=LIBELLE_FILTRE,
        options=options,
        annonce_une=ANNONCE_UNE,
        annonce_plusieurs=ANNONCE_PLUSIEURS,
    )


def vue_carte_message(message: str, lien: VueLien | None = None) -> VueCarte:
    """Carte remplacée par un message (aucun Passage, aucune Météo)."""
    return VueCarte(
        erreur=None,
        message=message,
        lien_message=lien,
        sous_titre=None,
        comptages=[],
        filtre=None,
        legende=None,
        lignes=[],
        livrables=[],
    )


def vue_carte_erreur(erreur: str) -> VueCarte:
    """Carte vide dont la lecture a échoué : le bandeau d'erreur porte le détail."""
    return vue_carte_message("").model_copy(update={"erreur": erreur, "message": None})


def vue_carte(consultation: LectureVueCarte) -> VueCarte:
    """Vue de la carte : comptages, filtre, une ligne par Entité et livrables du Passage."""
    meteos = entites_triees(consultation.meteo())
    if not meteos:
        return vue_carte_message(AUCUNE_METEO)
    evolutions = {evolution.entite: evolution for evolution in consultation.evolution_meteo()}
    lignes: list[VueLigneCarte] = []
    for meteo in meteos:
        cles = meteo.regles[0].tickets_en_cause if meteo.regles else ()
        lignes.append(
            VueLigneCarte(
                entite=meteo.entite,
                meteo=vue_meteo(meteo.couleur),
                tendance=tendance(evolutions.get(meteo.entite)),
                regle_principale=regle_principale(meteo),
                tickets=vues_tickets(cles[:TICKETS_MAX], consultation.url_ticket),
                suite=libelle_suite(len(cles) - TICKETS_MAX),
                url_detail=url_detail(meteo.entite),
                libelle_detail=f"Détail {meteo.entite}",
            )
        )
    comptages = [
        VueComptage(
            meteo=vue_meteo(couleur),
            nombre=sum(1 for meteo in meteos if meteo.couleur is couleur),
        )
        for couleur in sorted(Couleur, reverse=True)
    ]
    return VueCarte(
        erreur=None,
        message=None,
        lien_message=None,
        sous_titre=f"Date d'arrêté : {date_carte(consultation)}",
        comptages=comptages,
        filtre=_filtre(),
        legende=LEGENDE,
        lignes=lignes,
        livrables=vues_livrables(consultation),
    )
