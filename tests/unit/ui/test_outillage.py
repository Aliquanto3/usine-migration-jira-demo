"""Fiche outillage : lecture sous la racine et garde anti-duplication du texte dans `ui/`."""

import re
from pathlib import Path

import pytest

from tests.unit.chaine.environnement import RACINE_DEPOT
from usine.ui import outillage
from usine.ui.navigation import Ecran
from usine.ui.outillage import FICHE_ABSENTE, FICHIER_FICHE, LEGENDE, lire_fiche

REPERTOIRE_UI = Path(outillage.__file__).parent
LONGUEUR_TRIVIALE = 20  # une ligne de 20 caractères ou moins n'est pas comptée
TITRE = re.compile(r"^#+\s+(.*)$")
ELEMENT_LISTE = re.compile(r"^(?:[-*+]|\d+\.)\s+(.*)$")
SEPARATEUR_TABLEAU = re.compile(r"^[|:\-\s]+$")
EMPHASE_SOULIGNEE = re.compile(r"(?<!\w)_(.+?)_(?!\w)")
EMPHASE_ETOILE = re.compile(r"(?<![\w*])\*(.+?)\*(?![\w*])")


def test_lire_fiche_presente(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    contenu = "# Titre\n\nTexte accentué : é, à, ç.\n"
    (tmp_path / FICHIER_FICHE).write_text(contenu, encoding="utf-8")
    assert lire_fiche(tmp_path) == contenu


def test_lire_fiche_avec_bom(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    contenu = "# Titre accentué\n"
    (tmp_path / FICHIER_FICHE).write_bytes(contenu.encode("utf-8-sig"))
    assert lire_fiche(tmp_path) == contenu  # pas de U+FEFF avant le premier titre


def test_lire_fiche_du_depot() -> None:
    fiche = (RACINE_DEPOT / FICHIER_FICHE).read_text(encoding="utf-8-sig")
    assert lire_fiche(RACINE_DEPOT) == fiche


def test_lire_fiche_absente(tmp_path: Path) -> None:
    assert lire_fiche(tmp_path) is None


def test_lire_fiche_non_utf8(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / FICHIER_FICHE).write_bytes(b"\xff\xfe\xfa illisible")
    with pytest.raises(UnicodeDecodeError):
        lire_fiche(tmp_path)


def test_lire_fiche_repertoire(tmp_path: Path) -> None:
    (tmp_path / FICHIER_FICHE).mkdir(parents=True)  # un répertoire à la place du fichier
    with pytest.raises(OSError):
        lire_fiche(tmp_path)


def test_messages() -> None:
    assert FICHIER_FICHE.as_posix() == "docs/fiche-outillage.md"
    assert "`docs/fiche-outillage.md`" in FICHE_ABSENTE
    assert "Story 8.1" in FICHE_ABSENTE
    assert LEGENDE == "Fiche `docs/fiche-outillage.md` (Story 8.1), affichée en lecture seule."


def _sans_marques(texte: str) -> str:
    """Texte sans emphase Markdown (`**`, `*`, `_` en bord de mot, code en ligne)."""
    texte = texte.replace("**", "").replace("`", "")
    texte = EMPHASE_SOULIGNEE.sub(r"\1", texte)
    texte = EMPHASE_ETOILE.sub(r"\1", texte)
    return texte.strip()


def _lignes_non_triviales(fiche: str) -> set[str]:
    """Unités de texte de la fiche de plus de 20 caractères, sans marques Markdown.

    Titres, éléments de liste, lignes de paragraphe et cellules de tableau, une par une. Le
    titre principal reprend le libellé de l'écran, fixé par la Story 7.1 (`Ecran.outillage`) :
    ce libellé de navigation n'est pas une copie de la fiche.
    """
    unites: set[str] = set()
    for brute in fiche.splitlines():
        ligne = brute.strip()
        if not ligne or SEPARATEUR_TABLEAU.match(ligne):
            continue
        if titre := TITRE.match(ligne):
            texte = _sans_marques(titre.group(1))
            if texte != Ecran.outillage.value:
                unites.add(texte)
        elif element := ELEMENT_LISTE.match(ligne):
            unites.add(_sans_marques(element.group(1)))
        elif ligne.startswith("|"):
            unites.update(_sans_marques(cellule) for cellule in ligne.strip("|").split("|"))
        else:
            unites.add(_sans_marques(ligne))
    return {unite for unite in unites if len(unite) > LONGUEUR_TRIVIALE}


def _fichiers_ui() -> list[Path]:
    """Fichiers texte de `ui/`, sous-répertoires compris, hors `__pycache__`."""
    fichiers: list[Path] = []
    for chemin in sorted(REPERTOIRE_UI.rglob("*")):
        if not chemin.is_file() or "__pycache__" in chemin.parts:
            continue
        octets = chemin.read_bytes()
        if b"\0" not in octets:  # fichier binaire ignoré
            fichiers.append(chemin)
    return fichiers


def test_aucun_texte_de_la_fiche_dans_ui() -> None:
    fiche = (RACINE_DEPOT / FICHIER_FICHE).read_text(encoding="utf-8-sig")
    unites = _lignes_non_triviales(fiche)
    assert len(unites) >= 10  # la garde porte bien sur la fiche réelle
    sources = _fichiers_ui()
    assert {"app.py", "outillage.py", "navigation.py"} <= {source.name for source in sources}
    for source in sources:
        texte = source.read_text(encoding="utf-8", errors="replace")
        copies = sorted(unite for unite in unites if unite in texte)
        assert copies == [], source.name
