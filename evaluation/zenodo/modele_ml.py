"""Modèle ML de résolution des bloquantes, validé sur le Public Jira Dataset (FR-22, SM-8).

Hors CI (AD-20). Même protocole que `evaluation.zenodo.evaluation` (Story 4.4) : mêmes unités,
mêmes projets tenus à l'écart, mêmes coupures par dépôt, mêmes mesures exactes ; la Baseline
(`prevoir_sortie`, appelée telle quelle) et la naïve sont recalculées sur les mêmes jeux.

Le Modèle ML (LightGBM) prédit la probabilité p qu'une Anomalie bloquante ouverte soit résolue
sous N Jours ouvrés. Les `SerieStock` ne portent pas de ticket individuel : la cible
d'entraînement d'un (série, Jour ouvré) de stock S ≥ 1 est la part du stock résolue dans les N
Jours ouvrés suivants, min(Σ Sorties, S) / S, apprise avec la perte `cross_entropy` pondérée
par S. Entraînement : jours des projets non tenus à l'écart dont la date + N précède la coupure
du dépôt. Caractéristiques : stock, Entrées et Sorties cumulées sur 5, 10 et 20 Jours ouvrés,
variation du stock sur 10 jours, stock maximal sur 20 jours. La `Prevision` `methode=ml` vient
de `domaine.prevision.ml.prevoir_sortie_ml` (agrégation binomiale de l'addendum).

    uv run python -m evaluation.zenodo.modele_ml --series A.parquet B.parquet \\
        --sortie evaluation/zenodo/resultats/modele_ml.json
"""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import polars as pl

from evaluation.zenodo.evaluation import (
    HISTORIQUE,
    HORIZON,
    SEUIL,
    Decoupage,
    ReferenceNaive,
    Unite,
    arrondi,
    auc,
    brier,
    decouper,
    depot_de,
    meteo_de_unite,
    predire_sortie,
    prolonger_par_depot,
    tenue_a_l_ecart,
    unites,
)
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import MeteoEntite
from usine.contrats.prevision import SCHEMA_SERIE_STOCK, MethodePrevision, Prevision
from usine.contrats.schemas import valider
from usine.domaine.prevision import baseline
from usine.domaine.prevision.ml import DENOMINATEUR_MAX, prevoir_sortie_ml

FENETRES = (5, 10, 20)
CARACTERISTIQUES = (
    "stock",
    *(f"entrees_{w}" for w in FENETRES),
    *(f"sorties_{w}" for w in FENETRES),
    "variation_stock_10",
    "stock_max_20",
)
PARAMETRES: dict[str, Any] = {
    "objective": "cross_entropy",
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_data_in_leaf": 50,
    "seed": 42,
    "deterministic": True,
    "force_row_wise": True,
    "num_threads": 1,
    "verbose": -1,
}
TOURS = 200

Matrice = np.ndarray[Any, Any]


@dataclass(frozen=True)
class SerieML:
    """Une série prolongée : dates, stock, Sorties et caractéristiques par Jour ouvré."""

    dates: list[date]
    stock: Matrice
    sorties: Matrice
    caracteristiques: Matrice


def _somme_glissante(valeurs: Matrice, largeur: int) -> Matrice:
    cumul = np.concatenate([[0.0], np.cumsum(valeurs)])
    sortie = np.full(len(valeurs), np.nan)
    if len(valeurs) >= largeur:
        sortie[largeur - 1 :] = cumul[largeur:] - cumul[:-largeur]
    return sortie


def caracteristiques(stock: Matrice, entrees: Matrice, sorties: Matrice) -> Matrice:
    """Matrice (jours × `CARACTERISTIQUES`) ; NaN tant que 20 Jours ouvrés manquent."""
    n = len(stock)
    flottant = stock.astype(float)
    colonnes = [flottant]
    colonnes += [_somme_glissante(entrees.astype(float), w) for w in FENETRES]
    colonnes += [_somme_glissante(sorties.astype(float), w) for w in FENETRES]
    variation = np.full(n, np.nan)
    if n > 10:
        variation[10:] = flottant[10:] - flottant[:-10]
    maximum = np.full(n, np.nan)
    if n >= 20:
        fenetres = np.lib.stride_tricks.sliding_window_view(flottant, 20)
        maximum[19:] = fenetres.max(axis=1)
    colonnes += [variation, maximum]
    return np.column_stack(colonnes)


def series_ml(prolongees: pl.DataFrame) -> dict[str, SerieML]:
    """Caractéristiques de chaque série (denses en Jours ouvrés)."""
    resultat: dict[str, SerieML] = {}
    for (nom,), groupe in prolongees.sort("serie", "date").group_by("serie", maintain_order=True):
        stock = groupe.get_column("stock").to_numpy()
        entrees = groupe.get_column("entrees").to_numpy()
        sorties = groupe.get_column("sorties").to_numpy()
        resultat[str(nom)] = SerieML(
            groupe.get_column("date").to_list(),
            stock,
            sorties,
            caracteristiques(stock, entrees, sorties),
        )
    return resultat


