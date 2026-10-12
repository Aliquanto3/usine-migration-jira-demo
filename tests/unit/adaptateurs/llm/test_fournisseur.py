"""Adaptateurs Anthropic et Mistral sur faux transport : AD-13, reprise sur 429, erreurs."""

from collections.abc import Mapping
from decimal import Decimal

import httpx2
import pytest
from pydantic import BaseModel, JsonValue

from tests.doublures.transport_llm import (
    MODELES,
    TransportScripte,
    fournisseur_scripte,
    reponse_outil,
    reponse_texte,
    trop_de_requetes,
)
from usine.adaptateurs.llm import (
    REGISTRE,
    FournisseurPydanticAI,
    construire_fournisseur_llm,
    cout_estime_eur,
    tarif,
)
from usine.adaptateurs.llm.registre import TAUX_USD_EUR
from usine.contrats.config import ConfigLLM
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import MessageAgent, OutilAgent, ParametresAppel, Tache
from usine.ports import FournisseurLLM

FOURNISSEURS = ("anthropic", "mistral")
STRUCTURE = ParametresAppel(tache=Tache.classification, max_jetons_sortie=300)
AGENT = ParametresAppel(tache=Tache.agent, max_jetons_sortie=300)


class Sortie(BaseModel):
    reponse: str


class _Arguments(BaseModel):
    entite: str


def _sortie(fournisseur: str) -> httpx2.Response:
    return reponse_outil(fournisseur, "reponse", {"reponse": "ok"}, "id0000001")


def _outil(appels: list[Mapping[str, JsonValue]]) -> OutilAgent:
    def executer(arguments: Mapping[str, JsonValue]) -> str:
        appels.append(arguments)
        return "rouge"

    return OutilAgent("get_meteo", "Météo d'une Entité.", _Arguments, executer)


def _noms_outils(corps: Mapping[str, object]) -> set[str]:
    outils = corps.get("tools") or []
    assert isinstance(outils, list)
    return {o.get("name") or o["function"]["name"] for o in outils}


@pytest.mark.parametrize("fournisseur", FOURNISSEURS)
def test_construit_l_adaptateur_de_la_configuration(fournisseur: str) -> None:
    adaptateur = fournisseur_scripte(fournisseur, TransportScripte([]))
    assert isinstance(adaptateur, FournisseurLLM)
    assert adaptateur.version_modele == f"{fournisseur}:{MODELES[fournisseur]}"


@pytest.mark.parametrize("fournisseur", FOURNISSEURS)
def test_structure_en_mode_tool_output_sans_autre_outil(fournisseur: str) -> None:
    transport = TransportScripte([_sortie(fournisseur)])
    reponse = fournisseur_scripte(fournisseur, transport).generer_structure(
        "Classe DEMO-1.", Sortie, STRUCTURE
    )
    assert reponse.sortie == Sortie(reponse="ok")
    assert reponse.brut == '{"reponse":"ok"}'
    assert (reponse.jetons_entree, reponse.jetons_sortie) == (12, 7)
    (corps,) = transport.requetes
    assert _noms_outils(corps) == {"reponse"}
    assert corps["max_tokens"] == 300


@pytest.mark.parametrize("fournisseur", FOURNISSEURS)
def test_agent_en_texte_libre_avec_les_seuls_outils_recus(fournisseur: str) -> None:
    transport = TransportScripte(
        [
            reponse_outil(fournisseur, "get_meteo", {"entite": "ENT-A"}, "id0000002"),
            reponse_texte(fournisseur, "ENT-A est rouge."),
        ]
    )
    appels: list[Mapping[str, JsonValue]] = []
    messages = (
        MessageAgent(role="systeme", contenu="Réponds par les outils."),
        MessageAgent(role="utilisateur", contenu="Météo de ENT-A ?"),
    )
    reponse = fournisseur_scripte(fournisseur, transport).executer_agent(
        messages, (_outil(appels),), AGENT
    )
    assert reponse.texte == "ENT-A est rouge."
    assert appels == [{"entite": "ENT-A"}]
    assert all(_noms_outils(corps) == {"get_meteo"} for corps in transport.requetes)
    roles = [m.role for m in reponse.messages]
    assert roles == ["systeme", "utilisateur", "assistant", "outil", "assistant"]
    assert reponse.messages[3].contenu == "rouge"
    assert (reponse.jetons_entree, reponse.jetons_sortie) == (24, 14)


@pytest.mark.parametrize("fournisseur", FOURNISSEURS)
def test_agent_reprend_une_conversation_avec_resultat_d_outil(fournisseur: str) -> None:
    transport = TransportScripte([reponse_texte(fournisseur, "ENT-A est rouge.")])
    messages = (
        MessageAgent(role="utilisateur", contenu="Météo de ENT-A ?"),
        MessageAgent.model_validate(
            {
                "role": "assistant",
                "contenu": "",
                "appels_outils": [
                    {
                        "id_appel": "id0000009",
                        "nom_outil": "get_meteo",
                        "arguments": {"entite": "A"},
                    }
                ],
            }
        ),
        MessageAgent(role="outil", contenu="rouge", id_appel="id0000009"),
    )
    reponse = fournisseur_scripte(fournisseur, transport).executer_agent(
        messages, (_outil([]),), AGENT
    )
    assert reponse.texte == "ENT-A est rouge."
    assert len(transport.requetes) == 1


