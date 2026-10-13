"""Outil de préchauffage du cache de classification (Story 6.10)."""

from decimal import Decimal
from pathlib import Path

import pytest

from outils import prechauffer_cache
from tests.unit.chaine.environnement import preparer_racine
from usine.composition import BilanPrechauffage


def test_palier_1_refuse(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    racine = preparer_racine(tmp_path)
    code = prechauffer_cache.main(["--date-arrete", "2026-10-12", "--racine", str(racine)])
    assert code == 2
    assert "exige le palier 2" in capsys.readouterr().err


@pytest.mark.parametrize(("classees", "attendu"), [(10, 0), (7, 3)])
def test_code_de_sortie_selon_le_stock(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    classees: int,
    attendu: int,
) -> None:
    bilan = BilanPrechauffage(anomalies=10, classees=classees, appels=4, cout_eur=Decimal("0.001"))
    monkeypatch.setattr(prechauffer_cache, "prechauffer_classification", lambda *_: bilan)
    assert prechauffer_cache.main(["--date-arrete", "2026-10-12", "--duree-max", "5"]) == attendu
    assert f"Classées : {classees}/10 Anomalies ; 4 appels frais" in capsys.readouterr().out
