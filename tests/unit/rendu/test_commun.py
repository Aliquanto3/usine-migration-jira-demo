"""Formatage partagé du rendu : mesures, seuils, Prévisions, Risques, libellés (Story 5.3)."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from tests.unit.rendu.conftest import GRILLE
from usine.contrats.meteo import CodeIndicateur
from usine.contrats.prevision import (
    FacteurExplicatif,
    MethodePrevision,
    Prevision,
    RisqueEntreeRouge,
    StatutPrevision,
)
from usine.domaine.kpi import CODES_TENDANCE
from usine.rendu.commun import (
    LIBELLES_KPI,
    NatureMesure,
    formater_horodatage,
    formater_jours_ouvres,
    formater_kpi,
    formater_mesure,
    formater_prevision,
    formater_risque,
    formater_seuils,
    libelle_kpi,
    libelle_perimetre,
)

D = date(2026, 10, 9)
NBSP = " "


def test_libelles_kpi_couvrent_le_domaine() -> None:
    """Les libellés recopiés dans `rendu` couvrent chaque code de KPI et de Tendance."""
    assert set(CODES_TENDANCE) <= set(LIBELLES_KPI)
    assert libelle_kpi("code_inconnu") == "code_inconnu"
    assert libelle_perimetre("PROGRAMME") == "Programme"
    assert libelle_perimetre("ENT-A") == "ENT-A"


@pytest.mark.parametrize(
    ("numerateur", "denominateur", "nature", "attendu"),
    [
        (1234, 1, NatureMesure.compte, f"1{NBSP}234"),
        (5, 2, NatureMesure.age, "2,5"),
        (1, 8, NatureMesure.taux, f"12,5{NBSP}%"),
        (0, 0, NatureMesure.taux, "sans objet"),
        (3, 0, NatureMesure.compte, "∞"),
        (-1, 20, NatureMesure.taux, f"-5{NBSP}%"),
    ],
)
def test_formater_mesure(
    numerateur: int, denominateur: int, nature: NatureMesure, attendu: str
) -> None:
    assert formater_mesure(numerateur, denominateur, nature) == attendu


def test_formater_kpi() -> None:
    assert formater_kpi("taux_ko_cas_de_test", 1, 4) == f"25{NBSP}%"
    assert formater_kpi("anomalies_ouvertes", 12, 1) == "12"
    assert formater_kpi("age_median_anomalies_ouvertes", 15, 2) == "7,5"
    assert formater_kpi("inconnu", 3, 1) == "3"


def test_formater_seuils() -> None:
    assert formater_seuils(GRILLE, CodeIndicateur.ind_1) == "Orange ≥ 1 ; Rouge ≥ 3"
    assert formater_seuils(GRILLE, CodeIndicateur.ind_4) == (
        f"Jaune ≥ 5{NBSP}% ; Orange ≥ 10{NBSP}% ; Rouge ≥ 20{NBSP}%"
    )
    assert formater_seuils(GRILLE, CodeIndicateur.ind_7) == "Jaune > 1 ; Orange > 1,5"
    assert formater_seuils(None, CodeIndicateur.ind_1) == ""


def test_formater_horodatage() -> None:
    paris = timezone(timedelta(hours=2))
    assert formater_horodatage(datetime(2026, 10, 12, 9, 30, tzinfo=paris)) == (
        "12/10/2026 07:30:00 UTC"
    )
    assert formater_horodatage(datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)) == (
        "02/01/2026 03:04:05 UTC"
    )


def test_formater_jours_ouvres() -> None:
    assert formater_jours_ouvres(1) == "1 Jour ouvré"
    assert formater_jours_ouvres(10) == "10 Jours ouvrés"


def _prevision(**champs: object) -> Prevision:
    base: dict[str, object] = {
        "date_arrete": D,
        "entite": "ENT-A",
        "methode": MethodePrevision.baseline,
        "statut": StatutPrevision.sortie_projetee,
        "date_sortie_estimee": date(2026, 10, 19),
        "date_sortie_optimiste": date(2026, 10, 16),
        "date_sortie_pessimiste": date(2026, 11, 9),
        "probabilite_numerateur": 11,
        "probabilite_denominateur": 16,
        "horizon_jours_ouvres": 10,
        "facteurs": (
            FacteurExplicatif(nom="stock", libelle="Stock", numerateur=6, denominateur=1),
        ),
        "version_grille": "grille",
    }
    return Prevision.model_validate(base | champs)


@pytest.mark.parametrize(
    ("champs", "attendu"),
    [
        (
            {},
            "Sortie du rouge estimée le 19/10/2026 (fourchette 16/10/2026 – 09/11/2026),"
            f" probabilité 68,8{NBSP}% sous 10 Jours ouvrés",
        ),
        (
            {"date_sortie_pessimiste": None},
            "Sortie du rouge estimée le 19/10/2026 (fourchette 16/10/2026 – non bornée),"
            f" probabilité 68,8{NBSP}% sous 10 Jours ouvrés",
        ),
        (
            {
                "statut": StatutPrevision.pas_de_sortie_projetee,
                "date_sortie_estimee": None,
                "date_sortie_optimiste": None,
                "date_sortie_pessimiste": None,
                "probabilite_numerateur": 0,
                "probabilite_denominateur": 1,
            },
            f"Pas de sortie du rouge projetée (probabilité 0{NBSP}% sous 10 Jours ouvrés)",
        ),
        (
            {
                "statut": StatutPrevision.regle_non_projetable,
                "date_sortie_estimee": None,
                "date_sortie_optimiste": None,
                "date_sortie_pessimiste": None,
                "probabilite_numerateur": 0,
                "probabilite_denominateur": 1,
                "regles_non_projetables": (CodeIndicateur.ind_2, CodeIndicateur.ind_5),
            },
            "Sortie du rouge non projetable (règle IND-2, IND-5)",
        ),
    ],
    ids=["projetee", "pessimiste_non_bornee", "pas_de_sortie", "non_projetable"],
)
def test_formater_prevision(champs: dict[str, object], attendu: str) -> None:
    assert formater_prevision(_prevision(**champs)) == attendu


def test_formater_risque() -> None:
    risque = RisqueEntreeRouge(
        date_arrete=D,
        entite="ENT-C",
        indicateur=CodeIndicateur.ind_1,
        date_franchissement_estimee=date(2026, 10, 15),
        horizon_jours_ouvres=5,
        numerateur=2,
        denominateur=1,
        seuil_numerateur=3,
        seuil_denominateur=1,
        version_grille="grille",
    )
    assert formater_risque(risque) == (
        "Risque d'entrée en rouge IND-1 : franchissement estimé le 15/10/2026 (valeur 2,"
        " seuil rouge 3, horizon 5 Jours ouvrés)"
    )
