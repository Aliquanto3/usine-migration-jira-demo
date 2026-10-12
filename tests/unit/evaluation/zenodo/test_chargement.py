"""Lecteur du dump (`evaluation.zenodo.chargement`) sans MongoDB : client simulé (Story 4.3)."""

import json
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from pymongo.errors import ServerSelectionTimeoutError

from evaluation.zenodo import chargement
from evaluation.zenodo.conversion import convertir_en_series

EXTRAIT: list[dict[str, Any]] = json.loads(
    (Path(__file__).with_name("extrait_tickets.json")).read_text(encoding="utf-8")
)


def _projeter(document: dict[str, Any], projection: dict[str, int]) -> dict[str, Any]:
    """Applique une projection d'inclusion MongoDB (chemins pointés) à un document."""
    resultat: dict[str, Any] = {}
    for chemin, inclus in projection.items():
        if not inclus:
            continue
        source: Any = document
        cible = resultat
        *parents, feuille = chemin.split(".")
        for nom in parents:
            source = source.get(nom) if isinstance(source, dict) else None
            cible = cible.setdefault(nom, {})
        if isinstance(source, dict) and feuille in source:
            cible[feuille] = source[feuille]
    return resultat


class _Collection:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents

    def find(self, filtre: dict[str, Any], projection: dict[str, int]) -> list[dict[str, Any]]:
        assert filtre == {}
        return [_projeter(d, projection) for d in self.documents]


class _ClientSimule:
    documents: list[dict[str, Any]] = EXTRAIT
    erreur: Exception | None = None

    def __init__(self, uri: str, **_: Any) -> None:
        assert uri.startswith("mongodb://127.0.0.1")

    def __getitem__(self, base: str) -> dict[str, _Collection]:
        if self.erreur is not None:
            raise self.erreur
        return {"Apache": _Collection(self.documents)}

    def close(self) -> None:
        pass


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> type[_ClientSimule]:
    monkeypatch.setattr(chargement, "MongoClient", _ClientSimule)
    monkeypatch.setattr(_ClientSimule, "documents", EXTRAIT)
    monkeypatch.setattr(_ClientSimule, "erreur", None)
    return _ClientSimule


def _main(sortie: Path, *options: str) -> int:
    return chargement.main(
        ["--base", "JiraReposAnon", "--collection", "Apache", "--sortie", str(sortie), *options]
    )


def test_projection_suffit_a_la_conversion(client: type[_ClientSimule], tmp_path: Path) -> None:
    sortie = tmp_path / "series" / "apache.parquet"
    assert _main(sortie) == 0
    attendu = convertir_en_series(EXTRAIT, depot="Apache")
    assert not attendu.is_empty()
    assert pl.read_parquet(sortie).equals(attendu)


def test_depot_et_priorites_parametrables(client: type[_ClientSimule], tmp_path: Path) -> None:
    sortie = tmp_path / "s.parquet"
    assert _main(sortie, "--depot", "asf", "--priorite", "Major") == 0
    attendu = convertir_en_series(EXTRAIT, depot="asf", priorites=frozenset({"Major"}))
    assert pl.read_parquet(sortie).equals(attendu)


def test_aucune_serie_code_1(
    client: type[_ClientSimule], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sortie = tmp_path / "s.parquet"
    assert _main(sortie, "--priorite", "Inexistante") == 1
    assert not sortie.exists()
    assert "aucune série" in capsys.readouterr().err


def test_ticket_sans_cle_nomme_par_id(
    client: type[_ClientSimule], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client.documents = [{"_id": "6071f0c2", "fields": {}}]
    assert _main(tmp_path / "s.parquet") == 1
    assert "6071f0c2" in capsys.readouterr().err


def test_mongod_injoignable_code_1(
    client: type[_ClientSimule], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client.erreur = ServerSelectionTimeoutError("127.0.0.1:27017: connexion refusée")
    assert _main(tmp_path / "s.parquet") == 1
    assert "connexion refusée" in capsys.readouterr().err
