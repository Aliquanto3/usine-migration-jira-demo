"""Gardes structurelles de l'injecteur (Story 1.6, AD-4, AD-5).

- seul `generateur/injecteur/cli.py` lit `jira_token_injection` et construit le client
  d'écriture ; `composition.py` ne lit jamais la variable ;
- le cœur (`plan`, `site`, `injection`) n'importe, du démonstrateur, que `contrats` (et ses
  modules frères), ni `httpx`, ni horloge, ni attente ;
- aucun import CSV ou JSON : ni module `csv`, ni point d'accès d'import.
"""

import ast
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[4]
SRC = RACINE / "src" / "usine"
INJECTEUR = SRC / "generateur" / "injecteur"
COEUR = ("plan.py", "site.py", "injection.py")


def _sources() -> dict[str, str]:
    return {
        fichier.relative_to(SRC).as_posix(): fichier.read_text(encoding="utf-8")
        for fichier in sorted(SRC.rglob("*.py"))
    }


def test_seul_l_injecteur_lit_le_jeton_d_injection() -> None:
    lecteurs = {chemin for chemin, texte in _sources().items() if "jira_token_injection" in texte}
    assert lecteurs == {"config/secrets.py", "generateur/injecteur/cli.py"}
    composition = (SRC / "composition.py").read_text(encoding="utf-8")
    assert "jira_token_injection" not in composition.lower()


def test_seul_l_injecteur_construit_le_client_d_ecriture() -> None:
    appelants = set()
    for chemin, texte in _sources().items():
        if chemin.startswith("adaptateurs/jira_http/"):
            continue
        for noeud in ast.walk(ast.parse(texte)):
            if isinstance(noeud, ast.Call):
                fonction = noeud.func
                nom = fonction.id if isinstance(fonction, ast.Name) else None
                if isinstance(fonction, ast.Attribute):
                    nom = fonction.attr
                if nom == "construire_client_ecriture":
                    appelants.add(chemin)
    assert appelants == {"generateur/injecteur/cli.py"}


def _imports(fichier: Path) -> set[str]:
    modules: set[str] = set()
    for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
        if isinstance(noeud, ast.Import):
            modules.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            assert noeud.level == 0, f"{fichier.name} : import relatif"
            modules.add(noeud.module or "")
    return modules


def test_le_coeur_n_importe_que_contrats() -> None:
    permis = re.compile(
        r"(usine\.contrats(\..+)?|usine\.generateur\.injecteur\.(plan|site|injection)"
        r"|collections(\.abc)?|dataclasses|datetime|types|typing|uuid|pydantic)"
    )
    for nom in COEUR:
        hors = sorted(m for m in _imports(INJECTEUR / nom) if not permis.fullmatch(m))
        assert hors == [], nom


def test_le_paquet_n_importe_pas_sa_composition() -> None:
    assert not any("cli" in m for m in _imports(INJECTEUR / "__init__.py"))


def test_aucun_import_csv_ni_point_d_acces_d_import() -> None:
    for fichier in sorted(INJECTEUR.glob("*.py")):
        texte = fichier.read_text(encoding="utf-8")
        assert "csv" not in _imports(fichier), fichier.name
        assert not re.search(r"/(import|bulk)\b", texte), fichier.name
