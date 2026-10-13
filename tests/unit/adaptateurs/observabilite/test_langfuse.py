"""Observabilité externe : traces LLM envoyées à Langfuse, pseudonymisées (Story 6.13)."""

import json
import sys
import types
from typing import Any

import pytest
from pydantic import SecretStr

from outils.balayer_sm7 import balayer
from tests.doublures.fournisseur_factice import FournisseurFactice
from tests.unit.ia.espions import NUMERO_COMPTE, CacheMemoire, horloge_espion, pseudonymiseur
from tests.unit.ia.test_passerelle import CONTEXTE, PARAMETRES, PROMPT, Controleur, _reponse
from usine.adaptateurs.observabilite import ObservateurLangfuse, construire_observateur
from usine.composition import _observateur_langfuse
from usine.config import Secrets
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import ReponseExplication
from usine.ia.passerelle import Passerelle


class ClientSimule:
    """Client Langfuse simulé : garde chaque observation démarrée."""

    def __init__(self, echec: bool = False) -> None:
        self.observations: list[dict[str, Any]] = []
        self.terminees = 0
        self.vidages = 0
        self._echec = echec

    def start_observation(self, **arguments: Any) -> "ClientSimule":
        if self._echec:
            raise RuntimeError(f"Langfuse indisponible ({NUMERO_COMPTE})")
        self.observations.append(arguments)
        return self

    def end(self) -> None:
        self.terminees += 1

    def flush(self) -> None:
        self.vidages += 1


def _passerelle(client: ClientSimule) -> Passerelle:
    return Passerelle(
        FournisseurFactice([_reponse()], version_modele="factice:modele-1"),
        pseudonymiseur(),
        CacheMemoire(),
        horloge_espion([]),
        observateur=ObservateurLangfuse(client),
    )


def _appeler(passerelle: Passerelle) -> Any:
    return passerelle.executer_structure(
        PROMPT, ReponseExplication, PARAMETRES, CONTEXTE, Controleur([])
    )


def test_la_trace_est_aussi_envoyee_a_langfuse() -> None:
    client = ClientSimule()
    resultat = _appeler(_passerelle(client))
    (observation,) = client.observations
    trace = resultat.trace
    assert observation["as_type"] == "generation"
    assert observation["input"] == trace.entree_pseudonymisee
    assert observation["output"] == trace.sortie
    assert observation["model"] == "factice:modele-1"
    assert observation["metadata"]["passage_id"] == trace.passage_id
    assert (client.terminees, client.vidages) == (1, 1)


def test_balayage_sm7_des_donnees_envoyees_a_langfuse() -> None:
    client = ClientSimule()
    _appeler(_passerelle(client))
    textes = [
        ("langfuse", json.dumps(o, ensure_ascii=False, default=str)) for o in client.observations
    ]
    bilan = balayer(textes, [("COMPTE", NUMERO_COMPTE)])
    assert bilan.fuites == ()
    assert bilan.jetons > 0  # des identifiants ont bien été remplacés


def test_balayage_sm7_detecte_une_fuite_vers_langfuse() -> None:
    texte = json.dumps({"input": f"virement sur {NUMERO_COMPTE.replace(' ', '')}"})
    bilan = balayer([("langfuse", texte)], [("COMPTE", NUMERO_COMPTE)])
    assert [f.type for f in bilan.fuites] == ["COMPTE"]


def test_un_client_en_panne_ne_fait_pas_echouer_l_appel(caplog: pytest.LogCaptureFixture) -> None:
    resultat = _appeler(_passerelle(ClientSimule(echec=True)))
    assert NUMERO_COMPTE in resultat.sortie.texte  # ré-identification locale intacte
    assert NUMERO_COMPTE not in caplog.text  # le contenu n'est pas journalisé


def test_un_observateur_qui_leve_ne_fait_pas_echouer_l_appel() -> None:
    def casse(_: object) -> None:
        raise RuntimeError("boum")

    passerelle = Passerelle(
        FournisseurFactice([_reponse()]),
        pseudonymiseur(),
        CacheMemoire(),
        horloge_espion([]),
        observateur=casse,
    )
    assert _appeler(passerelle).sortie.texte


def test_envoi_desactive_par_defaut() -> None:
    assert Secrets().usine_langfuse is False
    assert _observateur_langfuse(Secrets(_env_file=None)) is None


def test_envoi_active_sans_cle_nomme_les_variables() -> None:
    secrets = Secrets(_env_file=None, usine_langfuse=True, langfuse_host="http://localhost:3000")
    with pytest.raises(UsineErreur, match="LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY"):
        _observateur_langfuse(secrets)


def test_construction_sur_le_client_langfuse(monkeypatch: pytest.MonkeyPatch) -> None:
    recus: dict[str, Any] = {}

    class Langfuse(ClientSimule):
        def __init__(self, **arguments: Any) -> None:
            super().__init__()
            recus.update(arguments)

    module = types.ModuleType("langfuse")
    module.Langfuse = Langfuse  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "langfuse", module)
    secrets = Secrets(
        _env_file=None,
        usine_langfuse=True,
        langfuse_host="http://localhost:3000",
        langfuse_public_key="pk",
        langfuse_secret_key=SecretStr("sk"),
    )
    assert _observateur_langfuse(secrets) is not None
    assert recus == {"public_key": "pk", "secret_key": "sk", "host": "http://localhost:3000"}


def test_paquet_langfuse_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "langfuse", None)
    with pytest.raises(UsineErreur, match="uv sync --group bonus"):
        construire_observateur("http://h", "pk", "sk")
