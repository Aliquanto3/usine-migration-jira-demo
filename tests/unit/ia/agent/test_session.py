"""Session de l'Agent : sérialisation bornée, contrôle des chiffres et tickets, traces JSONL
(Story 7.9, FR-39, FR-40)."""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from tests.contrat.consultation.fabriques import passage_palier_2
from tests.doublures.fournisseur_factice import FournisseurFactice, ReponseAgentScriptee
from tests.unit.ia.espions import INSTANT, CacheMemoire, pseudonymiseur
from usine.composition import construire_session_agent
from usine.contrats.agent import PointTendance, ResultatGetTendance, ResultatListAnomalies
from usine.contrats.llm import (
    AppelOutil,
    MessageAgent,
    ReponseAgentBrute,
    StatutControle,
    Tache,
)
from usine.contrats.trace import EntreeTrace
from usine.ia.agent.outils import outils_consultation
from usine.ia.agent.session import (
    LIMITE_POINTS_TENDANCE,
    REPERTOIRE_AGENT,
    SANS_REPONSE,
    SessionAgent,
    controler_reponse,
    serialiser_resultat,
    tickets_cites,
)
from usine.ia.passerelle import Passerelle
from usine.ports.consultation import Consultation

RESULTAT_RISQUES = json.dumps(
    {
        "date_arrete": "2026-10-09",
        "risques": [
            {
                "entite": "ENT-C",
                "indicateur": "IND-1",
                "date_franchissement_estimee": "2026-10-16",
                "numerateur": 4,
                "seuil_numerateur": 5,
                "part": 0.25,
            }
        ],
    }
)
RESULTAT_ANOMALIES = json.dumps({"anomalies": [{"cle_ticket": "MIG-12"}, {"cle_ticket": "MIG-7"}]})


def _brute(texte: str, *resultats: str) -> ReponseAgentBrute:
    appels = tuple(
        AppelOutil(id_appel=f"a{rang}", nom_outil=nom, arguments={})
        for rang, nom in enumerate(("get_risques", "list_anomalies")[: len(resultats)])
    )
    messages = [
        MessageAgent(role="systeme", contenu="Consignes 2026."),
        MessageAgent(role="utilisateur", contenu="Quelle Entité risque le rouge ?"),
    ]
    if appels:
        messages.append(MessageAgent(role="assistant", contenu="", appels_outils=appels))
    messages.extend(
        MessageAgent(role="outil", contenu=r, id_appel=a.id_appel)
        for a, r in zip(appels, resultats, strict=True)
    )
    messages.append(MessageAgent(role="assistant", contenu=texte))
    return ReponseAgentBrute(
        texte=texte,
        messages=tuple(messages),
        jetons_entree=1,
        jetons_sortie=1,
        version_modele="factice:modele",
    )


def test_reponse_conforme() -> None:
    texte = (
        "ENT-C risque de passer au rouge sur IND-1 le 2026-10-16 : 4 pour un seuil de 5,"
        " soit 25 % ; voir MIG-12 et MIG-7."
    )
    controle = controler_reponse(_brute(texte, RESULTAT_RISQUES, RESULTAT_ANOMALIES))
    assert controle.statut is StatutControle.conforme
    assert controle.sortie.texte == texte
    assert controle.sortie.outils_appeles == ("get_risques", "list_anomalies")
    assert controle.sortie.tickets_cites == ("MIG-12", "MIG-7")
    assert controle.sortie.question == "Quelle Entité risque le rouge ?"


def test_chiffre_invente_rejete() -> None:
    controle = controler_reponse(_brute("ENT-C a 42 Anomalies.", RESULTAT_RISQUES))
    assert controle.statut is StatutControle.rejete
    assert controle.sortie.statut_controle is StatutControle.rejete
    assert "« 42 »" in controle.sortie.texte
    assert "ENT-C a 42" not in controle.sortie.texte


def test_annee_absente_des_resultats_rejetee() -> None:
    controle = controler_reponse(_brute("En 2031, rien.", RESULTAT_RISQUES))
    assert controle.statut is StatutControle.rejete  # ni dans les outils, ni ailleurs


