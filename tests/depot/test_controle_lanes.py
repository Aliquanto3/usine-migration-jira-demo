"""Contrôle des chemins par lane (AD-21)."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _charger_script() -> ModuleType:
    chemin = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "controle_lanes.py"
    spec = importlib.util.spec_from_file_location("controle_lanes", chemin)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["controle_lanes"] = module
    spec.loader.exec_module(module)
    return module


lanes = _charger_script()


@pytest.mark.parametrize(
    ("branche", "attendu"),
    [("lane/2-extraction", 2), ("lane/8-portage", 8), ("main", None), ("lane-2", None)],
)
def test_numero_lane(branche: str, attendu: int | None) -> None:
    assert lanes.numero_lane(branche) == attendu


@pytest.mark.parametrize(
    ("numero", "fichier"),
    [
        (1, "src/usine/generateur/scenarios.py"),
        (1, "tests/unit/generateur/test_scenarios.py"),
        (1, "donnees/corpus/textes.json"),
        (2, "tests/unit/adaptateurs/test_jira_cloud.py"),
        (2, "src/usine/adaptateurs/cli.py"),
        (3, "tests/unit/domaine/test_kpi.py"),
        (7, "tests/unit/ia/test_agent.py"),
        (2, "src/usine/adaptateurs/jira_cloud.py"),
        (2, "src/usine/adaptateurs/jira_http/pagination.py"),
        (2, "tests/fixtures/jira_cloud/search.json"),
        (3, "config/grille_meteo.yaml"),
        (6, "src/usine/ia/passerelle.py"),
        (6, "tests/unit/ia/test_passerelle.py"),
        (7, "src/usine/ia/agent/outils.py"),
        (7, "evals/agent/test_agent.py"),
        (8, "docs/fiche-outillage.md"),
        (5, "_bmad-output/implementation-artifacts/sprint-status.yaml"),
    ],
)
def test_fichier_dans_la_lane(numero: int, fichier: str) -> None:
    assert lanes.fichiers_hors_lane(numero, [fichier]) == []


@pytest.mark.parametrize(
    ("numero", "fichier"),
    [
        (2, "src/usine/domaine/kpi.py"),
        (2, "src/usine/adaptateurs/llm/anthropic.py"),
        (2, "src/usine/adaptateurs/jira_cloud_bis.py"),
        (6, "src/usine/ia/agent/outils.py"),
        (6, "tests/unit/ia/agent/test_outils.py"),
        (6, "evals/agent/test_agent.py"),
        (6, "tests/unit/ia/test_agent.py"),
        (2, "tests/unit/adaptateurs/test_jira_cloud_bis.py"),
        (3, "src/usine/contrats/meteo.py"),
        (4, "src/usine/ports/__init__.py"),
        (1, "pyproject.toml"),
        (7, "src/usine/cli.py"),
        (9, "docs/x.md"),
    ],
)
def test_fichier_hors_lane(numero: int, fichier: str) -> None:
    assert lanes.fichiers_hors_lane(numero, [fichier]) == [fichier]


def test_branche_hors_lane_sans_objet(capsys: pytest.CaptureFixture[str]) -> None:
    assert lanes.main(["--branche", "main"]) == 0
    assert "sans objet" in capsys.readouterr().out


def test_fichier_hors_lane_fait_echouer(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(lanes, "_fichiers_modifies", lambda base: ["src/usine/domaine/kpi.py"])
    assert lanes.main(["--branche", "lane/2-extraction"]) == 1
    assert "src/usine/domaine/kpi.py" in capsys.readouterr().out


def test_fichiers_dans_la_lane_acceptes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        lanes, "_fichiers_modifies", lambda base: ["tests/unit/adaptateurs/test_jira_cloud.py"]
    )
    assert lanes.main(["--branche", "lane/2-extraction"]) == 0


@pytest.mark.parametrize("branche", ["lane/3", "lane/3-", "lane/3_calcul", "lane/x-y"])
def test_branche_de_lane_mal_formee(branche: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert lanes.main(["--branche", branche]) == 1
    assert branche in capsys.readouterr().out


def _git(depot: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@exemple.invalid", *args],
        cwd=depot,
        env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"},
        check=True,
        capture_output=True,
    )


def test_renommage_et_accents_dans_un_vrai_depot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git(tmp_path, "init", "-q", "-b", "principale")
    (tmp_path / "contrats").mkdir()
    (tmp_path / "contrats" / "a.py").write_text("VALEUR = 1\n" * 20, encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "base")
    _git(tmp_path, "mv", "contrats/a.py", "contrats/b.py")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "é.md").write_text("# Note\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "renommage")
    monkeypatch.chdir(tmp_path)

    assert sorted(lanes._fichiers_modifies("HEAD~1")) == [
        "contrats/a.py",
        "contrats/b.py",
        "docs/é.md",
    ]
