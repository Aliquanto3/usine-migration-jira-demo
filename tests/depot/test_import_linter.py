"""Non-régression des contrats d'import : chaque interdit fait échouer `lint-imports`."""

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

RACINE = Path(__file__).resolve().parents[2]
RACINES_HORS_PRODUIT = ("evaluation", "evals", "outils")

PYPROJECT = tomllib.loads((RACINE / "pyproject.toml").read_text(encoding="utf-8"))
NOM_ISOLATION_LLM = "pydantic_ai, anthropic, mistralai : adaptateurs/llm seulement"
"""Contrat transverse d'AD-12 (source `usine` entier), hors du tableau des couches."""
CONTRATS_INTERDITS: list[dict[str, Any]] = [
    c
    for c in PYPROJECT["tool"]["importlinter"]["contracts"]
    if c["type"] == "forbidden" and c["name"] != NOM_ISOLATION_LLM
]
NOM_LECTURE_SEULE_AGENT = "ia.agent : lecture seule"
"""Contrat de sous-paquet (Story 7.8) : ports d'écriture et de Jira interdits à l'Agent."""
CONTRATS_DES_COUCHES = [c for c in CONTRATS_INTERDITS if c["name"] != NOM_LECTURE_SEULE_AGENT]

# Classement des dépendances directes (groupes compris) : modules importables de chacune.
MODULES_DES_DEPENDANCES: dict[str, tuple[str, ...]] = {
    "pydantic": ("pydantic",),
    "pydantic-settings": ("pydantic_settings",),
    "polars": ("polars",),
    "duckdb": ("duckdb",),
    "numpy": ("numpy",),
    "pyarrow": ("pyarrow",),
    "pyyaml": ("yaml",),
    "typer": ("typer",),
    "httpx": ("httpx",),
    "pydantic-ai-slim": ("pydantic_ai", "anthropic", "mistralai"),
    "presidio-analyzer": ("presidio_analyzer",),
    "presidio-anonymizer": ("presidio_anonymizer",),
    "spacy": ("spacy",),
    "fr-core-news-md": ("fr_core_news_md",),
    "openpyxl": ("openpyxl",),
    "python-pptx": ("pptx",),
    "streamlit": ("streamlit",),
    "scikit-learn": ("sklearn",),
    "pymongo": ("pymongo",),
    "pytest": ("pytest",),
    "ruff": ("ruff",),
    "mypy": ("mypy",),
    "import-linter": ("importlinter",),
    "time-machine": ("time_machine",),
    "types-pyyaml": (),  # Stubs de typage seulement : rien à importer.
    "lightgbm": ("lightgbm",),
    "langfuse": ("langfuse",),
}
EXTERNES = {m for modules in MODULES_DES_DEPENDANCES.values() for m in modules}

# Liste blanche des externes : toute couche a droit à pydantic, polars et la stdlib.
EXTERNES_DE_BASE = {"pydantic", "polars"}
STDLIB_INTERDITE_AU_DOMAINE = {
    "io", "os", "pathlib", "random", "secrets", "shutil", "socket", "sqlite3", "subprocess",
    "tempfile", "time", "urllib", "uuid",
}  # fmt: skip
PAQUETS = {
    "contrats", "ports", "domaine", "consultation", "chaine", "ia", "rendu", "adaptateurs",
    "generateur", "config", "composition", "cli", "ui",
}  # fmt: skip

# Tableau des couches du spine : (paquets internes permis, externes permis en plus de la base).
AUTORISATIONS: dict[str, tuple[set[str], set[str] | None]] = {
    "usine.contrats": (set(), set()),
    "usine.ports": ({"contrats"}, set()),
    "usine.domaine": ({"contrats"}, set()),
    "usine.consultation": ({"contrats", "ports"}, set()),
    "usine.chaine": ({"contrats", "ports", "domaine", "consultation"}, set()),
    "usine.ia": ({"contrats", "ports", "consultation"}, set()),
    "usine.rendu": ({"contrats", "ports", "consultation"}, {"openpyxl", "pptx"}),
    "usine.adaptateurs": (
        {"contrats", "ports"},
        {
            "httpx",
            "duckdb",
            "pydantic_ai",
            "anthropic",
            "mistralai",
            "presidio_analyzer",
            "presidio_anonymizer",
            "spacy",
            "pymongo",
        },
    ),
    "usine.generateur": ({"contrats", "ports"}, set()),
    "usine.config": ({"contrats"}, {"yaml", "pydantic_settings"}),
    "usine.ui": ({"contrats", "consultation", "composition"}, {"streamlit"}),
    # Hors produit : aucun interdit externe (None).
    "evaluation": ({"contrats", "ports", "domaine", "composition"}, None),
}


def _nom_dependance(specification: str) -> str:
    nom = re.match(r"[A-Za-z0-9._-]+", specification)
    assert nom is not None, specification
    return re.sub(r"[-_.]+", "-", nom.group(0)).lower()


def _interdits_attendus(source: str) -> set[str]:
    internes, externes = AUTORISATIONS[source]
    soi = source.removeprefix("usine.")
    attendus = {f"usine.{p}" for p in PAQUETS - internes - {soi}}
    if externes is not None:
        attendus |= EXTERNES - EXTERNES_DE_BASE - externes
    if source == "usine.domaine":
        attendus |= STDLIB_INTERDITE_AU_DOMAINE
    return attendus


