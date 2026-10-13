"""Suite d'évaluation de l'Agent (Story 7.10, SM-4, FR-42) : rejeu hors réseau.

Le mode `--reel` (réseau, secrets, coût) n'est jamais lancé ici.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from evals.agent import __main__ as cli
from evals.agent.questions import (
    CHEMIN_QUESTIONS,
    NOMBRE_QUESTIONS,
    QUESTION_DEMO,
    FichierQuestions,
    QuestionAgent,
    TourEnregistre,
    charger_questions,
)
from evals.agent.suite import (
    FournisseurAgentEnregistre,
    contient_chiffre,
    contient_mot,
    executer_suite,
)
from usine.contrats.erreurs import UsineErreur
from usine.ports.fournisseur_llm import FournisseurLLM

INSTANT = datetime(2026, 10, 13, 7, 30, tzinfo=UTC)
RACINE = Path(__file__).resolve().parents[4]
PASSAGE = RACINE / "demo" / "repli" / "passage"
SANS_REPONSE = "Les données ne permettent pas de répondre."


@pytest.fixture(scope="module")
def fichier() -> FichierQuestions:
    return charger_questions()


@pytest.fixture(scope="module")
def resultat(fichier: FichierQuestions, tmp_path_factory: pytest.TempPathFactory) -> Any:
    return executer_suite(fichier, tmp_path_factory.mktemp("racine"), PASSAGE, horloge=INSTANT)


def _question(resultat: Any, identifiant: str) -> Any:
    return next(q for q in resultat["questions"] if q["identifiant"] == identifiant)


def _avec_texte(fichier: FichierQuestions, identifiant: str, texte: str) -> FichierQuestions:
    questions = tuple(
        q.model_copy(update={"tour": TourEnregistre(appels=q.tour.appels, texte=texte)})
        if q.identifiant == identifiant and q.tour is not None
        else q
        for q in fichier.questions
    )
    return fichier.model_copy(update={"questions": questions})


def _fichiers(repertoire: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in sorted(repertoire.rglob("*")) if p.is_file()}


def test_fournisseur_enregistre_implemente_le_port() -> None:
    assert isinstance(FournisseurAgentEnregistre({}), FournisseurLLM)


def test_quinze_questions_dont_la_demo_et_deux_sans_reponse(fichier: FichierQuestions) -> None:
    assert len(fichier.questions) == NOMBRE_QUESTIONS == 15
    (demo,) = [q for q in fichier.questions if q.demo]
    assert demo.question == QUESTION_DEMO
    assert QUESTION_DEMO == (
        "Quelles entités risquent de passer au rouge la semaine prochaine, et pourquoi ?"
    )
    assert sum(not q.repondable for q in fichier.questions) >= 2
    assert sum(q.repondable for q in fichier.questions) == 13
    assert all(q.tour is not None for q in fichier.questions)
    assert fichier.passage_id == "20261012T221158Z-96c621"


def test_rejeu_nominal_quinze_sur_quinze(resultat: Any) -> None:
    assert resultat["mode"] == "rejeu"
    assert resultat["passage_id"] == "20261012T221158Z-96c621"
    assert resultat["nombre_questions"] == 15
    assert resultat["nombre_repondables"] == 13
    assert resultat["score"] == 15
    assert resultat["chiffres_inventes"] == 0
    assert resultat["tickets_inventes"] == 0
    assert resultat["refus_repondables"] == 0
    assert resultat["sm4_atteint"] is True
    assert resultat["version_modele"] == "enregistre:rejeu"
    assert all(q["statut_controle"] == "conforme" for q in resultat["questions"])


def test_question_de_la_demo(resultat: Any) -> None:
    demo = _question(resultat, "q01")
    assert demo["demo"] and demo["reussie"]
    assert demo["outils_appeles"] == ["get_risques", "get_meteo"]
    assert contient_mot(demo["texte"], "ENT-C") and contient_mot(demo["texte"], "IND-4")
    assert "DEMO-2350" in demo["tickets_cites"]


def test_questions_sans_reponse_reussies(resultat: Any) -> None:
    sans_reponse = [q for q in resultat["questions"] if not q["repondable"]]
    assert len(sans_reponse) >= 2
    assert all(q["reussie"] and q["texte"] == SANS_REPONSE for q in sans_reponse)
    assert not any(q["refus"] for q in sans_reponse)


def test_traces_hors_du_passage(fichier: FichierQuestions, tmp_path: Path) -> None:
    avant = _fichiers(PASSAGE)
    resultat = executer_suite(fichier, tmp_path, PASSAGE, horloge=INSTANT)
    traces = Path(resultat["traces"])
    assert traces.is_relative_to(tmp_path / "sorties" / "agent")
    lignes = traces.read_text("utf-8").splitlines()
    appels = sum(len(q.tour.appels) for q in fichier.questions if q.tour is not None)
    assert len(lignes) == appels + NOMBRE_QUESTIONS  # une trace par outil, une par réponse
    assert _fichiers(PASSAGE) == avant


def test_chiffre_invente_compte(fichier: FichierQuestions, tmp_path: Path) -> None:
    modifie = _avec_texte(fichier, "q02", "ENT-A et ENT-B sont rouges sur IND-1 : 42 et 9.")
    resultat = executer_suite(modifie, tmp_path, PASSAGE, horloge=INSTANT)
    q02 = _question(resultat, "q02")
    assert not q02["reussie"]
    assert q02["statut_controle"] == "rejete"
    assert q02["chiffres_inventes"] == 1
    assert q02["chiffres_refuses"] == ["42"]
    assert resultat["chiffres_inventes"] == 1
    assert resultat["score"] == 14
    assert resultat["sm4_atteint"] is False


def test_ticket_invente_compte(fichier: FichierQuestions, tmp_path: Path) -> None:
    modifie = _avec_texte(fichier, "q07", "ENT-E est jaune sur IND-6 à cause de DEMO-99999.")
    resultat = executer_suite(modifie, tmp_path, PASSAGE, horloge=INSTANT)
    q07 = _question(resultat, "q07")
    assert not q07["reussie"]
    assert q07["tickets_refuses"] == ["DEMO-99999"]
    assert resultat["tickets_inventes"] == 1
    assert resultat["chiffres_inventes"] == 0


def test_refus_sur_une_repondable(fichier: FichierQuestions, tmp_path: Path) -> None:
    modifie = _avec_texte(fichier, "q03", SANS_REPONSE)
    resultat = executer_suite(modifie, tmp_path, PASSAGE, horloge=INSTANT)
    q03 = _question(resultat, "q03")
    assert not q03["reussie"]
    assert q03["refus"]
    assert resultat["refus_repondables"] == 1
    assert resultat["score"] == 14
    assert resultat["sm4_atteint"] is True  # 14 ≥ 13, aucun chiffre inventé, 1 refus toléré


def test_element_attendu_manquant(fichier: FichierQuestions, tmp_path: Path) -> None:
    modifie = _avec_texte(fichier, "q08", "ENT-C a des Anomalies ouvertes, dont DEMO-1922.")
    resultat = executer_suite(modifie, tmp_path, PASSAGE, horloge=INSTANT)
    q08 = _question(resultat, "q08")
    assert q08["statut_controle"] == "conforme"
    assert not q08["reussie"]
    assert q08["manquants"] == {"entites": [], "tickets": [], "chiffres": ["70"]}


def test_sans_reponse_mal_traitee(fichier: FichierQuestions, tmp_path: Path) -> None:
    modifie = _avec_texte(fichier, "q14", "Le budget est inconnu.")
    resultat = executer_suite(modifie, tmp_path, PASSAGE, horloge=INSTANT)
    assert not _question(resultat, "q14")["reussie"]
    assert resultat["refus_repondables"] == 0


def test_passage_different_arrete(fichier: FichierQuestions, tmp_path: Path) -> None:
    autre = fichier.model_copy(update={"passage_id": "20260101T000000Z-000000"})
    with pytest.raises(UsineErreur) as erreur:
        executer_suite(autre, tmp_path, PASSAGE, horloge=INSTANT)
    assert "20260101T000000Z-000000" in str(erreur.value)
    assert "20261012T221158Z-96c621" in str(erreur.value)


def test_passage_different_code_de_sortie(
    fichier: FichierQuestions, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    donnees = json.loads(CHEMIN_QUESTIONS.read_text("utf-8"))
    donnees["passage_id"] = "20260101T000000Z-000000"
    chemin = tmp_path / "questions.json"
    chemin.write_text(json.dumps(donnees, ensure_ascii=False), encoding="utf-8")
    code = cli.main(
        [
            *("executer", "--questions", str(chemin), "--racine", str(tmp_path)),
            *("--passage", str(PASSAGE), "--sortie", str(tmp_path / "res")),
            *("--historique", str(tmp_path / "historique.jsonl")),
        ]
    )
    assert code == 1
    erreur = capsys.readouterr().err
    assert "20260101T000000Z-000000" in erreur and "20261012T221158Z-96c621" in erreur
    assert not (tmp_path / "res").exists()


def test_tour_absent_nomme_la_question(fichier: FichierQuestions, tmp_path: Path) -> None:
    questions = tuple(
        q.model_copy(update={"tour": None}) if q.identifiant == "q05" else q
        for q in fichier.questions
    )
    with pytest.raises(UsineErreur, match="q05"):
        executer_suite(
            fichier.model_copy(update={"questions": questions}), tmp_path, PASSAGE, horloge=INSTANT
        )


def test_cli_publie_le_score_et_l_historique(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    historique = tmp_path / "historique.jsonl"
    code = cli.main(
        [
            *("executer", "--racine", str(tmp_path), "--passage", str(PASSAGE)),
            *("--sortie", str(tmp_path / "res"), "--historique", str(historique)),
        ]
    )
    assert code == 0
    sortie = capsys.readouterr().out
    assert "Score : 15/15" in sortie
    assert "Chiffres inventés : 0" in sortie
    assert "Refus sur les 13 questions répondables : 0" in sortie
    assert "SM-4 atteint : oui" in sortie
    (chemin,) = (tmp_path / "res").glob("*.json")
    assert json.loads(chemin.read_text("utf-8"))["score"] == 15
    (ligne,) = historique.read_text("utf-8").splitlines()
    entree = json.loads(ligne)
    assert entree["resultat"] == chemin.name
    assert entree["score"] == 15 and entree["sm4_atteint"] is True


def _ecrire(tmp_path: Path, transformer: Any) -> Path:
    donnees = json.loads(CHEMIN_QUESTIONS.read_text("utf-8"))
    transformer(donnees)
    chemin = tmp_path / "questions.json"
    chemin.write_text(json.dumps(donnees, ensure_ascii=False), encoding="utf-8")
    return chemin


def test_moins_de_quinze_questions_refuse(tmp_path: Path) -> None:
    chemin = _ecrire(tmp_path, lambda d: d["questions"].pop())
    with pytest.raises(UsineErreur, match="14 question"):
        charger_questions(chemin)


def test_deux_questions_demo_refuse(tmp_path: Path) -> None:
    chemin = _ecrire(tmp_path, lambda d: d["questions"][1].update(demo=True))
    with pytest.raises(UsineErreur, match="2 question"):
        charger_questions(chemin)


def test_question_demo_modifiee_refusee(tmp_path: Path) -> None:
    chemin = _ecrire(tmp_path, lambda d: d["questions"][0].update(question="Autre ?"))
    with pytest.raises(UsineErreur, match="démo"):
        charger_questions(chemin)


def test_une_seule_sans_reponse_refusee(tmp_path: Path) -> None:
    chemin = _ecrire(tmp_path, lambda d: d["questions"][-1].update(repondable=True))
    with pytest.raises(UsineErreur, match="sans réponse"):
        charger_questions(chemin)


def test_question_mal_formee_nomme_le_fichier(tmp_path: Path) -> None:
    chemin = _ecrire(tmp_path, lambda d: d["questions"][0].update(inconnu=1))
    with pytest.raises(UsineErreur, match="mal formées"):
        charger_questions(chemin)


@pytest.mark.parametrize(
    ("texte", "chiffre", "attendu"),
    [
        ("IND-4 vaut 27 sur 150.", "27", True),
        ("IND-4 vaut 270.", "27", False),
        ("IND-4 vaut 2,7.", "2", False),
        ("Voir IND-4.", "4", False),
        ("Voir DEMO-27.", "27", False),
        ("1 100 Anomalies", "1 100", True),
        ("1 100 Anomalies", "1 100", True),
        ("1 100 Anomalies", "100", False),
        ("1 100 Anomalies", "1", False),
        ("estimé au 2026-10-14.", "2026-10-14", True),
        ("estimé au 2026-10-14.", "14", False),
        ("probabilité de 0,5.", "0,5", True),
    ],
)
def test_contient_chiffre(texte: str, chiffre: str, attendu: bool) -> None:
    assert contient_chiffre(texte, chiffre) is attendu


@pytest.mark.parametrize(
    ("texte", "element", "attendu"),
    [
        ("ENT-C risque le rouge.", "ENT-C", True),
        ("ENT-CD risque le rouge.", "ENT-C", False),
        ("Voir DEMO-23500.", "DEMO-2350", False),
        ("Voir DEMO-2350, DEMO-2414.", "DEMO-2350", True),
        ("IND-40 monte.", "IND-4", False),
    ],
)
def test_contient_mot(texte: str, element: str, attendu: bool) -> None:
    assert contient_mot(texte, element) is attendu


def test_question_sans_tour_valide() -> None:
    question = QuestionAgent(identifiant="x", question="Q ?", repondable=False)
    assert question.tour is None
