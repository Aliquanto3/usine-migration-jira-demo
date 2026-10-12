"""Risque d'entrée en rouge (Story 4.2, FR-21, H-8).

Valeurs attendues calculées à la main. Table de référence ENT-C : 10 Jours ouvrés du lundi
28/09/2026 au vendredi 09/10/2026 (D) ; Météo orange ; Grille livrée (rouge : IND-1 `>= 3`,
IND-3 `>= 20`, IND-4 `>= 1/5`). x = 0..9, projection à x = 9 + h, h = 1..5 ; D + 1 JO = lundi
12/10, D + 5 JO = vendredi 16/10.

- IND-3 = 10..19 : b = 1, a = 10, p(1) = 20 ≥ 20 → risque à D + 1 JO.
- IND-1 = 0,0,0,0,0,1,1,1,2,2 : x̄ = 9/2, ȳ = 7/10, Σxy − n·x̄·ȳ = 52 − 63/2 = 41/2,
  Σ(x − x̄)² = 165/2 → b = 41/165, a = 7/10 − 369/330 = −23/55 ; p(4) = −69/165 + 533/165 =
  464/165 < 3, p(5) = −69/165 + 574/165 = 505/165 = 101/33 ≥ 3 → risque à D + 5 JO.
- IND-4 = 5/100..14/100 : b = 1/100, p(5) = 19/100 < 1/5 → aucun risque.
"""

import re
from collections.abc import Sequence
from dataclasses import FrozenInstanceError
from datetime import date
from fractions import Fraction
from pathlib import Path
from typing import Any

import polars as pl
import pytest
import yaml

from usine.contrats.calcul import SCHEMA_INDICATEUR
from usine.contrats.calendrier import jours_ouvres
from usine.contrats.config import GrilleMeteo
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import (
    CodeIndicateur,
    Couleur,
    MeteoEntite,
    Operateur,
    RegleDeclenchante,
)
from usine.contrats.prevision import RisqueEntreeRouge
from usine.contrats.schemas import valider
from usine.domaine.prevision import commun as module_commun
from usine.domaine.prevision import risque as module_risque
from usine.domaine.prevision.commun import avancer, declenche
from usine.domaine.prevision.risque import (
    IndicateurExclu,
    ParametresRisque,
    ResultatRisque,
    risques_entree_rouge,
)

RACINE = Path(__file__).resolve().parents[4]
CHEMIN_GRILLE = RACINE / "config" / "grille_meteo.yaml"
D = date(2026, 10, 9)
ENTITE = "ENT-C"
VERSION_GRILLE = "grille-test"
I1, I3, I4 = CodeIndicateur.ind_1, CodeIndicateur.ind_3, CodeIndicateur.ind_4

Valeur = tuple[int, int] | str
"""Valeur évaluée `(numerateur, denominateur)` ou motif d'un indicateur non évaluable."""

IND_1: list[Valeur] = [(v, 1) for v in (0, 0, 0, 0, 0, 1, 1, 1, 2, 2)]
IND_3: list[Valeur] = [(v, 1) for v in range(10, 20)]
IND_4: list[Valeur] = [(v, 100) for v in range(5, 15)]
STABLE_1: list[Valeur] = [(2, 1)] * 10
STABLE_3: list[Valeur] = [(v, 1) for v in range(19, 9, -1)]
STABLE_4: list[Valeur] = [(1, 10)] * 10


def _donnees_grille() -> dict[str, Any]:
    donnees: dict[str, Any] = yaml.safe_load(CHEMIN_GRILLE.read_text(encoding="utf-8"))
    return donnees


def _grille(**indicateurs_yaml: Any) -> GrilleMeteo:
    donnees = _donnees_grille()
    for code, modification in indicateurs_yaml.items():
        donnees["indicateurs"][code.replace("_", "-")].update(modification)
    return GrilleMeteo.model_validate(donnees)


GRILLE = _grille()


