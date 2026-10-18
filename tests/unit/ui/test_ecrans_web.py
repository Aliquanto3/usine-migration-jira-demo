"""Agent, Avant / après, Pseudonymisation et Outillage de l'UI web (Story 7.16, AD-25).

Aucun LLM ni moteur Presidio réel : la session de l'Agent et l'aperçu sont des doublures
injectées par `ServicesEcrans`, comme les services réels le sont par `ui/cli.py`.
"""

import json
import shutil
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.unit.ui.test_avant_apres import manifeste, publier
from usine.contrats.erreurs import UsineErreur
from usine.contrats.format import ESPACE_INSECABLE
from usine.contrats.llm import ReponseAgent, StatutControle
from usine.ia.agent.repli import QUESTIONS_DEMO, REPERTOIRE_REPONSES
from usine.ia.agent.session import SANS_REPONSE
from usine.ui import agent, avant_apres, cli, outillage, pseudonymisation
from usine.ui.chaine import GestionChaine
from usine.ui.ecrans import (
    BADGE_HORS_PERIMETRE,
    GardeSession,
    ServicesEcrans,
    SessionIndisponible,
    vue_reponse_agent,
)
from usine.ui.outillage import rendre_fiche
from usine.ui.serveur import HOTE, REPERTOIRE_STATIQUE, REPONSE_IMPOSSIBLE, creer_application
from usine.ui.textes import REPLI_ABSENT

PASSAGE_REPLI = "20261012T221158Z-96c621"


class SessionFactice:
    """Session de l'Agent qui rejoue des réponses scriptées, sans LLM."""

    def __init__(self, passage_id: str, reponses: list[ReponseAgent | Exception]) -> None:
        self._passage_id = passage_id
        self.reponses = reponses
        self.questions: list[str] = []
        self.fermee = False

    @property
    def passage_id(self) -> str:
        return self._passage_id

    def repondre(self, question: str) -> ReponseAgent:
        self.questions.append(question)
        suivante = self.reponses.pop(0)
        if isinstance(suivante, Exception):
            raise suivante
        return suivante

    def fermer(self) -> None:
        self.fermee = True


def reponse(
    texte: str = "ENT-B est rouge.",
    statut: StatutControle = StatutControle.conforme,
    outils: tuple[str, ...] = ("get_meteo",),
) -> ReponseAgent:
    return ReponseAgent(
        question="Pourquoi ENT-B est-elle rouge ?",
        texte=texte,
        outils_appeles=outils,
        statut_controle=statut,
    )


def application(
    racine: Path,
    *,
    repli: bool = False,
    **remplacements: Any,
) -> TestClient:
    services = replace(cli.services_ecrans(racine), **remplacements)
    return TestClient(
        creer_application(
            repli=repli,
            lire_manifeste=cli.lecture_manifeste(racine),
            lire_consultation=cli.lecture_consultation(racine),
            chaine=GestionChaine(None),
            services=services,
        ),
        base_url=f"http://{HOTE}",
    )


def fabrique(session: SessionFactice, appels: list[str] | None = None) -> Callable[..., Any]:
    def construire(_consultation: Any) -> SessionFactice:
        if appels is not None:
            appels.append("construite")
        return session

    return construire


# --- Agent : Mode réel ---


def test_agent_reel_saisie_suggestions_et_outils(racine_publiee: Path) -> None:
    vue = application(racine_publiee).get("/api/agent").json()
    assert vue["mode"] == "reel"
    assert vue["erreur"] is None
    assert vue["message_repli"] is None
    assert vue["saisie"]["valeur_defaut"] == agent.QUESTION_DEMO
    assert vue["saisie"]["libelle"] == agent.LIBELLE_QUESTION
    assert vue["legende"] == agent.LEGENDE
    assert [q["question"] for q in vue["questions"]] == list(QUESTIONS_DEMO)
    assert [o["nom"] for o in vue["outils"]] == [
        "get_meteo",
        "list_anomalies",
        "get_tendance",
        "get_prevision",
        "get_risques",
    ]
    assert vue["attente"] == "L'Agent consulte le Passage…"


def test_agent_reel_sans_passage_publie(tmp_path: Path) -> None:
    vue = application(tmp_path).get("/api/agent").json()
    assert vue["message"] == agent.AUCUN_PASSAGE
    assert vue["lien_message"]["url"] == "/chaine"
    assert vue["saisie"] is None


