"""Bout en bout (constat 23 de la rétro E0) : vrai `usine rapport` lancé par l'API de l'UI web.

Le sous-processus est réel (`subprocess.Popen`) ; seule la Date d'arrêté est fixée au
09/10/2026 pour retrouver le Passage d'essai. Le client sonde `/api/chaine` jusqu'à la fin,
puis lit la carte, le détail d'une Entité et un livrable du nouveau Passage (Story 7.17).
Un second parcours fait la même lecture en Mode repli, sans Jira ni sous-processus.
"""

import subprocess
import time
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from tests.unit.chaine.environnement import DATE_ARRETE, preparer_racine
from usine.contrats.passage import REPERTOIRE_PASSAGES, Etape
from usine.ui.chaine import GestionChaine
from usine.ui.cli import application_web, lecture_consultation, lecture_manifeste, services_ecrans
from usine.ui.serveur import HOTE, creer_application

DELAI_MAX = 60.0  # secondes
PAUSE = 0.5  # secondes entre deux sondages


def _popen_date_fixee(commande: list[str], **options: Any) -> "subprocess.Popen[bytes]":
    return subprocess.Popen([*commande, "--date-arrete", DATE_ARRETE.isoformat()], **options)


def test_vrai_rapport_depuis_l_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    racine = preparer_racine(tmp_path)
    monkeypatch.chdir(racine)
    application = creer_application(
        repli=False,
        lire_manifeste=lecture_manifeste(racine),
        lire_consultation=lecture_consultation(racine),
        chaine=GestionChaine(racine, popen=cast(Any, _popen_date_fixee)),
        services=services_ecrans(racine),
    )
    http = TestClient(application, base_url=f"http://{HOTE}")
    assert http.get("/api/carte").json()["message"]  # aucun Passage publié

    assert http.post("/api/chaine").status_code == 202
    limite = time.monotonic() + DELAI_MAX
    vue = http.get("/api/chaine").json()
    while vue["en_cours"]:
        assert time.monotonic() < limite, "usine rapport non terminé en 60 s"
        time.sleep(PAUSE)
        vue = http.get("/api/chaine").json()

    assert vue["statut"] == "terminee", vue["erreur"]
    assert vue["erreur"] is None
    assert vue["terminees"] == vue["total"] == len(Etape)
    assert [etape["nom"] for etape in vue["etapes"]] == [etape.value for etape in Etape]
    assert {etape["etat"] for etape in vue["etapes"]} <= {"reussie", "sautee"}
    publies = list((racine / REPERTOIRE_PASSAGES / DATE_ARRETE.isoformat()).iterdir())
    assert len(publies) == 1
    assert (publies[0] / "manifeste.json").is_file()

    # la carte du nouveau Passage, le détail d'une Entité et un livrable se lisent ensuite
    carte = http.get("/api/carte").json()
    assert carte["lignes"]
    assert "09/10/2026" in carte["sous_titre"]
    entite = carte["lignes"][0]["entite"]
    assert http.get(f"/api/entites/{entite}").json()["entite"] == entite
    assert http.get("/livrables/rapport_xlsx").content[:2] == b"PK"


def test_carte_detail_livrable_en_mode_repli(racine_publiee: Path) -> None:
    http = TestClient(application_web(racine_publiee, False), base_url=f"http://{HOTE}")
    assert http.post("/api/mode", json={"mode": "repli"}).status_code == 200
    cadre = http.get("/api/cadre").json()
    assert cadre["mode"] == "repli"
    assert cadre["bandeau_repli_html"]

    carte = http.get("/api/carte").json()
    assert carte["erreur"] is None
    assert all(t["url"] is None for ligne in carte["lignes"] for t in ligne["tickets"])
    entite = carte["lignes"][0]["entite"]
    detail = http.get(f"/api/entites/{entite}").json()
    assert detail["entite"] == entite
    assert detail["erreur"] is None
    livrable = http.get("/livrables/rapport_xlsx")
    assert livrable.status_code == 200
    assert livrable.content[:2] == b"PK"
    assert "attachment" in livrable.headers["content-disposition"]
