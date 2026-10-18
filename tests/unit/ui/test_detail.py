"""Détail d'une Entité : blocs en fonctions pures, alignement sur `Consultation`."""

import inspect
from datetime import date
from fractions import Fraction
from pathlib import Path

import polars as pl
import pytest

from usine.contrats.format import formater_fraction, formater_pourcentage
from usine.contrats.llm import SortieExplication, SortieNarration, StatutControle
from usine.contrats.meteo import CodeIndicateur, Couleur, MeteoEntite, Operateur, RegleDeclenchante
from usine.contrats.passage import Etape, StatutEtape
from usine.contrats.prevision import (
    FacteurExplicatif,
    MethodePrevision,
    Prevision,
    RisqueEntreeRouge,
    StatutPrevision,
)
from usine.ports.consultation import Consultation
from usine.ui.cli import consultation_dernier_passage
from usine.ui.detail import (
    KPI_CLES,
    LectureDetail,
    previsions_calculees,
    valeur_kpi,
)

DATE = date(2026, 10, 9)
METHODES = [
    "manifeste",
    "meteo",
    "kpi",
    "previsions",
    "risques",
    "explications",
    "narrations",
    "url_ticket",
]


def _url(cle: str) -> str:
    return f"https://jira.example.invalid/browse/{cle}"


def _sans_url(_cle: str) -> None:
    return None


def _regle(code: CodeIndicateur, tickets: tuple[str, ...]) -> RegleDeclenchante:
    return RegleDeclenchante(
        code=code,
        couleur=Couleur.rouge,
        operateur=Operateur.superieur_ou_egal,
        numerateur=11,
        denominateur=1,
        seuil_numerateur=10,
        seuil_denominateur=1,
        tickets_en_cause=tickets,
    )


def _meteo(entite: str = "ENT-A", regles: tuple[RegleDeclenchante, ...] = ()) -> MeteoEntite:
    return MeteoEntite(
        date_arrete=DATE,
        entite=entite,
        couleur=Couleur.rouge if regles else Couleur.vert,
        regles=regles,
        version_grille="abc",
    )


ROUGE = _meteo(regles=(_regle(CodeIndicateur.ind_2, ("DEMO-1",)),))
VERTE = _meteo("ENT-B")
FACTEURS = (
    FacteurExplicatif(nom="stock", libelle="Stock d'Anomalies", numerateur=12, denominateur=1),
    FacteurExplicatif(nom="velocite", libelle="Vélocité", numerateur=3, denominateur=2),
)


def _prevision(statut: StatutPrevision, entite: str = "ENT-A") -> Prevision:
    projetee = statut is StatutPrevision.sortie_projetee
    return Prevision(
        date_arrete=DATE,
        entite=entite,
        methode=MethodePrevision.baseline,
        statut=statut,
        date_sortie_estimee=date(2026, 10, 20) if projetee else None,
        date_sortie_optimiste=date(2026, 10, 16) if projetee else None,
        date_sortie_pessimiste=date(2026, 10, 23) if projetee else None,
        probabilite_numerateur=3,
        probabilite_denominateur=4,
        horizon_jours_ouvres=10,
        facteurs=FACTEURS,
        regles_non_projetables=(
            (CodeIndicateur.ind_2,) if statut is StatutPrevision.regle_non_projetable else ()
        ),
        version_grille="abc",
    )


def _risque(entite: str = "ENT-B") -> RisqueEntreeRouge:
    return RisqueEntreeRouge(
        date_arrete=DATE,
        entite=entite,
        indicateur=CodeIndicateur.ind_1,
        date_franchissement_estimee=date(2026, 10, 15),
        horizon_jours_ouvres=10,
        numerateur=8,
        denominateur=1,
        seuil_numerateur=10,
        seuil_denominateur=1,
        version_grille="abc",
    )


# Alignement du Protocol local sur le port


@pytest.mark.parametrize("nom", METHODES)
def test_lecture_detail_alignee_sur_consultation(nom: str) -> None:
    assert inspect.signature(getattr(LectureDetail, nom)) == inspect.signature(
        getattr(Consultation, nom)
    )


def test_lecture_detail_sans_methode_inconnue() -> None:
    methodes = {
        nom
        for nom, valeur in vars(LectureDetail).items()
        if inspect.isfunction(valeur) and not nom.startswith("_")
    }
    assert methodes == set(METHODES)


# Passage d'essai (graine 42, 09/10/2026)


# Règles déclenchantes


# KPI clés


def _table_kpi(lignes: list[tuple[str, str, int, int]]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "date": [DATE] * len(lignes),
            "perimetre": ["ENT-A"] * len(lignes),
            "code_kpi": [code for code, _, _, _ in lignes],
            "dimension": [dimension for _, dimension, _, _ in lignes],
            "numerateur": [n for _, _, n, _ in lignes],
            "denominateur": [d for _, _, _, d in lignes],
        }
    )


def test_valeur_kpi() -> None:
    assert valeur_kpi("anomalies_ouvertes", 0, 0) == "—"
    assert valeur_kpi("anomalies_ouvertes", 3, 0) == "∞"
    assert valeur_kpi("anomalies_ouvertes", 1234, 1) == formater_fraction(Fraction(1234))
    assert valeur_kpi("taux_ko_cas_de_test", 1, 3) == formater_pourcentage(Fraction(1, 3))


def test_kpi_cles_ordre() -> None:
    assert list(KPI_CLES) == [
        "anomalies_ouvertes",
        "entrees_fenetre",
        "sorties_fenetre",
        "age_median_anomalies_ouvertes",
        "age_max_anomalies_ouvertes",
        "taux_ko_cas_de_test",
    ]


# Prévision de sortie du rouge


# Risque d'entrée en rouge


@pytest.mark.parametrize(
    ("statut", "attendu"),
    [
        (StatutEtape.reussie, True),
        (StatutEtape.sautee, False),
        (StatutEtape.echouee, False),
        (None, False),
    ],
)
def test_previsions_calculees(
    racine_publiee: Path, statut: StatutEtape | None, attendu: bool
) -> None:
    consultation = consultation_dernier_passage(racine_publiee)
    assert consultation is not None
    manifeste = consultation.manifeste()
    etapes = tuple(
        e if e.etape is not Etape.prevision else e.model_copy(update={"statut": statut})
        for e in manifeste.etapes
        if statut is not None or e.etape is not Etape.prevision
    )
    assert previsions_calculees(manifeste.model_copy(update={"etapes": etapes})) is attendu


# Explication


def _explication(
    texte: str = "ENT-A est rouge : DEMO-12 et DEMO-1 bloquent la recette (DEMO-1).",
    citations: tuple[str, ...] = ("DEMO-1", "DEMO-12"),
    phrases_retirees: int = 1,
    statut: StatutControle = StatutControle.corrige,
) -> SortieExplication:
    return SortieExplication(
        date_arrete=DATE,
        entite="ENT-A",
        texte=texte,
        citations=citations,
        brouillon_commentaire="",
        phrases_retirees=phrases_retirees,
        statut_controle=statut,
    )


def _narration(statut: StatutControle, entite: str = "ENT-A") -> SortieNarration:
    return SortieNarration(
        date_arrete=DATE,
        entite=entite,
        texte="La sortie du rouge est attendue sous deux semaines.",
        statut_controle=statut,
    )
