"""Prévisions et Risques d'entrée en rouge (FR-20, FR-21)."""

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from usine.contrats.meteo import CodeIndicateur
from usine.contrats.prevision import (
    ContenuPrevisions,
    FacteurExplicatif,
    MethodePrevision,
    Prevision,
    RisqueEntreeRouge,
    StatutPrevision,
)

D = date(2026, 10, 12)


def _prevision(**champs: Any) -> Prevision:
    base: dict[str, Any] = {
        "date_arrete": D,
        "entite": "ENT-A",
        "methode": MethodePrevision.baseline,
        "statut": StatutPrevision.sortie_projetee,
        "date_sortie_estimee": date(2026, 10, 20),
        "probabilite_numerateur": 3,
        "probabilite_denominateur": 4,
        "horizon_jours_ouvres": 10,
        "facteurs": (
            FacteurExplicatif(nom="stock", libelle="Stock", numerateur=4, denominateur=1),
        ),
        "version_grille": "0123456789ab",
    }
    base.update(champs)
    return Prevision.model_validate(base)


def test_prevision_projetee() -> None:
    assert _prevision().date_sortie_estimee == date(2026, 10, 20)


def test_pas_de_sortie_sans_date() -> None:
    _prevision(statut=StatutPrevision.pas_de_sortie_projetee, date_sortie_estimee=None)
    with pytest.raises(ValidationError):
        _prevision(statut=StatutPrevision.pas_de_sortie_projetee)


def test_regle_non_projetable_nommee() -> None:
    _prevision(
        statut=StatutPrevision.regle_non_projetable,
        date_sortie_estimee=None,
        regles_non_projetables=(CodeIndicateur.ind_4,),
    )
    with pytest.raises(ValidationError):
        _prevision(statut=StatutPrevision.regle_non_projetable, date_sortie_estimee=None)


def test_probabilite_bornee() -> None:
    with pytest.raises(ValidationError):
        _prevision(probabilite_numerateur=5)


def test_risque_entree_rouge() -> None:
    risque = RisqueEntreeRouge(
        date_arrete=D,
        entite="ENT-C",
        indicateur=CodeIndicateur.ind_4,
        date_franchissement_estimee=date(2026, 10, 15),
        horizon_jours_ouvres=5,
        numerateur=3,
        denominateur=20,
        seuil_numerateur=1,
        seuil_denominateur=5,
        version_grille="0123456789ab",
    )
    with pytest.raises(ValidationError):
        RisqueEntreeRouge.model_validate(risque.model_dump() | {"indicateur": "IND-2"})
    with pytest.raises(ValidationError):
        RisqueEntreeRouge.model_validate(risque.model_dump() | {"date_franchissement_estimee": D})


def test_sortie_projetee_exige_une_date() -> None:
    with pytest.raises(ValidationError, match="si et seulement si"):
        _prevision(date_sortie_estimee=None)


def test_regles_non_projetables_exigent_le_statut() -> None:
    with pytest.raises(ValidationError, match="regle_non_projetable"):
        _prevision(regles_non_projetables=(CodeIndicateur.ind_4,))


def test_fourchette_ordonnee() -> None:
    prevision = _prevision(
        date_sortie_optimiste=date(2026, 10, 16),
        date_sortie_pessimiste=date(2026, 10, 27),
    )
    assert prevision.date_sortie_optimiste == date(2026, 10, 16)
    _prevision(date_sortie_optimiste=date(2026, 10, 20), date_sortie_pessimiste=date(2026, 10, 20))
    with pytest.raises(ValidationError, match="optimiste ≤ estimée ≤ pessimiste"):
        _prevision(date_sortie_optimiste=date(2026, 10, 21))
    with pytest.raises(ValidationError, match="optimiste ≤ estimée ≤ pessimiste"):
        _prevision(date_sortie_pessimiste=date(2026, 10, 19))


@pytest.mark.parametrize(
    "dates",
    [
        {"date_sortie_estimee": D},
        {"date_sortie_estimee": date(2026, 10, 9)},
        {"date_sortie_optimiste": D},
    ],
)
def test_dates_de_sortie_posterieures_a_la_date_d_arrete(dates: dict[str, date]) -> None:
    with pytest.raises(ValidationError, match="postérieure"):
        _prevision(**dates)


