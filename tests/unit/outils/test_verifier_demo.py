"""Outil `outils/verifier_demo.py` (Story 7.12) : déroulé de la démo en Mode repli, sans réseau."""

import json
import shutil
from pathlib import Path

import pytest

from outils import verifier_demo
from outils.verifier_demo import (
    FICHIER_CONFIG_DEMO,
    FICHIER_FICHE,
    REPERTOIRE_REPLI,
    REPERTOIRE_REPONSES,
    Resultat,
    compte_rendu,
    verifier,
)
from usine.contrats.erreurs import UsineErreur
from usine.contrats.meteo import Couleur
from usine.ia.agent import repli
from usine.ui import avant_apres, detail, outillage
from usine.ui import cli as ui_cli

DEPOT = Path(__file__).resolve().parents[3]


def _pseudo(texte: str) -> str:
    return texte.replace("ENT-", "ENT_")


@pytest.fixture
def racine(tmp_path: Path) -> Path:
    """Copie de ce que lit la démo en Mode repli : Passage, réponses, config et fiche."""
    shutil.copytree(DEPOT / "demo" / "repli", tmp_path / "demo" / "repli")
    for relatif in (FICHIER_CONFIG_DEMO, FICHIER_FICHE):
        (tmp_path / relatif).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(DEPOT / relatif, tmp_path / relatif)
    return tmp_path


def _echecs(resultats: list[Resultat]) -> dict[str, str]:
    return {r.sequence: r.detail for r in resultats if not r.ok}


def test_constantes_alignees_sur_l_ui() -> None:
    assert REPERTOIRE_REPLI == ui_cli.REPERTOIRE_REPLI
    assert REPERTOIRE_REPONSES == repli.REPERTOIRE_REPONSES
    assert Path(avant_apres.FICHIER_CONFIG) == FICHIER_CONFIG_DEMO
    assert FICHIER_FICHE == outillage.FICHIER_FICHE
    assert verifier_demo.MESSAGE_PALIER_1 == detail.EXPLICATION_PALIER_1


def test_reponses_identiques_a_celles_de_l_ui(racine: Path) -> None:
    passage_id = ui_cli.consultation_repli(racine).manifeste().passage_id  # type: ignore[union-attr]
    assert verifier_demo.charger_reponses(racine, passage_id) == ui_cli.reponses_repli(
        racine, passage_id
    )


def test_deroule_complet_sur_la_copie_versionnee(racine: Path) -> None:
    resultats = verifier(racine, apercu=_pseudo)
    assert _echecs(resultats) == {}
    assert len(resultats) == 9
    texte = compte_rendu(resultats)
    assert "rouges : ENT-A, ENT-B ; ENT-C orange" in texte
    assert "commentaire non généré (Palier 1)" in texte
    assert "5 réponses conformes" in texte
    assert "Bilan : déroulé complet" in texte


def test_main_code_0(
    racine: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(verifier_demo, "apercu_pseudonymisation", lambda _racine: _pseudo)
    assert verifier_demo.main(["--racine", str(racine)]) == 0
    assert "déroulé complet" in capsys.readouterr().out


def test_copie_absente(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert verifier_demo.main(["--racine", str(tmp_path)]) == 1
    sortie = capsys.readouterr().out
    assert "[KO] 0. Chargement du Passage de repli" in sortie
    assert "copie du Mode repli absente" in sortie


def test_reponse_d_un_autre_passage(racine: Path) -> None:
    chemin = racine / REPERTOIRE_REPONSES / "03.json"
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    contenu["passage_id"] = "20261001T000000Z-000000"
    chemin.write_text(json.dumps(contenu), encoding="utf-8")
    echecs = _echecs(verifier(racine, apercu=_pseudo))
    assert list(echecs) == ["7. Agent (réponses enregistrées)"]
    assert (
        "03.json porte le Passage 20261001T000000Z-000000"
        in echecs["7. Agent (réponses enregistrées)"]
    )


def test_aucune_reponse(racine: Path) -> None:
    shutil.rmtree(racine / REPERTOIRE_REPONSES)
    assert (
        "aucune réponse enregistrée"
        in _echecs(verifier(racine, apercu=_pseudo))["7. Agent (réponses enregistrées)"]
    )


def test_meteo_inattendue(racine: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(verifier_demo, "COULEURS_ATTENDUES", {"ENT-C": Couleur.rouge})
    assert (
        "ENT-C orange (attendu rouge)"
        in _echecs(verifier(racine, apercu=_pseudo))["2. Carte météo"]
    )


def test_config_et_fiche_absentes(racine: Path) -> None:
    (racine / FICHIER_CONFIG_DEMO).unlink()
    (racine / FICHIER_FICHE).unlink()
    echecs = _echecs(verifier(racine, apercu=_pseudo))
    assert set(echecs) == {"1. Avant / après", "8. Ce qu'il faut pour le faire en vrai"}


def test_pseudonymisation_sans_effet_ou_sans_cle(racine: Path) -> None:
    def sans_cle(_texte: str) -> str:
        raise UsineErreur("Variable d'environnement USINE_CLE_PSEUDO absente ou vide")

    cle = "6. Pseudonymisation"
    assert "ne change" in _echecs(verifier(racine, apercu=lambda texte: texte))[cle]
    assert "USINE_CLE_PSEUDO" in _echecs(verifier(racine, apercu=sans_cle))[cle]
