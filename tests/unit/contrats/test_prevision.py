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


def test_contenu_previsions() -> None:
    contenu = ContenuPrevisions(previsions=(_prevision(),), risques=())
    assert ContenuPrevisions.model_validate_json(contenu.model_dump_json()) == contenu