def _lignes_entrainement(
    series: dict[str, SerieML], coupures: dict[str, date], horizon: int, historique: int
) -> tuple[Matrice, Matrice, Matrice]:
    """(X, part du stock résolue à N, poids = stock) des jours d'entraînement."""
    X: list[Matrice] = []
    y: list[Matrice] = []
    poids: list[Matrice] = []
    for nom, s in series.items():
        coupure = coupures.get(depot_de(nom))
        n = len(s.stock)
        if tenue_a_l_ecart(nom) or coupure is None or n <= horizon + historique:
            continue
        cumul = np.concatenate([[0], np.cumsum(s.sorties)])
        indices = np.arange(historique - 1, n - horizon)
        futures = cumul[indices + horizon + 1] - cumul[indices + 1]
        stock = s.stock[indices]
        avant_coupure = np.array([s.dates[i + horizon] < coupure for i in indices], dtype=bool)
        garde = (stock >= 1) & avant_coupure
        X.append(s.caracteristiques[indices][garde])
        y.append(np.minimum(futures[garde], stock[garde]) / stock[garde])
        poids.append(stock[garde].astype(float))
    if not X or sum(len(a) for a in X) == 0:
        raise UsineErreur("Modèle ML : aucune ligne d'entraînement")
    return np.vstack(X), np.concatenate(y), np.concatenate(poids)


def entrainer(
    prolongees: pl.DataFrame, decoupage: Decoupage, *, horizon: int = HORIZON
) -> lgb.Booster:
    """Entraîne le Modèle ML (LightGBM, déterministe) sur le découpage d'entraînement."""
    X, y, poids = _lignes_entrainement(
        series_ml(prolongees), decoupage.coupures, horizon, HISTORIQUE
    )
    return lgb.train(PARAMETRES, lgb.Dataset(X, label=y, weight=poids), num_boost_round=TOURS)


def probabilites_bloquante(
    modele: lgb.Booster, series: dict[str, SerieML], jeu: Sequence[Unite]
) -> list[Fraction]:
    """Probabilité p de résolution d'une bloquante sous N pour chaque unité (fraction)."""
    if not jeu:
        return []
    lignes = [series[u.serie].caracteristiques[series[u.serie].dates.index(u.date)] for u in jeu]
    brutes = np.clip(modele.predict(np.vstack(lignes)), 0.0, 1.0)
    return [Fraction(float(p)).limit_denominator(DENOMINATEUR_MAX) for p in brutes]


def prevoir_entites(
    modele: lgb.Booster,
    serie: pl.DataFrame,
    meteos: Sequence[MeteoEntite],
    horizon: int = HORIZON,
) -> list[Prevision]:
    """`Prevision` `methode=ml` de chaque Entité rouge de `meteos` à sa Date d'arrêté.

    `serie` est une `SerieStock` dense contenant chaque Entité jusqu'à la Date d'arrêté (au
    moins 20 Jours ouvrés d'historique) ; c'est le point d'entrée pour un Passage réel.
    """
    series = series_ml(valider(serie, SCHEMA_SERIE_STOCK))
    resultat = []
    for meteo in meteos:
        s = series.get(meteo.entite)
        if s is None or meteo.date_arrete not in s.dates:
            raise UsineErreur(
                f"Modèle ML {meteo.entite} : absente de la série à {meteo.date_arrete.isoformat()}"
            )
        ligne = s.caracteristiques[s.dates.index(meteo.date_arrete)][np.newaxis, :]
        if np.isnan(ligne).any():
            raise UsineErreur(f"Modèle ML {meteo.entite} : moins de 20 Jours ouvrés d'historique")
        p = float(np.clip(modele.predict(ligne)[0], 0.0, 1.0))
        resultat.append(
            prevoir_sortie_ml(meteo, Fraction(p).limit_denominator(DENOMINATEUR_MAX), horizon)
        )
    return resultat


def predire_ml(
    modele: lgb.Booster, series: dict[str, SerieML], jeu: Sequence[Unite], horizon: int = HORIZON
) -> list[Prevision]:
    """`Prevision` `methode=ml` de chaque unité (Entité rouge à la date de l'unité)."""
    return [
        prevoir_sortie_ml(meteo_de_unite(u, SEUIL), p, horizon)
        for u, p in zip(jeu, probabilites_bloquante(modele, series, jeu), strict=True)
    ]


def _probabilite(prevision: Prevision) -> Fraction:
    if prevision.methode is not MethodePrevision.ml:
        raise UsineErreur(f"Modèle ML : Prévision {prevision.methode} au lieu de ml")
    return Fraction(prevision.probabilite_numerateur, prevision.probabilite_denominateur)


def _publiees(probabilites: Sequence[Fraction], cibles: Sequence[int]) -> dict[str, Any]:
    return {
        "brier": arrondi(brier(probabilites, cibles)),
        "auc": arrondi(auc(probabilites, cibles)),
    }