def test_question_passe_par_la_session_existante(racine_publiee: Path) -> None:
    manifeste_publie = cli.lecture_manifeste(racine_publiee)(False)
    assert manifeste_publie is not None
    session = SessionFactice(manifeste_publie.passage_id, [reponse(), reponse("Autre texte.")])
    construites: list[str] = []
    client = application(racine_publiee, session_agent=fabrique(session, construites))
    premiere = client.post("/api/agent/question", json={"question": "  Pourquoi ENT-B ?  "})
    assert premiere.status_code == 200
    vue = premiere.json()
    assert vue["texte"] == "ENT-B est rouge."
    assert vue["badge"] == agent.texte_statut(reponse())
    assert vue["badge_code"] == "conforme"
    assert vue["outils"] == ["get_meteo"]
    assert vue["libelle_outils"] == "Outils appelés :"
    assert vue["mention_repli"] is None
    assert vue["annonce"] == "Réponse de l'Agent reçue"
    second = client.post("/api/agent/question", json={"question": "Et ENT-C ?"}).json()
    assert second["texte"] == "Autre texte."
    assert session.questions == ["Pourquoi ENT-B ?", "Et ENT-C ?"]  # question nettoyée
    assert construites == ["construite"]  # une seule session, gardée d'une question à l'autre


def test_reponse_rejetee_n_expose_pas_son_texte(racine_publiee: Path) -> None:
    secret = "ENT-Z vaut 999 (texte faux rejeté)"
    session = SessionFactice("p", [reponse(secret, StatutControle.rejete, ())])
    client = application(racine_publiee, session_agent=fabrique(session))
    brut = client.post("/api/agent/question", json={"question": "Q ?"})
    assert brut.status_code == 200
    assert secret not in brut.text
    vue = brut.json()
    assert vue["texte"] is None
    assert "n'est pas affiché" in vue["texte_masque"]
    assert vue["badge_code"] == "rejete"
    assert vue["aucun_outil"] == "aucun"


def test_refus_hors_perimetre(racine_publiee: Path) -> None:
    session = SessionFactice("p", [reponse(SANS_REPONSE, outils=())])
    client = application(racine_publiee, session_agent=fabrique(session))
    vue = client.post("/api/agent/question", json={"question": "Budget ?"}).json()
    assert vue["badge"] == BADGE_HORS_PERIMETRE
    assert vue["badge_code"] == "hors_perimetre"
    assert vue["outils"] == []


def test_question_vide_ou_invalide_refusee(racine_publiee: Path) -> None:
    session = SessionFactice("p", [])
    client = application(racine_publiee, session_agent=fabrique(session))
    for corps in ({"question": ""}, {"question": "   "}, {}, {"question": "a", "x": 1}):
        assert client.post("/api/agent/question", json=corps).status_code == 422
    assert client.post("/api/agent/question", content="question=a").status_code == 422
    assert session.questions == []


def test_question_origine_etrangere_refusee(racine_publiee: Path) -> None:
    session = SessionFactice("p", [reponse()])
    client = application(racine_publiee, session_agent=fabrique(session))
    refus = client.post(
        "/api/agent/question", json={"question": "Q ?"}, headers={"Origin": "http://evil.test"}
    )
    assert refus.status_code == 403
    assert session.questions == []
    mauvais_hote = client.post(
        "/api/agent/question", json={"question": "Q ?"}, headers={"Host": "evil.test:8000"}
    )
    assert mauvais_hote.status_code == 400


def test_agent_indisponible_et_reponse_impossible(racine_publiee: Path) -> None:
    def echouer(_consultation: Any) -> SessionFactice:
        raise UsineErreur("USINE_CLE_LLM absente")

    client = application(racine_publiee, session_agent=echouer)
    refus = client.post("/api/agent/question", json={"question": "Q ?"})
    assert refus.status_code == 503
    assert "Agent indisponible" in refus.json()["detail"]
    assert "USINE_CLE_LLM absente" in refus.json()["detail"]

    session = SessionFactice("p", [RuntimeError("https://fournisseur.test/v1 cle=sk-secret")])
    client = application(racine_publiee, session_agent=fabrique(session))
    refus = client.post("/api/agent/question", json={"question": "Q ?"})
    assert refus.status_code == 502
    assert refus.json()["detail"] == REPONSE_IMPOSSIBLE  # détail au journal du serveur seulement
    assert "sk-secret" not in refus.text
    assert "fournisseur.test" not in refus.text


