"""Modèle ML de résolution des bloquantes (Story 4.6, FR-22, SM-8).

Données synthétiques seulement : chaque série a un régime de résolution persistant (taux par
bloquante et par Jour ouvré, rapide ou lent), des Entrées de Poisson ; les Parquet réels ne
servent qu'à la commande documentée dans `evaluation/zenodo/README.md`.
"""

import json
import os
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import pytest

from evaluation.zenodo.evaluation import (
    HISTORIQUE,
    HORIZON,
    decouper,
    prolonger_par_depot,
    unites,
)
from evaluation.zenodo.modele_ml import (
    CARACTERISTIQUES,
    caracteristiques,
    entrainer,
    evaluer_ml,
    main,
    predire_ml,
    prevoir_entites,
    probabilites_bloquante,
    series_ml,
    verdict_sm8,
)
from usine.contrats.calendrier import jours_ouvres
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import CodeIndicateur, Couleur, MeteoEntite, Operateur, RegleDeclenchante
from usine.contrats.prevision import SCHEMA_SERIE_STOCK, MethodePrevision, StatutPrevision

DEBUT = date(2020, 1, 6)
JOURS = 700


def _serie(nom: str, taux: float, graine: int, jours: int = JOURS) -> pl.DataFrame:
    """Série dense : Entrées de Poisson(0,35), chaque bloquante résolue avec probabilité `taux`."""
    hasard = np.random.default_rng(graine)
    dates = jours_ouvres(DEBUT, DEBUT + timedelta(days=2 * jours))[:jours]
    stock = 4
    lignes: dict[str, list[Any]] = {k: [] for k in SCHEMA_SERIE_STOCK.colonnes}
    for jour in dates:
        entrees = int(hasard.poisson(0.35))
        sorties = int(hasard.binomial(stock, taux))
        stock = stock + entrees - sorties
        lignes["serie"].append(nom)
        lignes["date"].append(jour)
        lignes["stock"].append(stock)
        lignes["entrees"].append(entrees)
        lignes["sorties"].append(sorties)
    return pl.DataFrame(lignes, schema=dict(SCHEMA_SERIE_STOCK.colonnes))


@pytest.fixture(scope="module")
def series() -> pl.DataFrame:
    rapides = [_serie(f"d/R{i}", 0.12, i) for i in range(10)]
    lentes = [_serie(f"d/L{i}", 0.02, 100 + i) for i in range(10)]
    return pl.concat([*rapides, *lentes])


def test_caracteristiques_calculees_a_la_main() -> None:
    stock = np.arange(1, 26)
    entrees = np.ones(25, dtype=int)
    sorties = np.arange(25) % 2
    matrice = caracteristiques(stock, entrees, sorties)
    assert matrice.shape == (25, len(CARACTERISTIQUES))
    ligne = dict(zip(CARACTERISTIQUES, matrice[24], strict=True))
    assert ligne["stock"] == 25
    assert ligne["entrees_5"] == 5 and ligne["entrees_20"] == 20
    assert ligne["sorties_5"] == 2 and ligne["sorties_10"] == 5 and ligne["sorties_20"] == 10
    assert ligne["variation_stock_10"] == 10
    assert ligne["stock_max_20"] == 25
    assert np.isnan(matrice[18, CARACTERISTIQUES.index("stock_max_20")])


def test_caracteristiques_serie_courte() -> None:
    matrice = caracteristiques(np.array([1, 2, 3]), np.array([1, 1, 1]), np.array([0, 0, 0]))
    assert matrice.shape == (3, len(CARACTERISTIQUES))
    assert np.isnan(matrice[:, 1:]).all()


def test_ml_bat_baseline_sur_donnees_synthetiques(series: pl.DataFrame) -> None:
    resultat = evaluer_ml(series)
    jeu = resultat["jeux"]["test_projets_tenus_a_l_ecart"]
    temporel = resultat["jeux"]["test_temporel"]
    assert jeu["effectif"] > 0 and temporel["effectif"] > 0
    assert resultat["protocole"]["horizon_jours_ouvres"] == HORIZON == 10
    assert resultat["protocole"]["modele"].startswith("LightGBM 4.7.0")
    assert temporel["ml"]["auc"] > temporel["baseline"]["auc"]
    assert temporel["ml_bat_baseline_auc"] is True
    for nom in ("ml", "baseline", "naive"):
        assert 0 <= temporel[nom]["brier"] <= 1
    assert list(resultat["entrainement"]["importance_gain"]) == list(CARACTERISTIQUES)