def test_fourchette_sans_sortie_projetee_refusee() -> None:
    for champ in ("date_sortie_optimiste", "date_sortie_pessimiste"):
        with pytest.raises(ValidationError, match="fourchette"):
            _prevision(
                statut=StatutPrevision.pas_de_sortie_projetee,
                date_sortie_estimee=None,
                **{champ: date(2026, 10, 20)},
            )


def _risque(**champs: Any) -> RisqueEntreeRouge:
    base: dict[str, Any] = {
        "date_arrete": D,
        "entite": "ENT-C",
        "indicateur": CodeIndicateur.ind_4,
        "date_franchissement_estimee": date(2026, 10, 15),
        "horizon_jours_ouvres": 5,
        "numerateur": 3,
        "denominateur": 20,
        "seuil_numerateur": 1,
        "seuil_denominateur": 5,
        "version_grille": "0123456789ab",
    }
    base.update(champs)
    return RisqueEntreeRouge.model_validate(base)


def test_valeur_projetee_absente_par_defaut() -> None:
    risque = _risque()
    assert (risque.valeur_projetee_numerateur, risque.valeur_projetee_denominateur) == (None, None)


def test_valeur_projetee_aller_retour_json() -> None:
    risque = _risque(valeur_projetee_numerateur=5, valeur_projetee_denominateur=24)
    relu = RisqueEntreeRouge.model_validate_json(risque.model_dump_json())
    assert relu == risque
    assert (relu.valeur_projetee_numerateur, relu.valeur_projetee_denominateur) == (5, 24)
    contenu = ContenuPrevisions(previsions=(), risques=(risque,))
    assert ContenuPrevisions.model_validate_json(contenu.model_dump_json()) == contenu


def test_valeur_projetee_absente_omise_du_json() -> None:
    """Sans valeur projetée, la forme JSON reste celle de 1.0.0 : clés omises."""
    risque = _risque()
    cles = ("valeur_projetee_numerateur", "valeur_projetee_denominateur")
    texte = risque.model_dump_json()
    assert all(cle not in texte for cle in cles)
    assert all(cle not in risque.model_dump() for cle in cles)
    contenu = ContenuPrevisions(previsions=(), risques=(risque,))
    assert all(cle not in contenu.model_dump_json() for cle in cles)
    assert RisqueEntreeRouge.model_validate_json(texte) == risque


def test_valeur_projetee_renseignee_serialisee() -> None:
    risque = _risque(valeur_projetee_numerateur=5, valeur_projetee_denominateur=24)
    donnees = risque.model_dump()
    assert (donnees["valeur_projetee_numerateur"], donnees["valeur_projetee_denominateur"]) == (
        5,
        24,
    )
    texte = risque.model_dump_json()
    assert '"valeur_projetee_numerateur":5' in texte
    assert '"valeur_projetee_denominateur":24' in texte
    assert RisqueEntreeRouge.model_validate(donnees) == risque
    assert RisqueEntreeRouge.model_validate_json(texte) == risque


def test_risque_v1_0_lu() -> None:
    """Un Risque écrit en contrats 1.0.0 (sans valeur projetée) se lit toujours."""
    texte = (
        '{"date_arrete": "2026-10-12", "entite": "ENT-C", "indicateur": "IND-4",'
        ' "date_franchissement_estimee": "2026-10-15", "horizon_jours_ouvres": 5,'
        ' "numerateur": 3, "denominateur": 20, "seuil_numerateur": 1,'
        ' "seuil_denominateur": 5, "version_grille": "0123456789ab"}'
    )
    risque = RisqueEntreeRouge.model_validate_json(texte)
    assert risque == _risque()
    assert risque.valeur_projetee_numerateur is None
    assert risque.valeur_projetee_denominateur is None


@pytest.mark.parametrize(
    "valeur",
    [
        {"valeur_projetee_numerateur": 5},
        {"valeur_projetee_denominateur": 24},
        {"valeur_projetee_numerateur": 5, "valeur_projetee_denominateur": 0},
        {"valeur_projetee_numerateur": 5, "valeur_projetee_denominateur": -24},
    ],
    ids=["numerateur_seul", "denominateur_seul", "denominateur_nul", "denominateur_negatif"],
)
def test_valeur_projetee_incomplete_ou_invalide(valeur: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        _risque(**valeur)


def test_contenu_previsions() -> None:
    contenu = ContenuPrevisions(previsions=(_prevision(),), risques=())
    assert ContenuPrevisions.model_validate_json(contenu.model_dump_json()) == contenu
