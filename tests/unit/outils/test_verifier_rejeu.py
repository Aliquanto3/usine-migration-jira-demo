"""Outil `outils/verifier_rejeu.py` : matrice de la Story 5.7 sur des Passages réduits fabriqués."""

import json
from pathlib import Path

import polars as pl
import pytest

from outils.verifier_rejeu import ABSENT, differences, hors_exclusions, main

DATE = "2026-10-09"


def _passage(
    racine: Path,
    passage_id: str,
    horodatage: str = "2026-10-12T22:27:01Z",
    meteo: str = "rouge",
    tendances: bool = True,
) -> Path:
    """Passage publié réduit : manifeste, météo, une table et une trace."""
    dossier = racine / "sorties" / "passages" / DATE / passage_id
    (dossier / "trace").mkdir(parents=True)
    manifeste = {
        "passage_id": passage_id,
        "date_arrete": DATE,
        "horodatage_extraction": horodatage,
        "etapes": [{"etape": "kpi", "statut": "reussie", "horodatage_debut": passage_id}],
    }
    (dossier / "manifeste.json").write_text(json.dumps(manifeste), encoding="utf-8")
    contenu = {"passage_id": passage_id, "entites": [{"code": "ENT-A", "couleur": meteo}]}
    (dossier / "meteo.json").write_text(json.dumps(contenu), encoding="utf-8")
    (dossier / "trace" / "previsions.jsonl").write_text(
        json.dumps({"passage_id": passage_id, "entite": "ENT-A"}) + "\n", encoding="utf-8"
    )
    if tendances:
        pl.DataFrame({"entite": ["ENT-A"], "stock": [3]}).write_parquet(
            dossier / "tendances.parquet"
        )
    return dossier


def test_rejeu_conforme(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    premier = _passage(tmp_path, "20261012T222702Z-ec5fab")
    second = _passage(tmp_path, "20261013T080000Z-123abc", horodatage="2026-10-13T08:00:00Z")
    observees = differences(premier, second, DATE)
    assert observees == {
        ("manifeste", "passage_id"),
        ("manifeste", "horodatage_extraction"),
        ("manifeste", "etapes[].horodatage_debut"),
        ("meteo", "passage_id"),
        ("trace_previsions", "passage_id"),
    }
    assert not hors_exclusions(observees)
    assert main([str(premier), str(second)]) == 0
    sortie = capsys.readouterr().out
    assert "exclue : manifeste : horodatage_extraction" in sortie
    assert "Rejeu conforme" in sortie


def test_rejeu_non_conforme(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    premier = _passage(tmp_path, "20261012T222702Z-ec5fab")
    second = _passage(tmp_path, "20261013T080000Z-123abc", meteo="orange")
    assert hors_exclusions(differences(premier, second, DATE)) == {("meteo", "entites[].couleur")}
    assert main([str(premier), str(second)]) == 1
    assert "  meteo : entites[].couleur" in capsys.readouterr().out


def test_fichier_absent_d_un_seul_cote(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    premier = _passage(tmp_path, "20261012T222702Z-ec5fab")
    second = _passage(tmp_path, "20261013T080000Z-123abc", tendances=False)
    assert hors_exclusions(differences(premier, second, DATE)) == {("tendances", ABSENT)}
    assert main([str(premier), str(second)]) == 1
    assert f"  tendances : {ABSENT}" in capsys.readouterr().out


def test_date_sans_deux_passages(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--date", DATE, "--racine", str(tmp_path)]) == 2
    _passage(tmp_path, "20261012T222702Z-ec5fab")
    assert main(["--date", DATE, "--racine", str(tmp_path)]) == 2
    assert "Moins de deux Passages" in capsys.readouterr().err


def test_date_compare_les_deux_derniers(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _passage(tmp_path, "20261011T000000Z-000000", meteo="vert")
    _passage(tmp_path, "20261012T222702Z-ec5fab")
    _passage(tmp_path, "20261013T080000Z-123abc")
    assert main(["--date", DATE, "--racine", str(tmp_path)]) == 0
    assert "20261012T222702Z-ec5fab contre 20261013T080000Z-123abc" in capsys.readouterr().out


def test_usage_incorrect(tmp_path: Path) -> None:
    assert main([str(tmp_path)]) == 2
    assert main([str(tmp_path / "a"), str(tmp_path / "b")]) == 2


def test_date_ignore_un_dossier_sans_manifeste(tmp_path: Path) -> None:
    _passage(tmp_path, "20261012T222702Z-ec5fab")
    _passage(tmp_path, "20261013T080000Z-123abc")
    (tmp_path / "sorties" / "passages" / DATE / "zz-brouillon").mkdir()
    assert main(["--date", DATE, "--racine", str(tmp_path)]) == 0


def test_dates_d_arrete_differentes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    premier = _passage(tmp_path, "20261012T222702Z-ec5fab")
    second = _passage(tmp_path, "20261013T080000Z-123abc")
    manifeste = second / "manifeste.json"
    contenu = json.loads(manifeste.read_text(encoding="utf-8"))
    manifeste.write_text(json.dumps({**contenu, "date_arrete": "2026-10-08"}), encoding="utf-8")
    assert main([str(premier), str(second)]) == 2
    assert "même Date d'arrêté" in capsys.readouterr().err
