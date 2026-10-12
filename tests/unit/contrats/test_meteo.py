"""Météo, Couleur ordonnée, Règles déclenchantes (FR-16, FR-17, FR-19)."""

from datetime import date

import pytest
from pydantic import ValidationError

from usine.contrats.meteo import (
    LIBELLES_COULEURS,
    CodeIndicateur,
    Couleur,
    EvolutionMeteo,
    MeteoEntite,
    Operateur,
    RegleDeclenchante,
)

D = date(2026, 10, 12)


def _regle(couleur: Couleur = Couleur.rouge, **champs: object) -> RegleDeclenchante:
    base: dict[str, object] = {
        "code": CodeIndicateur.ind_1,
        "couleur": couleur,
        "operateur": Operateur.superieur_ou_egal,
        "numerateur": 4,
        "denominateur": 1,
        "seuil_numerateur": 3,
        "seuil_denominateur": 1,
        "tickets_en_cause": ("DEMO-1", "DEMO-2"),
    }
    base.update(champs)
    return RegleDeclenchante.model_validate(base)


def test_couleurs_ordonnees_par_gravite() -> None:
    couleurs = [Couleur.rouge, Couleur.vert, Couleur.orange, Couleur.jaune]
    assert sorted(couleurs) == [Couleur.vert, Couleur.jaune, Couleur.orange, Couleur.rouge]
    assert max(couleurs) is Couleur.rouge
    assert min(couleurs) is Couleur.vert
    assert Couleur.jaune < Couleur.orange <= Couleur.orange
    assert Couleur.rouge > Couleur.orange >= Couleur.jaune


def test_comparaison_avec_un_texte_refusee() -> None:
    with pytest.raises(TypeError):
        _ = Couleur.vert < "jaune"
    with pytest.raises(TypeError):
        _ = Couleur.rouge >= "orange"


def test_egalite_de_texte_conservee() -> None:
    assert Couleur.rouge == "rouge"
    assert Couleur("orange") is Couleur.orange


def test_codes_indicateurs() -> None:
    assert [c.value for c in CodeIndicateur] == [f"IND-{n}" for n in range(1, 9)]


def test_meteo_rouge() -> None:
    meteo = MeteoEntite(
        date_arrete=D,
        entite="ENT-A",
        couleur=Couleur.rouge,
        regles=(_regle(),),
        version_grille="0123456789ab",
    )
    assert meteo.regles[0].tickets_en_cause == ("DEMO-1", "DEMO-2")


def test_meteo_verte_sans_regle() -> None:
    MeteoEntite(
        date_arrete=D,
        entite="ENT-A",
        couleur=Couleur.vert,
        regles=(),
        version_grille="0123456789ab",
    )


def test_vert_avec_regle_refuse() -> None:
    with pytest.raises(ValidationError):
        MeteoEntite(
            date_arrete=D,
            entite="ENT-A",
            couleur=Couleur.vert,
            regles=(_regle(),),
            version_grille="0123456789ab",
        )


def test_rouge_sans_regle_refuse() -> None:
    with pytest.raises(ValidationError):
        MeteoEntite(
            date_arrete=D,
            entite="ENT-A",
            couleur=Couleur.rouge,
            regles=(),
            version_grille="0123456789ab",
        )


def test_regle_d_une_autre_couleur_refusee() -> None:
    with pytest.raises(ValidationError):
        MeteoEntite(
            date_arrete=D,
            entite="ENT-A",
            couleur=Couleur.rouge,
            regles=(_regle(), _regle(Couleur.orange)),
            version_grille="0123456789ab",
        )


def test_regle_valeur_infinie_admise_non_evaluable_refusee() -> None:
    _regle(code=CodeIndicateur.ind_7, couleur=Couleur.orange, numerateur=5, denominateur=0)
    with pytest.raises(ValidationError):
        _regle(numerateur=0, denominateur=0)


def test_regle_verte_refusee() -> None:
    with pytest.raises(ValidationError):
        _regle(Couleur.vert)


def test_evolution_meteo() -> None:
    evolution = EvolutionMeteo(
        entite="ENT-A",
        date_arrete=D,
        couleur=Couleur.rouge,
        date_j1=date(2026, 10, 9),
        couleur_j1=Couleur.rouge,
        date_j5=date(2026, 10, 5),
        couleur_j5=Couleur.orange,
    )
    assert not evolution.change_depuis_j1
    assert evolution.change_depuis_j5


@pytest.mark.parametrize(
    ("operateur", "numerateur", "denominateur", "franchit"),
    [
        (Operateur.superieur_ou_egal, 3, 1, True),
        (Operateur.superieur_ou_egal, 2, 1, False),
        (Operateur.superieur, 3, 1, False),
        (Operateur.superieur, 7, 2, True),
        (Operateur.superieur, 1, 0, True),
    ],
)
def test_regle_franchit_son_seuil(
    operateur: Operateur, numerateur: int, denominateur: int, franchit: bool
) -> None:
    champs = {"operateur": operateur, "numerateur": numerateur, "denominateur": denominateur}
    if franchit:
        assert _regle(Couleur.rouge, **champs).franchit_le_seuil
    else:
        with pytest.raises(ValidationError, match="ne franchit pas"):
            _regle(Couleur.rouge, **champs)


def test_regle_seuil_fractionnaire() -> None:
    _regle(
        code=CodeIndicateur.ind_4,
        numerateur=4,
        denominateur=20,
        seuil_numerateur=1,
        seuil_denominateur=5,
    )
    with pytest.raises(ValidationError):
        _regle(
            code=CodeIndicateur.ind_4,
            numerateur=3,
            denominateur=20,
            seuil_numerateur=1,
            seuil_denominateur=5,
        )


def test_evolution_dates_j1_et_j5_du_calendrier() -> None:
    base: dict[str, object] = {
        "entite": "ENT-A",
        "date_arrete": D,
        "couleur": Couleur.rouge,
        "date_j1": date(2026, 10, 9),
        "couleur_j1": None,
        "date_j5": date(2026, 10, 5),
        "couleur_j5": None,
    }
    EvolutionMeteo.model_validate(base)
    with pytest.raises(ValidationError, match="J-1"):
        EvolutionMeteo.model_validate(base | {"date_j1": date(2026, 10, 8)})
    with pytest.raises(ValidationError, match="J-5"):
        EvolutionMeteo.model_validate(base | {"date_j5": date(2026, 10, 2)})


@pytest.mark.parametrize(
    ("date_j1", "date_j5"),
    [
        (date(2026, 10, 5), date(2026, 10, 9)),
        (D, date(2026, 10, 5)),
        (date(2026, 10, 9), date(2026, 10, 9)),
    ],
)
def test_evolution_dates_dans_l_ordre(date_j1: date, date_j5: date) -> None:
    with pytest.raises(ValidationError, match="J-5 < J-1"):
        EvolutionMeteo(
            entite="ENT-A",
            date_arrete=D,
            couleur=Couleur.rouge,
            date_j1=date_j1,
            couleur_j1=None,
            date_j5=date_j5,
            couleur_j5=None,
        )


def test_libelles_couleurs() -> None:
    assert [LIBELLES_COULEURS[c] for c in Couleur] == ["Vert", "Jaune", "Orange", "Rouge"]
    with pytest.raises(TypeError):
        LIBELLES_COULEURS[Couleur.vert] = "Verte"  # type: ignore[index]
