from pathlib import Path

import pytest

from usine.config import cles_sans_commentaire

YAML_LIVRES = sorted((Path(__file__).resolve().parents[3] / "config").glob("*.yaml"))


def test_cle_commentee_au_dessus_ou_en_ligne() -> None:
    texte = "# Palier de la Chaîne.\npalier: 1\nmarge: 2  # Marge en jours.\n"
    assert cles_sans_commentaire(texte) == []


def test_cle_sans_commentaire_signalee() -> None:
    texte = (
        "# Palier.\npalier: 1\n\nmarge: 2\nseuils:\n  # Seuil rouge.\n  - rouge: 3\n    orange: 2\n"
    )
    assert cles_sans_commentaire(texte) == [(4, "marge"), (5, "seuils"), (8, "orange")]


def test_commentaire_vide_ne_compte_pas() -> None:
    assert cles_sans_commentaire("#\npalier: 1\n") == [(2, "palier")]


def test_au_moins_un_yaml_livre() -> None:
    assert YAML_LIVRES


@pytest.mark.parametrize("chemin", YAML_LIVRES, ids=lambda c: c.name)
def test_chaque_cle_des_yaml_livres_est_commentee(chemin: Path) -> None:
    """NFR-10 : chaque clé de configuration porte un commentaire en français."""
    assert cles_sans_commentaire(chemin.read_text(encoding="utf-8")) == []


def test_cles_entre_guillemets_et_numeriques() -> None:
    texte = "# Nom.\n\"nom complet\": a\n'seuil': 1\n12: douze\n"
    assert cles_sans_commentaire(texte) == [(3, "seuil"), (4, "12")]


def test_flow_mapping() -> None:
    assert cles_sans_commentaire("seuils: {rouge: 3, orange: 2}\n") == [
        (1, "seuils"),
        (1, "rouge"),
        (1, "orange"),
    ]
    assert cles_sans_commentaire("seuils: {rouge: 3, orange: 2}  # Seuils.\n") == []


def test_bom_en_tete() -> None:
    assert cles_sans_commentaire("\ufeff# Palier.\npalier: 1\n") == []
    assert cles_sans_commentaire("\ufeffpalier: 1\n") == [(1, "palier")]


def test_diese_dans_une_valeur_n_est_pas_un_commentaire() -> None:
    texte = 'nom: "a #b"\nlien: http://exemple.fr/page#ancre\n'
    assert cles_sans_commentaire(texte) == [(1, "nom"), (2, "lien")]


def test_liste_d_url_sans_cle() -> None:
    texte = "# Sources.\nsources:\n  - https://exemple.fr/a\n  - http://exemple.fr/b\n"
    assert cles_sans_commentaire(texte) == []


def test_bloc_litteral() -> None:
    texte = (
        "# Aide affichée.\naide: |\n  Note: ceci n'est pas une clé.\n  # ni un commentaire\n"
        "suite: 1\n"
    )
    assert cles_sans_commentaire(texte) == [(5, "suite")]


def test_commentaire_en_tete_de_bloc() -> None:
    assert cles_sans_commentaire("aide: |  # Aide affichée.\n  texte\n") == []


def test_cle_de_fusion_non_comptee() -> None:
    texte = "# Base.\nbase: &b\n  # Valeur.\n  valeur: 1\n# Copie.\ncopie:\n  <<: *b\n  autre: 2\n"
    assert cles_sans_commentaire(texte) == [(8, "autre")]
