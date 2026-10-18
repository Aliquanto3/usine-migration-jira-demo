"""Écrans de la démo : ordre de la navigation, écran par défaut et stories à venir."""

from usine.ui.navigation import (
    ECRAN_PAR_DEFAUT,
    STORY_A_VENIR,
    Ecran,
)


def test_ordre_et_defaut() -> None:
    assert [ecran.value for ecran in Ecran] == [
        "Carte météo",
        "Détail d'une Entité",
        "Lancement de la Chaîne",
        "Avant / après",
        "Pseudonymisation",
        "Agent",
        "Ce qu'il faut pour le faire en vrai",
    ]
    assert ECRAN_PAR_DEFAUT is Ecran.carte
    assert next(iter(Ecran)) is ECRAN_PAR_DEFAUT


def test_stories_a_venir() -> None:
    assert dict(STORY_A_VENIR) == {}
    assert Ecran.agent not in STORY_A_VENIR  # écran livré par la Story 7.9
    assert Ecran.detail not in STORY_A_VENIR  # écran livré par la Story 7.2
    assert Ecran.avant_apres not in STORY_A_VENIR  # écran livré par la Story 7.4
    assert Ecran.outillage not in STORY_A_VENIR  # écran livré par la Story 7.5
    assert Ecran.pseudonymisation not in STORY_A_VENIR  # écran livré par la Story 7.7
