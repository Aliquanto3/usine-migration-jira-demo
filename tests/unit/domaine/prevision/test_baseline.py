"""Baseline de sortie du rouge (Story 4.1, FR-20, AD-18).

Valeurs attendues calculées à la main. Série de référence ENT-A : 20 Jours ouvrés du lundi
14/09/2026 au vendredi 09/10/2026 (D), stock S = 6 à D, IND-1 rouge `>= 3`. Sorties − Entrées
par Jour ouvré (Entrées = 1, Sorties = 1 + net si net ≥ 0) :

    JO 1-10  : 0 0 0 0 0 0 0 0 1 2   (v précédente = 3/10)
    JO 11-20 : 1 0 1 0 1 0 1 0 1 1   (v = 6/10 = 3/5)

Fenêtres glissantes de 5 JO (16) : sommes 0 0 0 0 1 3 4 4 5 4 3 2 3 2 3 3, triées
0 0 0 0 1 2 2 3 3 3 3 3 4 4 4 5. Type 7 : P25 = x3 + 0,75·(x4 − x3) = 3/4 → w = 3/20 ;
P75 = x11 + 0,25·(x12 − x11) = 13/4 → w = 13/20.
Jours à la sortie t = ⌊3/w⌋ + 1 : v = 3/5 → 6 (lundi 19/10) ; 13/20 → 5 (vendredi 16/10) ;
3/20 → 21 (lundi 09/11). Probabilité : sommes 0 (4) et 1 (t = 16) échouent, 2, 3, 4, 5
(t = 8, 6, 4, 4) réussissent → 11/16.
"""

import re
from dataclasses import FrozenInstanceError
from datetime import date
from pathlib import Path

import polars as pl
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
from usine.contrats.prevision import (
    SCHEMA_SERIE_STOCK,
    MethodePrevision,
    Prevision,
    StatutPrevision,
)
from usine.contrats.schemas import valider
from usine.domaine.prevision import baseline
from usine.domaine.prevision.baseline import ParametresBaseline, prevoir_sortie

RACINE = Path(__file__).resolve().parents[4]
D = date(2026, 10, 9)
ENTITE = "ENT-A"
VERSION_GRILLE = "grille-test"
PREMIERS = [0, 0, 0, 0, 0, 0, 0, 0, 1, 2]
DERNIERS = [1, 0, 1, 0, 1, 0, 1, 0, 1, 1]


def _serie(
    nets: list[int], stock_final: int = 6, fin: date = D, entite: str = ENTITE
) -> pl.DataFrame:
    """Série dense finissant à `fin` ; le stock recule de `net` chaque jour vers le passé."""
    dates = jours_ouvres(date(2026, 1, 1), fin)[-len(nets) :]
    stocks: list[int] = []
    stock = stock_final
    for net in reversed(nets):
        stocks.append(stock)
        stock += net
    stocks.reverse()
    return valider(
        pl.DataFrame(
            {
                "serie": [entite] * len(nets),
                "date": list(dates),
                "stock": stocks,
                "entrees": [1 if n >= 0 else 1 - n for n in nets],
                "sorties": [1 + n if n >= 0 else 1 for n in nets],
            },
            schema=dict(SCHEMA_SERIE_STOCK.colonnes),
        ),
        SCHEMA_SERIE_STOCK,
    )


def _regle(
    code: CodeIndicateur,
    valeur: int,
    seuil: int,
    couleur: Couleur = Couleur.rouge,
    operateur: Operateur = Operateur.superieur_ou_egal,
) -> RegleDeclenchante:
    return RegleDeclenchante(
        code=code,
        couleur=couleur,
        operateur=operateur,
        numerateur=valeur,
        denominateur=1,
        seuil_numerateur=seuil,
        seuil_denominateur=1,
        tickets_en_cause=(),
    )


IND_1 = _regle(CodeIndicateur.ind_1, 6, 3)
IND_5 = _regle(CodeIndicateur.ind_5, 1, 1)


def _meteo(*regles: RegleDeclenchante, couleur: Couleur = Couleur.rouge) -> MeteoEntite:
    return MeteoEntite(
        date_arrete=D,
        entite=ENTITE,
        couleur=couleur,
        regles=regles or (IND_1,),
        version_grille=VERSION_GRILLE,
    )