def test_agent_refuse_un_resultat_d_outil_orphelin() -> None:
    messages = (MessageAgent(role="outil", contenu="rouge", id_appel="inconnu"),)
    with pytest.raises(UsineErreur, match="inconnu"):
        fournisseur_scripte("anthropic", TransportScripte([])).executer_agent(messages, (), AGENT)


@pytest.mark.parametrize("fournisseur", FOURNISSEURS)
def test_deux_429_puis_succes_attente_croissante_et_retry_after(fournisseur: str) -> None:
    transport = TransportScripte(
        [
            trop_de_requetes(fournisseur, "3"),
            trop_de_requetes(fournisseur, None),
            _sortie(fournisseur),
        ]
    )
    attentes: list[float] = []
    reponse = fournisseur_scripte(fournisseur, transport, attentes=attentes).generer_structure(
        "Classe DEMO-1.", Sortie, STRUCTURE
    )
    assert reponse.sortie.reponse == "ok"
    assert len(transport.requetes) == 3
    # Retry-After (3 s) respecté, puis attente doublée.
    assert attentes == [3.0, 6.0]


@pytest.mark.parametrize("fournisseur", FOURNISSEURS)
def test_429_au_dela_des_tentatives_max_leve_une_usine_erreur(fournisseur: str) -> None:
    transport = TransportScripte([trop_de_requetes(fournisseur, "2") for _ in range(3)])
    attentes: list[float] = []
    adaptateur = fournisseur_scripte(fournisseur, transport, tentatives_max=3, attentes=attentes)
    with pytest.raises(UsineErreur, match=r"429.*3 tentatives"):
        adaptateur.generer_structure("Classe DEMO-1.", Sortie, STRUCTURE)
    assert len(transport.requetes) == 3
    assert attentes == [2.0, 4.0]


def test_retry_after_plafonne() -> None:
    transport = TransportScripte([trop_de_requetes("mistral", "3600"), _sortie("mistral")])
    attentes: list[float] = []
    fournisseur_scripte("mistral", transport, attentes=attentes).generer_structure(
        "p", Sortie, STRUCTURE
    )
    assert attentes == [60.0]


@pytest.mark.parametrize("fournisseur", FOURNISSEURS)
def test_autre_erreur_http_sans_reprise_ni_cle(fournisseur: str) -> None:
    transport = TransportScripte([httpx2.Response(401, json={"message": "cle-de-test refusée"})])
    with pytest.raises(UsineErreur, match="erreur HTTP 401") as exc:
        fournisseur_scripte(fournisseur, transport).generer_structure("p", Sortie, STRUCTURE)
    assert "cle-de-test" not in str(exc.value)
    assert len(transport.requetes) == 1


def test_espacement_par_modele_entre_deux_appels() -> None:
    transport = TransportScripte([_sortie("anthropic"), _sortie("anthropic")])
    attentes: list[float] = []
    adaptateur = fournisseur_scripte("anthropic", transport, attentes=attentes)
    adaptateur.generer_structure("p", Sortie, STRUCTURE)
    adaptateur.generer_structure("p", Sortie, STRUCTURE)
    assert attentes == [pytest.approx(tarif("anthropic:claude-sonnet-5-5").espacement_s)]


def _config(fournisseur: str, modele: str = "claude-sonnet-5-5") -> ConfigLLM:
    return ConfigLLM(fournisseur=fournisseur, modele=modele, plafond_cout_passage_eur=Decimal(1))


def test_fournisseur_inconnu_refuse() -> None:
    with pytest.raises(UsineErreur, match="openai"):
        construire_fournisseur_llm(_config("openai"), "k")


@pytest.mark.parametrize(
    ("fournisseur", "variable"),
    [("anthropic", "ANTHROPIC_API_KEY"), ("mistral", "MISTRAL_API_KEY")],
)
def test_cle_absente_nomme_la_variable(fournisseur: str, variable: str) -> None:
    with pytest.raises(UsineErreur, match=variable):
        construire_fournisseur_llm(_config(fournisseur, MODELES[fournisseur]), " ")


def test_modele_hors_registre_refuse() -> None:
    with pytest.raises(UsineErreur, match="registre"):
        construire_fournisseur_llm(_config("anthropic", "claude-inconnu"), "k")


