"""Réponses enregistrées de l'Agent pour le Mode repli (Story 7.11)."""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.unit.chaine.environnement import RACINE_DEPOT
from usine import composition
from usine.cli import app
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import ReponseAgent, ReponseAgentEnregistree, StatutControle
from usine.ia.agent.repli import (
    QUESTIONS_DEMO,
    REPERTOIRE_REPONSES,
    charger_reponses,
    enregistrer_reponses,
)
from usine.ia.agent.session import SANS_REPONSE

PASSAGE = "20261012T221158Z-96c621"
"""`passage_id` de la copie `demo/repli/passage/`."""
AUTRE = "20261001T000000Z-aaaaaa"
INSTANT = datetime(2026, 10, 12, 20, 0, tzinfo=UTC)


class SessionFactice:
    """Session qui répond « ENT-A. », ou rejette la question `rejetee`."""

    def __init__(self, passage_id: str = PASSAGE, rejetee: str | None = None) -> None:
        self.passage_id = passage_id
        self.rejetee = rejetee
        self.questions: list[str] = []
        self.fermee = False

    def repondre(self, question: str) -> ReponseAgent:
        self.questions.append(question)
        statut = StatutControle.rejete if question == self.rejetee else StatutControle.conforme
        return ReponseAgent(question=question, texte="ENT-A.", statut_controle=statut)

    def fermer(self) -> None:
        self.fermee = True


def test_enregistrer_puis_charger(tmp_path: Path) -> None:
    (tmp_path / "99.json").write_text("{}", encoding="utf-8")  # ancien fichier remplacé
    chemins = enregistrer_reponses(SessionFactice(), tmp_path, lambda: INSTANT)
    assert [c.name for c in chemins] == [f"{r:02d}.json" for r in range(1, 6)]
    assert sorted(p.name for p in tmp_path.glob("*.json")) == [c.name for c in chemins]
    reponses = charger_reponses(tmp_path, PASSAGE)
    assert [r.reponse.question for r in reponses] == list(QUESTIONS_DEMO)
    assert all(r.passage_id == PASSAGE and r.horodatage == INSTANT for r in reponses)


def test_reponse_rejetee_rien_n_est_ecrit(tmp_path: Path) -> None:
    session = SessionFactice(rejetee=QUESTIONS_DEMO[1])
    with pytest.raises(UsineErreur, match="rejetée par le contrôle"):
        enregistrer_reponses(session, tmp_path, lambda: INSTANT)
    assert not list(tmp_path.glob("*.json"))


def test_passage_different_refuse(tmp_path: Path) -> None:
    enregistrer_reponses(SessionFactice(passage_id=AUTRE), tmp_path, lambda: INSTANT)
    with pytest.raises(UsineErreur) as erreur:
        charger_reponses(tmp_path, PASSAGE)
    message = str(erreur.value)
    assert AUTRE in message and PASSAGE in message and "refusées" in message


def test_aucune_reponse_ou_illisible(tmp_path: Path) -> None:
    with pytest.raises(UsineErreur, match="usine agent --enregistrer"):
        charger_reponses(tmp_path / "absent", PASSAGE)
    (tmp_path / "01.json").write_text("{", encoding="utf-8")
    with pytest.raises(UsineErreur, match="illisible"):
        charger_reponses(tmp_path, PASSAGE)


def test_reponses_versionnees() -> None:
    """Les réponses du dépôt portent le Passage de la copie, une par question de la démo."""
    manifeste = json.loads(
        (RACINE_DEPOT / "demo/repli/passage/manifeste.json").read_text(encoding="utf-8")
    )
    assert manifeste["passage_id"] == PASSAGE
    reponses = charger_reponses(RACINE_DEPOT / REPERTOIRE_REPONSES, PASSAGE)
    assert [r.reponse.question for r in reponses] == list(QUESTIONS_DEMO)
    assert all(r.reponse.statut_controle is StatutControle.conforme for r in reponses)
    assert SANS_REPONSE in reponses[-1].reponse.texte  # question sans réponse possible
    assert "ENT-C" in reponses[0].reponse.texte  # question de la démo


def test_cli_enregistrer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shutil.copytree(RACINE_DEPOT / "demo/repli/passage", tmp_path / "demo/repli/passage")
    session = SessionFactice()
    monkeypatch.setattr(composition, "construire_session_agent", lambda *_: session)
    monkeypatch.chdir(tmp_path)
    resultat = CliRunner().invoke(app, ["agent", "--enregistrer"])
    assert resultat.exit_code == 0, resultat.output
    assert session.questions == list(QUESTIONS_DEMO) and session.fermee
    chemins = sorted((tmp_path / REPERTOIRE_REPONSES).glob("*.json"))
    assert len(chemins) == len(QUESTIONS_DEMO)
    ReponseAgentEnregistree.model_validate_json(chemins[0].read_bytes())


def test_cli_sans_copie(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    resultat = CliRunner().invoke(app, ["agent", "--enregistrer"])
    assert isinstance(resultat.exception, UsineErreur)
    assert "copie du Passage du Mode repli absente" in str(resultat.exception)
