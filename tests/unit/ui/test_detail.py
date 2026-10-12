"""Détail d'une Entité (Palier 1) : blocs en fonctions pures, alignement sur `Consultation`."""

import inspect
import re
from datetime import date
from fractions import Fraction
from pathlib import Path

import polars as pl
import pytest

from usine.contrats.format import formater_date, formater_fraction, formater_pourcentage
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
from usine.ui.carte import formater_regle
from usine.ui.cli import consultation_dernier_passage
from usine.ui.detail import (
    AUCUN_RISQUE,
    AUCUNE_REGLE,
    EXPLICATION_PALIER_1,
    EXPLICATION_PALIER_2,
    KPI_CLES,
    PREVISION_NON_CALCULEE_ENTITE,
    PREVISION_NON_CALCULEE_PASSAGE,
    PREVISION_SANS_OBJET,
    RISQUE_NON_CALCULE_PASSAGE,
    RISQUE_SANS_OBJET,
    LectureDetail,
    lignes_kpi,
    lignes_regles,
    previsions_calculees,
    texte_explication,
    texte_prevision,
    texte_risques,
    valeur_kpi,
)
from usine.ui.liens import echapper_markdown

DATE = date(2026, 10, 9)
METHODES = ["manifeste", "meteo", "kpi", "previsions", "risques", "url_ticket"]


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


def test_codes_kpi_presents_dans_le_passage(racine_publiee: Path) -> None:
    consultation = consultation_dernier_passage(racine_publiee)
    assert consultation is not None
    codes = set(consultation.kpi()["code_kpi"].to_list())
    assert set(KPI_CLES) <= codes
    for meteo in consultation.meteo():
        table = consultation.kpi(entite=meteo.entite)
        lignes = lignes_kpi(table)
        attendues = table.filter(pl.col("code_kpi").is_in(list(KPI_CLES))).height
        assert len(lignes) == attendues > 0


def test_passage_d_essai_previsions_reelles(racine_publiee: Path) -> None:
    """Étape `prevision` réussie (Story 5.3) : chaque Entité rouge montre sa Prévision publiée."""
    consultation = consultation_dernier_passage(racine_publiee)
    assert consultation is not None
    assert previsions_calculees(consultation.manifeste())
    rouges = [m for m in consultation.meteo() if m.couleur is Couleur.rouge]
    assert rouges
    for meteo in rouges:
        previsions = consultation.previsions(entite=meteo.entite)
        texte = texte_prevision(meteo, previsions, True)
        assert previsions
        for prevision in previsions:
            if prevision.statut is StatutPrevision.regle_non_projetable:
                codes = ", ".join(c.value for c in prevision.regles_non_projetables)
                assert f"règle non projetable ({codes})" in texte
            for facteur in prevision.facteurs:
                valeur = formater_fraction(Fraction(facteur.numerateur, facteur.denominateur))
                assert f"{echapper_markdown(facteur.libelle)} : {valeur}" in texte
        risques = consultation.risques(entite=meteo.entite)
        assert texte_risques(meteo, risques, True) == RISQUE_SANS_OBJET


def test_regles_du_passage_d_essai(racine_publiee: Path) -> None:
    consultation = consultation_dernier_passage(racine_publiee)
    assert consultation is not None
    for meteo in consultation.meteo():
        lignes = lignes_regles(meteo, consultation.url_ticket)
        assert [ligne["Règle"] for ligne in lignes] == [formater_regle(r) for r in meteo.regles]
        for ligne, regle in zip(lignes, meteo.regles, strict=True):
            for cle in regle.tickets_en_cause:
                assert f"[{cle}]({consultation.url_ticket(cle)})" in ligne["Tickets en cause"]


# Règles déclenchantes


def test_lignes_regles_tous_les_tickets() -> None:
    tickets = tuple(f"DEMO-{n}" for n in range(1, 6))
    meteo = _meteo(regles=(_regle(CodeIndicateur.ind_2, tickets), _regle(CodeIndicateur.ind_5, ())))
    lignes = lignes_regles(meteo, _url)
    assert lignes[0]["Règle"] == "IND-2 : 11 (seuil ≥ 10)"
    assert lignes[0]["Tickets en cause"] == ", ".join(f"[{c}]({_url(c)})" for c in tickets)
    assert lignes[1] == {"Règle": "IND-5 : 11 (seuil ≥ 10)", "Tickets en cause": "—"}


def test_lignes_regles_en_mode_repli() -> None:
    lignes = lignes_regles(ROUGE, _sans_url)
    assert lignes[0]["Tickets en cause"] == "DEMO-1"
    assert "](http" not in lignes[0]["Tickets en cause"]


