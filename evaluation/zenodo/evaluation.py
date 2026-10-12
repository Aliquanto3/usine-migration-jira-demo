"""Évaluation de la Baseline sur les `SerieStock` du Public Jira Dataset (FR-51, SM-10).

Hors CI (AD-20). Protocole de l'addendum PRD § E et H-21, valeurs par défaut :

- seuil = règle rouge IND-1 de la Grille par défaut (`>= 3`), horizon N = 10 Jours ouvrés,
  Baseline appelée telle quelle avec `ParametresBaseline()` (AD-18) ;
- chaque série est d'abord prolongée jusqu'à la dernière date de son dépôt (stock constant,
  Entrées et Sorties nulles) ;
- unité = (série, premier Jour ouvré présent de chaque semaine ISO) où le stock déclenche la
  règle, avec au moins `historique` (20) Jours ouvrés jusqu'à la date comprise et la date + N
  présente dans la série ; cible = 1 si le stock passe sous le seuil à au moins un des N Jours
  ouvrés suivants ;
- projets tenus à l'écart : SHA-256 du nom de série ≡ 0 mod 4 ; coupure temporelle par dépôt
  au 70ᵉ centile (rang le plus proche) des dates d'unités non tenues à l'écart ; entraînement
  = date + N < coupure (les cibles qui chevauchent la coupure sont purgées) ; test temporel
  = date ≥ coupure ; test de projets = toutes les unités des projets tenus à l'écart ;
- Baseline : probabilité de la `Prevision`, stock projeté max(0, S − v·N) ; naïve : taux de
  la cible sur l'entraînement du projet (repli : taux global), stock projeté = stock courant ;
- Brier, AUC (Mann-Whitney, ex aequo à 1/2) et erreur absolue moyenne du stock à N, exacts
  en `Fraction`, publiés arrondis à 6 décimales.

    uv run python -m evaluation.zenodo.evaluation --series A.parquet B.parquet \\
        --sortie evaluation/zenodo/resultats/evaluation.json
"""

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any

import polars as pl

from usine.contrats.calendrier import jour_ouvre_suivant, jours_ouvres
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import (
    CodeIndicateur,
    Couleur,
    MeteoEntite,
    Operateur,
    RegleDeclenchante,
)
from usine.contrats.prevision import SCHEMA_SERIE_STOCK
from usine.contrats.schemas import valider
from usine.domaine.prevision import baseline
from usine.domaine.prevision.commun import avancer, declenche

SEUIL = Fraction(3)
"""Seuil rouge IND-1 de la Grille par défaut (`config/grille_meteo.yaml`), repris en constante."""
OPERATEUR = Operateur.superieur_ou_egal
HORIZON = baseline.ParametresBaseline().horizon
"""Horizon N en Jours ouvrés, celui de la Baseline."""
HISTORIQUE = baseline.ParametresBaseline().profondeur_fourchette
"""Jours ouvrés d'historique exigés jusqu'à la date (profondeur de fourchette)."""
CENTILE_COUPURE = Fraction(7, 10)
MODULO_TENUE = 4
VERSION_GRILLE = "evaluation-zenodo"
DECIMALES = 6


@dataclass(frozen=True)
class Unite:
    """Unité d'évaluation : une série rouge (IND-1) à une date, avec sa vérité à N."""

    serie: str
    depot: str
    date: date
    stock: int
    cible: int
    """1 si le stock passe sous le seuil à au moins un des N Jours ouvrés suivants, sinon 0."""
    stock_a_horizon: int


@dataclass(frozen=True)
class Decoupage:
    """Entraînement, test temporel, test de projets tenus à l'écart et coupure par dépôt."""

    entrainement: tuple[Unite, ...]
    test_temporel: tuple[Unite, ...]
    test_projets: tuple[Unite, ...]
    coupures: dict[str, date]


def depot_de(serie: str) -> str:
    """Dépôt d'une série `"{depot}/{projet}"` (la série entière sans `/`)."""
    return serie.split("/", 1)[0]


