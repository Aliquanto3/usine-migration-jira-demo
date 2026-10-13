"""Écran Agent de la page Streamlit (`AppTest`) avec une session factice (Story 7.9)."""

import json
import shutil
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tests.doublures.fournisseur_factice import FournisseurFactice, ReponseAgentScriptee
from tests.unit.ia.espions import INSTANT, CacheMemoire, pseudonymiseur
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import AppelOutil, ReponseAgent, StatutControle
from usine.ia.agent.repli import QUESTIONS_DEMO, REPERTOIRE_REPONSES, charger_reponses
from usine.ia.agent.session import SANS_REPONSE, SessionAgent
from usine.ia.passerelle import Passerelle
from usine.ports.consultation import Consultation
from usine.ui import agent, cli, lancement, navigation
from usine.ui.liens import echapper_markdown
from usine.ui.navigation import Ecran

APP = Path(lancement.__file__).parent / "app.py"
PASSAGE_REPLI = "20261012T221158Z-96c621"
APPEL_METEO = AppelOutil(id_appel="a1", nom_outil="get_meteo", arguments={})


def _page() -> AppTest:
    page = AppTest.from_file(str(APP), default_timeout=60).run()
    page.sidebar.radio[0].set_value(Ecran.agent.value).run()
    return page


def _session_factice(
    monkeypatch: pytest.MonkeyPatch, traces: Path, scripts: list[ReponseAgentScriptee]
) -> FournisseurFactice:
    fournisseur = FournisseurFactice(reponses_agent=scripts)

    def session_agent(racine: Path, consultation: Consultation) -> SessionAgent:
        passerelle = Passerelle(fournisseur, pseudonymiseur(), CacheMemoire(), lambda: INSTANT)
        return SessionAgent(passerelle, consultation, traces, lambda: INSTANT, "session-ui")

    monkeypatch.setattr(cli, "session_agent", session_agent)
    return fournisseur


def _poser(page: AppTest) -> AppTest:
    page.button[0].click().run()
    return page


def test_question_de_la_demo(
    racine_publiee: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(racine_publiee)
    texte = "ENT-A est suivie par la météo du Passage."
    fournisseur = _session_factice(
        monkeypatch, tmp_path, [ReponseAgentScriptee(texte, (APPEL_METEO,))]
    )
    page = _page()
    assert not page.exception
    assert page.subheader[0].value == Ecran.agent.value
    assert page.text_input[0].value == agent.QUESTION_DEMO
    _poser(page)
    assert not page.exception
    assert not page.error
    assert texte in [str(m.value) for m in page.markdown]
    reponse = ReponseAgent(
        question=agent.QUESTION_DEMO,
        texte=texte,
        outils_appeles=("get_meteo",),
        statut_controle=StatutControle.conforme,
    )
    legendes = [c.value for c in page.caption]
    assert agent.texte_statut(reponse) in legendes
    assert agent.texte_outils(reponse) in legendes
    assert len(fournisseur.appels) == 1
    assert list((tmp_path / "sorties" / "agent").rglob("session-ui.jsonl"))


def test_reponse_rejetee(
    racine_publiee: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(racine_publiee)
    _session_factice(monkeypatch, tmp_path, [ReponseAgentScriptee("ENT-A a 42 Anomalies.")])
    page = _poser(_page())
    assert not page.exception
    (avertissement,) = page.warning
    assert "« 42 »" in avertissement.value
    assert f"Contrôle : {agent.LIBELLES_STATUT[StatutControle.rejete]}" in [
        c.value for c in page.caption
    ]
    assert "Outils appelés : aucun" in [c.value for c in page.caption]


def test_session_gardee_entre_deux_questions(
    racine_publiee: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(racine_publiee)
    construites: list[SessionAgent] = []
    fournisseur = FournisseurFactice(
        reponses_agent=[ReponseAgentScriptee(SANS_REPONSE), ReponseAgentScriptee(SANS_REPONSE)]
    )

    def session_agent(racine: Path, consultation: Consultation) -> SessionAgent:
        passerelle = Passerelle(fournisseur, pseudonymiseur(), CacheMemoire(), lambda: INSTANT)
        session = SessionAgent(passerelle, consultation, tmp_path, lambda: INSTANT, "s")
        construites.append(session)
        return session

    monkeypatch.setattr(cli, "session_agent", session_agent)
    page = _poser(_page())
    page.text_input[0].set_value("Autre question ?")
    _poser(page)
    assert not page.exception
    assert len(construites) == 1
    assert len(fournisseur.appels) == 2


def test_session_impossible(racine_publiee: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(racine_publiee)

    def session_agent(racine: Path, consultation: Consultation) -> SessionAgent:
        raise UsineErreur("config/llm.yaml absent")

    monkeypatch.setattr(cli, "session_agent", session_agent)
    page = _poser(_page())
    assert not page.exception
    (erreur,) = page.error
    assert "Agent indisponible" in erreur.value
    assert "config/llm.yaml absent" in erreur.value


def _page_repli(racine: Path, monkeypatch: pytest.MonkeyPatch) -> AppTest:
    monkeypatch.chdir(racine)
    monkeypatch.setenv("USINE_MODE_REPLI", "1")

    def session_agent(racine: Path, consultation: Consultation) -> SessionAgent:
        raise AssertionError("aucune session en Mode repli")

    monkeypatch.setattr(cli, "session_agent", session_agent)
    return _page()


def test_mode_repli_questions_en_choix_fermes(
    racine_publiee: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = _page_repli(racine_publiee, monkeypatch)
    assert not page.exception
    assert agent.MESSAGE_REPLI in [i.value for i in page.info]
    assert not page.text_input  # pas de saisie libre
    choix = page.radio(key=navigation.CLE_CHOIX_AGENT)
    assert list(choix.options) == list(QUESTIONS_DEMO)
    choix.set_value(2).run()
    page.button[0].click().run()
    assert not page.exception
    assert not page.error
    (enregistree,) = [
        e
        for e in charger_reponses(racine_publiee / REPERTOIRE_REPONSES, PASSAGE_REPLI)
        if e.reponse.question == QUESTIONS_DEMO[2]
    ]
    assert echapper_markdown(enregistree.reponse.texte) in [str(m.value) for m in page.markdown]
    legendes = [c.value for c in page.caption]
    assert agent.mention_repli(enregistree) in legendes
    assert "Mode repli" in agent.mention_repli(enregistree)
    assert agent.texte_outils(enregistree.reponse) in legendes


def test_mode_repli_passage_different_refuse(
    racine_publiee: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    racine = tmp_path / "racine"
    shutil.copytree(racine_publiee / "demo", racine / "demo")
    chemin = racine / REPERTOIRE_REPONSES / "01.json"
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    contenu["passage_id"] = "20261001T000000Z-aaaaaa"
    chemin.write_text(json.dumps(contenu), encoding="utf-8")
    page = _page_repli(racine, monkeypatch)
    assert not page.exception
    (erreur,) = page.error
    assert agent.REFUS_REPLI in erreur.value
    assert "20261001T000000Z-aaaaaa" in erreur.value
    assert PASSAGE_REPLI in erreur.value
    assert not page.button


def test_mode_repli_sans_reponses(
    racine_publiee: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    racine = tmp_path / "racine"
    shutil.copytree(racine_publiee / "demo" / "repli" / "passage", racine / "demo/repli/passage")
    page = _page_repli(racine, monkeypatch)
    assert not page.exception
    (erreur,) = page.error
    assert "usine agent --enregistrer" in erreur.value
