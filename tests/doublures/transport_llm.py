"""Faux transport HTTP des API Anthropic, Mistral et llama-server : réponses enregistrées.

`TransportScripte` rejoue une liste de réponses dans l'ordre et garde le corps JSON de chaque
requête. Les fonctions `anthropic_*` et `mistral_*` produisent les réponses au format des API
publiques (Messages d'Anthropic, Chat Completions de Mistral et d'OpenAI, servi par llama-server).
"""

import json
from collections.abc import Mapping
from typing import Any

import httpx2

from usine.adaptateurs.llm import FournisseurPydanticAI, construire_fournisseur_llm
from usine.contrats.config import ConfigLLM

MODELES = {
    "anthropic": "claude-sonnet-5-5",
    "mistral": "mistral-large-latest",
    "llama": "qwen3-8b-q4_k_m",
}
"""Modèle par défaut de chaque fournisseur dans les tests."""


def _noms_outils(corps: Mapping[str, Any]) -> set[str]:
    """Noms des outils d'une requête Anthropic, Mistral ou OpenAI (`function.name`)."""
    noms = set()
    for outil in corps.get("tools") or ():
        noms.add(outil.get("name") or outil.get("function", {}).get("name"))
    return noms


class TransportScripte:
    """Rejoue `reponses` dans l'ordre ; une requête de trop fait échouer le test.

    Une requête qui déclare l'outil de sortie `reponse` (mode Tool Output) est servie par
    `structure` si cette file est fournie, sinon par `reponses`.
    """

    def __init__(
        self, reponses: list[httpx2.Response], structure: list[httpx2.Response] | None = None
    ) -> None:
        self._reponses = list(reponses)
        self._structure = list(structure) if structure is not None else None
        self.requetes: list[dict[str, Any]] = []
        self.urls: list[str] = []

    def __call__(self, requete: httpx2.Request) -> httpx2.Response:
        self.urls.append(str(requete.url))
        corps = json.loads(requete.content or b"{}")
        self.requetes.append(corps)
        file = self._reponses
        if self._structure is not None and "reponse" in _noms_outils(corps):
            file = self._structure
        if not file:
            raise AssertionError(f"requête non scriptée : {requete.url}")
        return file.pop(0)

    def client(self) -> httpx2.AsyncClient:
        """Client HTTP asynchrone branché sur ce transport."""
        return httpx2.AsyncClient(transport=httpx2.MockTransport(self))


def _usage_anthropic() -> dict[str, int]:
    return {"input_tokens": 12, "output_tokens": 7}


def anthropic_outil(
    nom: str, arguments: Mapping[str, Any], id_appel: str = "toolu_1"
) -> httpx2.Response:
    """Réponse Messages qui demande l'outil `nom`."""
    return httpx2.Response(
        200,
        json={
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": MODELES["anthropic"],
            "content": [
                {"type": "tool_use", "id": id_appel, "name": nom, "input": dict(arguments)}
            ],
            "stop_reason": "tool_use",
            "stop_sequence": None,
            "usage": _usage_anthropic(),
        },
    )


