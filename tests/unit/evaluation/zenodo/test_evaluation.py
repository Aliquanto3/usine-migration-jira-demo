"""Évaluation de la Baseline sur `SerieStock` (Story 4.4, FR-51, SM-10).

Séries synthétiques construites en code, denses en Jours ouvrés à partir de `LUNDI`
(2021-01-04, un lundi) ; mesures vérifiées sur des exemples calculés à la main.
"""

import json
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from evaluation.zenodo import evaluation
from evaluation.zenodo.evaluation import (
    ReferenceNaive,
    Unite,
    arrondi,
    auc,
    avertissements_sm10,
    brier,
    decouper,
    erreur_absolue_moyenne,
    evaluer,
    predire_sortie,
    prolonger_par_depot,
    tenue_a_l_ecart,
    unites,
)
from usine.contrats.calendrier import jours_ouvres
from usine.contrats.erreurs import UsineErreur
from usine.contrats.prevision import SCHEMA_SERIE_STOCK
from usine.domaine.prevision import baseline

LUNDI = date(2021, 1, 4)
MARDI = date(2021, 1, 5)


def _serie(nom: str, stocks: list[int], debut: date = LUNDI) -> pl.DataFrame:
    """`SerieStock` dense de Jours ouvrés consécutifs depuis `debut`."""
    dates = jours_ouvres(debut, debut + timedelta(days=2 * len(stocks) + 7))[: len(stocks)]
    precedents = [0, *stocks[:-1]]
    return pl.DataFrame(
        {
            "serie": [nom] * len(stocks),
            "date": list(dates),
            "stock": stocks,
            "entrees": [max(s - p, 0) for s, p in zip(stocks, precedents, strict=True)],
            "sorties": [max(p - s, 0) for s, p in zip(stocks, precedents, strict=True)],
        },
        schema=dict(SCHEMA_SERIE_STOCK.colonnes),
    )


def _jour(rang: int, debut: date = LUNDI) -> date:
    return jours_ouvres(debut, debut + timedelta(days=2 * rang + 7))[rang]


# --- Unités (une ligne de la matrice par test) ---------------------------------------------


@pytest.mark.parametrize(
    ("suite", "cible", "a_horizon"),
    [([4, 4, 4, 2, 3, 3, 3, 3, 3, 5], 1, 5), ([3] * 9 + [6], 0, 6)],
)
def test_unite_retenue(suite: list[int], cible: int, a_horizon: int) -> None:
    # 25 Jours ouvrés sous le seuil, puis le lundi d'indice 25 à stock 4, et 10 jours après.
    serie = _serie("d/A", [2] * 25 + [4] + suite)
    assert unites(serie) == [
        Unite(
            serie="d/A",
            depot="d",
            date=_jour(25),
            stock=4,
            cible=cible,
            stock_a_horizon=a_horizon,
        )
    ]
    assert _jour(25).weekday() == 0


def test_stock_sous_le_seuil() -> None:
    assert unites(_serie("d/A", [2] * 25 + [2] + [4] * 10)) == []


def test_historique_court() -> None:
    # Série commençant un mardi : l'indice 9 (10ᵉ Jour ouvré) est un lundi.
    serie = _serie("d/A", [2] * 9 + [4] + [2] * 30, debut=MARDI)
    assert _jour(9, MARDI).weekday() == 0
    assert unites(serie) == []
    assert [u.date for u in unites(serie, historique=10)] == [_jour(9, MARDI)]


def test_fin_de_serie() -> None:
    assert unites(_serie("d/A", [2] * 25 + [4] * 10)) == []
    assert len(unites(_serie("d/A", [2] * 25 + [4] * 11))) == 1


def test_semaine_sans_lundi_ouvre() -> None:
    # Le lundi de la première semaine est absent de la série : unité au mardi.
    retenues = unites(_serie("d/A", [4] * 11, debut=MARDI), historique=1)
    assert [u.date for u in retenues] == [MARDI]


def test_prolongation_par_depot() -> None:
    series = pl.concat([_serie("d/A", [1, 2, 3]), _serie("d/B", [5] * 8), _serie("e/C", [1, 1])])
    prolongees = prolonger_par_depot(series)
    a = prolongees.filter(pl.col("serie") == "d/A")
    assert a.get_column("date").to_list() == list(jours_ouvres(LUNDI, _jour(7)))
    assert a.get_column("stock").to_list() == [1, 2, 3, 3, 3, 3, 3, 3]
    assert a.get_column("entrees").to_list()[3:] == [0] * 5
    assert a.get_column("sorties").to_list()[3:] == [0] * 5
    assert prolongees.filter(pl.col("serie") == "e/C").height == 2
    assert prolongees.filter(pl.col("serie") == "d/B").equals(
        series.filter(pl.col("serie") == "d/B")
    )