def test_question_sans_passage_ou_en_mode_repli(racine_publiee: Path, tmp_path: Path) -> None:
    session = SessionFactice("p", [reponse()])
    assert (
        application(tmp_path, session_agent=fabrique(session))
        .post("/api/agent/question", json={"question": "Q ?"})
        .status_code
        == 409
    )
    repli = application(racine_publiee, repli=True, session_agent=fabrique(session))
    refus = repli.post("/api/agent/question", json={"question": "Q ?"})
    assert refus.status_code == 409
    assert session.questions == []  # aucun appel au LLM en Mode repli


def test_la_session_change_avec_le_passage() -> None:
    class Passage:
        def __init__(self, passage_id: str) -> None:
            self.passage_id = passage_id

        def manifeste(self) -> Any:
            return self

    sessions: list[SessionFactice] = []

    def construire(consultation: Any) -> SessionFactice:
        session = SessionFactice(consultation.passage_id, [reponse(), reponse(), reponse()])
        sessions.append(session)
        return session

    garde = GardeSession(construire)
    garde.repondre(Passage("a"), "Q1")  # type: ignore[arg-type]
    garde.repondre(Passage("a"), "Q2")  # type: ignore[arg-type]
    assert len(sessions) == 1
    garde.repondre(Passage("b"), "Q3")  # type: ignore[arg-type]
    assert len(sessions) == 2
    assert sessions[0].fermee is True
    assert sessions[1].questions == ["Q3"]


def test_construction_refusee_est_une_session_indisponible() -> None:
    class Passage:
        passage_id = "a"

        def manifeste(self) -> Any:
            return self

    def echouer(_consultation: Any) -> SessionFactice:
        raise UsineErreur("config/llm.yaml absent")

    with pytest.raises(SessionIndisponible, match=r"config/llm\.yaml absent"):
        GardeSession(echouer).repondre(Passage(), "Q")  # type: ignore[arg-type]


# --- Agent : Mode repli ---


def test_agent_repli_sans_saisie_questions_enregistrees(racine_publiee: Path) -> None:
    client = application(racine_publiee, repli=True)
    vue = client.get("/api/agent").json()
    assert vue["mode"] == "repli"
    assert vue["saisie"] is None
    assert vue["message_repli"] == agent.MESSAGE_REPLI
    assert vue["erreur"] is None
    assert [q["question"] for q in vue["questions"]] == list(QUESTIONS_DEMO)
    assert [q["rang"] for q in vue["questions"]] == [0, 1, 2, 3, 4]


def test_agent_repli_rejoue_la_reponse_avec_sa_mention(racine_publiee: Path) -> None:
    client = application(racine_publiee, repli=True)
    brut = client.get("/api/agent/enregistrees/0")
    assert brut.status_code == 200
    vue = brut.json()
    enregistree = json.loads(
        (racine_publiee / REPERTOIRE_REPONSES / "01.json").read_text(encoding="utf-8")
    )
    assert vue["texte"] == enregistree["reponse"]["texte"]
    assert vue["outils"] == enregistree["reponse"]["outils_appeles"]
    assert vue["mention_repli"].startswith("Mode repli : réponse enregistrée le ")
    assert PASSAGE_REPLI in vue["mention_repli"]
    assert "sans LLM" in vue["mention_repli"]
    refus = client.get("/api/agent/enregistrees/4").json()  # la question hors périmètre
    assert refus["badge_code"] == "hors_perimetre"
    assert client.get("/api/agent/enregistrees/99").status_code == 404
    assert client.get("/api/agent/enregistrees/-1").status_code == 404
    assert application(racine_publiee).get("/api/agent/enregistrees/0").status_code == 409


def test_reponses_d_un_autre_passage_refusees(racine_publiee: Path, tmp_path: Path) -> None:
    shutil.copytree(racine_publiee / "demo", tmp_path / "demo")
    chemin = tmp_path / REPERTOIRE_REPONSES / "02.json"
    chemin.write_text(
        chemin.read_text(encoding="utf-8").replace(PASSAGE_REPLI, "20260101T000000Z-bbbbbb"),
        encoding="utf-8",
    )
    client = application(tmp_path, repli=True)
    vue = client.get("/api/agent").json()
    assert vue["erreur"].startswith(agent.REFUS_REPLI)
    assert vue["questions"] == []
    assert vue["saisie"] is None
    rejeu = client.get("/api/agent/enregistrees/0")
    assert rejeu.status_code == 409
    assert rejeu.json()["detail"].startswith(agent.REFUS_REPLI)