def tenue_a_l_ecart(serie: str) -> bool:
    """Vrai si le projet est tenu à l'écart : SHA-256 du nom ≡ 0 mod 4."""
    empreinte = int(hashlib.sha256(serie.encode("utf-8")).hexdigest(), 16)
    return empreinte % MODULO_TENUE == 0


def prolonger_par_depot(series: pl.DataFrame) -> pl.DataFrame:
    """Prolonge chaque série jusqu'à la dernière date de son dépôt (stock constant, 0 / 0)."""
    table = valider(series, SCHEMA_SERIE_STOCK)
    if table.is_empty():
        return table
    dernieres = table.group_by("serie").agg(
        pl.col("date").max().alias("fin_serie"),
        pl.col("stock").sort_by("date").last().alias("dernier_stock"),
    )
    fin_depot: dict[str, date] = defaultdict(lambda: date.min)
    lignes = dernieres.sort("serie").rows(named=True)
    for ligne in lignes:
        depot = depot_de(ligne["serie"])
        fin_depot[depot] = max(fin_depot[depot], ligne["fin_serie"])
    ajouts: dict[str, list[Any]] = {nom: [] for nom in SCHEMA_SERIE_STOCK.colonnes}
    for ligne in lignes:
        fin = fin_depot[depot_de(ligne["serie"])]
        for jour in jours_ouvres(jour_ouvre_suivant(ligne["fin_serie"]), fin):
            ajouts["serie"].append(ligne["serie"])
            ajouts["date"].append(jour)
            ajouts["stock"].append(ligne["dernier_stock"])
            ajouts["entrees"].append(0)
            ajouts["sorties"].append(0)
    colonnes = list(SCHEMA_SERIE_STOCK.colonnes)
    prolongee = pl.concat(
        [
            table.select(colonnes),
            pl.DataFrame(ajouts, schema=dict(SCHEMA_SERIE_STOCK.colonnes)),
        ]
    ).sort("serie", "date")
    return valider(prolongee, SCHEMA_SERIE_STOCK)


def unites(
    series: pl.DataFrame,
    *,
    seuil: Fraction = SEUIL,
    horizon: int = HORIZON,
    historique: int = HISTORIQUE,
) -> list[Unite]:
    """Unités d'évaluation des séries (denses en Jours ouvrés), triées par série puis date."""
    table = valider(series, SCHEMA_SERIE_STOCK).sort("serie", "date")
    resultat: list[Unite] = []
    for (nom,), groupe in table.group_by("serie", maintain_order=True):
        serie = str(nom)
        dates: list[date] = groupe.get_column("date").to_list()
        stocks: list[int] = groupe.get_column("stock").to_list()
        rang = {jour: i for i, jour in enumerate(dates)}
        semaines_vues: set[tuple[int, int]] = set()
        for i, jour in enumerate(dates):
            semaine = jour.isocalendar()[:2]
            if semaine in semaines_vues:
                continue
            semaines_vues.add(semaine)
            if i + 1 < historique or not declenche(Fraction(stocks[i]), OPERATEUR, seuil):
                continue
            fin = rang.get(avancer(jour, horizon))
            if fin is None:
                continue
            suivants = stocks[i + 1 : fin + 1]
            cible = int(any(not declenche(Fraction(s), OPERATEUR, seuil) for s in suivants))
            resultat.append(
                Unite(
                    serie=serie,
                    depot=depot_de(serie),
                    date=jour,
                    stock=stocks[i],
                    cible=cible,
                    stock_a_horizon=stocks[fin],
                )
            )
    return resultat


def decouper(unites: Iterable[Unite], *, horizon: int = HORIZON) -> Decoupage:
    """Découpage déterministe : projets tenus à l'écart, puis coupure temporelle par dépôt."""
    toutes = sorted(unites, key=lambda u: (u.serie, u.date))
    tenues = tuple(u for u in toutes if tenue_a_l_ecart(u.serie))
    dates_par_depot: dict[str, list[date]] = defaultdict(list)
    for u in toutes:
        if not tenue_a_l_ecart(u.serie):
            dates_par_depot[u.depot].append(u.date)
    coupures: dict[str, date] = {}
    for depot in sorted(dates_par_depot):
        triees = sorted(dates_par_depot[depot])
        rang = max(math.ceil(CENTILE_COUPURE * len(triees)), 1)
        coupures[depot] = triees[rang - 1]
    restantes = [u for u in toutes if not tenue_a_l_ecart(u.serie)]
    entrainement = tuple(u for u in restantes if avancer(u.date, horizon) < coupures[u.depot])
    test_temporel = tuple(u for u in restantes if u.date >= coupures[u.depot])
    return Decoupage(entrainement, test_temporel, tenues, coupures)


