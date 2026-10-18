"""Détail d'une Entité : blocs de l'écran, via `Consultation`.

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
from usine.ui.carte import (
    INCONNUE,
    TICKETS_MAX,
    entites_triees,
    formater_regle,
    libelle_suite,
    url_detail,
    vue_meteo,
    vues_tickets,
)
from usine.ui.vues import (
    VueBloc,
    VueDetail,
    VueExplication,
    VueExplications,
    VueLien,
    VueLigneKpi,
    VueOptionPalier,
    VueRegle,
    VueSection,
    VueSegmentPalier,
    VueSegmentTexte,
    VueTableau,
)

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


def valeur_kpi(code: str, numerateur: int, denominateur: int) -> str:
    """Fraction formatée (`%` pour `taux_*`) ; `∞` si `n/0` avec `n > 0`, `—` si `0/0`."""
    if denominateur == 0:
        return INFINI if numerateur > 0 else INCONNUE
    valeur = Fraction(numerateur, denominateur)
    if code.startswith("taux_"):
        return formater_pourcentage(valeur)
    return formater_fraction(valeur)


def _kpi_cles(table: pl.DataFrame, mise_en_forme: Callable[[str], str]) -> list[dict[str, str]]:
    lignes: list[dict[str, str]] = []
    rangees = list(table.iter_rows(named=True))
    for code, libelle in KPI_CLES.items():
        for rangee in rangees:
            if rangee["code_kpi"] != code:
                continue
            dimension: str = rangee["dimension"]
            nom = f"{libelle} ({mise_en_forme(dimension)})" if dimension else libelle
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


def _probabilite_et_horizon(prevision: Prevision) -> list[str]:
    probabilite = Fraction(prevision.probabilite_numerateur, prevision.probabilite_denominateur)
    return [
        f"Probabilité de sortie dans l'horizon : {formater_pourcentage(probabilite)}",
        f"Horizon : {prevision.horizon_jours_ouvres} jours ouvrés",
    ]


def _fourchette(prevision: Prevision) -> list[str]:
    optimiste, pessimiste = prevision.date_sortie_optimiste, prevision.date_sortie_pessimiste
    if optimiste is not None and pessimiste is not None:
        return [f"Fourchette : {formater_date(optimiste)} – {formater_date(pessimiste)}"]
    if optimiste is not None:
        return [f"Date optimiste : {formater_date(optimiste)}"]
    if pessimiste is not None:
        return [f"Date pessimiste : {formater_date(pessimiste)}"]
    return []


def _valeur(numerateur: int, denominateur: int) -> str:
    return formater_fraction(Fraction(numerateur, denominateur))


def _lignes_risques(propres: list[RisqueEntreeRouge]) -> list[dict[str, str]]:
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
    return lignes


def _morceaux(texte: str, citations: tuple[str, ...]) -> list[tuple[str, bool]]:
    """`texte` découpé sur les clés de `citations` : (morceau, est une clé citée).

    Les clés sont bornées par `(?<![\\w-])` et `(?![\\w-])`, les plus longues d'abord.
    """
    cles = sorted({c for c in citations if c}, key=len, reverse=True)
    if not cles:
        return [(texte, False)]
    motif = re.compile(rf"(?<![\w-])({'|'.join(re.escape(c) for c in cles)})(?![\w-])")
    morceaux = motif.split(texte)  # hors clé aux rangs pairs, clés aux rangs impairs
    return [(morceau, rang % 2 == 1) for rang, morceau in enumerate(morceaux)]


# --- Vue JSON de l'écran Détail d'une Entité (AD-25) : données structurées, sans Markdown ---

TITRE_PREVISION = "Prévision de sortie du rouge"
TITRE_RISQUE = "Risque d'entrée en rouge"
TITRE_EXPLICATION = "Explication"
LEGENDE_PALIER = "Palier 1 : la même Entité sans aucune sortie LLM."
LIBELLE_CARTE = "← Carte météo"
LIBELLE_CARTE_MESSAGE = "Voir la carte météo"


def entite_absente(entite: str) -> str:
    """Message d'une Entité qui n'est pas dans le Passage affiché."""
    return f"Entité {entite} absente du Passage affiché."


def _bloc_une_prevision(prevision: Prevision) -> VueBloc:
    if prevision.statut is StatutPrevision.sortie_projetee:
        estimee = prevision.date_sortie_estimee
        facteurs = [
            f"{facteur.libelle} :"
            f" {formater_fraction(Fraction(facteur.numerateur, facteur.denominateur))}"
            for facteur in prevision.facteurs
        ]
        return VueBloc(
            titre=f"Sortie du rouge estimée : {formater_date(estimee) if estimee else INCONNUE}",
            items=[
                *_fourchette(prevision),
                *_probabilite_et_horizon(prevision),
                f"Méthode : {prevision.methode.value}",
            ],
            sous_titre="Facteurs explicatifs" if facteurs else None,
            sous_items=facteurs,
        )
    if prevision.statut is StatutPrevision.pas_de_sortie_projetee:
        return VueBloc(titre=PAS_DE_SORTIE, items=_probabilite_et_horizon(prevision))
    codes = ", ".join(code.value for code in prevision.regles_non_projetables)
    return VueBloc(titre=f"{NON_PROJETABLE} ({codes})")


def section_prevision(
    meteo: MeteoEntite,
    previsions: tuple[Prevision, ...],
    calculees: bool,
    narrations: tuple[SortieNarration, ...] = (),
) -> VueSection:
    """Bloc Prévision en blocs structurés."""

    def message(texte: str) -> VueSection:
        return VueSection(titre=TITRE_PREVISION, message=texte, blocs=[], tableau=None)

    if not calculees:
        return message(PREVISION_NON_CALCULEE_PASSAGE)
    if meteo.couleur is not Couleur.rouge:
        return message(PREVISION_SANS_OBJET)
    propres = [p for p in previsions if p.entite == meteo.entite]
    if not propres:
        return message(PREVISION_NON_CALCULEE_ENTITE)
    controlees = [
        n for n in narrations if n.entite == meteo.entite and n.statut_controle in STATUTS_ACCEPTES
    ]
    if controlees:
        blocs = [
            VueBloc(
                texte=n.texte,
                note=f"{NARRATION_CONTROLEE} ({LIBELLES_STATUT[n.statut_controle]})",
            )
            for n in controlees
        ]
    else:
        blocs = [_bloc_une_prevision(prevision) for prevision in propres]
    return VueSection(titre=TITRE_PREVISION, message=None, blocs=blocs, tableau=None)


def section_risque(
    meteo: MeteoEntite, risques: tuple[RisqueEntreeRouge, ...], calculees: bool
) -> VueSection:
    """Bloc Risque d'entrée en rouge : message ou tableau."""

    def message(texte: str) -> VueSection:
        return VueSection(titre=TITRE_RISQUE, message=texte, blocs=[], tableau=None)

    if not calculees:
        return message(RISQUE_NON_CALCULE_PASSAGE)
    if meteo.couleur is Couleur.rouge:
        return message(RISQUE_SANS_OBJET)
    propres = [r for r in risques if r.entite == meteo.entite]
    if not propres:
        return message(AUCUN_RISQUE)
    lignes = _lignes_risques(propres)
    colonnes = list(lignes[0])
    tableau = VueTableau(
        colonnes=colonnes, lignes=[[ligne[c] for c in colonnes] for ligne in lignes]
    )
    return VueSection(titre=TITRE_RISQUE, message=None, blocs=[], tableau=tableau)


