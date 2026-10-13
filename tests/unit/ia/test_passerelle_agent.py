"""Passerelle de l'Agent : ordre d'AD-12, outils enveloppés, cache, plafond (Story 7.9)."""

import json
from collections.abc import Mapping
from decimal import Decimal

import pytest
from pydantic import JsonValue

from tests.doublures.fournisseur_factice import FournisseurFactice, ReponseAgentScriptee
from tests.unit.ia.espions import (
    DATE_ARRETE,
    INSTANT,
    NUMERO_COMPTE,
    PASSAGE_ID,
    CacheMemoire,
    EspionFournisseur,
    jeton_compte,
    pseudonymiseur,
)
from usine.contrats.agent import ArgumentsGetMeteo
from usine.contrats.llm import (
    AppelOutil,
    MessageAgent,
    ParametresAppel,
    ReponseAgent,
    ReponseAgentBrute,
    StatutControle,
    Tache,
)
from usine.ia.passerelle import (
    ContexteAppel,
    Controle,
    OutilSource,
    Passerelle,
    PlafondCoutAtteint,
    message_erreur_arguments,
)

CONTEXTE = ContexteAppel(
    passage_id=PASSAGE_ID,
    date_arrete=DATE_ARRETE,
    cible=PASSAGE_ID,
    version_prompt="p" * 64,
    version_grille="grille123456",
    version_donnees="d" * 64,
)
PARAMETRES = ParametresAppel(tache=Tache.agent, max_jetons_sortie=256)
MESSAGES = (
    MessageAgent(role="systeme", contenu="Consignes."),
    MessageAgent(role="utilisateur", contenu=f"Que bloque le compte {NUMERO_COMPTE} ?"),
)


class Marqueur:
    """Pseudonymiseur factice qui marque ses entrées et journalise ses appels."""

    def __init__(self, journal: list[str]) -> None:
        self.journal = journal

    def pseudonymiser(self, texte: str) -> str:
        self.journal.append("pseudonymiser")
        return f"PSEUDO[{texte}]"

    def reidentifier(self, texte: str) -> str:
        self.journal.append("reidentifier")
        return texte

    def apercu(self, texte: str) -> str:
        return f"PSEUDO[{texte}]"


def _source(resultat: str, journal: list[str] | None = None) -> OutilSource:
    def executer(arguments: Mapping[str, JsonValue]) -> str:
        if journal is not None:
            journal.append("outil")
        ArgumentsGetMeteo.model_validate(arguments)
        return resultat

    return OutilSource("get_meteo", "Météo.", ArgumentsGetMeteo, executer)


def _appel(arguments: dict[str, JsonValue] | None = None) -> AppelOutil:
    return AppelOutil(id_appel="a1", nom_outil="get_meteo", arguments=arguments or {})


def _controler(journal: list[str] | None = None) -> "Controleur":
    return Controleur(journal if journal is not None else [])


class Controleur:
    """Contrôle conforme qui garde la réponse reçue."""

    def __init__(self, journal: list[str]) -> None:
        self.journal = journal
        self.recues: list[ReponseAgentBrute] = []

    def __call__(self, reponse: ReponseAgentBrute) -> Controle[ReponseAgent]:
        self.journal.append("controle")
        self.recues.append(reponse)
        sortie = ReponseAgent(
            question="q",
            texte=reponse.texte,
            outils_appeles=tuple(a.nom_outil for m in reponse.messages for a in m.appels_outils),
            statut_controle=StatutControle.conforme,
        )
        return Controle(sortie, StatutControle.conforme)


def test_outil_pseudonymise_et_trace_avant_la_reponse() -> None:
    journal: list[str] = []
    factice = FournisseurFactice(reponses_agent=[ReponseAgentScriptee("Réponse.", (_appel(),))])
    passerelle = Passerelle(
        EspionFournisseur(factice, journal),
        Marqueur(journal),
        CacheMemoire(journal),
        lambda: INSTANT,
    )
    controleur = _controler(journal)
    resultat = passerelle.executer_agent(
        MESSAGES, [_source('{"x": "ENT-A"}', journal)], PARAMETRES, CONTEXTE, controleur
    )

    (appel,) = factice.appels
    assert all(m.contenu.startswith("PSEUDO[") for m in appel.entree if isinstance(m, MessageAgent))
    assert appel.outils == ("get_meteo",)
    (brute,) = controleur.recues
    (message_outil,) = [m for m in brute.messages if m.role == "outil"]
    assert message_outil.contenu == 'PSEUDO[{"x": "ENT-A"}]'  # seul le pseudonymisé passe
    assert journal.index("outil") < journal.index("controle")
    assert journal[:4] == ["pseudonymiser", "pseudonymiser", "cache.lire", "fournisseur.agent"]

    trace_outil, trace_reponse = resultat.traces
    assert trace_outil.tache is Tache.agent
    assert trace_outil.cible == "get_meteo"
    assert trace_outil.statut_controle is StatutControle.non_controle
    assert trace_outil.sortie == 'PSEUDO[{"x": "ENT-A"}]'
    assert trace_outil.entree_pseudonymisee.startswith("PSEUDO[")
    assert trace_reponse.cible == PASSAGE_ID
    assert trace_reponse.statut_controle is StatutControle.conforme
    assert not resultat.depuis_cache
    assert resultat.sortie.outils_appeles == ("get_meteo",)