def test_agent_repli_copie_absente(tmp_path: Path) -> None:
    vue = application(tmp_path, repli=True).get("/api/agent").json()
    assert vue["erreur"] == REPLI_ABSENT
    assert vue["message_repli"] == agent.MESSAGE_REPLI
    assert vue["lien_repli"] is None


def test_agent_reel_erreur_propose_le_mode_repli(racine_publiee: Path) -> None:
    def echouer(_repli: bool) -> Any:
        raise UsineErreur("lecture impossible")

    services = cli.services_ecrans(racine_publiee)
    client = TestClient(
        creer_application(
            repli=False,
            lire_manifeste=cli.lecture_manifeste(racine_publiee),
            lire_consultation=echouer,
            services=services,
        ),
        base_url=f"http://{HOTE}",
    )
    vue = client.get("/api/agent").json()
    assert vue["erreur"] == "lecture impossible"
    assert vue["lien_repli"]["url"] == "/chaine"


def test_le_mode_courant_s_applique_aux_ecrans(racine_publiee: Path) -> None:
    client = application(racine_publiee)
    assert client.get("/api/agent").json()["mode"] == "reel"
    assert client.post("/api/mode", json={"mode": "repli"}).status_code == 200
    vue = client.get("/api/agent").json()
    assert vue["mode"] == "repli"
    assert vue["saisie"] is None
    assert client.get("/api/agent/enregistrees/0").status_code == 200
    client.post("/api/mode", json={"mode": "reel"})
    assert client.get("/api/agent/enregistrees/0").status_code == 409


# --- Avant / après ---


def racine_mesuree(tmp_path: Path, **options: Any) -> Path:
    shutil.copytree(Path(cli.__file__).parents[3] / "config", tmp_path / "config")
    publier(tmp_path, manifeste(**options))
    return tmp_path


def test_avant_apres_valeurs_des_deux_periodes(tmp_path: Path) -> None:
    racine = racine_mesuree(tmp_path, secondes=3.4)
    brut = application(racine).get("/api/avant-apres")
    vue = brut.json()
    assert vue["erreur"] is None
    assert vue["manuel"]["valeurs"] == {"rapport": "120 min", "cumul": "600 min"}
    assert vue["manuel"]["etiquette"] == "déclaré"
    assert vue["chaine"]["valeurs"] == {"rapport": "3,4 s", "cumul": "17 s"}
    assert vue["chaine"]["etiquette"] == "mesuré"
    assert [o["valeur"] for o in vue["periodes"]] == ["rapport", "cumul"]
    assert vue["tableau"]["colonnes"] == [
        "Rapport",
        "Reporting manuel (déclaré)",
        "Chaîne (mesuré)",
    ]
    assert vue["tableau"]["lignes"] == [
        ["Par Rapport quotidien", "120 min", "3,4 s"],
        ["Cumulé sur 5 Rapports", "600 min", "17 s"],
    ]
    assert "20261012T073000Z-aaaaaa" in vue["legende"]
    assert vue["avertissements"] == []
    texte = brut.text.lower()
    assert "%" not in texte
    assert "écart" not in texte
    assert "ratio" not in texte
    assert avant_apres.MENTION_FICTIVE in vue["legende"]


def test_avant_apres_periode_choisie(tmp_path: Path) -> None:
    client = application(racine_mesuree(tmp_path))
    assert client.get("/api/avant-apres?periode=cumul").json()["periode"] == "cumul"
    assert client.get("/api/avant-apres").json()["periode"] == "rapport"
    assert client.get("/api/avant-apres?periode=ecart").status_code == 422