def test_ticket_non_retourne_rejete() -> None:
    controle = controler_reponse(_brute("Voir MIG-999.", RESULTAT_RISQUES, RESULTAT_ANOMALIES))
    assert controle.statut is StatutControle.rejete
    assert "MIG-999" in controle.sortie.texte
    assert controle.sortie.tickets_cites == ()


def test_chiffres_d_une_cle_ou_d_un_jeton_non_autorises() -> None:
    resultat = json.dumps({"libelle": "voir MIG-42 et PERSONNE_a1b2c3, taux 12,5"})
    assert controler_reponse(_brute("Il y a 42 cas.", resultat)).statut is StatutControle.rejete
    assert controler_reponse(_brute("Il y a 3 cas.", resultat)).statut is StatutControle.rejete
    assert controler_reponse(_brute("Le taux vaut 12,5.", resultat)).statut is (
        StatutControle.conforme
    )


def test_reponse_vide_rejetee() -> None:
    controle = controler_reponse(_brute("  ", RESULTAT_RISQUES))
    assert controle.statut is StatutControle.rejete
    assert "réponse vide" in controle.sortie.texte


def test_sans_reponse_conforme() -> None:
    controle = controler_reponse(_brute(SANS_REPONSE))
    assert controle.statut is StatutControle.conforme
    assert controle.sortie.outils_appeles == ()


def test_tickets_cites_ignore_indicateurs_et_entites() -> None:
    assert tickets_cites("IND-1, ENT-C, J-5, DEMO-3 et DEMO-3, MIG-1") == ("DEMO-3", "MIG-1")


def _point(jour: date) -> PointTendance:
    return PointTendance(
        date=jour,
        perimetre="ENT-A",
        code_kpi="sorties_semaine",
        dimension="",
        numerateur=1,
        denominateur=1,
    )


def test_tendance_bornee_aux_points_les_plus_recents() -> None:
    debut = date(2026, 1, 1)
    points = tuple(_point(debut + timedelta(days=n)) for n in range(LIMITE_POINTS_TENDANCE + 10))
    donnees = json.loads(serialiser_resultat(ResultatGetTendance(points=points[::-1])))
    assert donnees["points_omis"] == 10
    assert len(donnees["points"]) == LIMITE_POINTS_TENDANCE
    assert donnees["points"][0]["date"] == (debut + timedelta(days=10)).isoformat()
    assert donnees["points"][-1]["date"] == points[-1].date.isoformat()


def test_tendance_courte_inchangee() -> None:
    resultat = ResultatGetTendance(points=(_point(date(2026, 1, 1)),))
    assert json.loads(serialiser_resultat(resultat)) == resultat.model_dump(mode="json")


def _session(
    consultation: Consultation, racine: Path, scripts: list[ReponseAgentScriptee]
) -> tuple[SessionAgent, FournisseurFactice]:
    fournisseur = FournisseurFactice(reponses_agent=scripts)
    passerelle = Passerelle(fournisseur, pseudonymiseur(), CacheMemoire(), lambda: INSTANT)
    session = SessionAgent(passerelle, consultation, racine, lambda: INSTANT, "session-test")
    return session, fournisseur


@pytest.fixture(scope="module")
def cas_palier_2() -> Consultation:
    return passage_palier_2().consultation


def _fichiers(repertoire: Path) -> dict[Path, bytes]:
    return {p: p.read_bytes() for p in sorted(repertoire.rglob("*")) if p.is_file()}


