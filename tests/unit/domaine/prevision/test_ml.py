"""Prévision `methode=ml` par agrégation binomiale (Story 4.6, FR-22, AD-18).

Valeurs calculées à la main. Stock S, résolutions requises k (IND-1 rouge `>= 3` : k = S − 2),
résolutions indépendantes de probabilité p :

    S = 3, k = 1, p = 1/2 : 1 − (1/2)³ = 7/8
    S = 4, k = 2, p = 1/2 : 1 − (1 + 4)/16 = 11/16
    S = 6, k = 4, p = 1/2 : (15 + 6 + 1)/64 = 11/32
"""

from datetime import date
from fractions import Fraction

import pytest

from usine.contrats.calendrier import jours_ouvres
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import (
    CodeIndicateur,
    Couleur,
    MeteoEntite,
    Operateur,
    RegleDeclenchante,
)
from usine.contrats.prevision import MethodePrevision, StatutPrevision
from usine.domaine.prevision.commun import avancer
from usine.domaine.prevision.ml import (
    facteurs_depuis_contributions,
    prevoir_sortie_ml,
    probabilite_sortie,
    resolutions_requises,
)

D = date(2026, 10, 9)
MOITIE = Fraction(1, 2)


def _regle(
    stock: int,
    seuil: int = 3,
    code: CodeIndicateur = CodeIndicateur.ind_1,
    operateur: Operateur = Operateur.superieur_ou_egal,
) -> RegleDeclenchante:
    return RegleDeclenchante(
        code=code,
        couleur=Couleur.rouge,
        operateur=operateur,
        numerateur=stock,
        denominateur=1,
        seuil_numerateur=seuil,
        seuil_denominateur=1,
        tickets_en_cause=(),
    )


def _meteo(*regles: RegleDeclenchante, couleur: Couleur = Couleur.rouge) -> MeteoEntite:
    return MeteoEntite(
        date_arrete=D,
        entite="ENT-A",
        couleur=couleur,
        regles=regles,
        version_grille="grille-test",
    )


@pytest.mark.parametrize(
    ("stock", "operateur", "seuil", "attendu"),
    [
        (3, Operateur.superieur_ou_egal, 3, 1),
        (6, Operateur.superieur_ou_egal, 3, 4),
        (4, Operateur.superieur_ou_egal, 3, 2),
        (4, Operateur.superieur, 3, 1),
        (2, Operateur.superieur_ou_egal, 3, 0),
    ],
)
def test_resolutions_requises(stock: int, operateur: Operateur, seuil: int, attendu: int) -> None:
    assert resolutions_requises(stock, operateur, Fraction(seuil)) == attendu


@pytest.mark.parametrize(
    ("stock", "k", "p", "attendu"),
    [
        (3, 1, MOITIE, Fraction(7, 8)),
        (4, 2, MOITIE, Fraction(11, 16)),
        (6, 4, MOITIE, Fraction(11, 32)),
        (5, 0, Fraction(1, 10), Fraction(1)),
        (3, 4, Fraction(9, 10), Fraction(0)),
        (4, 2, Fraction(0), Fraction(0)),
        (4, 2, Fraction(1), Fraction(1)),
    ],
)
def test_probabilite_binomiale_exacte(stock: int, k: int, p: Fraction, attendu: Fraction) -> None:
    assert probabilite_sortie(stock, k, p) == attendu


def test_probabilite_hors_bornes() -> None:
    with pytest.raises(UsineErreur, match="hors de"):
        probabilite_sortie(3, 1, Fraction(3, 2))


def test_prevision_ml_projetee() -> None:
    prevision = prevoir_sortie_ml(_meteo(_regle(4)), MOITIE, 10)
    assert prevision.methode is MethodePrevision.ml
    assert prevision.statut is StatutPrevision.sortie_projetee
    assert (prevision.probabilite_numerateur, prevision.probabilite_denominateur) == (11, 16)
    assert prevision.date_sortie_estimee == avancer(D, 10)
    assert prevision.horizon_jours_ouvres == 10
    assert prevision.date_sortie_optimiste is None
    assert prevision.facteurs == ()