def _vue_explication(
    explication: SortieExplication, url_ticket: Callable[[str], str | None]
) -> VueExplication:
    statut = f"{STATUT_CONTROLE} : {LIBELLES_STATUT[explication.statut_controle]}"
    code = explication.statut_controle.value
    if explication.statut_controle is StatutControle.rejete:
        segments = [VueSegmentTexte(texte=explication.texte, ticket=None)]
        return VueExplication(
            segments=segments,
            citations=[],
            titre_citations=CITATIONS,
            phrases_retirees=None,
            statut=statut,
            statut_code=code,
        )
    segments = [
        VueSegmentTexte(
            texte=morceau,
            ticket=vues_tickets([morceau], url_ticket)[0] if est_cle else None,
        )
        for morceau, est_cle in _morceaux(explication.texte, explication.citations)
        if morceau
    ]
    return VueExplication(
        segments=segments,
        citations=vues_tickets(explication.citations, url_ticket),
        titre_citations=CITATIONS,
        phrases_retirees=f"{PHRASES_RETIREES} : {explication.phrases_retirees}",
        statut=statut,
        statut_code=code,
    )


def section_explication(
    palier: Palier,
    explications: tuple[SortieExplication, ...],
    url_ticket: Callable[[str], str | None],
) -> VueExplications:
    """Zone Explication en données."""
    if palier == 1:
        return VueExplications(
            titre=TITRE_EXPLICATION, message=EXPLICATION_PALIER_1, explications=[]
        )
    if not explications:
        return VueExplications(
            titre=TITRE_EXPLICATION, message=EXPLICATION_ABSENTE, explications=[]
        )
    return VueExplications(
        titre=TITRE_EXPLICATION,
        message=None,
        explications=[_vue_explication(e, url_ticket) for e in explications],
    )