def _evaluer_jeu(
    jeu: Sequence[Unite],
    modele: lgb.Booster,
    series: dict[str, SerieML],
    par_serie: dict[str, pl.DataFrame],
    naive: ReferenceNaive,
) -> dict[str, Any]:
    resultat: dict[str, Any] = {
        "effectif": len(jeu),
        "positifs": sum(u.cible for u in jeu),
        "series": len({u.serie for u in jeu}),
    }
    if not jeu:
        return resultat | {"ml": None, "baseline": None, "naive": None}
    cibles = [u.cible for u in jeu]
    p_ml = [_probabilite(p) for p in predire_ml(modele, series, jeu)]
    p_baseline = [predire_sortie(par_serie[u.serie], u)[0] for u in jeu]
    p_naive = [naive.predire(u)[0] for u in jeu]
    auc_ml, auc_base = auc(p_ml, cibles), auc(p_baseline, cibles)
    return resultat | {
        "ml": _publiees(p_ml, cibles),
        "baseline": _publiees(p_baseline, cibles),
        "naive": _publiees(p_naive, cibles),
        "ml_bat_baseline_auc": None if auc_ml is None or auc_base is None else auc_ml > auc_base,
        "ml_bat_baseline_brier": brier(p_ml, cibles) < brier(p_baseline, cibles),
    }


def evaluer_ml(series: pl.DataFrame) -> dict[str, Any]:
    """Entraîne le Modèle ML et le compare à la Baseline et à la naïve (protocole de la 4.4)."""
    prolongees = prolonger_par_depot(series)
    retenues = unites(prolongees)
    if not retenues:
        raise UsineErreur("Modèle ML : aucune unité d'évaluation")
    decoupage = decouper(retenues)
    naive = ReferenceNaive(decoupage.entrainement)
    modele = entrainer(prolongees, decoupage)
    ml = series_ml(prolongees)
    par_serie = {
        str(nom): groupe for (nom,), groupe in prolongees.group_by("serie", maintain_order=True)
    }
    gains = modele.feature_importance(importance_type="gain")
    return {
        "protocole": {
            "reference": "evaluation.zenodo.evaluation (Story 4.4)",
            "horizon_jours_ouvres": HORIZON,
            "seuil": arrondi(SEUIL),
            "modele": "LightGBM " + lgb.__version__,
            "parametres": PARAMETRES | {"tours": TOURS},
            "cible_entrainement": "part du stock résolue sous N Jours ouvrés, poids = stock",
            "agregation": "P(Binomiale(S, p) >= k), k = résolutions requises, indépendance",
            "caracteristiques": list(CARACTERISTIQUES),
            "parametres_baseline": asdict(baseline.ParametresBaseline()),
        },
        "entrainement": {
            "unites": len(decoupage.entrainement),
            "importance_gain": {
                nom: round(float(g), 3) for nom, g in zip(CARACTERISTIQUES, gains, strict=True)
            },
        },
        "jeux": {
            "test_temporel": _evaluer_jeu(decoupage.test_temporel, modele, ml, par_serie, naive),
            "test_projets_tenus_a_l_ecart": _evaluer_jeu(
                decoupage.test_projets, modele, ml, par_serie, naive
            ),
        },
    }


def verdict_sm8(resultat: dict[str, Any]) -> list[str]:
    """Jeux où le Modèle ML ne bat pas la Baseline en AUC et en Brier (SM-8, à arbitrer)."""
    lignes = []
    for nom, jeu in resultat["jeux"].items():
        if jeu["ml"] is None:
            continue
        if jeu["ml_bat_baseline_auc"] is not True or jeu["ml_bat_baseline_brier"] is not True:
            lignes.append(
                f"Avertissement SM-8 : sur {nom}, le Modèle ML ne bat pas la Baseline en AUC et"
                f" Brier (ML {jeu['ml']}, Baseline {jeu['baseline']}) ; publié tel quel."
            )
    return lignes


def main(arguments: Sequence[str] | None = None) -> int:
    """Évalue le Modèle ML sur des `SerieStock` Parquet et écrit les agrégats en JSON."""
    parseur = argparse.ArgumentParser(prog="python -m evaluation.zenodo.modele_ml")
    parseur.add_argument("--series", required=True, nargs="+", type=Path, help="Parquet 4.3")
    parseur.add_argument("--sortie", required=True, type=Path, help="JSON des agrégats")
    options = parseur.parse_args(arguments)
    try:
        series = pl.concat(
            [valider(pl.read_parquet(f), SCHEMA_SERIE_STOCK) for f in options.series]
        )
        resultat = evaluer_ml(series)
        options.sortie.parent.mkdir(parents=True, exist_ok=True)
        options.sortie.write_text(
            json.dumps(resultat, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except (UsineErreur, OSError, pl.exceptions.PolarsError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    for nom, jeu in resultat["jeux"].items():
        print(f"{nom} : {jeu['effectif']} unité(s), {jeu['positifs']} positive(s)")
        for k in ("ml", "baseline", "naive"):
            if jeu[k] is not None:
                print(f"  {k} : Brier {jeu[k]['brier']}, AUC {jeu[k]['auc']}")
    for ligne in verdict_sm8(resultat):
        print(ligne)
    print(f"Résultats écrits dans {options.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
