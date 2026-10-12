"""Rejeu idempotent sur source composite simulée, échec sans rapport, journal de progression (5.5).

Deux Passages Palier 1 de même Date d'arrêté, dont l'instant d'extraction et la version des
données diffèrent, sont comparés fichier par fichier (`FICHIERS_PASSAGE`) : seuls des chemins
de `EXCLUSIONS_REJEU` peuvent différer, et les champs de traçabilité exclus diffèrent bien.
"""

import json
import logging
from collections.abc import Iterator
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from outils.verifier_rejeu import differences, hors_exclusions
from tests.unit.chaine.environnement import INSTANT, preparer_racine
from usine import cli, composition
from usine.contrats.passage import (
    FICHIERS_PASSAGE,
    ContextePassage,
    DonneesPassage,
    Etape,
    ResultatEtape,
    StatutEtape,
)
from usine.contrats.versions import version_donnees
from usine.ports.consultation import Consultation
from usine.rendu.etape import EtapeRendu

DATE = "2026-10-09"
DIFFERENCES_ATTENDUES = {
    ("manifeste", "horodatage_extraction"),
    ("manifeste", "version_donnees"),
    ("manifeste", "passage_id"),
    ("meteo", "passage_id"),
    ("previsions", "passage_id"),
    ("trace_previsions", "passage_id"),
    ("rapport_xlsx", "Traçabilité!B5"),
    ("rapport_xlsx", "Traçabilité!B8"),
    ("rapport_pptx", "Annexe méthode!Horodatage d'extraction"),
    ("rapport_pptx", "Annexe méthode!Version des données"),
}
"""Différences qui doivent effectivement apparaître : sinon l'exclusion ne serait pas exercée."""


@pytest.fixture
def racine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    preparer_racine(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _usine(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    monkeypatch.setattr("sys.argv", ["usine", "rapport", "--date-arrete", DATE])
    with pytest.raises(SystemExit) as sortie:
        cli.main()
    code = sortie.value.code
    return (0 if code is None else int(code)), capsys.readouterr().err


def _simuler_composite(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chaque composition reçoit son propre instant d'extraction et sa version des données."""
    construire = composition.construire_rapport
    instants: Iterator[int] = iter(range(1, 100))

    def construire_composite(r: Path, *args: Any, **kwargs: Any) -> composition.Rapport:
        rapport = construire(r, *args, **kwargs)
        horodatage = INSTANT + timedelta(hours=next(instants))
        donnees = DonneesPassage(
            "composite",
            rapport.donnees.version_grille,
            version_donnees(b"journal composite", horodatage),
        )
        gabarit = (r / composition.CHEMIN_GABARIT).read_bytes()
        registre = {**rapport.registre, Etape.rendu: EtapeRendu(gabarit, donnees, horodatage)}
        return replace(
            rapport, donnees=donnees, horodatage_extraction=horodatage, registre=registre
        )

    monkeypatch.setattr(composition, "construire_rapport", construire_composite)


def test_rejeu_composite_ne_differe_que_par_les_exclusions(
    racine: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    _simuler_composite(monkeypatch)
    caplog.set_level(logging.INFO, logger="usine.chaine.execution")
    for _ in range(2):
        code, erreur = _usine(monkeypatch, capsys)
        assert code == 0, erreur
    premier, second = sorted((racine / "sorties" / "passages" / DATE).iterdir())

    manifeste = json.loads((premier / FICHIERS_PASSAGE["manifeste"]).read_text(encoding="utf-8"))
    assert manifeste["palier"] == 1
    assert manifeste["source"] == "composite"
    statuts = {e["etape"]: e["statut"] for e in manifeste["etapes"]}
    for etape in composition.ETAPES_LLM:
        assert statuts[etape.value] == StatutEtape.sautee.value
    for p in (premier, second):
        assert (p / f"rapport-{DATE}.xlsx").is_file()
        assert (p / f"rapport-{DATE}.pptx").is_file()

    observees = differences(premier, second, DATE)
    assert not hors_exclusions(observees)
    assert observees >= DIFFERENCES_ATTENDUES

    messages = [r.getMessage() for r in caplog.records if r.name == "usine.chaine.execution"]
    assert any("début" in m for m in messages)
    for etape in Etape:
        assert any(f"Étape « {etape.value} »" in m for m in messages), etape
    assert sum("publié" in m for m in messages) == 2


class _Panne:
    def executer(self, ctx: ContextePassage[Consultation]) -> ResultatEtape:
        raise RuntimeError("panne du rendu")


def test_echec_du_rendu_sans_rapport_publie(
    racine: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    construire = composition.construire_rapport

    def construire_en_panne(r: Path, *args: Any, **kwargs: Any) -> composition.Rapport:
        rapport = construire(r, *args, **kwargs)
        return replace(rapport, registre={**rapport.registre, Etape.rendu: _Panne()})

    monkeypatch.setattr(composition, "construire_rapport", construire_en_panne)
    code, erreur = _usine(monkeypatch, capsys)
    assert code == 1
    assert "rendu" in erreur
    assert not list((racine / "sorties" / "passages").rglob("rapport-*"))
    assert len(list((racine / "sorties" / "echecs").iterdir())) == 1