# --- Découpage -------------------------------------------------------------------------------


def _unite(serie: str, jour: date, cible: int = 1, stock: int = 4) -> Unite:
    return Unite(
        serie=serie,
        depot=serie.split("/")[0],
        date=jour,
        stock=stock,
        cible=cible,
        stock_a_horizon=stock,
    )


def test_projets_tenus_a_l_ecart() -> None:
    assert [n for n in ("d/A", "d/B", "d/J", "e/H", "e/A") if tenue_a_l_ecart(n)] == [
        "d/J",
        "e/H",
    ]


def test_decoupage() -> None:
    lundis = [LUNDI + timedelta(weeks=k) for k in range(10)]
    # Six projets tenus à l'écart datés du dernier lundi : les compter dans le centile
    # déplacerait la coupure au rang ⌈0,7 × 16⌉ = 12, soit lundis[9].
    tenus = [_unite(nom, lundis[9]) for nom in ("d/J", "d/O", "d/Q", "d/R", "d/S", "d/U")]
    entree = [_unite("d/A", j) for j in lundis] + tenus
    decoupage = decouper(entree)
    # Centile 70 au rang ⌈0,7 × 10⌉ = 7 : 7ᵉ lundi.
    assert decoupage.coupures == {"d": lundis[6]}
    # Entraînement : lundi + 10 Jours ouvrés < coupure → 4 premiers ; 5ᵉ et 6ᵉ purgés.
    assert [u.date for u in decoupage.entrainement] == lundis[:4]
    assert [u.date for u in decoupage.test_temporel] == lundis[6:]
    assert decoupage.test_projets == tuple(tenus)
    assert decouper(reversed(entree)) == decoupage


# --- Prédicteurs ------------------------------------------------------------------------------


def test_predire_sortie_sortie() -> None:
    # Stock 30 puis −1 par Jour ouvré : stock 5 à l'indice 25, v = 1, sortie en 3 jours.
    serie = _serie("d/A", [30 - k for k in range(26)])
    probabilite, projete = predire_sortie(serie, _unite("d/A", _jour(25), stock=5))
    assert probabilite == 1
    assert projete == 0


def test_predire_sortie_stock_stable() -> None:
    serie = _serie("d/A", [4] * 26)
    assert predire_sortie(serie, _unite("d/A", _jour(25))) == (Fraction(0), Fraction(4))


def test_predire_sortie_appelle_la_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    appels: list[Any] = []
    origine = baseline.prevoir_sortie

    def espion(*args: Any) -> Any:
        appels.append(args)
        return origine(*args)

    monkeypatch.setattr(baseline, "prevoir_sortie", espion)
    serie = _serie("d/A", [4] * 26)
    predire_sortie(serie, _unite("d/A", _jour(25)))
    assert len(appels) == 1
    assert appels[0][2] == baseline.ParametresBaseline()
    assert appels[0][1].entite == "d/A"


def test_naive_taux_du_projet_et_repli() -> None:
    entrainement = [
        _unite("d/A", LUNDI, cible=1),
        _unite("d/A", MARDI, cible=0),
        _unite("d/B", LUNDI, cible=1),
        _unite("d/B", MARDI, cible=1),
    ]
    naive = ReferenceNaive(entrainement)
    assert naive.predire(_unite("d/A", LUNDI, stock=7)) == (Fraction(1, 2), Fraction(7))
    # Projet sans unité d'entraînement : taux global 3/4.
    assert naive.predire(_unite("d/J", LUNDI))[0] == Fraction(3, 4)


def test_naive_sans_entrainement() -> None:
    with pytest.raises(UsineErreur, match="aucune unité d'entraînement"):
        ReferenceNaive([])


# --- Mesures ----------------------------------------------------------------------------------


def test_brier() -> None:
    # ((1/2 − 1)² + (1 − 0)²) / 2 = 5/8
    assert brier([Fraction(1, 2), Fraction(1)], [1, 0]) == Fraction(5, 8)