def test_evaluation_deterministe(series: pl.DataFrame) -> None:
    assert evaluer_ml(series) == evaluer_ml(series)


def test_predictions_methode_ml(series: pl.DataFrame) -> None:
    prolongees = prolonger_par_depot(series)
    decoupage = decouper(unites(prolongees))
    modele = entrainer(prolongees, decoupage)
    par_serie = series_ml(prolongees)
    jeu = decoupage.test_temporel[:25]
    previsions = predire_ml(modele, par_serie, jeu)
    probabilites = probabilites_bloquante(modele, par_serie, jeu)
    assert len(previsions) == len(jeu) == len(probabilites)
    assert all(p.methode is MethodePrevision.ml for p in previsions)
    assert all(0 <= p <= 1 for p in probabilites)
    assert all(p.horizon_jours_ouvres == HORIZON for p in previsions)
    assert probabilites_bloquante(modele, par_serie, []) == []


def test_regime_rapide_anticipe_la_sortie_et_regime_lent_le_maintien(
    series: pl.DataFrame,
) -> None:
    """Analogue synthétique de A (sortie) et B (maintien) : un régime rapide sort, un lent reste."""
    prolongees = prolonger_par_depot(series)
    modele = entrainer(prolongees, decouper(unites(prolongees)))
    par_serie = series_ml(prolongees)

    def probabilite(nom: str) -> Fraction:
        s = par_serie[nom]
        ligne = s.caracteristiques[300:301]
        return Fraction(float(modele.predict(ligne)[0])).limit_denominator(10**6)

    moyennes_rapides = [probabilite(f"d/R{i}") for i in range(10)]
    moyennes_lentes = [probabilite(f"d/L{i}") for i in range(10)]
    assert sum(moyennes_rapides) / 10 > sum(moyennes_lentes) / 10 * 2


def test_verdict_sm8() -> None:
    jeu: dict[str, Any] = {
        "ml": {"brier": 0.1, "auc": 0.9},
        "baseline": {"brier": 0.2, "auc": 0.6},
        "ml_bat_baseline_auc": True,
        "ml_bat_baseline_brier": True,
    }
    mauvais = jeu | {"ml_bat_baseline_brier": False}
    vide = {"ml": None}
    assert verdict_sm8({"jeux": {"a": jeu, "b": vide}}) == []
    avertissements = verdict_sm8({"jeux": {"a": jeu, "b": mauvais}})
    assert len(avertissements) == 1 and "sur b" in avertissements[0]


