"""Écrans de la démo : ordre de la navigation, écran par défaut et stories à venir."""

from usine.ui.navigation import (
    CLE_ECRAN,
    CLE_ENTITE,
    ECRAN_PAR_DEFAUT,
    STORY_A_VENIR,
    Ecran,
    libelles_ecrans,
    ouvrir_detail,
)


def test_ordre_et_defaut() -> None:
    assert libelles_ecrans() == [
        "Carte météo",
        "Détail d'une Entité",
        "Lancement de la Chaîne",
        "Avant / après",
        "Agent",
        "Ce qu'il faut pour le faire en vrai",
    ]
    assert ECRAN_PAR_DEFAUT is Ecran.carte
    assert libelles_ecrans()[0] == ECRAN_PAR_DEFAUT.value


def test_stories_a_venir() -> None:
    assert dict(STORY_A_VENIR) == {
        Ecran.detail: "7.2",
        Ecran.avant_apres: "7.4",
        Ecran.outillage: "7.5",
        Ecran.agent: "7.9",
    }


def test_ouvrir_detail() -> None:
    etat: dict[str, object] = {CLE_ECRAN: Ecran.carte.value}
    ouvrir_detail(etat, "ENT-B")
    assert etat == {CLE_ECRAN: Ecran.detail.value, CLE_ENTITE: "ENT-B"}
