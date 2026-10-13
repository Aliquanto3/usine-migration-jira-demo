"""Mode réel de la suite Agent : une erreur réseau sort en code 1, sans trace (7.10-a)."""

from pathlib import Path
from typing import Any

import httpx
import pytest

from evals.agent import __main__ as cli


def _lever(erreur: Exception) -> Any:
    def _executer(*_args: Any, **_kwargs: Any) -> Any:
        raise erreur

    return _executer


def test_erreur_reseau_en_reel_code_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "executer_suite", _lever(httpx.ConnectError("connexion refusée")))
    code = cli.main(["executer", "--reel", "--sortie", str(tmp_path / "res")])
    assert code == 1
    erreur = capsys.readouterr().err
    assert "ConnectError" in erreur
    assert "aucun résultat écrit" in erreur
    assert len(erreur.strip().splitlines()) == 1
    assert not (tmp_path / "res").exists()


def test_erreur_reseau_en_rejeu_inchangee(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "executer_suite", _lever(httpx.ConnectError("x")))
    with pytest.raises(httpx.ConnectError):
        cli.main(["executer"])