def _meteo(unite: Unite, seuil: Fraction) -> MeteoEntite:
    regle = RegleDeclenchante(
        code=CodeIndicateur.ind_1,
        couleur=Couleur.rouge,
        operateur=OPERATEUR,
        numerateur=unite.stock,
        denominateur=1,
        seuil_numerateur=seuil.numerator,
        seuil_denominateur=seuil.denominator,
        tickets_en_cause=(),
    )
    return MeteoEntite(
        date_arrete=unite.date,
        entite=unite.serie,
        couleur=Couleur.rouge,
        regles=(regle,),
        version_grille=VERSION_GRILLE,
    )


def predire_sortie(
    serie_projet: pl.DataFrame, unite: Unite, *, seuil: Fraction = SEUIL
) -> tuple[Fraction, Fraction]:
    """(probabilité de sortie, stock projeté à N) de la Baseline, appelée telle quelle.

    Nom sans « baseline » : `test_baseline_unique_ad_18` réserve tout `def *baseline*` à
    `domaine.prevision.baseline` (AD-18).
    """
    prevision = baseline.prevoir_sortie(
        serie_projet, _meteo(unite, seuil), baseline.ParametresBaseline()
    )
    probabilite = Fraction(prevision.probabilite_numerateur, prevision.probabilite_denominateur)
    facteur = next(f for f in prevision.facteurs if f.nom == baseline.VELOCITE_NETTE)
    velocite = Fraction(facteur.numerateur, facteur.denominateur)
    projete = max(Fraction(0), unite.stock - velocite * prevision.horizon_jours_ouvres)
    return probabilite, projete


class ReferenceNaive:
    """Prédicteur naïf : taux de la cible sur l'entraînement du projet, sinon taux global."""

    def __init__(self, entrainement: Sequence[Unite]) -> None:
        if not entrainement:
            raise UsineErreur("Évaluation Zenodo : aucune unité d'entraînement pour la naïve")
        comptes: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for u in entrainement:
            comptes[u.serie][0] += u.cible
            comptes[u.serie][1] += 1
        self.taux_par_serie = {s: Fraction(p, n) for s, (p, n) in comptes.items()}
        self.taux_global = Fraction(sum(u.cible for u in entrainement), len(entrainement))

    def predire(self, unite: Unite) -> tuple[Fraction, Fraction]:
        """(probabilité, stock projeté = stock courant)."""
        taux = self.taux_par_serie.get(unite.serie, self.taux_global)
        return taux, Fraction(unite.stock)


def _verifier(nom: str, a: Sequence[Any], b: Sequence[Any]) -> None:
    if not a or len(a) != len(b):
        raise UsineErreur(f"{nom} : listes vides ou de longueurs différentes")


def brier(probabilites: Sequence[Fraction], cibles: Sequence[int]) -> Fraction:
    """Score de Brier exact : moyenne de (p − y)²."""
    _verifier("Brier", probabilites, cibles)
    return sum(((p - y) ** 2 for p, y in zip(probabilites, cibles, strict=True)), Fraction(0)) / (
        len(cibles)
    )


