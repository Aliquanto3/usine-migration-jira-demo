import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from usine import cli
from usine.cli import app
from usine.contrats.erreurs import UsineErreur

SOUS_APPLICATIONS = ["donnees", "extraction", "rapport", "ia", "agent", "ui"]


def test_aide_liste_les_sous_applications() -> None:
    resultat = CliRunner().invoke(app, ["--help"])
    assert resultat.exit_code == 0
    for nom in SOUS_APPLICATIONS:
        assert nom in resultat.output


def test_chaque_sous_application_a_une_aide() -> None:
    for nom in SOUS_APPLICATIONS:
        resultat = CliRunner().invoke(app, [nom, "--help"])
        assert resultat.exit_code == 0, resultat.output


def test_main_traduit_une_usine_erreur(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def app_en_echec() -> None:
        raise UsineErreur("chaine.yaml : clé « palier » refusée")

    monkeypatch.setattr(cli, "app", app_en_echec)
    with pytest.raises(SystemExit) as sortie:
        cli.main()
    assert sortie.value.code == 1
    assert "chaine.yaml : clé « palier » refusée" in capsys.readouterr().err


def test_script_usine_pointe_sur_main(racine_depot: Path) -> None:
    projet = tomllib.loads((racine_depot / "pyproject.toml").read_text(encoding="utf-8"))
    assert projet["project"]["scripts"]["usine"] == "usine.cli:main"
