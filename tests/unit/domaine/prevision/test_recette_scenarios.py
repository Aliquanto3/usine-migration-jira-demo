"""Recette de la Prévision sur les Scénarios de démo par la Chaîne (Story 4.5, SM-6).

Un Passage réel (`composition.lancer_rapport`, étape `prevision` câblée sur
`prevision_du_passage`) s'exécute sur le Journal généré (`composition.generer_journal`) avec la
configuration et les gabarits livrés (Grille et seuils inchangés, SM-C3). `previsions.json` est
relu par `ConsultationPassage` à la Date d'arrêté D, dernier Jour ouvré avant la génération.

À D : seules A et B sont rouges ; A sort du rouge dans l'horizon, B ne sort pas, aucune des deux
n'a de règle non projetable ; C porte un Risque IND-4 ; tout Risque publié porte sa valeur
projetée. Recoupement : `series_stock` sur l'état des tickets du Passage = IND-1 publié.
"""

import shutil
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import polars as pl
import pytest

from usine.composition import generer_journal, lancer_rapport
from usine.config import charger_yaml
from usine.consultation.passage import ConsultationPassage
from usine.contrats.calendrier import jour_ouvre_precedent
from usine.contrats.config import ConfigProgramme
from usine.contrats.meteo import CodeIndicateur, Couleur
from usine.contrats.prevision import StatutPrevision
from usine.domaine.prevision.commun import avancer
from usine.domaine.prevision.serie import series_stock

RACINE_DEPOT = Path(__file__).resolve().parents[4]
GRAINE = 42
DATE_GENERATION = date(2026, 10, 12)
"""Lundi : D est le vendredi 2026-10-09."""
GENERATION_MARDI = date(2026, 10, 13)
"""Mardi : D est le lundi 2026-10-12 (SM-6 hors vendredi, suite rapide)."""
GRAINES_LENTES = (1, 7, 123)


@dataclass(frozen=True)
class _Recette:
    date_arrete: date
    consultation: ConsultationPassage


def _recette(racine: Path, date_generation: date, graine: int = GRAINE) -> _Recette:
    """Passage réel sur le Journal généré le `date_generation`, D = Jour ouvré précédent."""
    for repertoire in ("config", "gabarits"):
        shutil.copytree(RACINE_DEPOT / repertoire, racine / repertoire)
    programme = charger_yaml(racine / "config" / "programme.yaml", ConfigProgramme)
    generer_journal(programme, graine, date_generation, racine)
    arrete = jour_ouvre_precedent(date_generation, 1)
    instant = datetime.combine(date_generation, time(7, 30), tzinfo=UTC)
    lance = lancer_rapport(racine, arrete, lambda: instant, lambda: "4e5a00")
    return _Recette(arrete, ConsultationPassage(lance.repertoire))


def _ecarts_sm6(recette: _Recette) -> list[str]:
    """Écarts à SM-6, à la valeur projetée et au recoupement `stock` = IND-1 ; vides si tenu."""
    ecarts: list[str] = []
    consultation, arrete = recette.consultation, recette.date_arrete
    rouges = sorted(m.entite for m in consultation.meteo(arrete) if m.couleur is Couleur.rouge)
    if rouges != ["ENT-A", "ENT-B"]:
        ecarts.append(f"Entités rouges à {arrete} : {rouges}, attendu ENT-A et ENT-B")

    publiees = consultation.previsions(arrete)
    if [p.entite for p in publiees] != ["ENT-A", "ENT-B"]:
        ecarts.append(f"Prévisions à {arrete} : {[p.entite for p in publiees]}, attendu A puis B")
    previsions = {p.entite: p for p in publiees}
    a, b = previsions.get("ENT-A"), previsions.get("ENT-B")
    if a is None or a.statut is not StatutPrevision.sortie_projetee:
        ecarts.append(f"A : {a and a.statut} {a and a.regles_non_projetables}, sortie attendue")
    else:
        horizon = avancer(arrete, a.horizon_jours_ouvres)
        if a.date_sortie_estimee is None or not arrete < a.date_sortie_estimee <= horizon:
            ecarts.append(f"A : sortie estimée {a.date_sortie_estimee} hors ]{arrete}, {horizon}]")
        if a.regles_non_projetables != ():
            ecarts.append(f"A : règles non projetables {a.regles_non_projetables}")
    if b is None or b.statut is not StatutPrevision.pas_de_sortie_projetee:
        ecarts.append(f"B : {b and b.statut} {b and b.regles_non_projetables}, pas de sortie")
    elif b.regles_non_projetables != ():
        ecarts.append(f"B : règles non projetables {b.regles_non_projetables}")

    risques_c = consultation.risques(arrete, "ENT-C")
    if CodeIndicateur.ind_4 not in {r.indicateur for r in risques_c}:
        ecarts.append(f"C : aucun Risque IND-4 à {arrete}")
    for jour in consultation.dates_disponibles():
        for risque in consultation.risques(jour):
            projetee = (risque.valeur_projetee_numerateur, risque.valeur_projetee_denominateur)
            if None in projetee:
                ecarts.append(f"Risque {risque.entite} {risque.indicateur} du {jour} : {projetee}")

    ecarts.extend(_ecarts_stock_ind_1(consultation))
    return ecarts


