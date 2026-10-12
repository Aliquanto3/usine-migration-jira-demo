"""Détail d'une Entité, sans Streamlit : blocs de l'écran, via `Consultation`.

Règles déclenchantes, KPI clés, Prévision de sortie du rouge (ou sa narration contrôlée en
Palier 2), Risque d'entrée en rouge et Explication sourcée (FR-43, FR-17, FR-20, FR-21, FR-24,
FR-32, FR-46). L'UI ne calcule aucun chiffre : elle formate les fractions de `Consultation`
avec `contrats.format`, et le nombre de phrases retirées vient de `SortieExplication`.
"""

import re
from collections.abc import Callable, Mapping
from datetime import date
from fractions import Fraction
from types import MappingProxyType
from typing import Literal, Protocol

import polars as pl

from usine.contrats.format import formater_date, formater_fraction, formater_pourcentage
from usine.contrats.llm import SortieExplication, SortieNarration, StatutControle
from usine.contrats.meteo import Couleur, MeteoEntite
from usine.contrats.passage import Etape, ManifestePassage, StatutEtape
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
EXPLICATION_ABSENTE = "Aucune Explication sourcée pour cette Entité dans ce Passage."
NARRATION_CONTROLEE = "narration contrôlée"
CITATIONS = "Citations"
PHRASES_RETIREES = "Phrases retirées au contrôle"
STATUT_CONTROLE = "Statut du contrôle"

LIBELLES_STATUT: Mapping[StatutControle, str] = MappingProxyType(
    {
        StatutControle.non_controle: "non contrôlée",
        StatutControle.conforme: "conforme",
        StatutControle.corrige: "corrigée (phrases fautives retirées)",
        StatutControle.rejete: "rejetée (texte de remplacement)",
    }
)
"""Libellé français de chaque `StatutControle`."""

STATUTS_ACCEPTES = frozenset({StatutControle.conforme, StatutControle.corrige})
"""Statuts d'une narration qui peut remplacer la Prévision brute."""

Palier = Literal[1, 2]
"""Même alias que `ports.consultation.Palier` (que `ui` n'importe pas)."""


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

    def explications(
        self, entite: str | None = None, palier: Palier = 2
    ) -> tuple[SortieExplication, ...]:
        """Explications sourcées et Brouillons de commentaire (FR-32, FR-33)."""
        ...

    def narrations(
        self, entite: str | None = None, palier: Palier = 2
    ) -> tuple[SortieNarration, ...]:
        """Narrations des Prévisions (FR-24)."""
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


def previsions_calculees(manifeste: ManifestePassage) -> bool:
    """Vrai si l'étape `prevision` du Passage a réussi.

    `Consultation` rend `()` aussi bien sans `previsions.json` que sans Risque : seul le
    manifeste dit si la Prévision a été calculée (même règle que `consultation.prevision`,
    que `ui` n'importe pas).
    """
    return any(
        execution.etape is Etape.prevision and execution.statut is StatutEtape.reussie
        for execution in manifeste.etapes
    )


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


def _texte_narration(narration: SortieNarration) -> str:
    return (
        f"{echapper_markdown(narration.texte)}\n\n"
        f"*{NARRATION_CONTROLEE} ({LIBELLES_STATUT[narration.statut_controle]})*"
    )


def texte_prevision(
    meteo: MeteoEntite,
    previsions: tuple[Prevision, ...],
    calculees: bool,
    narrations: tuple[SortieNarration, ...] = (),
) -> str:
    """Bloc Prévision de sortie du rouge de l'Entité (Markdown).

    Une narration de l'Entité remplace la Prévision brute seulement si son contrôle est
    `conforme` ou `corrige` ; sinon (rejetée, non contrôlée, absente, Palier 1), la Prévision
    brute reste affichée.
    """
    if not calculees:
        return PREVISION_NON_CALCULEE_PASSAGE
    if meteo.couleur is not Couleur.rouge:
        return PREVISION_SANS_OBJET
    propres = [p for p in previsions if p.entite == meteo.entite]
    if not propres:
        return PREVISION_NON_CALCULEE_ENTITE
    controlees = [
        n for n in narrations if n.entite == meteo.entite and n.statut_controle in STATUTS_ACCEPTES
    ]
    if controlees:
        return "\n\n".join(_texte_narration(narration) for narration in controlees)
    return "\n\n".join(_texte_une_prevision(prevision) for prevision in propres)