def _facteurs(prevision: Prevision) -> dict[str, tuple[int, int]]:
    return {f.nom: (f.numerateur, f.denominateur) for f in prevision.facteurs}


FACTEURS_REFERENCE = {
    "stock": (6, 1),
    "entrees": (10, 1),
    "sorties": (16, 1),
    "velocite_nette": (3, 5),
    "variation_velocite": (3, 10),
}
LIBELLE_VARIATION_REFERENCE = (
    "Variation de la vélocité nette par rapport aux 10 Jours ouvrés précédents"
)


def test_sortie_projetee() -> None:
    prevision = prevoir_sortie(_serie(PREMIERS + DERNIERS), _meteo())

    assert prevision.methode is MethodePrevision.baseline
    assert prevision.statut is StatutPrevision.sortie_projetee
    assert (prevision.date_arrete, prevision.entite) == (D, ENTITE)
    assert prevision.version_grille == VERSION_GRILLE
    assert prevision.horizon_jours_ouvres == 10
    assert prevision.date_sortie_estimee == date(2026, 10, 19)
    assert prevision.date_sortie_optimiste == date(2026, 10, 16)
    assert prevision.date_sortie_pessimiste == date(2026, 11, 9)
    assert (prevision.probabilite_numerateur, prevision.probabilite_denominateur) == (11, 16)
    assert _facteurs(prevision) == FACTEURS_REFERENCE
    assert [f.nom for f in prevision.facteurs] == list(FACTEURS_REFERENCE)
    assert prevision.facteurs[4].libelle == LIBELLE_VARIATION_REFERENCE
    assert prevision.regles_non_projetables == ()


def test_serie_plus_longue_que_la_profondeur() -> None:
    # 10 JO à +5 ajoutés avant la série de référence : hors des 20 derniers JO, ignorés.
    prevision = prevoir_sortie(_serie([5] * 10 + PREMIERS + DERNIERS), _meteo())

    assert prevision.date_sortie_estimee == date(2026, 10, 19)
    assert prevision.date_sortie_optimiste == date(2026, 10, 16)
    assert prevision.date_sortie_pessimiste == date(2026, 11, 9)
    assert (prevision.probabilite_numerateur, prevision.probabilite_denominateur) == (11, 16)
    assert _facteurs(prevision) == FACTEURS_REFERENCE
    assert prevision.facteurs[4].libelle == LIBELLE_VARIATION_REFERENCE


def test_fenetre_precedente_partielle() -> None:
    prevision = prevoir_sortie(_serie([0, 0, 1, *DERNIERS]), _meteo())

    assert _facteurs(prevision)["variation_velocite"] == (4, 15)
    assert prevision.facteurs[4].libelle == (
        "Variation de la vélocité nette par rapport aux 3 Jours ouvrés précédents"
    )


def test_parametres_non_par_defaut() -> None:
    # Vélocité sur 4 JO (nets 1 0 1 1) : v = 3/4, précédents 1 0 1 0 → 1/2, variation 1/4 ;
    # t = ⌊3/(3/4)⌋ + 1 = 5 → 16/10. Fourchette : 6 derniers JO 1 0 1 0 1 1, fenêtres de 3 :
    # 2/3 1/3 2/3 2/3 ; P25 = 1/3 + 0,75·1/3 = 7/12 → t = ⌊36/7⌋ + 1 = 6 → 19/10 ;
    # P75 = 2/3 < v → optimiste = estimée. Horizon 9 : 1/3 (t = 10) échoue → 3/4.
    parametres = ParametresBaseline(
        fenetre_velocite=4, horizon=9, fenetre_fourchette=3, profondeur_fourchette=6
    )
    prevision = prevoir_sortie(_serie(PREMIERS + DERNIERS), _meteo(), parametres)

    assert prevision.horizon_jours_ouvres == 9
    assert prevision.date_sortie_estimee == date(2026, 10, 16)
    assert prevision.date_sortie_optimiste == date(2026, 10, 16)
    assert prevision.date_sortie_pessimiste == date(2026, 10, 19)
    assert (prevision.probabilite_numerateur, prevision.probabilite_denominateur) == (3, 4)
    assert _facteurs(prevision) == {
        "stock": (6, 1),
        "entrees": (4, 1),
        "sorties": (7, 1),
        "velocite_nette": (3, 4),
        "variation_velocite": (1, 4),
    }
    assert "4 derniers Jours ouvrés" in prevision.facteurs[1].libelle
    assert "4 Jours ouvrés précédents" in prevision.facteurs[4].libelle