def test_cli_succes(
    series: pl.DataFrame, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    chemin = tmp_path / "s.parquet"
    series.write_parquet(chemin)
    sortie = tmp_path / "sous" / "ml.json"
    assert main(["--series", str(chemin), "--sortie", str(sortie)]) == 0
    ecrit = json.loads(sortie.read_text(encoding="utf-8"))
    assert set(ecrit["jeux"]) == {"test_temporel", "test_projets_tenus_a_l_ecart"}
    assert "ml : Brier" in capsys.readouterr().out


def test_cli_aucune_unite(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    chemin = tmp_path / "courte.parquet"
    _serie("d/A", 0.1, 1, jours=HISTORIQUE).write_parquet(chemin)
    assert main(["--series", str(chemin), "--sortie", str(tmp_path / "x.json")]) == 1
    assert "aucune unité" in capsys.readouterr().err


def test_evaluer_ml_sans_unite() -> None:
    with pytest.raises(UsineErreur, match="aucune unité"):
        evaluer_ml(_serie("d/A", 0.1, 1, jours=HISTORIQUE))


def test_statuts_possibles(series: pl.DataFrame) -> None:
    prolongees = prolonger_par_depot(series)
    decoupage = decouper(unites(prolongees))
    modele = entrainer(prolongees, decoupage)
    previsions = predire_ml(modele, series_ml(prolongees), decoupage.test_temporel)
    assert {p.statut for p in previsions} <= {
        StatutPrevision.sortie_projetee,
        StatutPrevision.pas_de_sortie_projetee,
    }


def passage_demo(racine: Path) -> tuple[pl.DataFrame, list[MeteoEntite]]:
    """Passage de démo (graine 42, D = 2026-10-09) : `SerieStock` et Météo des Entités rouges."""
    import shutil
    from datetime import UTC, datetime, time

    from usine.composition import generer_journal, lancer_rapport
    from usine.config import charger_yaml
    from usine.consultation.passage import ConsultationPassage
    from usine.contrats.config import ConfigProgramme
    from usine.contrats.meteo import Couleur
    from usine.domaine.prevision.serie import series_stock

    depot = Path(__file__).resolve().parents[4]
    for repertoire in ("config", "gabarits"):
        shutil.copytree(depot / repertoire, racine / repertoire)
    programme = charger_yaml(racine / "config" / "programme.yaml", ConfigProgramme)
    generation, arrete = date(2026, 10, 12), date(2026, 10, 9)
    generer_journal(programme, 42, generation, racine)
    instant = datetime.combine(generation, time(7, 30), tzinfo=UTC)
    consultation = ConsultationPassage(
        lancer_rapport(racine, arrete, lambda: instant, lambda: "4e6a00").repertoire
    )
    jours = consultation.dates_disponibles()
    etats = pl.concat([consultation.tickets_etats(jour) for jour in jours], how="vertical")
    rouges = [m for m in consultation.meteo(arrete) if m.couleur is Couleur.rouge]
    return series_stock(etats, [m.entite for m in rouges], jours), rouges


@pytest.mark.lent
def test_scenarios_de_demo_via_la_chaine(series: pl.DataFrame, tmp_path: Path) -> None:
    """Le ML s'applique au Passage de démo : A sort (probabilité haute), A au-dessus de B.

    Le maintien de B dépend du modèle appris sur données réelles (spec 4.6), pas du modèle
    synthétique de ce test.
    """
    demo, rouges = passage_demo(tmp_path)
    assert [m.entite for m in rouges] == ["ENT-A", "ENT-B"]
    prolongees = prolonger_par_depot(series)
    modele = entrainer(prolongees, decouper(unites(prolongees)))
    a, b = prevoir_entites(modele, demo, rouges)
    assert (a.methode, b.methode) == (MethodePrevision.ml, MethodePrevision.ml)
    assert a.statut is StatutPrevision.sortie_projetee
    assert Fraction(a.probabilite_numerateur, a.probabilite_denominateur) > Fraction(
        b.probabilite_numerateur, b.probabilite_denominateur
    )


def test_prevoir_entites_historique_court(series: pl.DataFrame) -> None:
    prolongees = prolonger_par_depot(series)
    modele = entrainer(prolongees, decouper(unites(prolongees)))
    courte = _serie("d/C", 0.1, 3, jours=12).with_columns(pl.lit(5, dtype=pl.Int64).alias("stock"))
    meteo = _meteo_rouge("d/C", courte["date"][-1], 5)
    with pytest.raises(UsineErreur, match="moins de 20"):
        prevoir_entites(modele, courte, [meteo])


def test_prevoir_entites_entite_ou_date_absente(series: pl.DataFrame) -> None:
    prolongees = prolonger_par_depot(series)
    modele = entrainer(prolongees, decouper(unites(prolongees)))
    courte = _serie("d/C", 0.1, 3, jours=30)
    jour = courte["date"][-1]
    with pytest.raises(UsineErreur, match="absente"):
        prevoir_entites(modele, courte, [_meteo_rouge("d/inconnue", jour, 5)])
    with pytest.raises(UsineErreur, match="absente"):
        prevoir_entites(modele, courte, [_meteo_rouge("d/C", jour + timedelta(days=365), 5)])


def _meteo_rouge(entite: str, jour: date, stock: int) -> MeteoEntite:
    regle = RegleDeclenchante(
        code=CodeIndicateur.ind_1,
        couleur=Couleur.rouge,
        operateur=Operateur.superieur_ou_egal,
        numerateur=stock,
        denominateur=1,
        seuil_numerateur=3,
        seuil_denominateur=1,
        tickets_en_cause=(),
    )
    return MeteoEntite(
        date_arrete=jour, entite=entite, couleur=Couleur.rouge, regles=(regle,), version_grille="t"
    )


@pytest.mark.lent
def test_scenarios_de_demo_modele_reel(tmp_path: Path) -> None:
    """Modèle entraîné sur les Parquet réels (`USINE_SERIES_REELLES`) : A sort, B reste (4.6)."""
    dossier = os.environ.get("USINE_SERIES_REELLES")
    if not dossier:
        pytest.skip("USINE_SERIES_REELLES non défini (Parquet de la Story 4.3)")
    reelles = pl.concat([pl.read_parquet(f) for f in sorted(Path(dossier).glob("*.parquet"))])
    prolongees = prolonger_par_depot(reelles)
    modele = entrainer(prolongees, decouper(unites(prolongees)))
    demo, rouges = passage_demo(tmp_path)
    a, b = prevoir_entites(modele, demo, rouges)
    assert a.statut is StatutPrevision.sortie_projetee
    assert b.statut is StatutPrevision.pas_de_sortie_projetee