def auc(probabilites: Sequence[Fraction], cibles: Sequence[int]) -> Fraction | None:
    """AUC de Mann-Whitney exacte (ex aequo à 1/2) ; `None` si une seule classe."""
    _verifier("AUC", probabilites, cibles)
    positifs = sum(1 for y in cibles if y)
    negatifs = len(cibles) - positifs
    if not positifs or not negatifs:
        return None
    par_score: dict[Fraction, list[int]] = defaultdict(lambda: [0, 0])
    for p, y in zip(probabilites, cibles, strict=True):
        par_score[p][0 if y else 1] += 1
    gagnes = Fraction(0)
    negatifs_dessous = 0
    for score in sorted(par_score):
        pos, neg = par_score[score]
        gagnes += pos * (negatifs_dessous + Fraction(neg, 2))
        negatifs_dessous += neg
    return gagnes / (positifs * negatifs)


def erreur_absolue_moyenne(projetes: Sequence[Fraction], verites: Sequence[int]) -> Fraction:
    """Moyenne exacte de |stock projeté − stock réel à N|."""
    _verifier("Erreur absolue moyenne", projetes, verites)
    return sum((abs(p - v) for p, v in zip(projetes, verites, strict=True)), Fraction(0)) / len(
        verites
    )


def arrondi(valeur: Fraction | None) -> float | None:
    """Valeur exacte publiée à 6 décimales."""
    return None if valeur is None else float(round(valeur, DECIMALES))


def _mesures(
    predictions: Sequence[tuple[Fraction, Fraction]], jeu: Sequence[Unite]
) -> dict[str, Any]:
    probabilites = [p for p, _ in predictions]
    cibles = [u.cible for u in jeu]
    exactes = {
        "brier": brier(probabilites, cibles),
        "auc": auc(probabilites, cibles),
        "erreur_absolue_moyenne": erreur_absolue_moyenne(
            [s for _, s in predictions], [u.stock_a_horizon for u in jeu]
        ),
    }
    return {"exactes": exactes, "publiees": {k: arrondi(v) for k, v in exactes.items()}}


def _evaluer_jeu(
    jeu: Sequence[Unite],
    par_serie: dict[str, pl.DataFrame],
    naive: ReferenceNaive,
    seuil: Fraction,
) -> dict[str, Any]:
    resultat: dict[str, Any] = {
        "effectif": len(jeu),
        "positifs": sum(u.cible for u in jeu),
        "series": len({u.serie for u in jeu}),
    }
    if not jeu:
        resultat |= {"baseline": None, "naive": None, "baseline_bat_naive_brier": None}
        return resultat
    mesures_baseline = _mesures(
        [predire_sortie(par_serie[u.serie], u, seuil=seuil) for u in jeu], jeu
    )
    mesures_naive = _mesures([naive.predire(u) for u in jeu], jeu)
    resultat |= {
        "baseline": mesures_baseline["publiees"],
        "naive": mesures_naive["publiees"],
        "baseline_bat_naive_brier": mesures_baseline["exactes"]["brier"]
        < mesures_naive["exactes"]["brier"],
    }
    return resultat