def test_auc_avec_ex_aequo() -> None:
    # Paires (positif, négatif) : 0,8>0,4 ; 0,8>0,2 ; 0,4=0,4 (1/2) ; 0,4>0,2 → 3,5 / 4
    scores = [Fraction(8, 10), Fraction(4, 10), Fraction(4, 10), Fraction(2, 10)]
    assert auc(scores, [1, 1, 0, 0]) == Fraction(7, 8)
    assert auc(list(reversed(scores)), [0, 0, 1, 1]) == Fraction(7, 8)


def test_auc_une_seule_classe() -> None:
    assert auc([Fraction(1, 2), Fraction(1)], [1, 1]) is None


def test_erreur_absolue_moyenne() -> None:
    assert erreur_absolue_moyenne([Fraction(3), Fraction(0)], [1, 2]) == 2


def test_mesure_sur_listes_vides() -> None:
    with pytest.raises(UsineErreur):
        brier([], [])


def test_arrondi() -> None:
    assert arrondi(Fraction(1, 3)) == 0.333333
    assert arrondi(Fraction(2, 3)) == 0.666667
    assert arrondi(None) is None


# --- Évaluation complète et CLI ---------------------------------------------------------------

_CYCLE = [5, 5, 5, 4, 4, 4, 3, 3, 3, 2, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6]


def _jeu_synthetique() -> pl.DataFrame:
    """Dépôt `d` : A et B (évalués dans le temps), J (tenu à l'écart) ; B finit plus tôt."""
    series = []
    for nom, decalage, longueur in (("d/A", 0, 300), ("d/B", 3, 260), ("d/J", 7, 300)):
        stocks = [_CYCLE[(k + decalage) % len(_CYCLE)] for k in range(longueur)]
        series.append(_serie(nom, stocks))
    return pl.concat(series)