def _table(
    series: dict[CodeIndicateur, Sequence[Valeur]],
    fin: date = D,
    entite: str = ENTITE,
    dates: dict[CodeIndicateur, list[date]] | None = None,
) -> pl.DataFrame:
    lignes: dict[str, list[object]] = {colonne: [] for colonne in SCHEMA_INDICATEUR.colonnes}
    for code, valeurs in series.items():
        jours = (dates or {}).get(code) or list(jours_ouvres(date(2026, 1, 1), fin))[
            -len(valeurs) :
        ]
        for jour, valeur in zip(jours, valeurs, strict=True):
            evaluee = not isinstance(valeur, str)
            lignes["date"].append(jour)
            lignes["entite"].append(entite)
            lignes["code"].append(code.value)
            lignes["statut"].append("evalue" if evaluee else "non_evaluable")
            lignes["motif"].append("" if evaluee else valeur)
            lignes["numerateur"].append(valeur[0] if not isinstance(valeur, str) else 0)
            lignes["denominateur"].append(valeur[1] if not isinstance(valeur, str) else 0)
            lignes["couleur"].append("vert")
    table = pl.DataFrame(lignes, schema=dict(SCHEMA_INDICATEUR.colonnes))
    return valider(table, SCHEMA_INDICATEUR)


def _reference(**remplacements: Sequence[Valeur]) -> pl.DataFrame:
    series: dict[CodeIndicateur, Sequence[Valeur]] = {I1: IND_1, I3: IND_3, I4: IND_4}
    for nom, valeurs in remplacements.items():
        series[CodeIndicateur(nom.replace("_", "-").upper())] = valeurs
    return _table(series)


def _meteo(couleur: Couleur = Couleur.orange) -> MeteoEntite:
    regle = RegleDeclenchante(
        code=CodeIndicateur.ind_3,
        couleur=couleur,
        operateur=Operateur.superieur_ou_egal,
        numerateur=19,
        denominateur=1,
        seuil_numerateur=10,
        seuil_denominateur=1,
        tickets_en_cause=(),
    )
    return MeteoEntite(
        date_arrete=D,
        entite=ENTITE,
        couleur=couleur,
        regles=(regle,),
        version_grille=VERSION_GRILLE,
    )


def _calculer(table: pl.DataFrame, grille: GrilleMeteo = GRILLE) -> ResultatRisque:
    return risques_entree_rouge(table, _meteo(), grille)


# --- Matrice I/O ---


def test_franchissement_ind_3_et_tendance_non_lineaire_ind_1() -> None:
    resultat = _calculer(_reference())

    assert resultat.exclus == ()
    assert [r.risque.indicateur for r in resultat.risques] == [I1, I3]
    ind_1, ind_3 = resultat.risques

    assert ind_3.risque == RisqueEntreeRouge(
        date_arrete=D,
        entite=ENTITE,
        indicateur=I3,
        date_franchissement_estimee=date(2026, 10, 12),
        horizon_jours_ouvres=5,
        numerateur=19,
        denominateur=1,
        seuil_numerateur=20,
        seuil_denominateur=1,
        version_grille=VERSION_GRILLE,
    )
    assert ind_3.valeur_projetee == Fraction(20)

    assert ind_1.risque.date_franchissement_estimee == date(2026, 10, 16)
    assert ind_1.valeur_projetee == Fraction(101, 33)
    assert (ind_1.risque.numerateur, ind_1.risque.denominateur) == (2, 1)
    assert (ind_1.risque.seuil_numerateur, ind_1.risque.seuil_denominateur) == (3, 1)


def test_tendance_ind_1_juste_sous_le_seuil_avec_horizon_4() -> None:
    """p(4) = 464/165 < 3 : aucun risque IND-1 avec un horizon de 4 JO."""
    resultat = risques_entree_rouge(_reference(), _meteo(), GRILLE, ParametresRisque(horizon=4))

    assert [r.risque.indicateur for r in resultat.risques] == [I3]
    assert resultat.risques[0].risque.horizon_jours_ouvres == 4


