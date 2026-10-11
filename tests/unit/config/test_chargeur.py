from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel

from usine.config import MODELES, charger, charger_yaml
from usine.config.chargeur import _ChargeurSansDoublon
from usine.contrats.config import ConfigChaine
from usine.contrats.erreurs import UsineErreur


class _Seuil(BaseModel):
    valeur: int


class _Grille(BaseModel):
    seuils: list[_Seuil]


def _ecrire(tmp_path: Path, texte: str, nom: str = "chaine.yaml") -> Path:
    chemin = tmp_path / nom
    chemin.write_text(texte, encoding="utf-8")
    return chemin


def test_charge_une_configuration_valide(tmp_path: Path) -> None:
    chemin = _ecrire(tmp_path, "# Palier.\npalier: 2\n")
    assert charger_yaml(chemin, ConfigChaine) == ConfigChaine(palier=2)


def test_type_errone_nomme_fichier_cle_et_valeur(tmp_path: Path) -> None:
    chemin = _ecrire(tmp_path, "palier: trois\n")
    with pytest.raises(UsineErreur) as erreur:
        charger_yaml(chemin, ConfigChaine)
    message = str(erreur.value)
    assert str(chemin) in message
    assert "« palier »" in message
    assert "'trois'" in message


def test_cle_imbriquee_nommee_par_son_chemin(tmp_path: Path) -> None:
    chemin = _ecrire(tmp_path, "seuils:\n  - valeur: 3\n  - valeur: beaucoup\n", "grille.yaml")
    with pytest.raises(UsineErreur, match=r"« seuils\[1\]\.valeur ».*'beaucoup'"):
        charger_yaml(chemin, _Grille)


def test_fichier_absent(tmp_path: Path) -> None:
    with pytest.raises(UsineErreur, match="introuvable"):
        charger_yaml(tmp_path / "absent.yaml", ConfigChaine)


def test_yaml_illisible(tmp_path: Path) -> None:
    chemin = _ecrire(tmp_path, "palier: [1\n")
    with pytest.raises(UsineErreur, match="YAML illisible"):
        charger_yaml(chemin, ConfigChaine)


def test_cle_inconnue_refusee(tmp_path: Path) -> None:
    chemin = _ecrire(tmp_path, "palier: 1\npallier: 2\n")
    with pytest.raises(UsineErreur, match="« pallier »"):
        charger_yaml(chemin, ConfigChaine)


def test_charger_par_nom(racine_depot: Path) -> None:
    assert isinstance(charger("chaine", racine_depot / "config"), ConfigChaine)


def test_charger_nom_inconnu(racine_depot: Path) -> None:
    with pytest.raises(UsineErreur, match="inconnue"):
        charger("meteo", racine_depot / "config")


@pytest.mark.parametrize("nom", sorted(MODELES))
def test_les_yaml_livres_se_chargent(racine_depot: Path, nom: str) -> None:
    charger(nom, racine_depot / "config")


@pytest.mark.parametrize(
    ("texte", "valeur"), [("palier: true\n", "True"), ("palier: 2.0\n", "2.0")]
)
def test_type_strict(tmp_path: Path, texte: str, valeur: str) -> None:
    chemin = _ecrire(tmp_path, texte)
    with pytest.raises(UsineErreur) as erreur:
        charger_yaml(chemin, ConfigChaine)
    message = str(erreur.value)
    assert str(chemin) in message
    assert "« palier »" in message
    assert f"valeur {valeur} refusée" in message


def test_fichier_non_utf8(tmp_path: Path) -> None:
    chemin = tmp_path / "chaine.yaml"
    chemin.write_bytes("# Été.\npalier: 1\n".encode("cp1252"))
    with pytest.raises(UsineErreur, match="UTF-8") as erreur:
        charger_yaml(chemin, ConfigChaine)
    assert str(chemin) in str(erreur.value)


def test_repertoire_a_la_place_du_fichier(tmp_path: Path) -> None:
    chemin = tmp_path / "chaine.yaml"
    chemin.mkdir()
    with pytest.raises(UsineErreur, match="illisible") as erreur:
        charger_yaml(chemin, ConfigChaine)
    assert str(chemin) in str(erreur.value)


def test_cle_dupliquee(tmp_path: Path) -> None:
    chemin = _ecrire(tmp_path, "# Palier.\npalier: 1\n# Encore.\npalier: 1\n")
    with pytest.raises(UsineErreur) as erreur:
        charger_yaml(chemin, ConfigChaine)
    message = str(erreur.value)
    assert str(chemin) in message
    assert "« palier » dupliquée" in message
    assert "ligne 4" in message


def test_cle_dupliquee_imbriquee(tmp_path: Path) -> None:
    chemin = _ecrire(tmp_path, "seuils:\n  - valeur: 1\n    valeur: 2\n", "grille.yaml")
    with pytest.raises(UsineErreur, match=r"« valeur » dupliquée \(ligne 3\)"):
        charger_yaml(chemin, _Grille)


def test_fusion_yaml_acceptee(tmp_path: Path) -> None:
    texte = "base: &b\n  valeur: 1\nseuils:\n  - <<: *b\n    valeur: 2\n"
    chemin = _ecrire(tmp_path, texte, "grille.yaml")

    class _AvecBase(_Grille):
        base: _Seuil

    assert charger_yaml(chemin, _AvecBase).seuils[0].valeur == 2


def test_cle_valeur_yaml_acceptee(tmp_path: Path) -> None:
    chemin = _ecrire(tmp_path, "palier:\n  =: 1\n")
    texte = chemin.read_text(encoding="utf-8")
    assert yaml.load(texte, Loader=_ChargeurSansDoublon) == yaml.safe_load(texte)
