"""Gardes structurelles de l'entrepôt d'extraction (AD-6, AD-9).

- `duckdb` et `usine.adaptateurs.entrepot_duckdb` ne sont importés, dans `src/usine`, que par
  le paquet lui-même ou `composition.py` ;
- dans le paquet, seule `EtapeExtraction` construit un `EntrepotDuckDB` ;
- le SQL du paquet ne contient aucun agrégat (`SUM`, `AVG`, `COUNT`, `MIN`, `MAX`, `GROUP BY`).
"""

import ast
import re

import pytest

from tests.unit.adaptateurs.jira_http.outils import RACINE

SRC = RACINE / "src" / "usine"
PAQUET = SRC / "adaptateurs" / "entrepot_duckdb"
_MODULES_RESERVES = ("duckdb", "usine.adaptateurs.entrepot_duckdb")
_SQL = re.compile(r"\b(SELECT|INSERT|CREATE|UPDATE|DELETE)\b", re.IGNORECASE)
_AGREGAT = re.compile(r"\b(SUM|AVG|COUNT|MIN|MAX)\s*\(|\bGROUP\s+BY\b", re.IGNORECASE)


def _reserve(module: str) -> bool:
    return any(module == m or module.startswith(f"{m}.") for m in _MODULES_RESERVES)


def imports_reserves(source: str) -> list[str]:
    """Imports de `duckdb` ou du paquet de l'entrepôt trouvés dans `source`."""
    trouves: list[str] = []
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, ast.Import):
            trouves += [f"import {a.name}" for a in noeud.names if _reserve(a.name)]
        elif isinstance(noeud, ast.ImportFrom) and noeud.level == 0:
            module = noeud.module or ""
            if _reserve(module) or any(_reserve(f"{module}.{a.name}") for a in noeud.names):
                trouves.append(f"from {module} import …")
        elif isinstance(noeud, ast.Call):
            trouves += [
                f"argument {arg.value!r} (accès dynamique)"
                for arg in noeud.args
                if isinstance(arg, ast.Constant)
                and isinstance(arg.value, str)
                and _reserve(arg.value)
            ]
    return trouves


def constructions_hors_etape(source: str) -> list[str]:
    """Appels `EntrepotDuckDB(…)` hors de la classe `EtapeExtraction`."""
    trouves: list[str] = []

    def visiter(noeud: ast.AST, dans_etape: bool) -> None:
        if isinstance(noeud, ast.ClassDef):
            dans_etape = dans_etape or noeud.name == "EtapeExtraction"
        if isinstance(noeud, ast.Call) and not dans_etape:
            fonction = noeud.func
            nom = fonction.id if isinstance(fonction, ast.Name) else None
            if isinstance(fonction, ast.Attribute):
                nom = fonction.attr
            if nom == "EntrepotDuckDB":
                trouves.append(f"ligne {noeud.lineno}")
        for enfant in ast.iter_child_nodes(noeud):
            visiter(enfant, dans_etape)

    visiter(ast.parse(source), False)
    return trouves


def agregats_sql(source: str) -> list[str]:
    """Chaînes SQL de `source` qui contiennent un agrégat."""
    return [
        noeud.value
        for noeud in ast.walk(ast.parse(source))
        if isinstance(noeud, ast.Constant)
        and isinstance(noeud.value, str)
        and _SQL.search(noeud.value)
        and _AGREGAT.search(noeud.value)
    ]


def _fichiers_src() -> list[tuple[str, str]]:
    return [
        (f.relative_to(SRC).as_posix(), f.read_text(encoding="utf-8"))
        for f in sorted(SRC.rglob("*.py"))
    ]


def test_duckdb_et_entrepot_importes_dans_le_paquet_ou_la_composition_seulement() -> None:
    fautifs = {
        relatif: trouves
        for relatif, source in _fichiers_src()
        if not relatif.startswith("adaptateurs/entrepot_duckdb/")
        and relatif != "composition.py"
        and (trouves := imports_reserves(source))
    }
    assert fautifs == {}


def test_seule_l_etape_extraction_ouvre_l_entrepot() -> None:
    fautifs = {
        relatif: trouves
        for relatif, source in _fichiers_src()
        if relatif != "composition.py" and (trouves := constructions_hors_etape(source))
    }
    assert fautifs == {}


def test_sql_sans_agregat() -> None:
    fichiers = sorted(PAQUET.rglob("*.py"))
    assert fichiers
    fautifs = {
        f.name: trouves
        for f in fichiers
        if (trouves := agregats_sql(f.read_text(encoding="utf-8")))
    }
    assert fautifs == {}


@pytest.mark.parametrize(
    "source",
    [
        "import duckdb",
        "import duckdb.typing",
        "from duckdb import connect",
        "from usine.adaptateurs.entrepot_duckdb import EntrepotDuckDB",
        "from usine.adaptateurs.entrepot_duckdb.entrepot import EntrepotDuckDB",
        "from usine.adaptateurs import entrepot_duckdb",
        "import importlib\nimportlib.import_module('duckdb')",
    ],
)
def test_garde_detecte_les_imports_reserves(source: str) -> None:
    assert imports_reserves(source)


def test_garde_laisse_passer_les_autres_imports() -> None:
    assert imports_reserves("import polars as pl\nfrom usine.ports import Etape") == []


def test_garde_detecte_une_ouverture_hors_etape() -> None:
    source = (
        "class EtapeExtraction:\n"
        "    def executer(self):\n"
        "        return EntrepotDuckDB(self._chemin)\n"
        "def ailleurs(chemin):\n"
        "    return entrepot.EntrepotDuckDB(chemin)\n"
    )
    assert constructions_hors_etape(source) == ["ligne 5"]


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT count(*) FROM evenements",
        "SELECT MAX(rang) FROM evenements",
        "select sum (lot) from evenements",
        "SELECT cle_ticket FROM evenements GROUP BY cle_ticket",
    ],
)
def test_garde_detecte_un_agregat(sql: str) -> None:
    assert agregats_sql(f"REQUETE = {sql!r}")


def test_garde_ignore_le_texte_non_sql() -> None:
    assert agregats_sql('"""Marge en minutes, au min (1) ; max(…) ailleurs."""') == []