def test_prevision_ml_pas_de_sortie() -> None:
    prevision = prevoir_sortie_ml(_meteo(_regle(6)), MOITIE, 10)
    assert prevision.statut is StatutPrevision.pas_de_sortie_projetee
    assert (prevision.probabilite_numerateur, prevision.probabilite_denominateur) == (11, 32)
    assert prevision.date_sortie_estimee is None


def test_prevision_ml_regle_non_projetable() -> None:
    meteo = _meteo(_regle(6), _regle(1, 1, CodeIndicateur.ind_5))
    prevision = prevoir_sortie_ml(meteo, MOITIE, 10)
    assert prevision.statut is StatutPrevision.regle_non_projetable
    assert prevision.regles_non_projetables == (CodeIndicateur.ind_5,)
    assert prevision.probabilite_numerateur == 0


def test_prevision_ml_deterministe_et_dans_la_date() -> None:
    meteo = _meteo(_regle(5))
    assert prevoir_sortie_ml(meteo, Fraction(1, 3), 10) == prevoir_sortie_ml(
        meteo, Fraction(1, 3), 10
    )
    assert avancer(D, 10) in jours_ouvres(D, avancer(D, 10))


def test_prevision_ml_refus() -> None:
    with pytest.raises(UsineErreur, match="rouge attendue"):
        prevoir_sortie_ml(_meteo(couleur=Couleur.vert), MOITIE, 10)
    with pytest.raises(UsineErreur, match="horizon"):
        prevoir_sortie_ml(_meteo(_regle(4)), MOITIE, 0)


def test_facteurs_au_plus_cinq_tries_et_libelles_en_francais() -> None:
    contributions = {
        "stock": Fraction(-3, 2),
        "entrees_5": Fraction(1, 4),
        "entrees_10": Fraction(-1, 4),
        "sorties_5": Fraction(2),
        "sorties_10": Fraction(1, 10),
        "sorties_20": Fraction(1, 2),
        "variation_stock_10": Fraction(0),
        "stock_max_20": Fraction(1, 5),
    }
    facteurs = facteurs_depuis_contributions(contributions)
    assert [f.nom for f in facteurs] == [
        "sorties_5",
        "stock",
        "sorties_20",
        "entrees_10",
        "entrees_5",
    ]
    assert (
        facteurs[0].libelle
        == "Sorties sur les 5 derniers Jours ouvrés : favorise la sortie du rouge"
    )
    assert facteurs[1].libelle.endswith("freine la sortie du rouge")
    assert (facteurs[1].numerateur, facteurs[1].denominateur) == (-3, 2)


def test_facteurs_nuls_ou_vides_et_variable_inconnue() -> None:
    assert facteurs_depuis_contributions({"stock": Fraction(1, 10_000)}) == ()
    with pytest.raises(UsineErreur, match="sans libellé"):
        facteurs_depuis_contributions({"inconnue": Fraction(1)})


def test_prevision_ml_porte_les_facteurs_sauf_non_projetable() -> None:
    contributions = {"stock": Fraction(1, 2)}
    sortie = prevoir_sortie_ml(_meteo(_regle(3)), Fraction(9, 10), 10, contributions)
    assert [f.nom for f in sortie.facteurs] == ["stock"]
    assert prevoir_sortie_ml(_meteo(_regle(3)), Fraction(9, 10), 10).facteurs == ()
    autre = _regle(5, code=CodeIndicateur.ind_2)
    non_projetable = prevoir_sortie_ml(_meteo(_regle(3), autre), MOITIE, 10, contributions)
    assert non_projetable.statut is StatutPrevision.regle_non_projetable
    assert non_projetable.facteurs == ()