def test_velocite_nulle() -> None:
    # Fenêtres : sommes 0 (10), 1, 2, 3 (4) → réussites 2 et 3 → 5/16.
    prevision = prevoir_sortie(_serie(PREMIERS + [0] * 10), _meteo())

    assert prevision.statut is StatutPrevision.pas_de_sortie_projetee
    assert prevision.date_sortie_estimee is None
    assert prevision.date_sortie_optimiste is None
    assert prevision.date_sortie_pessimiste is None
    assert (prevision.probabilite_numerateur, prevision.probabilite_denominateur) == (5, 16)
    assert _facteurs(prevision)["velocite_nette"] == (0, 1)
    assert _facteurs(prevision)["variation_velocite"] == (-3, 10)


def test_velocite_defavorable() -> None:
    prevision = prevoir_sortie(_serie([0] * 10 + [-1] * 10), _meteo())

    assert prevision.statut is StatutPrevision.pas_de_sortie_projetee
    assert prevision.date_sortie_estimee is None
    assert (prevision.probabilite_numerateur, prevision.probabilite_denominateur) == (0, 16)
    facteurs = _facteurs(prevision)
    assert (facteurs["entrees"], facteurs["sorties"]) == ((20, 1), (10, 1))
    assert facteurs["velocite_nette"] == (-1, 1)
    assert facteurs["variation_velocite"] == (-1, 1)


def test_regle_non_projetable() -> None:
    prevision = prevoir_sortie(_serie(PREMIERS + DERNIERS), _meteo(IND_1, IND_5))

    assert prevision.statut is StatutPrevision.regle_non_projetable
    assert prevision.regles_non_projetables == (CodeIndicateur.ind_5,)
    assert prevision.date_sortie_estimee is None
    assert (prevision.probabilite_numerateur, prevision.probabilite_denominateur) == (0, 1)
    assert _facteurs(prevision) == FACTEURS_REFERENCE


def test_rouge_par_ind_5_seul() -> None:
    prevision = prevoir_sortie(_serie(PREMIERS + DERNIERS), _meteo(IND_5))

    assert prevision.statut is StatutPrevision.regle_non_projetable
    assert prevision.regles_non_projetables == (CodeIndicateur.ind_5,)
    assert prevision.date_sortie_estimee is None
    assert (prevision.probabilite_numerateur, prevision.probabilite_denominateur) == (0, 1)
    assert _facteurs(prevision) == FACTEURS_REFERENCE


def test_regles_non_projetables_ordonnees_sans_doublon() -> None:
    ind_3 = _regle(CodeIndicateur.ind_3, 1, 1)
    prevision = prevoir_sortie(_serie(PREMIERS + DERNIERS), _meteo(IND_1, IND_5, ind_3, IND_5))

    assert prevision.regles_non_projetables == (CodeIndicateur.ind_5, CodeIndicateur.ind_3)


def test_historique_court() -> None:
    # 7 JO (01/10 → 09/10), nets 1 1 0 1 0 1 0 : v = 4/7, t = ⌊21/4⌋ + 1 = 6 → 19/10.
    # Fenêtres complètes : 3, 3, 2 ; P25 = 5/2 → w = 1/2, t = 7 → 20/10 ;
    # P75 = 3 → w = 3/5 ≥ v, t = 6 → 19/10. Probabilité 3/3 ; aucune fenêtre précédente.
    prevision = prevoir_sortie(_serie([1, 1, 0, 1, 0, 1, 0]), _meteo())

    assert prevision.statut is StatutPrevision.sortie_projetee
    assert prevision.date_sortie_estimee == date(2026, 10, 19)
    assert prevision.date_sortie_optimiste == date(2026, 10, 19)
    assert prevision.date_sortie_pessimiste == date(2026, 10, 20)
    assert (prevision.probabilite_numerateur, prevision.probabilite_denominateur) == (3, 3)
    facteurs = _facteurs(prevision)
    assert facteurs["velocite_nette"] == (4, 7)
    assert facteurs["entrees"] == (7, 1)
    assert facteurs["variation_velocite"] == (0, 1)
    assert "7 derniers Jours ouvrés" in prevision.facteurs[1].libelle
    assert prevision.facteurs[4].libelle == (
        "Variation de la vélocité nette (aucun Jour ouvré précédent)"
    )