def evaluer(
    series: pl.DataFrame,
    *,
    seuil: Fraction = SEUIL,
    horizon: int = HORIZON,
    historique: int = HISTORIQUE,
) -> dict[str, Any]:
    """Mesures agrégées de la Baseline et de la naïve sur les deux jeux de test."""
    if horizon != baseline.ParametresBaseline().horizon:
        raise UsineErreur(
            f"Évaluation Zenodo : horizon {horizon} différent de celui de la Baseline"
            f" ({baseline.ParametresBaseline().horizon} Jours ouvrés)"
        )
    prolongees = prolonger_par_depot(series)
    retenues = unites(prolongees, seuil=seuil, horizon=horizon, historique=historique)
    if not retenues:
        raise UsineErreur(
            "Évaluation Zenodo : aucune unité (aucune série rouge avec assez d'historique et"
            f" {horizon} Jours ouvrés de suite)"
        )
    decoupage = decouper(retenues, horizon=horizon)
    naive = ReferenceNaive(decoupage.entrainement)
    par_serie = {
        str(nom): groupe for (nom,), groupe in prolongees.group_by("serie", maintain_order=True)
    }
    noms = sorted(par_serie)
    depots = sorted({depot_de(s) for s in noms})
    return {
        "protocole": {
            "indicateur": CodeIndicateur.ind_1.value,
            "operateur": OPERATEUR.value,
            "seuil": arrondi(seuil),
            "horizon_jours_ouvres": horizon,
            "historique_jours_ouvres": historique,
            "parametres_baseline": asdict(baseline.ParametresBaseline()),
            "echantillonnage": "premier Jour ouvré présent de chaque semaine ISO",
            "projets_tenus_a_l_ecart": f"sha256(nom de série) mod {MODULO_TENUE} == 0",
            "coupure_temporelle": "centile 70 (rang le plus proche) des dates par dépôt",
            "naive": "taux de la cible à l'entraînement du projet, repli taux global",
        },
        "donnees": {
            "depots": {
                depot: {
                    "series": sum(1 for s in noms if depot_de(s) == depot),
                    "series_tenues_a_l_ecart": sum(
                        1 for s in noms if depot_de(s) == depot and tenue_a_l_ecart(s)
                    ),
                    "unites": sum(1 for u in retenues if u.depot == depot),
                    "coupure": (
                        decoupage.coupures[depot].isoformat()
                        if depot in decoupage.coupures
                        else None
                    ),
                }
                for depot in depots
            },
            "series": len(noms),
            "unites": len(retenues),
        },
        "entrainement": {
            "effectif": len(decoupage.entrainement),
            "positifs": sum(u.cible for u in decoupage.entrainement),
            "taux_cible": arrondi(naive.taux_global),
        },
        "jeux": {
            "test_temporel": _evaluer_jeu(decoupage.test_temporel, par_serie, naive, seuil),
            "test_projets_tenus_a_l_ecart": _evaluer_jeu(
                decoupage.test_projets, par_serie, naive, seuil
            ),
        },
    }


def avertissements_sm10(resultat: dict[str, Any]) -> list[str]:
    """Jeux de test où la Baseline ne bat pas la naïve en Brier (SM-10, arbitrage auteur)."""
    return [
        f"Avertissement SM-10 : sur {nom}, la Baseline ne bat pas la naïve en Brier"
        f" ({jeu['baseline']['brier']} contre {jeu['naive']['brier']}) ; résultat publié tel"
        " quel, à arbitrer par l'auteur."
        for nom, jeu in resultat["jeux"].items()
        if jeu["baseline_bat_naive_brier"] is False
    ]


def _resume(resultat: dict[str, Any]) -> list[str]:
    lignes = [
        f"{resultat['donnees']['series']} série(s), {resultat['donnees']['unites']} unité(s),"
        f" entraînement {resultat['entrainement']['effectif']}"
    ]
    for nom, jeu in resultat["jeux"].items():
        if jeu["baseline"] is None:
            lignes.append(f"{nom} : aucune unité")
            continue
        lignes.append(f"{nom} : {jeu['effectif']} unité(s), {jeu['positifs']} positive(s)")
        for predicteur in ("baseline", "naive"):
            m = jeu[predicteur]
            lignes.append(
                f"  {predicteur} : Brier {m['brier']}, AUC {m['auc']},"
                f" erreur absolue moyenne {m['erreur_absolue_moyenne']}"
            )
    return lignes


def main(arguments: Sequence[str] | None = None) -> int:
    """Évalue la Baseline sur des `SerieStock` Parquet et écrit les agrégats en JSON."""
    parseur = argparse.ArgumentParser(prog="python -m evaluation.zenodo.evaluation")
    parseur.add_argument("--series", required=True, nargs="+", type=Path, help="Parquet 4.3")
    parseur.add_argument("--sortie", required=True, type=Path, help="JSON des agrégats")
    options = parseur.parse_args(arguments)
    try:
        series = pl.concat(
            [valider(pl.read_parquet(f), SCHEMA_SERIE_STOCK) for f in options.series]
        )
        resultat = evaluer(series)
        options.sortie.parent.mkdir(parents=True, exist_ok=True)
        options.sortie.write_text(
            json.dumps(resultat, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except (UsineErreur, OSError, pl.exceptions.PolarsError) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 1
    for ligne in [*_resume(resultat), *avertissements_sm10(resultat)]:
        print(ligne)
    print(f"Résultats écrits dans {options.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
