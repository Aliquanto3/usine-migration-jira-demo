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

from usine.contrats.format import formater_date, formater_fraction
from usine.contrats.meteo import (
    LIBELLES_COULEURS,
    Couleur,
    EvolutionMeteo,
    MeteoEntite,
    Operateur,
    RegleDeclenchante,
)
from usine.contrats.passage import ManifestePassage
from usine.ui.liens import echapper_markdown, lien_ticket

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