def test_historique_sans_fenetre_complete() -> None:
    # 3 JO, net 1 : la fenêtre de vélocité (v = 1) est la fenêtre unique ; t = 4 → 15/10.
    prevision = prevoir_sortie(_serie([1, 1, 1]), _meteo())

    assert prevision.date_sortie_estimee == date(2026, 10, 15)
    assert prevision.date_sortie_optimiste == date(2026, 10, 15)
    assert prevision.date_sortie_pessimiste == date(2026, 10, 15)
    assert (prevision.probabilite_numerateur, prevision.probabilite_denominateur) == (1, 1)


def test_operateur_strict() -> None:
    # `> 3` : sortie dès que le stock vaut 3 ; v = 1 → t = ⌈3/1⌉ = 3 → mercredi 14/10.
    regle = _regle(CodeIndicateur.ind_1, 6, 3, operateur=Operateur.superieur)
    prevision = prevoir_sortie(_serie([1, 1, 1]), _meteo(regle))

    assert prevision.date_sortie_estimee == date(2026, 10, 14)


def test_operateur_strict_quotient_fractionnaire() -> None:
    # `> 3`, nets 1 1 0 : v = 2/3, (6 − 3)/(2/3) = 9/2 → t = ⌈9/2⌉ = 5 → vendredi 16/10.
    regle = _regle(CodeIndicateur.ind_1, 6, 3, operateur=Operateur.superieur)
    prevision = prevoir_sortie(_serie([1, 1, 0]), _meteo(regle))

    assert prevision.date_sortie_estimee == date(2026, 10, 16)


@pytest.mark.parametrize(
    ("stock", "operateur"),
    [(2, Operateur.superieur_ou_egal), (3, Operateur.superieur)],
)
def test_stock_ne_declenchant_plus_ind_1(stock: int, operateur: Operateur) -> None:
    regle = _regle(CodeIndicateur.ind_1, 6, 3, operateur=operateur)
    with pytest.raises(UsineErreur, match=rf"{ENTITE} : stock {stock} .* IND-1 rouge .* 3"):
        prevoir_sortie(_serie(DERNIERS, stock_final=stock), _meteo(regle))


def test_pessimiste_non_projetable() -> None:
    # JO 1-10 à 0 : sommes 0 (6), 1 1 2 2 3 2 3 2 3 3 ; P25 = 0 → pas de pessimiste ;
    # P75 = 2 + 0,25 = 9/4 → 9/20 < v → optimiste = estimée. Réussites 2 et 3 → 8/16.
    prevision = prevoir_sortie(_serie([0] * 10 + DERNIERS), _meteo())

    assert prevision.statut is StatutPrevision.sortie_projetee
    assert prevision.date_sortie_estimee == date(2026, 10, 19)
    assert prevision.date_sortie_optimiste == date(2026, 10, 19)
    assert prevision.date_sortie_pessimiste is None
    assert (prevision.probabilite_numerateur, prevision.probabilite_denominateur) == (8, 16)


def test_lignes_hors_entite_et_posterieures_ignorees() -> None:
    reference = _serie(PREMIERS + DERNIERS)
    autre = _serie([5] * 20, stock_final=40, entite="ENT-B")
    apres = _serie([-3, -3], stock_final=12, fin=date(2026, 10, 13))

    prevision = prevoir_sortie(pl.concat([apres, autre, reference]), _meteo())

    assert prevision == prevoir_sortie(reference, _meteo())


def _sans_ligne(serie: pl.DataFrame, jour: date) -> pl.DataFrame:
    return serie.filter(pl.col("date") != jour)


def _avec_ligne(serie: pl.DataFrame, jour: date) -> pl.DataFrame:
    ligne = serie.head(1).with_columns(pl.lit(jour).alias("date"))
    return pl.concat([serie, ligne])