def test_question_de_la_demo(cas_palier_2: Consultation, tmp_path: Path) -> None:
    consultation = cas_palier_2
    (risque,) = consultation.risques(consultation.manifeste().date_arrete)
    outils = {d.nom: d for d in outils_consultation(consultation)}
    anomalies = outils["list_anomalies"].executer({"limite": 2})
    assert isinstance(anomalies, ResultatListAnomalies)
    cles = [a.cle_ticket for a in anomalies.anomalies]
    assert len(cles) == 2
    texte = (
        f"{risque.entite} risque de passer au rouge sur {risque.indicateur.value} vers le"
        f" {risque.date_franchissement_estimee.isoformat()} ({risque.numerateur} pour un seuil"
        f" de {risque.seuil_numerateur}). Tickets à suivre : {cles[0]} et {cles[1]}."
    )
    appels = (
        AppelOutil(id_appel="a1", nom_outil="get_risques", arguments={}),
        AppelOutil(id_appel="a2", nom_outil="list_anomalies", arguments={"limite": 2}),
    )
    avant = _fichiers(tmp_path)
    session, fournisseur = _session(consultation, tmp_path, [ReponseAgentScriptee(texte, appels)])
    reponse = session.repondre("Quelle Entité risque de passer au rouge ?")

    assert reponse.statut_controle is StatutControle.conforme
    assert reponse.outils_appeles == ("get_risques", "list_anomalies")
    assert reponse.tickets_cites == tuple(cles)
    assert reponse.texte == texte
    assert fournisseur.appels[0].outils == (
        "get_meteo",
        "list_anomalies",
        "get_tendance",
        "get_prevision",
        "get_risques",
    )

    chemin = tmp_path / REPERTOIRE_AGENT / INSTANT.date().isoformat() / "session-test.jsonl"
    assert session.chemin_traces == chemin
    traces = [
        EntreeTrace.model_validate_json(ligne) for ligne in chemin.read_text("utf-8").splitlines()
    ]
    assert [t.cible for t in traces] == ["get_risques", "list_anomalies", session.passage_id]
    assert all(t.tache is Tache.agent for t in traces)
    assert traces[-1].statut_controle is StatutControle.conforme
    assert traces[-1].passage_id == consultation.manifeste().passage_id
    # seul le fichier de traces a été écrit sous la racine
    assert set(_fichiers(tmp_path)) - set(avant) == {chemin}


def test_passage_non_modifie(cas_palier_2: Consultation, tmp_path: Path) -> None:
    manifeste = cas_palier_2.manifeste()
    repertoire = Path(vars(cas_palier_2)["_repertoire"])  # Passage consulté
    avant = _fichiers(repertoire)
    appels = (AppelOutil(id_appel="a1", nom_outil="get_meteo", arguments={}),)
    session, _ = _session(cas_palier_2, tmp_path, [ReponseAgentScriptee(SANS_REPONSE, appels)])
    reponse = session.repondre("Question ?")
    assert reponse.statut_controle is StatutControle.conforme
    assert _fichiers(repertoire) == avant
    assert manifeste == cas_palier_2.manifeste()


def test_tendance_sans_filtre_bornee(cas_palier_2: Consultation, tmp_path: Path) -> None:
    appels = (AppelOutil(id_appel="a1", nom_outil="get_tendance", arguments={}),)
    session, _ = _session(cas_palier_2, tmp_path, [ReponseAgentScriptee(SANS_REPONSE, appels)])
    session.repondre("Tendance ?")
    assert session.dernier_resultat is not None
    trace_outil = session.dernier_resultat.traces[0]
    donnees = json.loads(trace_outil.sortie)
    assert len(donnees["points"]) == LIMITE_POINTS_TENDANCE
    assert donnees["points_omis"] > 0


def test_meme_question_rejouee_depuis_le_cache(cas_palier_2: Consultation, tmp_path: Path) -> None:
    appels = (AppelOutil(id_appel="a1", nom_outil="get_risques", arguments={}),)
    session, fournisseur = _session(
        cas_palier_2, tmp_path, [ReponseAgentScriptee(SANS_REPONSE, appels)]
    )
    premiere = session.repondre("Risques ?")
    seconde = session.repondre("Risques ?")
    assert seconde == premiere
    assert session.dernier_resultat is not None
    assert session.dernier_resultat.depuis_cache
    assert len(fournisseur.appels) == 1
    lignes = session.chemin_traces.read_text("utf-8").splitlines()
    assert len(lignes) == 3  # outil + réponse, puis réponse en cache


def test_construire_session_agent(cas_palier_2: Consultation, tmp_path: Path) -> None:
    fournisseur = FournisseurFactice(reponses_agent=[ReponseAgentScriptee(SANS_REPONSE)])
    session = construire_session_agent(tmp_path, cas_palier_2, fournisseur, pseudonymiseur())
    reponse = session.repondre("Question ?")
    session.fermer()
    assert reponse.statut_controle is StatutControle.conforme
    assert session.passage_id == cas_palier_2.manifeste().passage_id
    assert session.chemin_traces.is_relative_to(tmp_path / REPERTOIRE_AGENT)
    assert session.chemin_traces.exists()