def test_registre_quotas_et_prix() -> None:
    assert "anthropic:claude-sonnet-5-5" in REGISTRE
    gratuits = [cle for cle, prix in REGISTRE.items() if prix.gratuit]
    assert gratuits and all(cle.startswith("mistral:") for cle in gratuits)
    assert all(p.requetes_par_minute > 0 and p.jetons_par_minute > 0 for p in REGISTRE.values())
    sonnet = tarif("anthropic:claude-sonnet-5-5")
    attendu = (sonnet.prix_entree_eur_mtok * 1000 + sonnet.prix_sortie_eur_mtok * 500) / 1_000_000
    assert cout_estime_eur("anthropic:claude-sonnet-5-5", 1000, 500) == attendu
    # Story 6.5 : Haiku 5.5, 0,10 $ et 0,50 $ par million de jetons, 50 requêtes par minute.
    haiku = tarif("anthropic:claude-haiku-5-5")
    assert (haiku.prix_entree_eur_mtok, haiku.prix_sortie_eur_mtok) == (
        Decimal("0.1") * TAUX_USD_EUR,
        Decimal("0.5") * TAUX_USD_EUR,
    )
    assert haiku.requetes_par_minute == 50


def test_adaptateur_ferme_sa_boucle() -> None:
    adaptateur = fournisseur_scripte("mistral", TransportScripte([]))
    assert isinstance(adaptateur, FournisseurPydanticAI)
    adaptateur.fermer()


@pytest.mark.parametrize("fournisseur", FOURNISSEURS)
def test_429_en_cours_d_agent_ne_rejoue_pas_les_outils(fournisseur: str) -> None:
    transport = TransportScripte(
        [
            reponse_outil(fournisseur, "get_meteo", {"entite": "ENT-A"}, "id0000002"),
            trop_de_requetes(fournisseur, "2"),
            reponse_texte(fournisseur, "ENT-A est rouge."),
        ]
    )
    appels: list[Mapping[str, JsonValue]] = []
    attentes: list[float] = []
    reponse = fournisseur_scripte(fournisseur, transport, attentes=attentes).executer_agent(
        (MessageAgent(role="utilisateur", contenu="Météo de ENT-A ?"),), (_outil(appels),), AGENT
    )
    assert reponse.texte == "ENT-A est rouge."
    assert appels == [{"entite": "ENT-A"}]
    assert 2.0 in attentes


def test_exception_d_un_outil_traduite() -> None:
    transport = TransportScripte(
        [reponse_outil("anthropic", "get_meteo", {"entite": "ENT-A"}, "id0000002")]
    )

    def casse(arguments: Mapping[str, JsonValue]) -> str:
        raise KeyError("ENT-A")

    outil = OutilAgent("get_meteo", "Météo.", _Arguments, casse)
    with pytest.raises(UsineErreur, match="get_meteo"):
        fournisseur_scripte("anthropic", transport).executer_agent(
            (MessageAgent(role="utilisateur", contenu="?"),), (outil,), AGENT
        )


def test_message_assistant_vide_refuse() -> None:
    messages = (
        MessageAgent(role="utilisateur", contenu="?"),
        MessageAgent(role="assistant", contenu=""),
        MessageAgent(role="utilisateur", contenu="?"),
    )
    with pytest.raises(UsineErreur, match="assistant"):
        fournisseur_scripte("mistral", TransportScripte([])).executer_agent(messages, (), AGENT)


def test_adaptateur_ferme_refuse_l_appel() -> None:
    adaptateur = fournisseur_scripte("mistral", TransportScripte([]))
    adaptateur.fermer()
    with pytest.raises(UsineErreur, match="fermé"):
        adaptateur.generer_structure("p", Sortie, STRUCTURE)


def _avec_temperature(
    fournisseur: str, modele: str, transport: TransportScripte, temperature: float
) -> FournisseurPydanticAI:
    config = ConfigLLM(
        fournisseur=fournisseur,
        modele=modele,
        plafond_cout_passage_eur=Decimal(1),
        temperature=temperature,
    )
    return construire_fournisseur_llm(config, "k", transport.client(), lambda _: None)


def test_temperature_de_la_configuration_sauf_explicite() -> None:
    """Report 6.1 : la température vient de `config/llm.yaml` ; un appel explicite prime."""
    transport = TransportScripte([_sortie("mistral"), _sortie("mistral")])
    adaptateur = _avec_temperature("mistral", "mistral-large-latest", transport, 0.3)
    adaptateur.generer_structure("Classe DEMO-1.", Sortie, STRUCTURE)
    explicite = ParametresAppel(tache=Tache.classification, max_jetons_sortie=300, temperature=0.7)
    adaptateur.generer_structure("Classe DEMO-1.", Sortie, explicite)
    assert [corps["temperature"] for corps in transport.requetes] == [0.3, 0.7]


@pytest.mark.parametrize(
    ("modele", "accepte"),
    [
        ("claude-sonnet-5-5", False),
        ("claude-opus-5-5", False),
        ("claude-haiku-5-5", False),
        ("claude-haiku-4-5", True),
    ],
)
def test_temperature_decidee_par_le_modele(modele: str, accepte: bool) -> None:
    """Claude Haiku, Sonnet et Opus 5.5 refusent la température : elle n'est pas envoyée."""
    assert tarif(f"anthropic:{modele}").temperature is accepte
    transport = TransportScripte([_sortie("anthropic")])
    _avec_temperature("anthropic", modele, transport, 0.2).generer_structure(
        "Classe DEMO-1.", Sortie, STRUCTURE
    )
    (corps,) = transport.requetes
    assert ("temperature" in corps) is accepte
    if accepte:
        assert corps["temperature"] == 0.2