def test_avant_apres_avertissements(tmp_path: Path) -> None:
    racine = racine_mesuree(tmp_path / "a", classification_initiale=True)
    vue = application(racine).get("/api/avant-apres").json()
    assert vue["avertissements"] == [avant_apres.SEULE_CLASSIFICATION_INITIALE]
    assert vue["chaine"] is None
    assert vue["manuel"]["valeurs"]["rapport"] == "120 min"
    assert vue["legende"] is None

    sans_config = racine_mesuree(tmp_path / "b")
    (sans_config / "config" / "demo.yaml").unlink()
    vue = application(sans_config).get("/api/avant-apres").json()
    assert vue["avertissements"] == [avant_apres.CONFIG_ABSENTE]
    assert vue["manuel"] is None
    assert vue["chaine"]["valeurs"]["rapport"] == "3,4 s"
    assert vue["tableau"]["colonnes"] == ["Rapport", "Chaîne (mesuré)"]

    invalide = racine_mesuree(tmp_path / "c")
    (invalide / "config" / "demo.yaml").write_text("temps_manuel_minutes_par_rapport: 0\n")
    vue = application(invalide).get("/api/avant-apres").json()
    assert vue["erreur"].startswith("Configuration de la démo invalide")


def test_avant_apres_aucun_passage(tmp_path: Path) -> None:
    shutil.copytree(Path(cli.__file__).parents[3] / "config", tmp_path / "config")
    vue = application(tmp_path).get("/api/avant-apres").json()
    assert vue["message"] == avant_apres.AUCUN_PASSAGE
    assert vue["manuel"] is None
    assert vue["chaine"] is None


def test_avant_apres_mode_repli_lit_la_copie(racine_publiee: Path, tmp_path: Path) -> None:
    vue = application(racine_publiee, repli=True).get("/api/avant-apres").json()
    assert vue["erreur"] is None
    assert vue["manuel"] is not None or vue["avertissements"]
    vide = application(tmp_path, repli=True).get("/api/avant-apres").json()
    assert vide["erreur"] == REPLI_ABSENT


def test_manifestes_mesures_du_repli(racine_publiee: Path, tmp_path: Path) -> None:
    mesure, dernier = cli.manifestes_mesures(racine_publiee, True)
    assert dernier is not None
    assert (mesure is None) == dernier.classification_initiale
    with pytest.raises(UsineErreur):
        cli.manifestes_mesures(tmp_path, True)
    assert cli.manifestes_mesures(tmp_path, False) == (None, None)


# --- Pseudonymisation ---


def apercu_factice(
    texte: str = "<b>[PERSONNE_1]</b> a écrit",
) -> Callable[[], Callable[[str], str]]:
    return lambda: lambda _original: texte


def test_pseudonymisation_cote_a_cote_en_texte_brut(racine_publiee: Path) -> None:
    client = application(racine_publiee, repli=True, apercu_pseudonymisation=apercu_factice())
    brut = client.get("/api/pseudonymisation?ticket=DEMO-17")
    vue = brut.json()
    assert vue["erreur"] is None
    assert vue["ticket"]["cle"] == "DEMO-17"
    assert vue["ticket"]["url"] is None  # Mode repli : texte simple
    assert vue["tickets"] == sorted(vue["tickets"])
    assert "DEMO-17" in vue["tickets"]
    assert vue["original"]
    assert vue["pseudonymise"] == "<b>[PERSONNE_1]</b> a écrit"  # brut, sans HTML ni surlignage
    assert vue["legende"] == pseudonymisation.LEGENDE
    assert "<mark" not in brut.text
    assert vue["titre_original"] == "Original"
    assert vue["titre_pseudonymise"] == "Version pseudonymisée"
    assert vue["etiquette_pseudonymise"] == "envoyée au LLM"


def test_pseudonymisation_ticket_par_defaut_et_inconnu(racine_publiee: Path) -> None:
    client = application(racine_publiee, repli=True, apercu_pseudonymisation=apercu_factice())
    vue = client.get("/api/pseudonymisation").json()
    assert vue["ticket"]["cle"] == vue["tickets"][0]
    inconnu = client.get("/api/pseudonymisation?ticket=NOPE-1").json()
    assert "NOPE-1" in inconnu["erreur"]
    assert inconnu["original"] is None
    assert inconnu["tickets"]


