"""Détail d'une Entité (Palier 1), sans Streamlit : blocs de l'écran, via `Consultation`.

Règles déclenchantes, KPI clés, Prévision de sortie du rouge, Risque d'entrée en rouge et zone
Explication (FR-43, FR-17, FR-20, FR-21). L'UI ne calcule aucun chiffre : elle formate les
fractions de `Consultation` avec `contrats.format`.
"""

from collections.abc import Callable, Mapping
from datetime import date
from fractions import Fraction
from types import MappingProxyType
from typing import Literal, Protocol

import polars as pl

from usine.contrats.format import formater_date, formater_fraction, formater_pourcentage
from usine.contrats.meteo import Couleur, MeteoEntite
from usine.contrats.passage import ManifestePassage
from usine.contrats.prevision import Prevision, RisqueEntreeRouge, StatutPrevision
from usine.ui.carte import INCONNUE, formater_regle, tableau_markdown
from usine.ui.liens import echapper_markdown, lien_ticket

KPI_CLES: Mapping[str, str] = MappingProxyType(
    {
        "anomalies_ouvertes": "Anomalies ouvertes",
        "entrees_fenetre": "Entrées sur la fenêtre",
        "sorties_fenetre": "Sorties sur la fenêtre",
        "age_median_anomalies_ouvertes": "Âge médian des Anomalies ouvertes",
        "age_max_anomalies_ouvertes": "Âge maximal des Anomalies ouvertes",
        "taux_ko_cas_de_test": "Taux KO des Cas de test",
    }
)
"""KPI clés du détail, dans l'ordre d'affichage (codes de `domaine.kpi`, non importable)."""

INFINI = "∞"

AUCUNE_REGLE = "Aucune Règle déclenchante (Entité verte)."
AUCUN_KPI = "Aucun KPI pour cette Entité à la Date d'arrêté du Passage."
PREVISION_NON_CALCULEE_PASSAGE = "Prévision non calculée pour ce Passage"
PREVISION_NON_CALCULEE_ENTITE = "Prévision non calculée pour cette Entité"
PREVISION_SANS_OBJET = "Sans objet : l'Entité n'est pas rouge."
PAS_DE_SORTIE = "pas de sortie projetée"
NON_PROJETABLE = "pas de sortie projetée : règle non projetable"
RISQUE_NON_CALCULE_PASSAGE = "Risque d'entrée en rouge non calculé pour ce Passage"
AUCUN_RISQUE = "Aucun Risque d'entrée en rouge dans l'horizon."
RISQUE_SANS_OBJET = "Sans objet : l'Entité est déjà rouge."
EXPLICATION_PALIER_1 = "commentaire non généré (Palier 1)"
EXPLICATION_PALIER_2 = "Explication sourcée : Story 7.7"