def test_reidentification_et_traces_pseudonymisees() -> None:
    pseudo = pseudonymiseur()
    jeton = jeton_compte()
    factice = FournisseurFactice(
        reponses_agent=[ReponseAgentScriptee(f"Le compte {jeton} est bloqué.", (_appel(),))]
    )
    passerelle = Passerelle(factice, pseudo, CacheMemoire(), lambda: INSTANT)
    resultat = passerelle.executer_agent(
        MESSAGES,
        [_source(json.dumps({"compte": NUMERO_COMPTE}))],
        PARAMETRES,
        CONTEXTE,
        _controler(),
    )
    assert resultat.sortie.texte == f"Le compte {NUMERO_COMPTE} est bloqué."
    for trace in resultat.traces:
        assert NUMERO_COMPTE not in trace.model_dump_json()
    assert jeton in resultat.traces[0].sortie
    (appel,) = factice.appels
    assert all(NUMERO_COMPTE not in m.contenu for m in appel.entree if isinstance(m, MessageAgent))


def test_jeton_hors_conversation_non_reidentifie() -> None:
    pseudo = pseudonymiseur()
    jeton = jeton_compte()
    pseudo.pseudonymiser(NUMERO_COMPTE)  # connu du pseudonymiseur, absent de la conversation
    factice = FournisseurFactice(reponses_agent=[ReponseAgentScriptee(f"Voir {jeton}.")])
    passerelle = Passerelle(factice, pseudo, CacheMemoire(), lambda: INSTANT)
    messages = (MessageAgent(role="utilisateur", contenu="Question sans donnée personnelle."),)
    resultat = passerelle.executer_agent(messages, [], PARAMETRES, CONTEXTE, _controler())
    assert resultat.sortie.texte == f"Voir {jeton}."


def test_arguments_invalides_rendus_en_texte() -> None:
    factice = FournisseurFactice(
        reponses_agent=[ReponseAgentScriptee("Rien.", (_appel({"date_arrete": "pas-une-date"}),))]
    )
    passerelle = Passerelle(factice, pseudonymiseur(), CacheMemoire(), lambda: INSTANT)
    controleur = _controler()
    resultat = passerelle.executer_agent(
        MESSAGES, [_source("{}")], PARAMETRES, CONTEXTE, controleur
    )
    (brute,) = controleur.recues
    (message_outil,) = [m for m in brute.messages if m.role == "outil"]
    assert message_outil.contenu == message_erreur_arguments("get_meteo")
    assert message_outil.contenu == "erreur : arguments invalides pour get_meteo"
    assert len(resultat.traces) == 2


def test_meme_question_servie_du_cache() -> None:
    factice = FournisseurFactice(reponses_agent=[ReponseAgentScriptee("Réponse.", (_appel(),))])
    passerelle = Passerelle(factice, pseudonymiseur(), CacheMemoire(), lambda: INSTANT)
    premiere = passerelle.executer_agent(
        MESSAGES, [_source("{}")], PARAMETRES, CONTEXTE, _controler()
    )
    seconde = passerelle.executer_agent(
        MESSAGES, [_source("{}")], PARAMETRES, CONTEXTE, _controler()
    )
    assert len(factice.appels) == 1  # aucun nouvel appel au fournisseur
    assert seconde.depuis_cache
    assert not premiere.depuis_cache
    assert len(seconde.traces) == 1  # aucun outil exécuté
    assert seconde.sortie == premiere.sortie
    assert seconde.traces[0].cout_estime_eur == 0


def test_plafond_atteint() -> None:
    factice = FournisseurFactice(
        reponses_agent=[ReponseAgentScriptee("Une."), ReponseAgentScriptee("Deux.")]
    )
    passerelle = Passerelle(
        factice,
        pseudonymiseur(),
        CacheMemoire(),
        lambda: INSTANT,
        tarif=lambda _v, _e, _s: Decimal(1),
        plafond_cout_passage_eur=Decimal(1),
    )
    resultat = passerelle.executer_agent(MESSAGES, [], PARAMETRES, CONTEXTE, _controler())
    assert resultat.traces[-1].cout_estime_eur == 1
    autre = (MessageAgent(role="utilisateur", contenu="Autre question."),)
    with pytest.raises(PlafondCoutAtteint):
        passerelle.executer_agent(autre, [], PARAMETRES, CONTEXTE, _controler())
    assert len(factice.appels) == 1