def _ecarts_stock_ind_1(consultation: ConsultationPassage) -> list[str]:
    """`series_stock` sur l'état des tickets du Passage = IND-1 publié, Entité par Jour ouvré."""
    jours = consultation.dates_disponibles()
    entites = [m.entite for m in consultation.meteo(jours[-1])]
    etats = pl.concat([consultation.tickets_etats(jour) for jour in jours], how="vertical")
    series = series_stock(etats, entites, jours)
    ind_1 = (
        pl.concat([consultation.indicateurs(jour) for jour in jours], how="vertical")
        .filter(pl.col("code") == CodeIndicateur.ind_1.value)
        .select(pl.col("entite").alias("serie"), "date", pl.col("numerateur").alias("ind_1"))
    )
    recoupement = series.join(ind_1, on=["serie", "date"], how="full", coalesce=True)
    differents = recoupement.filter(
        pl.col("stock").is_null() | pl.col("ind_1").is_null() | (pl.col("stock") != pl.col("ind_1"))
    )
    ecarts: list[str] = []
    if series.height != len(entites) * len(jours):
        ecarts.append(f"SerieStock : {series.height} lignes pour {len(entites)} × {len(jours)}")
    if differents.height:
        ecarts.append(f"stock ≠ IND-1 : {differents.head(5).rows()}")
    return ecarts


@pytest.fixture(scope="module")
def recette_vendredi(tmp_path_factory: pytest.TempPathFactory) -> _Recette:
    """Graine 42, génération le lundi 2026-10-12 : un seul Passage pour les tests rapides."""
    return _recette(tmp_path_factory.mktemp("recette-vendredi"), DATE_GENERATION)


def test_recette_sm6(recette_vendredi: _Recette) -> None:
    """D = vendredi 2026-10-09 : SM-6 tenu par la Chaîne."""
    assert recette_vendredi.date_arrete == date(2026, 10, 9)
    assert _ecarts_sm6(recette_vendredi) == []
    consultation = recette_vendredi.consultation
    previsions = consultation.previsions(recette_vendredi.date_arrete)
    assert [p.entite for p in previsions] == ["ENT-A", "ENT-B"]
    # Chaque Jour ouvré de l'historique est publié.
    assert len(consultation.dates_disponibles()) == 40


def test_risques_publies_avec_valeur_projetee(recette_vendredi: _Recette) -> None:
    """Un Risque publié d'une Entité non rouge porte la valeur projetée de `risque.py`."""
    consultation = recette_vendredi.consultation
    risques = consultation.risques(recette_vendredi.date_arrete, "ENT-C")
    assert risques
    for risque in risques:
        assert risque.valeur_projetee_numerateur is not None
        assert risque.valeur_projetee_denominateur is not None
        assert risque.valeur_projetee_denominateur > 0
        couleurs = [m.couleur for m in consultation.meteo(risque.date_arrete, risque.entite)]
        assert couleurs and Couleur.rouge not in couleurs


def test_recette_sm6_hors_vendredi(tmp_path: Path) -> None:
    """Génération le mardi 2026-10-13 (D = lundi 12/10) : SM-6 et IND-4 pour C tiennent."""
    recette = _recette(tmp_path, GENERATION_MARDI)
    assert recette.date_arrete == date(2026, 10, 12)
    assert _ecarts_sm6(recette) == []


@pytest.mark.lent
@pytest.mark.parametrize(
    "date_generation",
    [DATE_GENERATION + timedelta(days=n) for n in (2, 3, 4, 5)],
    ids=["mercredi", "jeudi", "vendredi", "samedi"],
)
def test_recette_sm6_derniere_semaine_partielle(tmp_path: Path, date_generation: date) -> None:
    """Dernière semaine partielle (génération du mercredi au samedi, D mardi à vendredi)."""
    recette = _recette(tmp_path, date_generation)
    assert recette.date_arrete == jour_ouvre_precedent(date_generation, 1)
    assert _ecarts_sm6(recette) == []


@pytest.mark.lent
@pytest.mark.parametrize("graine", GRAINES_LENTES)
def test_recette_sm6_autres_graines(tmp_path: Path, graine: int) -> None:
    """Autres graines, génération le 2026-10-12 : SM-6 tenu."""
    assert _ecarts_sm6(_recette(tmp_path, DATE_GENERATION, graine)) == []