class LectureDetail(Protocol):
    """Lectures de la `Consultation` dont le détail a besoin (alignées sur elle par un test)."""

    def manifeste(self) -> ManifestePassage:
        """Manifeste du Passage lu."""
        ...

    def meteo(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[MeteoEntite, ...]:
        """Météo et Règles déclenchantes (FR-17, FR-43)."""
        ...

    def kpi(self, date_arrete: date | None = None, entite: str | None = None) -> pl.DataFrame:
        """Table `SCHEMA_KPI` ; `entite=None` rend aussi le périmètre Programme."""
        ...

    def previsions(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[Prevision, ...]:
        """Prévisions de sortie du rouge (FR-20)."""
        ...

    def risques(
        self, date_arrete: date | None = None, entite: str | None = None
    ) -> tuple[RisqueEntreeRouge, ...]:
        """Risques d'entrée en rouge (FR-21)."""
        ...

    def url_ticket(self, cle: str) -> str | None:
        """Lien Jira du ticket (FR-29) ; `None` en Mode repli."""
        ...


def lignes_regles(
    meteo: MeteoEntite, url_ticket: Callable[[str], str | None]
) -> list[dict[str, str]]:
    """Une ligne par Règle déclenchante (ordre de la Grille), avec tous ses tickets en cause."""
    return [
        {
            "Règle": formater_regle(regle),
            "Tickets en cause": ", ".join(
                lien_ticket(cle, url_ticket(cle)) for cle in regle.tickets_en_cause
            )
            or INCONNUE,
        }
        for regle in meteo.regles
    ]


def valeur_kpi(code: str, numerateur: int, denominateur: int) -> str:
    """Fraction formatée (`%` pour `taux_*`) ; `∞` si `n/0` avec `n > 0`, `—` si `0/0`."""
    if denominateur == 0:
        return INFINI if numerateur > 0 else INCONNUE
    valeur = Fraction(numerateur, denominateur)
    if code.startswith("taux_"):
        return formater_pourcentage(valeur)
    return formater_fraction(valeur)


def lignes_kpi(table: pl.DataFrame) -> list[dict[str, str]]:
    """KPI clés de la table `SCHEMA_KPI` d'une Entité, dans l'ordre de `KPI_CLES`.

    Une ligne par dimension présente ; un KPI ventilé ajoute ` (dimension)` à son libellé.
    """
    lignes: list[dict[str, str]] = []
    rangees = list(table.iter_rows(named=True))
    for code, libelle in KPI_CLES.items():
        for rangee in rangees:
            if rangee["code_kpi"] != code:
                continue
            dimension: str = rangee["dimension"]
            nom = f"{libelle} ({echapper_markdown(dimension)})" if dimension else libelle
            lignes.append(
                {
                    "KPI": nom,
                    "Valeur": valeur_kpi(code, rangee["numerateur"], rangee["denominateur"]),
                }
            )
    return lignes


def previsions_calculees(consultation: LectureDetail) -> bool:
    """Vrai si le Passage contient au moins une Prévision ou un Risque (toutes Entités)."""
    return bool(consultation.previsions()) or bool(consultation.risques())


def _facteurs(prevision: Prevision) -> list[str]:
    if not prevision.facteurs:
        return []
    return ["", "**Facteurs explicatifs**", ""] + [
        f"- {echapper_markdown(facteur.libelle)} :"
        f" {formater_fraction(Fraction(facteur.numerateur, facteur.denominateur))}"
        for facteur in prevision.facteurs
    ]


def _probabilite_et_horizon(prevision: Prevision) -> list[str]:
    probabilite = Fraction(prevision.probabilite_numerateur, prevision.probabilite_denominateur)
    return [
        f"- Probabilité de sortie dans l'horizon : {formater_pourcentage(probabilite)}",
        f"- Horizon : {prevision.horizon_jours_ouvres} jours ouvrés",
    ]


def _fourchette(prevision: Prevision) -> list[str]:
    optimiste, pessimiste = prevision.date_sortie_optimiste, prevision.date_sortie_pessimiste
    if optimiste is not None and pessimiste is not None:
        return [f"- Fourchette : {formater_date(optimiste)} – {formater_date(pessimiste)}"]
    if optimiste is not None:
        return [f"- Date optimiste : {formater_date(optimiste)}"]
    if pessimiste is not None:
        return [f"- Date pessimiste : {formater_date(pessimiste)}"]
    return []


def _texte_une_prevision(prevision: Prevision) -> str:
    if prevision.statut is StatutPrevision.sortie_projetee:
        estimee = prevision.date_sortie_estimee
        lignes = [
            f"**Sortie du rouge estimée** : {formater_date(estimee) if estimee else INCONNUE}",
            "",
            *_fourchette(prevision),
            *_probabilite_et_horizon(prevision),
            f"- Méthode : {prevision.methode.value}",
        ]
    elif prevision.statut is StatutPrevision.pas_de_sortie_projetee:
        lignes = [f"**{PAS_DE_SORTIE}**", "", *_probabilite_et_horizon(prevision)]
    else:
        codes = ", ".join(code.value for code in prevision.regles_non_projetables)
        lignes = [f"**{NON_PROJETABLE} ({codes})**"]
    return "\n".join([*lignes, *_facteurs(prevision)])


def texte_prevision(meteo: MeteoEntite, previsions: tuple[Prevision, ...], calculees: bool) -> str:
    """Bloc Prévision de sortie du rouge de l'Entité (Markdown)."""
    if not calculees:
        return PREVISION_NON_CALCULEE_PASSAGE
    if meteo.couleur is not Couleur.rouge:
        return PREVISION_SANS_OBJET
    propres = [p for p in previsions if p.entite == meteo.entite]
    if not propres:
        return PREVISION_NON_CALCULEE_ENTITE
    return "\n\n".join(_texte_une_prevision(prevision) for prevision in propres)


def _valeur(numerateur: int, denominateur: int) -> str:
    return formater_fraction(Fraction(numerateur, denominateur))


def texte_risques(
    meteo: MeteoEntite, risques: tuple[RisqueEntreeRouge, ...], calculees: bool
) -> str:
    """Bloc Risque d'entrée en rouge de l'Entité (Markdown : message ou tableau)."""
    if not calculees:
        return RISQUE_NON_CALCULE_PASSAGE
    if meteo.couleur is Couleur.rouge:
        return RISQUE_SANS_OBJET
    propres = [r for r in risques if r.entite == meteo.entite]
    if not propres:
        return AUCUN_RISQUE
    return tableau_markdown(
        [
            {
                "Indicateur": risque.indicateur.value,
                "Valeur courante": _valeur(risque.numerateur, risque.denominateur),
                "Seuil rouge": _valeur(risque.seuil_numerateur, risque.seuil_denominateur),
                "Franchissement estimé": formater_date(risque.date_franchissement_estimee),
                "Horizon": f"{risque.horizon_jours_ouvres} jours ouvrés",
            }
            for risque in propres
        ]
    )


def texte_explication(palier: Literal[1, 2]) -> str:
    """Zone Explication : en Palier 1, aucun commentaire n'est généré."""
    return EXPLICATION_PALIER_1 if palier == 1 else EXPLICATION_PALIER_2