def anthropic_texte(texte: str) -> httpx2.Response:
    """Réponse Messages en texte libre."""
    return httpx2.Response(
        200,
        json={
            "id": "msg_2",
            "type": "message",
            "role": "assistant",
            "model": MODELES["anthropic"],
            "content": [{"type": "text", "text": texte}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": _usage_anthropic(),
        },
    )


def _chat_completions(message: dict[str, Any], fin: str, modele: str) -> httpx2.Response:
    return httpx2.Response(
        200,
        json={
            "id": "cmpl-1",
            "object": "chat.completion",
            "created": 1760000000,
            "model": modele,
            "choices": [{"index": 0, "message": message, "finish_reason": fin}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 7, "total_tokens": 19},
        },
    )


def _mistral(message: dict[str, Any], fin: str) -> httpx2.Response:
    return _chat_completions(message, fin, MODELES["mistral"])


def mistral_outil(
    nom: str, arguments: Mapping[str, Any], id_appel: str = "abc123def"
) -> httpx2.Response:
    """Réponse Chat Completions qui demande l'outil `nom`."""
    appel = {
        "id": id_appel,
        "type": "function",
        "function": {"name": nom, "arguments": json.dumps(dict(arguments))},
    }
    return _mistral({"role": "assistant", "content": "", "tool_calls": [appel]}, "tool_calls")


def mistral_texte(texte: str) -> httpx2.Response:
    """Réponse Chat Completions en texte libre."""
    return _mistral({"role": "assistant", "content": texte, "tool_calls": None}, "stop")


def llama_outil(
    nom: str, arguments: Mapping[str, Any], id_appel: str = "abc123def"
) -> httpx2.Response:
    """Réponse Chat Completions d'OpenAI (llama-server) qui demande l'outil `nom`."""
    appel = {
        "id": id_appel,
        "type": "function",
        "function": {"name": nom, "arguments": json.dumps(dict(arguments))},
    }
    message = {"role": "assistant", "content": None, "tool_calls": [appel]}
    return _chat_completions(message, "tool_calls", MODELES["llama"])


def llama_texte(texte: str) -> httpx2.Response:
    """Réponse Chat Completions d'OpenAI (llama-server) en texte libre."""
    message = {"role": "assistant", "content": texte}
    return _chat_completions(message, "stop", MODELES["llama"])


def trop_de_requetes(fournisseur: str, retry_after: str | None) -> httpx2.Response:
    """Réponse 429, avec `Retry-After` si fourni."""
    entetes = {"retry-after": retry_after} if retry_after is not None else {}
    corps: dict[str, Any]
    if fournisseur == "anthropic":
        corps = {"type": "error", "error": {"type": "rate_limit_error", "message": "trop"}}
    elif fournisseur == "llama":
        corps = {
            "error": {
                "message": "Rate limit exceeded",
                "type": "rate_limit_error",
                "code": "rate_limit_exceeded",
            }
        }
    else:
        corps = {
            "object": "error",
            "message": "Requests rate limit exceeded",
            "type": "rate_limited",
        }
    return httpx2.Response(429, headers=entetes, json=corps)


def reponse_outil(
    fournisseur: str, nom: str, arguments: Mapping[str, Any], id_appel: str
) -> httpx2.Response:
    """`anthropic_outil` ou `mistral_outil` selon `fournisseur`."""
    if fournisseur == "anthropic":
        return anthropic_outil(nom, arguments, id_appel)
    if fournisseur == "llama":
        return llama_outil(nom, arguments, id_appel)
    return mistral_outil(nom, arguments, id_appel)


def reponse_texte(fournisseur: str, texte: str) -> httpx2.Response:
    """`anthropic_texte` ou `mistral_texte` selon `fournisseur`."""
    if fournisseur == "anthropic":
        return anthropic_texte(texte)
    return llama_texte(texte) if fournisseur == "llama" else mistral_texte(texte)


def fournisseur_scripte(
    fournisseur: str,
    transport: TransportScripte,
    tentatives_max: int = 5,
    attentes: list[float] | None = None,
    url_llama: str | None = None,
) -> FournisseurPydanticAI:
    """Adaptateur réel de `fournisseur`, branché sur `transport` ; attentes notées, sans dormir."""
    horloge = [0.0]
    notees = attentes if attentes is not None else []

    def attendre(secondes: float) -> None:
        notees.append(secondes)
        horloge[0] += secondes

    config = ConfigLLM(
        fournisseur=fournisseur,
        modele=MODELES[fournisseur],
        plafond_cout_passage_eur=1,
        tentatives_max=tentatives_max,
    )
    return construire_fournisseur_llm(
        config,
        "" if fournisseur == "llama" else "cle-de-test",
        transport.client(),
        attendre,
        lambda: horloge[0],
        url_llama=url_llama,
    )
