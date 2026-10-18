"""Bornes de la fiche « outillage demandé » (Story 8.1, FR-47, NFR-8)."""

import re
from pathlib import Path

import pytest

FICHE = Path(__file__).resolve().parents[3] / "docs" / "fiche-outillage.md"
MOTS_MAX = 750  # 700 avant le texte Flask de la ligne UI (SCP 2026-10-17, § 4.5)
BRIQUES = (
    "Extraction Jira",
    "KPI, météo",
    "Prévision ML",
    "LLM",
    "Excel / PPT",
    "Agent conversationnel",
    "Planification",
    "UI de démo (FastAPI + HTML statique)",
)
CIBLES = ("VM Python", "Dataiku", "Power Platform", "Poste seul")
REFERENCES = ("AD-1", "AD-19", "NFR-8")
ENTETE = (
    "| Brique | Serveur / VM Python | Dataiku | Power Platform | Poste local seul "
    "| Appui dans le dépôt |"
)


@pytest.fixture(scope="module")
def texte() -> str:
    return FICHE.read_text(encoding="utf-8")


def _section(texte: str, titre: str) -> str:
    morceaux = re.split(r"^## ", texte, flags=re.MULTILINE)
    for morceau in morceaux:
        if morceau.partition("\n")[0].strip() == titre:
            return morceau
    pytest.fail(f"section « {titre} » absente de la fiche")


def test_tient_en_une_page(texte: str) -> None:
    mots = len(re.findall(r"\w+", texte))
    assert mots <= MOTS_MAX, f"la fiche compte {mots} mots, au-delà de {MOTS_MAX}"


def test_quatre_demandes_numerotees(texte: str) -> None:
    demandes = _section(texte, "Demandes, par ordre de priorité")
    numeros = re.findall(r"^(\d+)\. ", demandes, flags=re.MULTILINE)
    assert numeros == ["1", "2", "3", "4"], f"demandes numérotées trouvées : {numeros}"


@pytest.mark.parametrize("brique", BRIQUES)
def test_brique_presente(texte: str, brique: str) -> None:
    tableau = _section(texte, "Correspondance par brique")
    lignes = [ligne for ligne in tableau.splitlines() if ligne.startswith(f"| {brique} |")]
    assert lignes, f"brique absente du tableau : {brique}"
    cellules = [cellule.strip() for cellule in lignes[0].strip().strip("|").split("|")]
    assert len(cellules) == 6 and all(cellules), f"ligne {brique} : 6 cellules non vides attendues"
    assert re.search(r"\b(AD-1|AD-19|NFR-8)\b", cellules[-1]), f"ligne {brique} : appui sans règle"


def test_entete_du_tableau(texte: str) -> None:
    tableau = _section(texte, "Correspondance par brique")
    assert ENTETE in tableau.splitlines(), "en-tête du tableau par brique modifié"


@pytest.mark.parametrize("cible", CIBLES)
def test_cible_presente(texte: str, cible: str) -> None:
    attention = _section(texte, "Points d'attention par cible")
    assert f"### {cible}\n" in attention, f"cible absente des points d'attention : {cible}"


@pytest.mark.parametrize("reference", REFERENCES)
def test_reference_citee(texte: str, reference: str) -> None:
    assert re.search(rf"\b{reference}\b", texte), f"référence absente de la fiche : {reference}"