def test_hausse_insuffisante_ind_4() -> None:
    resultat = _calculer(_reference())

    assert I4 not in {r.risque.indicateur for r in resultat.risques}
    assert I4 not in {e.code for e in resultat.exclus}


def test_ind_4_au_seuil_avec_un_horizon_plus_long() -> None:
    """Contre-épreuve : p(6) = 20/100 = 1/5 franchit `>= 1/5` à D + 6 JO."""
    resultat = risques_entree_rouge(_reference(), _meteo(), GRILLE, ParametresRisque(horizon=6))

    ind_4 = next(r for r in resultat.risques if r.risque.indicateur is I4)
    assert ind_4.valeur_projetee == Fraction(1, 5)
    assert ind_4.risque.date_franchissement_estimee == date(2026, 10, 19)
    assert (ind_4.risque.numerateur, ind_4.risque.denominateur) == (14, 100)
    assert (ind_4.risque.seuil_numerateur, ind_4.risque.seuil_denominateur) == (1, 5)


def test_series_stables_ou_en_baisse() -> None:
    resultat = _calculer(_reference(ind_1=STABLE_1, ind_3=STABLE_3, ind_4=STABLE_4))

    assert resultat == ResultatRisque(risques=(), exclus=())


def test_ind_4_non_evaluable_sur_une_partie_de_la_fenetre() -> None:
    ind_4: list[Valeur] = list(IND_4)
    ind_4[3] = "moins de 20 Cas de test exécutés"
    ind_4[6] = "hors Phase"

    resultat = _calculer(_reference(ind_4=ind_4))

    assert resultat.exclus == (
        IndicateurExclu(I4, "non évaluable le 2026-10-01 : moins de 20 Cas de test exécutés"),
    )
    assert [r.risque.indicateur for r in resultat.risques] == [I1, I3]


def test_non_evaluable_hors_fenetre_ignore() -> None:
    ind_4: list[Valeur] = ["hors Phase", *IND_4]

    resultat = _calculer(_reference(ind_4=ind_4))

    assert resultat.exclus == ()


def test_historique_d_un_seul_jour() -> None:
    resultat = _calculer(_reference(ind_1=[(2, 1)]))

    assert resultat.exclus == (
        IndicateurExclu(I1, "historique insuffisant : 1 Jour ouvré (2 au moins attendus)"),
    )
    assert [r.risque.indicateur for r in resultat.risques] == [I3]


def test_historique_court_regression_sur_les_jours_presents() -> None:
    """IND-3 = 17, 18, 19 (3 JO) : b = 1, p(1) = 20 → risque à D + 1 JO."""
    resultat = _calculer(_reference(ind_3=[(17, 1), (18, 1), (19, 1)]))

    ind_3 = next(r for r in resultat.risques if r.risque.indicateur is I3)
    assert ind_3.valeur_projetee == Fraction(20)
    assert ind_3.risque.date_franchissement_estimee == date(2026, 10, 12)


def test_fenetre_limitee_aux_derniers_jours() -> None:
    """15 JO dont 5 anciens à 100 : seule la fenêtre de 10 JO compte (IND-3 = 10..19)."""
    resultat = _calculer(_reference(ind_3=[(100, 1)] * 5 + list(IND_3)))

    ind_3 = next(r for r in resultat.risques if r.risque.indicateur is I3)
    assert ind_3.valeur_projetee == Fraction(20)


@pytest.mark.parametrize(
    ("modification", "motif"),
    [
        ({"active": False}, "indicateur inactif dans la Grille"),
        ({"seuils": {"orange": ">= 10", "jaune": ">= 5"}}, "aucun seuil rouge dans la Grille"),
    ],
)
def test_indicateur_inactif_ou_sans_seuil_rouge(modification: dict[str, Any], motif: str) -> None:
    table = _table({I1: STABLE_1, I4: STABLE_4})  # aucune ligne IND-3 : la table n'est pas lue

    resultat = _calculer(table, _grille(IND_3=modification))

    assert resultat == ResultatRisque(risques=(), exclus=(IndicateurExclu(I3, motif),))


