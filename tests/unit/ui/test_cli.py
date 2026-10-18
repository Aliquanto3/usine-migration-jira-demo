"""Commande `usine ui` et services de la page : configuration de la démo, manifestes mesurés."""

from datetime import date
from pathlib import Path
from typing import Any

import click
import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from tests.unit.ui.test_avant_apres import manifeste, publier
from usine.cli import app
from usine.contrats.erreurs import UsineErreur
from usine.ui import cli as cli_ui
from usine.ui.serveur import HOTE


def test_aide() -> None:
    resultat = CliRunner().invoke(app, ["ui", "--help"])
    assert resultat.exit_code == 0, resultat.output
    assert "--port" in click.unstyle(resultat.output)  # rich colore l'aide en CI


def test_option_inconnue_refusee() -> None:
    resultat = CliRunner().invoke(app, ["ui", "--option-inconnue"])
    assert resultat.exit_code == 2


def _capter_uvicorn(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    appels: list[dict[str, Any]] = []

    def executer(application: object, **options: Any) -> None:
        appels.append({"application": application, **options})

    monkeypatch.setattr(uvicorn, "run", executer)
    return appels


def test_lance_uvicorn_sur_127_0_0_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    appels = _capter_uvicorn(monkeypatch)
    resultat = CliRunner().invoke(app, ["ui"])
    assert resultat.exit_code == 0, resultat.output
    assert len(appels) == 1
    assert appels[0]["host"] == "127.0.0.1"
    assert appels[0]["port"] == cli_ui.PORT
    assert isinstance(appels[0]["application"], FastAPI)
    assert "http://127.0.0.1:8000/" in resultat.output
    assert "Mode repli" not in resultat.output


def test_ui_port_et_mode_repli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("USINE_MODE_REPLI", "1")
    appels = _capter_uvicorn(monkeypatch)
    resultat = CliRunner().invoke(app, ["ui", "--port", "8123"])
    assert resultat.exit_code == 0, resultat.output
    assert appels[0]["port"] == 8123
    assert "(Mode repli)" in resultat.output
    vue = TestClient(appels[0]["application"], base_url=f"http://{HOTE}").get("/api/cadre").json()
    assert vue["mode"] == "repli"


def test_ui_variable_illisible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("USINE_MODE_REPLI", "peut-etre")
    appels = _capter_uvicorn(monkeypatch)
    resultat = CliRunner().invoke(app, ["ui"])
    assert resultat.exit_code == 1
    assert "USINE_MODE_REPLI" in resultat.stderr
    assert appels == []


def test_ui_interruption_et_port_occupe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    def interrompre(application: object, **options: Any) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(uvicorn, "run", interrompre)
    assert CliRunner().invoke(app, ["ui"]).exit_code == 0

    def occupe(application: object, **options: Any) -> None:
        raise OSError(98, "adresse déjà utilisée")

    monkeypatch.setattr(uvicorn, "run", occupe)
    resultat = CliRunner().invoke(app, ["ui"])
    assert resultat.exit_code == 1
    assert "démarrage du serveur impossible" in resultat.stderr


def test_racine_ui(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert cli_ui.racine_ui() == tmp_path
    (tmp_path / ".env").write_text("USINE_RACINE=autre\n", encoding="utf-8")
    assert cli_ui.racine_ui() == Path("autre")
    monkeypatch.setenv("USINE_RACINE", str(tmp_path / "depot"))
    assert cli_ui.racine_ui() == tmp_path / "depot"
    monkeypatch.setenv("USINE_RACINE", "  ")
    assert cli_ui.racine_ui() == tmp_path  # blanche : le répertoire courant


def test_racine_ui_secrets_illisibles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("USINE_MODE_REPLI", "peut-être")
    with pytest.raises(UsineErreur, match="USINE_MODE_REPLI"):
        cli_ui.racine_ui()


def test_config_demo_absente(tmp_path: Path) -> None:
    assert cli_ui.config_demo(tmp_path) is None


def test_config_demo_valide(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "demo.yaml").write_text(
        "# Temps manuel.\ntemps_manuel_minutes_par_rapport: 45\n", encoding="utf-8"
    )
    config = cli_ui.config_demo(tmp_path)
    assert config is not None
    assert config.temps_manuel_minutes_par_rapport == 45


def test_config_demo_du_depot() -> None:
    config = cli_ui.config_demo(Path(__file__).resolve().parents[3])
    assert config is not None
    assert config.temps_manuel_minutes_par_rapport == 120


@pytest.mark.parametrize(
    "contenu", ["temps_manuel_minutes_par_rapport: 0\n", "inconnue: 1\n", "{illisible\n"]
)
def test_config_demo_invalide(tmp_path: Path, contenu: str) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "demo.yaml").write_text(contenu, encoding="utf-8")
    with pytest.raises(UsineErreur, match=r"demo\.yaml"):
        cli_ui.config_demo(tmp_path)


def test_config_demo_invalide_nomme_cle_et_valeur(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "demo.yaml").write_text(
        "temps_manuel_minutes_par_rapport: 0\n", encoding="utf-8"
    )
    with pytest.raises(UsineErreur, match=r"temps_manuel_minutes_par_rapport.*valeur 0"):
        cli_ui.config_demo(tmp_path)


def test_manifestes_avant_apres_sans_passage(tmp_path: Path) -> None:
    assert cli_ui.manifestes_avant_apres(tmp_path) == (None, None)


def test_manifestes_avant_apres_exclut_la_classification_initiale(tmp_path: Path) -> None:
    ancien = manifeste(2.0, passage_id="20261011T073000Z-aaaaaa", date_arrete=date(2026, 10, 8))
    recent = manifeste(9.0, classification_initiale=True)
    publier(tmp_path, ancien)
    publier(tmp_path, recent)
    assert cli_ui.manifestes_avant_apres(tmp_path) == (ancien, recent)


def test_manifestes_avant_apres_seule_classification_initiale(tmp_path: Path) -> None:
    seul = manifeste(classification_initiale=True)
    publier(tmp_path, seul)
    assert cli_ui.manifestes_avant_apres(tmp_path) == (None, seul)


def test_ui_port_reellement_occupe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import socket

    monkeypatch.chdir(tmp_path)
    with socket.socket() as occupant:
        occupant.bind(("127.0.0.1", 0))
        occupant.listen()
        port = occupant.getsockname()[1]
        resultat = CliRunner().invoke(app, ["ui", "--port", str(port)])
    assert resultat.exit_code == 1
    assert f"impossible sur 127.0.0.1:{port}" in resultat.stderr


def test_hote_conteneur_ecoute_sur_toutes_les_interfaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("USINE_UI_HOTE", "0.0.0.0")
    appels = _capter_uvicorn(monkeypatch)
    resultat = CliRunner().invoke(app, ["ui"])
    assert resultat.exit_code == 0, resultat.output
    assert appels[0]["host"] == "0.0.0.0"
    assert "http://127.0.0.1:8000/" in resultat.output
    assert "-p 127.0.0.1:8000:8000" in resultat.output
    # Le contrôle du Host reste celui de la boucle locale.
    client = TestClient(appels[0]["application"], base_url="http://0.0.0.0")
    assert client.get("/api/cadre").status_code == 400


def test_hote_par_defaut_et_valeur_explicite_127(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("USINE_UI_HOTE", "127.0.0.1")
    appels = _capter_uvicorn(monkeypatch)
    resultat = CliRunner().invoke(app, ["ui"])
    assert appels[0]["host"] == "127.0.0.1"
    assert "conteneur" not in resultat.output


def test_hote_refuse_toute_autre_valeur(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("USINE_UI_HOTE", "192.168.1.5")
    appels = _capter_uvicorn(monkeypatch)
    resultat = CliRunner().invoke(app, ["ui"])
    assert resultat.exit_code == 1
    assert "USINE_UI_HOTE" in resultat.stderr
    assert appels == []