@pytest.mark.parametrize(
    ("serie", "meteo", "cause"),
    [
        pytest.param(
            _serie(DERNIERS),
            _meteo(_regle(CodeIndicateur.ind_1, 6, 3, Couleur.orange), couleur=Couleur.orange),
            "rouge attendue",
            id="meteo-non-rouge",
        ),
        pytest.param(_sans_ligne(_serie(DERNIERS), D), _meteo(), "absente", id="d-absente"),
        pytest.param(_sans_ligne(_serie(DERNIERS), date(2026, 10, 5)), _meteo(), "trou", id="trou"),
        pytest.param(
            _avec_ligne(_serie(DERNIERS), date(2026, 10, 3)),
            _meteo(),
            "pas un Jour ouvré",
            id="non-ouvree",
        ),
        pytest.param(
            _avec_ligne(_serie(DERNIERS), date(2026, 10, 7)),
            _meteo(),
            "en double",
            id="doublon",
        ),
        pytest.param(_serie(DERNIERS).drop("sorties"), _meteo(), "sorties", id="schema-invalide"),
    ],
)
def test_entrees_invalides(serie: pl.DataFrame, meteo: MeteoEntite, cause: str) -> None:
    with pytest.raises(UsineErreur, match=cause) as erreur:
        prevoir_sortie(serie, meteo)
    assert ENTITE in str(erreur.value)


def test_serie_vide_pour_l_entite() -> None:
    with pytest.raises(UsineErreur, match=f"{ENTITE}.*absente"):
        prevoir_sortie(_serie(DERNIERS, entite="ENT-B"), _meteo())


@pytest.mark.parametrize(
    "nom", ["fenetre_velocite", "horizon", "fenetre_fourchette", "profondeur_fourchette"]
)
@pytest.mark.parametrize("valeur", [0, -1, 1.5, True])
def test_parametre_invalide(nom: str, valeur: object) -> None:
    with pytest.raises(UsineErreur, match=nom):
        ParametresBaseline(**{nom: valeur})  # type: ignore[arg-type]


def test_parametres_h7_par_defaut_et_geles() -> None:
    parametres = ParametresBaseline()
    assert (
        parametres.fenetre_velocite,
        parametres.horizon,
        parametres.fenetre_fourchette,
        parametres.profondeur_fourchette,
    ) == (10, 10, 5, 20)
    with pytest.raises(FrozenInstanceError):
        parametres.horizon = 5  # type: ignore[misc]


def test_parametres_transmis() -> None:
    # Horizon 5 : seules les fenêtres de somme 4 ou 5 (t = 4) réussissent → 4/16.
    prevision = prevoir_sortie(_serie(PREMIERS + DERNIERS), _meteo(), ParametresBaseline(horizon=5))
    assert prevision.horizon_jours_ouvres == 5
    assert (prevision.probabilite_numerateur, prevision.probabilite_denominateur) == (4, 16)


def test_deterministe_et_sans_mutation() -> None:
    serie = _serie(PREMIERS + DERNIERS)
    copie = serie.clone()

    premiere = prevoir_sortie(serie, _meteo())
    seconde = prevoir_sortie(serie, _meteo())

    assert premiere == seconde
    assert premiere.model_dump_json() == seconde.model_dump_json()
    assert serie.equals(copie)


def test_sans_horloge_ni_hasard() -> None:
    source = Path(baseline.__file__).read_text(encoding="utf-8")
    for interdit in ("now(", "today(", "random"):
        assert interdit not in source


def test_baseline_unique_ad_18() -> None:
    motif = re.compile(r"^\s*def\s+(prevoir_sortie|\w*baseline\w*)\s*\(", re.IGNORECASE)
    definitions = [
        f"{chemin.relative_to(RACINE).as_posix()}:{ligne.strip()}"
        for racine in (RACINE / "src", RACINE / "evaluation")
        for chemin in sorted(racine.rglob("*.py"))
        for ligne in chemin.read_text(encoding="utf-8").splitlines()
        if motif.match(ligne)
    ]
    assert definitions == ["src/usine/domaine/prevision/baseline.py:def prevoir_sortie("]