def test_ordre_des_exclus() -> None:
    ind_1: list[Valeur] = ["sans donnée"] * 10
    grille = _grille(IND_3={"active": False})

    resultat = _calculer(_table({I1: ind_1, I4: [(1, 10)]}), grille)

    assert [e.code for e in resultat.exclus] == [I1, I3, I4]


def test_autres_entites_et_lignes_posterieures_ignorees() -> None:
    reference = _reference()
    autre = _table({I1: [(9, 1)] * 10}, entite="ENT-X")
    apres = _table(
        {I1: [(50, 1)] * 3},
        fin=date(2026, 10, 14),
        dates={I1: [date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 14)]},
    )

    resultat = _calculer(pl.concat([reference, autre, apres]))

    assert resultat == _calculer(reference)


# --- Entrées invalides ---


def _erreur(table: pl.DataFrame, meteo: MeteoEntite | None = None) -> str:
    with pytest.raises(UsineErreur) as erreur:
        risques_entree_rouge(table, meteo or _meteo(), GRILLE)
    message = str(erreur.value)
    assert ENTITE in message
    return message


def test_meteo_rouge_refusee() -> None:
    assert "Météo rouge" in _erreur(_reference(), _meteo(Couleur.rouge))


def test_date_d_arrete_absente() -> None:
    table = _table({I1: IND_1, I3: IND_3, I4: IND_4}, fin=date(2026, 10, 8))

    assert "Date d'arrêté 2026-10-09 absente" in _erreur(table)


def test_indicateur_actif_absent() -> None:
    assert "IND-4" in _erreur(_table({I1: IND_1, I3: IND_3}))


def test_trou_de_jours_ouvres() -> None:
    dates = [date(2026, 10, 5), date(2026, 10, 7), date(2026, 10, 8), D]
    table = pl.concat([_table({I1: IND_1, I4: IND_4}), _table({I3: IND_3[:4]}, dates={I3: dates})])

    assert "trou de Jours ouvrés entre 2026-10-05 et 2026-10-07" in _erreur(table)


def test_date_non_ouvree() -> None:
    dates = [date(2026, 10, 4), D]
    table = pl.concat([_table({I1: IND_1, I4: IND_4}), _table({I3: IND_3[:2]}, dates={I3: dates})])

    assert "2026-10-04 n'est pas un Jour ouvré" in _erreur(table)


def test_doublon() -> None:
    reference = _reference()
    doublon = reference.filter((pl.col("code") == "IND-3") & (pl.col("date") == D))

    assert "date 2026-10-09 en double" in _erreur(pl.concat([reference, doublon]))


def test_valeur_evaluee_de_denominateur_nul() -> None:
    ind_4: list[Valeur] = list(IND_4)
    ind_4[2] = (1, 0)

    assert "dénominateur > 0 attendu" in _erreur(_reference(ind_4=ind_4))


def test_table_hors_schema() -> None:
    assert "SCHEMA_INDICATEUR" in _erreur(_reference().drop("motif"))


@pytest.mark.parametrize("valeurs", [{"fenetre": 0}, {"horizon": 0}, {"horizon": 1.5}])
def test_parametres_invalides(valeurs: dict[str, Any]) -> None:
    with pytest.raises(UsineErreur, match="paramètre"):
        ParametresRisque(**valeurs)


def test_parametres_par_defaut_et_geles() -> None:
    parametres = ParametresRisque()

    assert (parametres.fenetre, parametres.horizon) == (10, 5)
    with pytest.raises(FrozenInstanceError):
        parametres.horizon = 3  # type: ignore[misc]


# --- Déterminisme, pureté, AD-18 ---


def test_deterministe_et_table_non_mutee() -> None:
    table = _reference()
    copie = table.clone()

    premier = _calculer(table)
    second = _calculer(table)

    assert premier == second
    assert table.equals(copie)


def test_sans_horloge_ni_hasard() -> None:
    for module in (module_risque, module_commun):
        texte = Path(str(module.__file__)).read_text(encoding="utf-8")
        for interdit in ("now(", "today(", "random"):
            assert interdit not in texte


