"""Écrans de la démo : ordre de la navigation, écran par défaut et stories à venir."""

from usine.ui.navigation import (
    CLE_ECRAN,
    CLE_ENTITE,
    CLE_PALIER,
    CLE_REPLI,
    CLE_TICKET_APERCU,
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
        "Pseudonymisation",
        "Agent",
        "Ce qu'il faut pour le faire en vrai",
    ]
    assert ECRAN_PAR_DEFAUT is Ecran.carte
    assert libelles_ecrans()[0] == ECRAN_PAR_DEFAUT.value


def test_stories_a_venir() -> None:
    assert dict(STORY_A_VENIR) == {}
    assert Ecran.agent not in STORY_A_VENIR  # écran livré par la Story 7.9
    assert Ecran.detail not in STORY_A_VENIR  # écran livré par la Story 7.2
    assert Ecran.avant_apres not in STORY_A_VENIR  # écran livré par la Story 7.4
    assert Ecran.outillage not in STORY_A_VENIR  # écran livré par la Story 7.5
    assert Ecran.pseudonymisation not in STORY_A_VENIR  # écran livré par la Story 7.7


def test_cles_distinctes() -> None:
    cles = [CLE_ECRAN, CLE_ENTITE, CLE_REPLI, CLE_PALIER, CLE_TICKET_APERCU]
    assert len(set(cles)) == len(cles)


def test_ouvrir_detail() -> None:
    etat: dict[str, object] = {CLE_ECRAN: Ecran.carte.value}
    ouvrir_detail(etat, "ENT-B")
    assert etat == {CLE_ECRAN: Ecran.detail.value, CLE_ENTITE: "ENT-B"}