def _valeur(numerateur: int, denominateur: int) -> str:
    return formater_fraction(Fraction(numerateur, denominateur))


def texte_risques(
    meteo: MeteoEntite, risques: tuple[RisqueEntreeRouge, ...], calculees: bool
) -> str:
    """Bloc Risque d'entrée en rouge de l'Entité (Markdown : message ou tableau).

    La colonne « Valeur projetée » (contrats 1.1.0) n'apparaît que si un Risque la porte.
    """
    if not calculees:
        return RISQUE_NON_CALCULE_PASSAGE
    if meteo.couleur is Couleur.rouge:
        return RISQUE_SANS_OBJET
    propres = [r for r in risques if r.entite == meteo.entite]
    if not propres:
        return AUCUN_RISQUE
    avec_projection = any(r.valeur_projetee_denominateur is not None for r in propres)
    lignes: list[dict[str, str]] = []
    for risque in propres:
        ligne = {
            "Indicateur": risque.indicateur.value,
            "Valeur courante": _valeur(risque.numerateur, risque.denominateur),
            "Seuil rouge": _valeur(risque.seuil_numerateur, risque.seuil_denominateur),
            "Franchissement estimé": formater_date(risque.date_franchissement_estimee),
            "Horizon": f"{risque.horizon_jours_ouvres} jours ouvrés",
        }
        if avec_projection:
            numerateur = risque.valeur_projetee_numerateur
            denominateur = risque.valeur_projetee_denominateur
            ligne["Valeur projetée"] = (
                _valeur(numerateur, denominateur)
                if numerateur is not None and denominateur is not None
                else INCONNUE
            )
        lignes.append(ligne)
    return tableau_markdown(lignes)


def texte_avec_liens(
    texte: str, citations: tuple[str, ...], url_ticket: Callable[[str], str | None]
) -> str:
    """`texte` en Markdown, chaque clé citée en lien Jira (texte simple en Mode repli).

    Le texte est découpé sur les clés de `citations`, bornées par `(?<![\\w-])` et
    `(?![\\w-])`, les plus longues d'abord ; les morceaux hors clé sont échappés.
    """
    cles = sorted({c for c in citations if c}, key=len, reverse=True)
    if not cles:
        return echapper_markdown(texte)
    motif = re.compile(rf"(?<![\w-])({'|'.join(re.escape(c) for c in cles)})(?![\w-])")
    morceaux = motif.split(texte)  # hors clé aux rangs pairs, clés aux rangs impairs
    return "".join(
        lien_ticket(morceau, url_ticket(morceau)) if rang % 2 else echapper_markdown(morceau)
        for rang, morceau in enumerate(morceaux)
    )


def _texte_une_explication(
    explication: SortieExplication, url_ticket: Callable[[str], str | None]
) -> str:
    statut = f"{STATUT_CONTROLE} : {LIBELLES_STATUT[explication.statut_controle]}"
    if explication.statut_controle is StatutControle.rejete:
        return f"{echapper_markdown(explication.texte)}\n\n*{statut}*"
    lignes = [texte_avec_liens(explication.texte, explication.citations, url_ticket), ""]
    if explication.citations:
        lignes += [f"**{CITATIONS}**", ""]
        lignes += [f"- {lien_ticket(cle, url_ticket(cle))}" for cle in explication.citations]
        lignes.append("")
    lignes += [f"- {PHRASES_RETIREES} : {explication.phrases_retirees}", f"- {statut}"]
    return "\n".join(lignes)


def _sans_lien(_cle: str) -> None:
    return None


def texte_explication(
    palier: Palier,
    explications: tuple[SortieExplication, ...] = (),
    url_ticket: Callable[[str], str | None] = _sans_lien,
) -> str:
    """Zone Explication de l'Entité (Markdown).

    En Palier 1, aucun commentaire n'est généré (`EXPLICATION_PALIER_1`). En Palier 2 : le
    texte avec ses clés citées en liens, la liste des Citations (une clé absente du texte
    reste visible), le nombre de phrases retirées au contrôle et le statut ; une Explication
    rejetée affiche son texte de remplacement tel quel, avec son statut.
    """
    if palier == 1:
        return EXPLICATION_PALIER_1
    if not explications:
        return EXPLICATION_ABSENTE
    return "\n\n".join(_texte_une_explication(e, url_ticket) for e in explications)