def test_primitives_communes() -> None:
    assert avancer(D, 0) == D
    assert avancer(D, 1) == date(2026, 10, 12)
    assert avancer(D, 5) == date(2026, 10, 16)
    assert declenche(Fraction(3), Operateur.superieur_ou_egal, Fraction(3))
    assert not declenche(Fraction(3), Operateur.superieur, Fraction(3))
    assert declenche(Fraction(31, 10), Operateur.superieur, Fraction(3))


def test_avancer_defini_une_seule_fois_ad_18() -> None:
    motif = re.compile(r"^\s*def\s+(_?avancer|_?declenche)\s*\(")
    racine = RACINE / "src" / "usine" / "domaine" / "prevision"
    definitions = [
        f"{chemin.name}:{ligne.strip()}"
        for chemin in sorted(racine.rglob("*.py"))
        for ligne in chemin.read_text(encoding="utf-8").splitlines()
        if motif.match(ligne)
    ]
    assert definitions == [
        "commun.py:def avancer(jour: date, n: int) -> date:",
        "commun.py:def declenche(valeur: Fraction, operateur: Operateur, seuil: Fraction) -> bool:",
    ]


def test_baseline_utilise_les_primitives_communes() -> None:
    from usine.domaine.prevision import baseline

    assert vars(baseline)["avancer"] is avancer
    assert vars(baseline)["declenche"] is declenche
    assert "def _avancer" not in Path(str(baseline.__file__)).read_text(encoding="utf-8")


def test_indicateur_absent_de_la_grille() -> None:
    donnees = _donnees_grille()
    del donnees["indicateurs"]["IND-3"]
    grille = GrilleMeteo.model_validate(donnees)

    resultat = _calculer(_reference(), grille)

    assert resultat.exclus == (IndicateurExclu(I3, "indicateur absent de la Grille"),)
    assert I3 not in {r.risque.indicateur for r in resultat.risques}


def test_operateur_strict() -> None:
    """IND-3 rouge `> 20` : p(1) = 20 ne déclenche pas, p(2) = 21 déclenche à D + 2 JO."""
    grille = _grille(IND_3={"seuils": {"rouge": "> 20", "orange": ">= 10", "jaune": ">= 5"}})

    resultat = _calculer(_reference(), grille)

    ind_3 = next(r for r in resultat.risques if r.risque.indicateur is I3)
    assert ind_3.valeur_projetee == Fraction(21)
    assert ind_3.risque.date_franchissement_estimee == avancer(D, 2) == date(2026, 10, 13)


def test_fenetre_non_par_defaut() -> None:
    """IND-3 = 19, 18, …, 13, 15, 17, 19.

    Sur 10 JO : Σxy − n·x̄·ȳ = 720 − 733,5 < 0, pente négative → aucun risque. Sur les 3
    derniers JO (15, 17, 19) : b = 2, a = 15, p(1) = 15 + 2·3 = 21 ≥ 20 → risque à D + 1 JO.
    """
    ind_3: list[Valeur] = [(v, 1) for v in (19, 18, 17, 16, 15, 14, 13, 15, 17, 19)]
    table = _reference(ind_3=ind_3)

    defaut = _calculer(table)
    court = risques_entree_rouge(table, _meteo(), GRILLE, ParametresRisque(fenetre=3))

    assert I3 not in {r.risque.indicateur for r in defaut.risques}
    ind_3_court = next(r for r in court.risques if r.risque.indicateur is I3)
    assert ind_3_court.valeur_projetee == Fraction(21)
    assert ind_3_court.risque.date_franchissement_estimee == date(2026, 10, 12)


def test_indicateurs_non_projetes_ignores() -> None:
    reference = _reference()
    ind_2 = _table(
        {CodeIndicateur.ind_2: [(7, 1), "sans bloquante"]},
        dates={CodeIndicateur.ind_2: [date(2026, 10, 1), date(2026, 10, 4)]},
    )

    assert _calculer(pl.concat([reference, ind_2])) == _calculer(reference)
