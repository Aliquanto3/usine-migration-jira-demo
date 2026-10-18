import io
import logging
import sys
import tomllib
from datetime import UTC, datetime
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


def test_configurer_console_ecrit_en_utf8(monkeypatch: pytest.MonkeyPatch) -> None:
    """Console Windows en cp1252 : « Étape » et les guillemets français sortent en UTF-8."""
    flux = {
        nom: io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="\n")
        for nom in ("out", "err")
    }
    monkeypatch.setattr(sys, "stdout", flux["out"])
    monkeypatch.setattr(sys, "stderr", flux["err"])
    appels: list[dict[str, object]] = []
    monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: appels.append(kwargs))
    monkeypatch.setattr(logging.getLogger("usine"), "level", logging.NOTSET)  # rendu après
    cli.configurer_console()
    texte = "Étape « rendu » : réussie ✓\n"
    for f in flux.values():
        f.write(texte)
        f.flush()
        assert f.buffer.getvalue().decode("utf-8") == texte
    assert len(appels) == 1
    assert appels[0]["level"] == logging.WARNING
    gestionnaires = appels[0]["handlers"]
    assert isinstance(gestionnaires, list)
    (gestionnaire,) = gestionnaires
    assert isinstance(gestionnaire, logging.StreamHandler)
    assert gestionnaire.stream is flux["err"]
    assert isinstance(gestionnaire.formatter, cli.FormateurJournal)
    assert logging.getLogger("usine").level == logging.INFO


@pytest.mark.parametrize(
    ("instant", "attendu"),
    [
        (datetime(2026, 10, 12, 22, 12, tzinfo=UTC), "13/10/2026 00:12:00 INFO usine : x"),
        (datetime(2026, 1, 15, 22, 12, tzinfo=UTC), "15/01/2026 23:12:00 INFO usine : x"),
    ],
)
def test_journal_horodate_en_heure_de_paris(instant: datetime, attendu: str) -> None:
    """Heure d'été puis d'hiver, changement de jour compris, sans mention « UTC »."""
    enregistrement = logging.LogRecord("usine", logging.INFO, "f", 1, "x", None, None)
    enregistrement.created = instant.timestamp()
    assert cli.FormateurJournal(cli.FORMAT_JOURNAL).format(enregistrement) == attendu


def test_main_configure_la_console_avant_la_commande(monkeypatch: pytest.MonkeyPatch) -> None:
    ordre: list[str] = []
    monkeypatch.setattr(cli, "configurer_console", lambda: ordre.append("console"))
    monkeypatch.setattr(cli, "app", lambda: ordre.append("app"))
    cli.main()
    assert ordre == ["console", "app"]
