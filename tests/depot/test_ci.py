"""Workflows CI : aucune expression `${{ }}` interpolée dans un script `run` (injection shell)."""

from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOWS = sorted((Path(__file__).resolve().parents[2] / ".github" / "workflows").glob("*.yml"))


def test_au_moins_un_workflow() -> None:
    assert WORKFLOWS


@pytest.mark.parametrize("chemin", WORKFLOWS, ids=lambda c: c.name)
def test_aucune_expression_dans_run(chemin: Path) -> None:
    workflow: dict[str, Any] = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    fautifs = [
        f"{nom_job} / {etape.get('name', etape.get('uses', '?'))}"
        for nom_job, job in workflow["jobs"].items()
        for etape in job.get("steps", [])
        if "${{" in str(etape.get("run", ""))
    ]
    assert fautifs == [], "passer ces expressions par `env:`"