def _copie_du_depot(racine: Path, cible: Path) -> Path:
    shutil.copytree(racine / "src", cible / "src", ignore=shutil.ignore_patterns("__pycache__"))
    for nom in RACINES_HORS_PRODUIT:
        shutil.copytree(racine / nom, cible / nom, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy(racine / "pyproject.toml", cible / "pyproject.toml")
    return cible


def _lint_imports(depot: Path) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(depot / "src"), str(depot)]),
        "PYTHONUTF8": "1",
    }
    lint = Path(sys.executable).with_name("lint-imports.exe" if os.name == "nt" else "lint-imports")
    return subprocess.run(
        [str(lint), "--no-cache"],
        cwd=depot,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _repertoire(depot: Path, module: str) -> Path:
    racine = depot / "src" if module.startswith("usine") else depot
    return racine.joinpath(*module.split("."))


@pytest.fixture(scope="module")
def sortie_violations(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Un seul `lint-imports` : chaque source de contrat `forbidden` importe tous ses interdits."""
    depot = _copie_du_depot(RACINE, tmp_path_factory.mktemp("depot"))
    for contrat in CONTRATS_INTERDITS:
        imports = "".join(f"import {m}  # noqa: F401\n" for m in contrat["forbidden_modules"])
        for source in contrat["source_modules"]:
            (_repertoire(depot, source) / "violation.py").write_text(imports, encoding="utf-8")
    resultat = _lint_imports(depot)
    assert resultat.returncode != 0, resultat.stdout + resultat.stderr
    return resultat.stdout


@pytest.mark.parametrize("contrat", CONTRATS_INTERDITS, ids=lambda c: c["name"])
def test_chaque_interdit_casse_son_contrat(sortie_violations: str, contrat: dict[str, Any]) -> None:
    assert f"{contrat['name']} BROKEN" in sortie_violations
    manquants = [
        f"{source} -> {module}"
        for source in contrat["source_modules"]
        for module in contrat["forbidden_modules"]
        if f"{source} is not allowed to import {module}:" not in sortie_violations
        or not re.search(
            rf"-\s+{re.escape(source)}\.violation -> {re.escape(module)} \(l\.", sortie_violations
        )
    ]
    assert manquants == []


def test_chaque_dependance_directe_est_classee() -> None:
    specifications = [
        *PYPROJECT["project"]["dependencies"],
        *(s for groupe in PYPROJECT["dependency-groups"].values() for s in groupe),
    ]
    non_classees = sorted(
        {_nom_dependance(s) for s in specifications} - set(MODULES_DES_DEPENDANCES)
    )
    assert non_classees == []


def test_chaque_couche_a_un_contrat() -> None:
    sources = {c["source_modules"][0] for c in CONTRATS_DES_COUCHES}
    assert sources == set(AUTORISATIONS)


@pytest.mark.parametrize("contrat", CONTRATS_DES_COUCHES, ids=lambda c: c["name"])
def test_interdits_conformes_a_la_liste_blanche(contrat: dict[str, Any]) -> None:
    attendus = _interdits_attendus(contrat["source_modules"][0])
    assert sorted(set(contrat["forbidden_modules"]) ^ attendus) == []


# Le graphe est construit dans un sous-processus : `usine` y est importé depuis `src`.
_SCRIPT_GRAPHE = """
import json
import grimp

graphe = grimp.build_graph("usine", include_external_packages=True, cache_dir=None)
internes = sorted(m for m in graphe.modules if m == "usine" or m.startswith("usine."))
print(json.dumps({
    m: sorted(i for i in graphe.find_modules_directly_imported_by(m) if i not in internes)
    for m in internes
}))
"""


def _externes_importes(src: Path) -> dict[str, list[str]]:
    """Pour chaque module `usine.*` sous `src`, les modules externes qu'il importe directement."""
    env = {**os.environ, "PYTHONPATH": str(src), "PYTHONUTF8": "1"}
    sortie = subprocess.run(
        [sys.executable, "-c", _SCRIPT_GRAPHE],
        cwd=src,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    resultat: dict[str, list[str]] = json.loads(sortie)
    return resultat


def _hors_liste_blanche(imports: dict[str, list[str]]) -> list[str]:
    """Imports externes directs non permis, transitifs compris (`cli` exclus)."""
    fautifs: list[str] = []
    for source, (_, permis) in AUTORISATIONS.items():
        if not source.startswith("usine."):
            continue
        assert permis is not None
        autorises = EXTERNES_DE_BASE | permis | set(sys.stdlib_module_names)
        if source == "usine.domaine":
            autorises -= STDLIB_INTERDITE_AU_DOMAINE
        for module, externes in imports.items():
            if module != source and not module.startswith(f"{source}."):
                continue
            if module.rsplit(".", 1)[-1] == "cli":
                continue
            fautifs += [f"{module} -> {e}" for e in externes if e not in autorises]
    return fautifs


def test_externes_du_depot_dans_la_liste_blanche() -> None:
    assert _hors_liste_blanche(_externes_importes(RACINE / "src")) == []


def test_dependance_transitive_refusee(tmp_path: Path) -> None:
    depot = _copie_du_depot(RACINE, tmp_path)
    violation = depot / "src" / "usine" / "domaine" / "violation.py"
    violation.write_text("import click  # noqa: F401\n", encoding="utf-8")
    assert _hors_liste_blanche(_externes_importes(depot / "src")) == [
        "usine.domaine.violation -> click"
    ]


def test_pydantic_ai_hors_adaptateurs_llm_refuse(tmp_path: Path) -> None:
    """AD-12 : `pydantic_ai` importé hors de `adaptateurs/llm/`, même dans un adaptateur, casse."""
    depot = _copie_du_depot(RACINE, tmp_path)
    violation = depot / "src" / "usine" / "adaptateurs" / "journal" / "violation.py"
    violation.write_text("import pydantic_ai  # noqa: F401\n", encoding="utf-8")
    sortie = _lint_imports(depot).stdout
    assert f"{NOM_ISOLATION_LLM} BROKEN" in sortie
    assert "usine.adaptateurs.journal.violation -> pydantic_ai" in sortie