def test_entite_verte() -> None:
    assert lignes_regles(VERTE, _url) == []
    assert AUCUNE_REGLE == "Aucune Règle déclenchante (Entité verte)."
    assert texte_prevision(VERTE, (), True) == PREVISION_SANS_OBJET


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


def test_lignes_kpi() -> None:
    table = _table_kpi(
        [
            ("taux_ko_cas_de_test", "recette", 0, 0),
            ("taux_ko_cas_de_test", "tnr", 1, 8),
            ("age_max_anomalies_ouvertes", "", 7, 0),
            ("anomalies_ouvertes", "", 2, 1),
            ("certifications", "accordee", 1, 1),
            ("age_median_anomalies_ouvertes", "", 3, 2),
        ]
    )
    assert lignes_kpi(table) == [
        {"KPI": "Anomalies ouvertes", "Valeur": "2"},
        {"KPI": "Âge médian des Anomalies ouvertes", "Valeur": "1,5"},
        {"KPI": "Âge maximal des Anomalies ouvertes", "Valeur": "∞"},
        {"KPI": "Taux KO des Cas de test (recette)", "Valeur": "—"},
        {"KPI": "Taux KO des Cas de test (tnr)", "Valeur": "12,5 %"},
    ]


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


def test_sortie_projetee() -> None:
    texte = texte_prevision(ROUGE, (_prevision(StatutPrevision.sortie_projetee),), True)
    assert "20/10/2026" in texte
    assert "16/10/2026 – 23/10/2026" in texte
    assert formater_pourcentage(Fraction(3, 4)) in texte
    assert "10 jours ouvrés" in texte
    assert "baseline" in texte
    assert "Stock d'Anomalies : 12" in texte
    assert "Vélocité : 1,5" in texte


def test_pas_de_sortie_projetee() -> None:
    texte = texte_prevision(ROUGE, (_prevision(StatutPrevision.pas_de_sortie_projetee),), True)
    assert "pas de sortie projetée" in texte
    assert formater_pourcentage(Fraction(3, 4)) in texte
    assert "10 jours ouvrés" in texte
    assert "Stock d'Anomalies : 12" in texte
    assert not re.search(r"\d{2}/\d{2}/\d{4}", texte)


def test_regle_non_projetable() -> None:
    texte = texte_prevision(ROUGE, (_prevision(StatutPrevision.regle_non_projetable),), True)
    assert "pas de sortie projetée : règle non projetable (IND-2)" in texte
    assert "Stock d'Anomalies : 12" in texte


def test_rouge_sans_prevision() -> None:
    autre = _prevision(StatutPrevision.sortie_projetee, entite="ENT-C")
    assert texte_prevision(ROUGE, (autre,), True) == PREVISION_NON_CALCULEE_ENTITE
    assert texte_prevision(ROUGE, (), False) == PREVISION_NON_CALCULEE_PASSAGE


# Risque d'entrée en rouge


def test_non_rouge_avec_risque() -> None:
    texte = texte_risques(VERTE, (_risque(),), True)
    assert "IND-1" in texte
    assert "| 8 |" in texte
    assert "| 10 |" in texte
    assert formater_date(date(2026, 10, 15)) in texte
    assert "10 jours ouvrés" in texte


def test_non_rouge_sans_risque() -> None:
    assert texte_risques(VERTE, (_risque("ENT-C"),), True) == AUCUN_RISQUE
    assert AUCUN_RISQUE == "Aucun Risque d'entrée en rouge dans l'horizon."


def test_risque_entite_rouge() -> None:
    assert texte_risques(ROUGE, (_risque("ENT-A"),), True) == RISQUE_SANS_OBJET
    assert texte_risques(VERTE, (), False) == RISQUE_NON_CALCULE_PASSAGE


def test_valeur_projetee() -> None:
    projete = _risque().model_copy(
        update={"valeur_projetee_numerateur": 23, "valeur_projetee_denominateur": 2}
    )
    texte = texte_risques(VERTE, (projete,), True)
    assert "| Valeur projetée |" in texte
    assert "10 jours ouvrés | 11,5 |" in texte
    assert "Valeur projetée" not in texte_risques(VERTE, (_risque(),), True)
    mixte = texte_risques(VERTE, (projete, _risque()), True)
    assert "10 jours ouvrés | — |" in mixte


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


def test_explication() -> None:
    assert texte_explication(1) == "commentaire non généré (Palier 1)" == EXPLICATION_PALIER_1
    assert texte_explication(2) == "Explication sourcée : Story 7.7" == EXPLICATION_PALIER_2