def test_moteur_absent_nomme_dans_le_bandeau(racine_publiee: Path) -> None:
    def moteur_absent() -> Callable[[str], str]:
        raise ImportError("No module named 'presidio_analyzer'")

    client = application(racine_publiee, repli=True, apercu_pseudonymisation=moteur_absent)
    vue = client.get("/api/pseudonymisation?ticket=DEMO-17").json()
    assert "Moteur de Pseudonymisation indisponible (Presidio ou modèle spaCy)" in vue["erreur"]
    assert "presidio_analyzer" in vue["erreur"]
    assert vue["original"] is None
    assert vue["pseudonymise"] is None
    assert vue["tickets"]  # la sélection du ticket reste utilisable


def test_moteur_en_echec_nomme_dans_le_bandeau(racine_publiee: Path) -> None:
    def moteur_en_echec() -> Callable[[str], str]:
        def apercu(_texte: str) -> str:
            raise ValueError("modèle spaCy fr_core_news_md incompatible\ndétail")

        return apercu

    client = application(racine_publiee, repli=True, apercu_pseudonymisation=moteur_en_echec)
    reponse = client.get("/api/pseudonymisation?ticket=DEMO-17")
    assert reponse.status_code == 200
    vue = reponse.json()
    assert vue["erreur"] == (
        "Moteur de Pseudonymisation indisponible (Presidio ou modèle spaCy) : ValueError :"
        " modèle spaCy fr_core_news_md incompatible"
    )
    assert vue["tickets"]


def test_aperçu_impossible_cle_absente(racine_publiee: Path) -> None:
    def sans_cle() -> Callable[[str], str]:
        raise UsineErreur("USINE_CLE_PSEUDO absente")

    client = application(racine_publiee, repli=True, apercu_pseudonymisation=sans_cle)
    vue = client.get("/api/pseudonymisation").json()
    assert vue["erreur"] == "Aperçu de la Pseudonymisation impossible : USINE_CLE_PSEUDO absente"


def test_pseudonymisation_sans_passage(tmp_path: Path) -> None:
    vue = application(tmp_path).get("/api/pseudonymisation").json()
    assert vue["message"].startswith("Aucun Passage publié")
    assert vue["lien_message"]["url"] == "/chaine"


# --- Outillage ---


def test_fiche_rendue_sans_marqueurs_ni_titre(racine_publiee: Path) -> None:
    vue = application(racine_publiee).get("/api/outillage").json()
    html = vue["html"]
    assert vue["legende"] == outillage.LEGENDE
    assert "<h1" not in html
    assert "<h2>Demandes, par ordre de priorité</h2>" in html
    assert "<ol>" in html
    assert 'role="region" tabindex="0"' in html  # tableau défilant, région focalisable
    for marqueur in ("✅", "⚠️", "❌", "⚠"):
        assert marqueur not in html
    assert '<span class="pastille pastille--oui">Oui</span>' in html
    assert '<span class="pastille pastille--surveiller">À surveiller</span>' in html
    assert '<span class="pastille pastille--non">Non</span>' in html


def test_fiche_html_brut_desactive(racine_publiee: Path) -> None:
    fiche = (
        "# Titre\n\n## Section\n\n<script>alert(1)</script>\n\n"
        '<img src=x onerror="alert(2)">\n\n'
        "| A | B |\n|---|---|\n| ✅ oui | ⚠️ peut-être |\n| ❌ non | texte |\n"
    )
    vue = application(racine_publiee, lire_fiche=lambda: fiche).get("/api/outillage").json()
    html = vue["html"]
    assert "<script" not in html
    assert "<img" not in html
    assert "&lt;script&gt;" in html
    assert html.count("pastille pastille--") == 3
    assert "Oui</span> oui" in html


def test_fiche_absente_ou_illisible(racine_publiee: Path) -> None:
    absente = application(racine_publiee, lire_fiche=lambda: None).get("/api/outillage").json()
    assert absente["message"] == outillage.FICHE_ABSENTE
    assert absente["html"] is None

    def illisible() -> str:
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "octet invalide")

    vue = application(racine_publiee, lire_fiche=illisible).get("/api/outillage").json()
    assert vue["erreur"].startswith("Lecture de la fiche outillage impossible")


def test_rendre_fiche_neutralise_html_et_liens_javascript() -> None:
    html = rendre_fiche(
        "# T\n\n<script>alert(1)</script>\n\n[clic](javascript:alert(1))"
        " <img src=x onerror=alert(1)>\n"
    )
    assert "<script>" not in html
    assert "<img" not in html
    assert 'href="javascript:' not in html
    assert "&lt;script&gt;" in html