def _segment_palier(palier: Palier) -> VueSegmentPalier:
    options = [
        VueOptionPalier(valeur=2, libelle="Palier 2", actif=palier == 2),
        VueOptionPalier(valeur=1, libelle="Palier 1", actif=palier == 1),
    ]
    return VueSegmentPalier(options=options, legende=LEGENDE_PALIER)


def vue_detail_message(
    message: str, entites: list[VueLien] | None = None, entite: str | None = None
) -> VueDetail:
    """Détail remplacé par un message (aucune Météo, Entité absente) et un lien vers la carte."""
    return VueDetail(
        erreur=None,
        message=message,
        lien_message=VueLien(libelle=LIBELLE_CARTE_MESSAGE, url="/"),
        entite=entite,
        entites=entites or [],
        lien_carte=VueLien(libelle=LIBELLE_CARTE, url="/"),
        palier=2,
        segment_palier=None,
        meteo=None,
        regles=[],
        aucune_regle=None,
        kpi=[],
        aucun_kpi=None,
        prevision=None,
        risque=None,
        explication=None,
    )


def vue_detail_erreur(erreur: str) -> VueDetail:
    """Détail vide dont la lecture a échoué : le bandeau d'erreur porte le détail."""
    return vue_detail_message("").model_copy(
        update={"erreur": erreur, "message": None, "lien_message": None}
    )


def vue_detail(consultation: LectureDetail, entite: str, palier_demande: Palier = 2) -> VueDetail:
    """Vue du détail de `entite` ; `palier_demande` vaut `?palier=` (Palier 1 ou 2, FR-46).

    Sur un Passage de Palier 2, `palier_demande=1` affiche l'Explication du Palier 1
    (`EXPLICATION_PALIER_1`) et masque la Prévision ; Météo, Règles, KPI et Risque ne changent
    pas. Sur un Passage de Palier 1, le segment est absent et aucune sortie LLM n'est lue.
    """
    manifeste = consultation.manifeste()
    meteos = entites_triees(consultation.meteo())
    if not meteos:
        return vue_detail_message("Ce Passage ne contient aucune Météo.")
    entites = [VueLien(libelle=m.entite, url=url_detail(m.entite)) for m in meteos]
    meteo = next((m for m in meteos if m.entite == entite), None)
    if meteo is None:
        return vue_detail_message(entite_absente(entite), entites)
    avec_segment = manifeste.palier == 2
    palier: Palier = 1 if not avec_segment or palier_demande == 1 else 2
    calculees = previsions_calculees(manifeste)
    kpi = _kpi_cles(consultation.kpi(entite=entite), lambda dimension: dimension)
    narrations = consultation.narrations(entite=entite, palier=palier)
    explications = consultation.explications(entite=entite, palier=palier)
    previsions = consultation.previsions(entite=entite)
    risques = consultation.risques(entite=entite)
    masquer_prevision = avec_segment and palier == 1
    return VueDetail(
        erreur=None,
        message=None,
        lien_message=None,
        entite=entite,
        entites=entites,
        lien_carte=VueLien(libelle=LIBELLE_CARTE, url="/"),
        palier=palier,
        segment_palier=_segment_palier(palier) if avec_segment else None,
        meteo=vue_meteo(meteo.couleur),
        regles=[
            VueRegle(
                regle=formater_regle(regle),
                tickets=vues_tickets(regle.tickets_en_cause[:TICKETS_MAX], consultation.url_ticket),
                tickets_suite=vues_tickets(
                    regle.tickets_en_cause[TICKETS_MAX:], consultation.url_ticket
                ),
                libelle_suite=libelle_suite(len(regle.tickets_en_cause) - TICKETS_MAX),
            )
            for regle in meteo.regles
        ],
        aucune_regle=None if meteo.regles else AUCUNE_REGLE,
        kpi=[VueLigneKpi(libelle=ligne["KPI"], valeur=ligne["Valeur"]) for ligne in kpi],
        aucun_kpi=None if kpi else AUCUN_KPI,
        prevision=None
        if masquer_prevision
        else section_prevision(meteo, previsions, calculees, narrations),
        risque=section_risque(meteo, risques, calculees),
        explication=section_explication(palier, explications, consultation.url_ticket),
    )
