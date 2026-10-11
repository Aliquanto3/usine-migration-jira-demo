"""Commande `usine donnees generer` (Story 0.3)."""

import json
import shutil
from datetime import datetime
from pathlib import Path

import pytest
import time_machine
from typer.testing import CliRunner

from usine import cli
from usine.cli import app
from usine.contrats.calendrier import FUSEAU
from usine.contrats.erreurs import UsineErreur
from usine.contrats.evenements import EnteteJournal, Evenement

RACINE = Path(__file__).resolve().parents[3]
CONFIG = RACINE / "config" / "programme.yaml"


def _generer(sortie: Path, *options: str) -> None:
    resultat = CliRunner().invoke(
        app,
        ["donnees", "generer", "--config", str(CONFIG), "--sortie", str(sortie), *options],
    )
    assert resultat.exit_code == 0, resultat.output
    assert resultat.exception is None


def test_generation(tmp_path: Path) -> None:
    sortie = tmp_path / "donnees"
    _generer(sortie, "--graine", "42", "--date-generation", "2026-10-12")
    lignes = (sortie / "journal.jsonl").read_bytes().decode("utf-8").splitlines()
    entete = EnteteJournal.model_validate_json(lignes[0])
    assert entete.graine == 42
    assert entete.date_injection.isoformat() == "2026-10-09"
    assert entete.ancrage_semaines.isoformat() == "2026-08-17"
    assert all(Evenement.model_validate_json(ligne) for ligne in lignes[1:])
    assert json.loads((sortie / "verite_terrain.json").read_text(encoding="utf-8"))


def test_reproductible_et_graine_differente(tmp_path: Path) -> None:
    options = ("--date-generation", "2026-10-12")
    _generer(tmp_path / "a", "--graine", "42", *options)
    _generer(tmp_path / "b", "--graine", "42", *options)
    _generer(tmp_path / "c", "--graine", "43", *options)
    for nom in ("journal.jsonl", "verite_terrain.json"):
        assert (tmp_path / "a" / nom).read_bytes() == (tmp_path / "b" / nom).read_bytes()
    journal = (tmp_path / "a" / "journal.jsonl").read_bytes()
    assert (tmp_path / "c" / "journal.jsonl").read_bytes() != journal


@pytest.mark.parametrize(
    "instant",
    [
        datetime(2026, 10, 12, 10, 0, tzinfo=FUSEAU),
        # Juste après minuit à Paris : la date UTC est encore le 2026-10-11.
        datetime(2026, 10, 12, 0, 30, tzinfo=FUSEAU),
    ],
    ids=["10h-paris", "00h30-paris"],
)
def test_graine_et_date_par_defaut(tmp_path: Path, instant: datetime) -> None:
    with time_machine.travel(instant, tick=False):
        _generer(tmp_path)
    entete = EnteteJournal.model_validate_json(
        (tmp_path / "journal.jsonl").read_bytes().splitlines()[0]
    )
    assert entete.graine == 42
    assert entete.date_generation.isoformat() == "2026-10-12"


@pytest.mark.parametrize("valeur", ["2026-13-01", "12/10/2026", "20261012", "2026-1-5"])
def test_date_invalide(tmp_path: Path, valeur: str) -> None:
    resultat = CliRunner().invoke(
        app,
        [
            "donnees",
            "generer",
            "--config",
            str(CONFIG),
            "--sortie",
            str(tmp_path),
            "--date-generation",
            valeur,
        ],
    )
    assert resultat.exit_code != 0
    assert isinstance(resultat.exception, UsineErreur)
    assert valeur in str(resultat.exception)
    assert not (tmp_path / "journal.jsonl").exists()


@pytest.mark.parametrize("valeur", ["2026-13-01", "20261012"])
def test_date_invalide_code_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    valeur: str,
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "usine",
            "donnees",
            "generer",
            "--config",
            str(CONFIG),
            "--sortie",
            str(tmp_path),
            "--date-generation",
            valeur,
        ],
    )
    with pytest.raises(SystemExit) as sortie:
        cli.main()
    assert sortie.value.code == 1
    assert valeur in capsys.readouterr().err


def test_graine_negative(tmp_path: Path) -> None:
    resultat = CliRunner().invoke(
        app,
        [
            "donnees",
            "generer",
            "--config",
            str(CONFIG),
            "--sortie",
            str(tmp_path),
            "--date-generation",
            "2026-10-12",
            "--graine",
            "-42",
        ],
    )
    assert isinstance(resultat.exception, UsineErreur)
    assert "-42" in str(resultat.exception)
    assert not (tmp_path / "journal.jsonl").exists()


def test_chemins_par_defaut(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "config").mkdir()
    shutil.copyfile(CONFIG, tmp_path / "config" / "programme.yaml")
    monkeypatch.chdir(tmp_path)
    resultat = CliRunner().invoke(app, ["donnees", "generer", "--date-generation", "2026-10-12"])
    assert resultat.exit_code == 0, resultat.output
    assert (tmp_path / "donnees" / "journal.jsonl").is_file()
    assert (tmp_path / "donnees" / "verite_terrain.json").is_file()


def test_sortie_non_inscriptible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fichier = tmp_path / "pas_un_repertoire"
    fichier.write_text("occupé", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "usine",
            "donnees",
            "generer",
            "--config",
            str(CONFIG),
            "--sortie",
            str(fichier),
            "--date-generation",
            "2026-10-12",
        ],
    )
    with pytest.raises(SystemExit) as sortie:
        cli.main()
    assert sortie.value.code == 1
    assert str(fichier) in capsys.readouterr().err


def test_config_fautive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fautive = tmp_path / "programme.yaml"
    fautive.write_text(
        CONFIG.read_text(encoding="utf-8").replace("vague: V1", "vague: V9", 1),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["usine", "donnees", "generer", "--config", str(fautive), "--sortie", str(tmp_path)],
    )
    with pytest.raises(SystemExit) as sortie:
        cli.main()
    assert sortie.value.code == 1
    erreur = capsys.readouterr().err
    assert str(fautive) in erreur
    assert "Vague inconnue" in erreur
    assert "V9" in erreur
    assert not (tmp_path / "journal.jsonl").exists()