def test_rendre_fiche_enveloppes_par_section() -> None:
    html = rendre_fiche("# T\n\nIntro\n\n## Un\n\ntexte\n\n### Sous\n\nx\n\n## Deux\n\ny\n")
    assert html.count('<section class="carte carte--fiche">') == 3
    assert "<h3>Sous</h3>" in html


# --- Sans services, pages, sécurité du DOM ---


def test_sans_services_les_ecrans_disent_pourquoi(tmp_path: Path) -> None:
    client = TestClient(
        creer_application(
            repli=False,
            lire_manifeste=lambda _repli: None,
            lire_consultation=lambda _repli: None,
        ),
        base_url=f"http://{HOTE}",
    )
    assert "services" in client.get("/api/agent").json()["erreur"]
    assert "services" in client.get("/api/avant-apres").json()["erreur"]
    assert "services" in client.get("/api/pseudonymisation").json()["erreur"]
    assert "services" in client.get("/api/outillage").json()["erreur"]
    assert client.post("/api/agent/question", json={"question": "Q"}).status_code == 503
    assert client.get("/api/agent/enregistrees/0").status_code == 503


def test_pages_et_scripts_des_quatre_ecrans() -> None:
    agent_html = (REPERTOIRE_STATIQUE / "agent.html").read_text(encoding="utf-8")
    assert '<script src="/statique/agent.js" defer></script>' in agent_html
    assert 'id="reponse"' in agent_html
    assert 'id="reponse" tabindex="-1"' in agent_html
    assert 'id="annonce" role="status"' in agent_html
    pseudo = (REPERTOIRE_STATIQUE / "pseudonymisation.html").read_text(encoding="utf-8")
    assert pseudo.count('role="region" tabindex="0"') == 2
    for fichier in ("avant-apres", "outillage", "pseudonymisation"):
        page = (REPERTOIRE_STATIQUE / f"{fichier}.html").read_text(encoding="utf-8")
        assert f'<script src="/statique/{fichier}.js" defer></script>' in page
        assert "Contenu de l'écran" not in page


def test_scripts_sans_innerhtml_de_donnees_ni_ressource_externe() -> None:
    for script in ("agent", "avant-apres", "pseudonymisation"):
        source = (REPERTOIRE_STATIQUE / f"{script}.js").read_text(encoding="utf-8")
        assert "innerHTML" not in source
        assert "http://" not in source
        assert "https://" not in source
    fiche = (REPERTOIRE_STATIQUE / "outillage.js").read_text(encoding="utf-8")
    assert fiche.count("innerHTML") == 1  # le HTML rendu par le serveur, HTML brut désactivé


def test_services_reels_de_la_composition(racine_publiee: Path) -> None:
    services = cli.services_ecrans(racine_publiee)
    assert isinstance(services, ServicesEcrans)
    assert services.questions_suggerees == QUESTIONS_DEMO
    assert services.texte_hors_perimetre == SANS_REPONSE
    config = services.config_demo()
    assert config is not None
    assert config.temps_manuel_minutes_par_rapport == 120
    fiche = services.lire_fiche()
    assert fiche is not None and fiche.startswith("# ")
    assert vue_reponse_agent(reponse(), SANS_REPONSE).texte == "ENT-B est rouge."


def test_avant_apres_milliers_et_arrondi(tmp_path: Path) -> None:
    racine = racine_mesuree(tmp_path, secondes=12.34)
    (racine / "config" / "demo.yaml").write_text(
        "temps_manuel_minutes_par_rapport: 240\n", encoding="utf-8"
    )
    vue = application(racine).get("/api/avant-apres").json()
    assert vue["tableau"]["lignes"] == [
        ["Par Rapport quotidien", "240 min", "12,3 s"],
        ["Cumulé sur 5 Rapports", f"1{ESPACE_INSECABLE}200 min", "61,7 s"],
    ]


def test_ui_sans_acces_interdit() -> None:
    """AD-11 : aucun module de `ui/` ne cite l'entrepôt DuckDB ni son verrou."""
    interdits = ("entrepot.duckdb", ".en-cours", "duckdb")
    for chemin in sorted(Path(cli.__file__).parent.glob("*.py")):
        texte = chemin.read_text(encoding="utf-8")
        assert [m for m in interdits if m in texte] == [], chemin.name