def test_evaluer_appelle_la_baseline_pour_chaque_unite_de_test(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appels: list[Any] = []
    origine = baseline.prevoir_sortie

    def espion(*args: Any) -> Any:
        appels.append(args)
        return origine(*args)

    monkeypatch.setattr(baseline, "prevoir_sortie", espion)
    resultat = evaluer(_jeu_synthetique())
    temporel = resultat["jeux"]["test_temporel"]
    projets = resultat["jeux"]["test_projets_tenus_a_l_ecart"]
    assert temporel["effectif"] > 0
    assert projets["effectif"] > 0
    assert projets["series"] == 1
    assert len(appels) == temporel["effectif"] + projets["effectif"]
    assert all(a[2] == baseline.ParametresBaseline() for a in appels)
    for jeu in (temporel, projets):
        for predicteur in ("baseline", "naive"):
            assert set(jeu[predicteur]) == {"brier", "auc", "erreur_absolue_moyenne"}
            assert 0 <= jeu[predicteur]["brier"] <= 1
        assert jeu["baseline_bat_naive_brier"] == (jeu["baseline"]["brier"] < jeu["naive"]["brier"])
    assert resultat["donnees"]["depots"]["d"]["series_tenues_a_l_ecart"] == 1
    assert resultat["entrainement"]["effectif"] > 0


def test_evaluer_deterministe() -> None:
    series = _jeu_synthetique()
    assert evaluer(series) == evaluer(series.reverse())


def test_evaluer_sans_unite() -> None:
    with pytest.raises(UsineErreur, match="aucune unité"):
        evaluer(_serie("d/A", [4] * 15))


def test_evaluer_sans_entrainement() -> None:
    # Une seule série, tenue à l'écart : aucune unité d'entraînement.
    with pytest.raises(UsineErreur, match="aucune unité d'entraînement"):
        evaluer(_serie("d/J", [_CYCLE[k % 20] for k in range(120)]))


def test_avertissement_sm10() -> None:
    def jeu(bat: bool | None) -> dict[str, Any]:
        return {
            "baseline": {"brier": 0.3},
            "naive": {"brier": 0.2},
            "baseline_bat_naive_brier": bat,
        }

    resultat = {"jeux": {"test_temporel": jeu(False), "test_projets": jeu(True), "vide": jeu(None)}}
    messages = avertissements_sm10(resultat)
    assert len(messages) == 1
    assert "SM-10" in messages[0] and "test_temporel" in messages[0]


def test_cli_succes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    series = _jeu_synthetique()
    premier, second = tmp_path / "a.parquet", tmp_path / "b.parquet"
    series.filter(pl.col("serie") != "d/J").write_parquet(premier)
    series.filter(pl.col("serie") == "d/J").write_parquet(second)
    sortie = tmp_path / "resultats" / "evaluation.json"
    code = evaluation.main(["--series", str(premier), str(second), "--sortie", str(sortie)])
    assert code == 0
    publie = json.loads(sortie.read_text(encoding="utf-8"))
    assert publie == json.loads(json.dumps(evaluer(series)))
    sortie_cli = capsys.readouterr().out
    assert "test_temporel" in sortie_cli
    assert str(sortie) in sortie_cli
    perdants = [n for n, j in publie["jeux"].items() if j["baseline_bat_naive_brier"] is False]
    assert ("Avertissement SM-10" in sortie_cli) == bool(perdants)


def _jeu_a_la_main(creux: tuple[int, ...] = (22,)) -> pl.DataFrame:
    """`e/A` (évalué dans le temps) et `d/J` (seul projet de son dépôt, tenu à l'écart).

    e/A : stock 4 sur 71 Jours ouvrés, 2 aux indices `creux` ; unités aux lundis d'indice
    20, 25, …, 60 ; coupure au 7ᵉ (indice 50) ; entraînement 20, 25, 30, 35 (cible 1
    seulement à 20 avec le creux en 22 : taux 1/4) ; test temporel 50, 55, 60 (cibles 0,
    stock 4 à N).
    d/J : stock 4 sur 30 Jours ouvrés puis 7 ; une unité au lundi d'indice 20, cible 0,
    stock 7 à N.
    """
    stocks_a = [2 if k in creux else 4 for k in range(71)]
    return pl.concat([_serie("e/A", stocks_a), _serie("d/J", [4] * 30 + [7])])


def test_evaluer_calcule_a_la_main() -> None:
    resultat = evaluer(_jeu_a_la_main())
    assert resultat["entrainement"] == {"effectif": 4, "positifs": 1, "taux_cible": 0.25}
    temporel = resultat["jeux"]["test_temporel"]
    projets = resultat["jeux"]["test_projets_tenus_a_l_ecart"]
    # Baseline : vélocité nulle → probabilité 0, stock projeté = stock (4).
    # Naïve : 1/4 (taux d'e/A ; repli global pour d/J), stock projeté = stock (4).
    assert (temporel["effectif"], temporel["positifs"]) == (3, 0)
    assert temporel["baseline"] == {"brier": 0.0, "auc": None, "erreur_absolue_moyenne": 0.0}
    assert temporel["naive"] == {"brier": 0.0625, "auc": None, "erreur_absolue_moyenne": 0.0}
    assert temporel["baseline_bat_naive_brier"] is True
    # d/J : vérité 7 à N, d'où |4 − 7| = 3 pour les deux prédicteurs.
    assert (projets["effectif"], projets["positifs"]) == (1, 0)
    assert projets["baseline"] == {"brier": 0.0, "auc": None, "erreur_absolue_moyenne": 3.0}
    assert projets["naive"] == {"brier": 0.0625, "auc": None, "erreur_absolue_moyenne": 3.0}
    assert projets["baseline_bat_naive_brier"] is True


def test_evaluer_horizon_different_de_la_baseline() -> None:
    with pytest.raises(UsineErreur, match="horizon 5"):
        evaluer(_jeu_a_la_main(), horizon=5)


def test_cli_avertissement_sm10(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Sans creux, le taux d'entraînement est 0 : naïve et Baseline à Brier 0, pas d'avantage.
    fichier = tmp_path / "plat.parquet"
    _jeu_a_la_main(creux=()).write_parquet(fichier)
    sortie = tmp_path / "evaluation.json"
    assert evaluation.main(["--series", str(fichier), "--sortie", str(sortie)]) == 0
    publie = json.loads(sortie.read_text(encoding="utf-8"))
    assert publie["jeux"]["test_temporel"]["baseline_bat_naive_brier"] is False
    assert "Avertissement SM-10 : sur test_temporel" in capsys.readouterr().out


def test_cli_fichier_non_parquet(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fichier = tmp_path / "corrompu.parquet"
    fichier.write_text("pas un parquet", encoding="utf-8")
    sortie = tmp_path / "evaluation.json"
    assert evaluation.main(["--series", str(fichier), "--sortie", str(sortie)]) == 1
    assert capsys.readouterr().err.startswith("Erreur : ")
    assert not sortie.exists()


def test_cli_aucune_unite(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fichier = tmp_path / "court.parquet"
    _serie("d/A", [4] * 15).write_parquet(fichier)
    sortie = tmp_path / "evaluation.json"
    assert evaluation.main(["--series", str(fichier), "--sortie", str(sortie)]) == 1
    assert "aucune unité" in capsys.readouterr().err
    assert not sortie.exists()
