"""`FournisseurLLM` sur Pydantic AI : Anthropic, Mistral et llama.cpp derrière le même port (AD-13).

`generer_structure` utilise le mode Tool Output avec le schéma demandé, sans outil ;
`executer_agent` utilise `output_type=str` avec les seuls outils reçus. Un appel ne combine
jamais les deux. La reprise sur 429 (attente croissante, `Retry-After` respecté, tentatives
maximales de `config/llm.yaml`) et l'espacement par modèle du registre se font ici. Les
reprises internes des SDK sont coupées : seule cette boucle décide d'une nouvelle tentative.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable, Coroutine, Mapping, Sequence
from typing import Any

import anthropic
import openai
from mistralai.client import Mistral
from pydantic import BaseModel, JsonValue
from pydantic_ai import Agent, ToolOutput
from pydantic_ai.exceptions import AgentRunError, ModelAPIError, ModelHTTPError, UserError
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelRequestPart,
    ModelResponse,
    ModelResponsePart,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import Model, ModelRequestParameters
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.mistral import MistralModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.wrapper import WrapperModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.mistral import MistralProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.tools import Tool

from usine.adaptateurs.llm.registre import tarif
from usine.contrats.config import ConfigLLM
from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import (
    AppelOutil,
    MessageAgent,
    OutilAgent,
    ParametresAppel,
    ReponseAgentBrute,
    ReponseStructuree,
)
from usine.contrats.versions import version_modele

FOURNISSEURS = ("anthropic", "mistral", "llama")
"""Valeurs admises de `fournisseur` dans `config/llm.yaml`."""

VARIABLES_CLE = {"anthropic": "ANTHROPIC_API_KEY", "mistral": "MISTRAL_API_KEY"}
"""Variable d'environnement de la clé d'API de chaque fournisseur distant (AD-19, H-23).

`llama` (llama-server local) n'a pas de clé.
"""

URL_LLAMA_DEFAUT = "http://127.0.0.1:8080/v1"
"""Adresse de llama-server si `USINE_LLAMA_URL` n'est pas défini."""

ATTENTE_BASE_S = 1.0
"""Première attente après un 429 sans `Retry-After` ; chaque attente double au moins."""

ATTENTE_MAX_S = 60.0
"""Plafond d'une attente, quel que soit `Retry-After`."""

NOM_SORTIE = "reponse"
"""Nom de l'outil de sortie du mode Tool Output."""


def _retry_after(entetes: Mapping[str, str] | None) -> float:
    """Secondes de `Retry-After` (forme numérique), 0 si absent ou illisible."""
    valeur = (entetes or {}).get("retry-after", "")
    try:
        return max(0.0, float(valeur))
    except ValueError:
        return 0.0


def _vers_pydantic_ai(messages: Sequence[MessageAgent]) -> list[ModelMessage]:
    """Conversation du contrat → historique Pydantic AI (requêtes et réponses alternées)."""
    historique: list[ModelMessage] = []
    noms_outils: dict[str, str] = {}
    requete: list[ModelRequestPart] = []
    for message in messages:
        if message.role == "assistant":
            if requete:
                historique.append(ModelRequest(parts=requete))
                requete = []
            parties: list[ModelResponsePart] = []
            if message.contenu:
                parties.append(TextPart(content=message.contenu))
            for appel in message.appels_outils:
                noms_outils[appel.id_appel] = appel.nom_outil
                parties.append(
                    ToolCallPart(
                        tool_name=appel.nom_outil,
                        args=dict(appel.arguments),
                        tool_call_id=appel.id_appel,
                    )
                )
            if not parties:
                raise UsineErreur("message « assistant » sans contenu ni appel d'outil")
            historique.append(ModelResponse(parts=parties))
        elif message.role == "systeme":
            requete.append(SystemPromptPart(content=message.contenu))
        elif message.role == "utilisateur":
            requete.append(UserPromptPart(content=message.contenu))
        else:
            id_appel = message.id_appel or ""
            if id_appel not in noms_outils:
                raise UsineErreur(
                    f"message « outil » {id_appel!r} sans appel d'outil qui le précède"
                )
            requete.append(
                ToolReturnPart(
                    tool_name=noms_outils[id_appel], content=message.contenu, tool_call_id=id_appel
                )
            )
    if requete:
        historique.append(ModelRequest(parts=requete))
    if not historique or not isinstance(historique[-1], ModelRequest):
        raise UsineErreur("conversation d'Agent vide ou terminée par un message « assistant »")
    return historique


def _depuis_pydantic_ai(historique: Sequence[ModelMessage]) -> tuple[MessageAgent, ...]:
    """Historique Pydantic AI → conversation du contrat."""
    messages: list[MessageAgent] = []
    for element in historique:
        if isinstance(element, ModelResponse):
            texte = "".join(p.content for p in element.parts if isinstance(p, TextPart))
            appels = tuple(
                AppelOutil(
                    id_appel=p.tool_call_id,
                    nom_outil=p.tool_name,
                    arguments=p.args_as_dict(),
                )
                for p in element.parts
                if isinstance(p, ToolCallPart)
            )
            messages.append(MessageAgent(role="assistant", contenu=texte, appels_outils=appels))
            continue
        for partie in element.parts:
            if isinstance(partie, SystemPromptPart):
                messages.append(MessageAgent(role="systeme", contenu=partie.content))
            elif isinstance(partie, UserPromptPart) and isinstance(partie.content, str):
                messages.append(MessageAgent(role="utilisateur", contenu=partie.content))
            elif isinstance(partie, ToolReturnPart):
                messages.append(
                    MessageAgent(
                        role="outil",
                        contenu=partie.model_response_str(),
                        id_appel=partie.tool_call_id,
                    )
                )
            elif isinstance(partie, RetryPromptPart) and partie.tool_name is not None:
                # Relance d'un appel d'outil invalide : l'appel garde sa réponse « outil ».
                messages.append(
                    MessageAgent(
                        role="outil", contenu=partie.model_response(), id_appel=partie.tool_call_id
                    )
                )
    return tuple(messages)


def _outil(outil: OutilAgent) -> Tool[None]:
    """Outil reçu → outil Pydantic AI, au schéma d'arguments de l'outil."""

    def executer(**arguments: JsonValue) -> str:
        try:
            return outil.executer(arguments)
        except UsineErreur:
            raise
        except Exception as exc:
            raise UsineErreur(f"outil {outil.nom!r} en échec ({type(exc).__name__})") from None

    return Tool.from_schema(
        executer, outil.nom, outil.description, outil.arguments.model_json_schema()
    )


class _ModeleRepris(WrapperModel):
    """Modèle dont chaque requête passe par la reprise de l'adaptateur (429, espacement)."""

    def __init__(
        self,
        modele: Model,
        requete: Callable[
            [Callable[[], Coroutine[Any, Any, ModelResponse]]], Awaitable[ModelResponse]
        ],
    ) -> None:
        super().__init__(modele)
        self._requete_reprise = requete

    async def request(
        self,
        messages: list[ModelMessage],
        model_settings: ModelSettings | None,
        model_request_parameters: ModelRequestParameters,
    ) -> ModelResponse:
        return await self._requete_reprise(
            lambda: self.wrapped.request(messages, model_settings, model_request_parameters)
        )


class FournisseurPydanticAI:
    """Adaptateur `FournisseurLLM` commun aux fournisseurs servis par Pydantic AI."""

    def __init__(
        self,
        fournisseur: str,
        modele: Model,
        nom_modele: str,
        tentatives_max: int,
        attendre: Callable[[float], None] = time.sleep,
        horloge: Callable[[], float] = time.monotonic,
        temperature: float | None = 0.0,
    ) -> None:
        """`temperature` : valeur de `config/llm.yaml`, `None` si le modèle refuse ce réglage.

        `ParametresAppel.temperature` ne prime que s'il est fixé explicitement par l'appelant.
        """
        self._temperature = temperature
        self._version = version_modele(fournisseur, nom_modele)
        self._espacement = tarif(self._version).espacement_s
        self._modele = _ModeleRepris(modele, self._requete)
        self._tentatives_max = tentatives_max
        self._attendre = attendre
        self._horloge = horloge
        self._dernier_appel: float | None = None
        self._boucle = asyncio.new_event_loop()

    @property
    def version_modele(self) -> str:
        """`fournisseur:modele`."""
        return self._version

    def fermer(self) -> None:
        """Ferme la boucle d'évènements propre à l'adaptateur."""
        self._boucle.close()

    def _espacer(self) -> None:
        """Attend l'espacement minimal du registre depuis la requête précédente au modèle."""
        if self._dernier_appel is not None:
            reste = self._espacement - (self._horloge() - self._dernier_appel)
            if reste > 0:
                self._attendre(reste)
        self._dernier_appel = self._horloge()

    async def _requete[R](self, appel: Callable[[], Coroutine[Any, Any, R]]) -> R:
        """Une requête au modèle, espacée et reprise sur 429 seule (outils jamais rejoués).

        L'attente bloque la boucle propre à l'adaptateur, qui ne sert qu'à cet appel.
        """
        attente = ATTENTE_BASE_S / 2
        for tentative in range(self._tentatives_max):
            self._espacer()
            try:
                return await appel()
            except ModelHTTPError as exc:
                if exc.status_code != 429:
                    raise UsineErreur(
                        f"{self._version} : erreur HTTP {exc.status_code} du fournisseur LLM"
                    ) from None
                if tentative + 1 >= self._tentatives_max:
                    raise UsineErreur(
                        f"{self._version} : débit dépassé (429) après {self._tentatives_max}"
                        " tentatives ; voir « tentatives_max » dans config/llm.yaml"
                    ) from None
                # Croissante : au moins le double de la précédente, et jamais sous Retry-After.
                attente = min(max(_retry_after(exc.headers), 2 * attente), ATTENTE_MAX_S)
                self._attendre(attente)
        raise UsineErreur(f"{self._version} : aucune tentative (tentatives_max nul)")

    def _executer[R](self, execution: Coroutine[Any, Any, R]) -> R:
        """Exécute une conversation ; toute erreur du fournisseur devient une `UsineErreur`."""
        if self._boucle.is_closed():
            execution.close()
            raise UsineErreur(f"{self._version} : adaptateur fermé")
        try:
            return self._boucle.run_until_complete(execution)
        except UsineErreur:
            raise
        except (
            ModelAPIError,
            AgentRunError,
            UserError,
            anthropic.APIError,
            openai.APIError,
            RuntimeError,
        ) as exc:
            raise UsineErreur(
                f"{self._version} : appel au fournisseur LLM en échec ({type(exc).__name__})"
            ) from None

    def _reglages(self, parametres: ParametresAppel) -> ModelSettings:
        reglages = ModelSettings(max_tokens=parametres.max_jetons_sortie)
        if self._temperature is not None:
            explicite = "temperature" in parametres.model_fields_set
            reglages["temperature"] = parametres.temperature if explicite else self._temperature
        return reglages

    def generer_structure[T: BaseModel](
        self, prompt: str, schema: type[T], parametres: ParametresAppel
    ) -> ReponseStructuree[T]:
        """Mode Tool Output avec `schema`, sans aucun autre outil."""
        agent: Agent[None, T] = Agent(
            self._modele,
            output_type=ToolOutput(schema, name=NOM_SORTIE),
            model_settings=self._reglages(parametres),
        )
        resultat = self._executer(agent.run(prompt))
        usage = resultat.usage
        return ReponseStructuree[T](
            sortie=resultat.output,
            brut=resultat.output.model_dump_json(),
            jetons_entree=usage.input_tokens,
            jetons_sortie=usage.output_tokens,
            version_modele=self._version,
        )

    def executer_agent(
        self,
        messages: Sequence[MessageAgent],
        outils: Sequence[OutilAgent],
        parametres: ParametresAppel,
    ) -> ReponseAgentBrute:
        """`output_type=str`, avec les seuls `outils` reçus ; un outil inconnu est refusé."""
        historique = _vers_pydantic_ai(messages)
        noms = {outil.nom for outil in outils}
        agent: Agent[None, str] = Agent(
            self._modele,
            output_type=str,
            tools=[_outil(outil) for outil in outils],
            model_settings=self._reglages(parametres),
        )

        async def tour() -> tuple[str, list[ModelMessage], int, int]:
            async with agent.iter(message_history=historique) as execution:
                async for noeud in execution:
                    if Agent.is_call_tools_node(noeud):
                        inconnus = sorted(
                            p.tool_name
                            for p in noeud.model_response.parts
                            if isinstance(p, ToolCallPart) and p.tool_name not in noms
                        )
                        if inconnus:
                            raise UsineErreur(
                                f"{self._version} : outil non fourni demandé par le modèle :"
                                f" {', '.join(inconnus)}"
                            )
                resultat = execution.result
                if resultat is None:  # pragma: no cover - itération menée à son terme
                    raise UsineErreur(f"{self._version} : conversation d'Agent inachevée")
                usage = resultat.usage
                return (
                    resultat.output,
                    resultat.all_messages(),
                    usage.input_tokens,
                    usage.output_tokens,
                )

        texte, conversation, entree, sortie = self._executer(tour())
        return ReponseAgentBrute(
            texte=texte,
            messages=_depuis_pydantic_ai(conversation),
            jetons_entree=entree,
            jetons_sortie=sortie,
            version_modele=self._version,
        )


def construire_fournisseur_llm(
    config: ConfigLLM,
    cle_api: str,
    client_http: Any = None,
    attendre: Callable[[float], None] = time.sleep,
    horloge: Callable[[], float] = time.monotonic,
    url_llama: str | None = None,
) -> FournisseurPydanticAI:
    """Adaptateur du fournisseur de `config/llm.yaml`, sans modification de code (H-23).

    `client_http` remplace le client HTTP asynchrone des SDK (tests : faux transport).
    `url_llama` : adresse de llama-server (`USINE_LLAMA_URL`), `URL_LLAMA_DEFAUT` si vide ;
    `llama` n'exige aucune clé.
    """
    if config.fournisseur not in FOURNISSEURS:
        raise UsineErreur(
            f"config/llm.yaml, clé « fournisseur » : {config.fournisseur!r} inconnu ;"
            f" valeurs admises : {', '.join(FOURNISSEURS)}"
        )
    if config.fournisseur in VARIABLES_CLE and not cle_api.strip():
        raise UsineErreur(
            f"variable d'environnement {VARIABLES_CLE[config.fournisseur]} absente ou vide"
        )
    modele: Model
    if config.fournisseur == "anthropic":
        client = anthropic.AsyncAnthropic(api_key=cle_api, http_client=client_http, max_retries=0)
        modele = AnthropicModel(config.modele, provider=AnthropicProvider(anthropic_client=client))
    elif config.fournisseur == "llama":
        client_llama = openai.AsyncOpenAI(
            base_url=(url_llama or "").strip() or URL_LLAMA_DEFAUT,
            api_key=cle_api.strip() or "sans-cle",
            http_client=client_http,
            max_retries=0,
        )
        modele = OpenAIChatModel(config.modele, provider=OpenAIProvider(openai_client=client_llama))
    else:
        mistral = Mistral(api_key=cle_api, async_client=client_http)
        modele = MistralModel(config.modele, provider=MistralProvider(mistral_client=mistral))
    return FournisseurPydanticAI(
        config.fournisseur,
        modele,
        config.modele,
        config.tentatives_max,
        attendre,
        horloge,
        temperature=(
            config.temperature
            if tarif(version_modele(config.fournisseur, config.modele)).temperature
            else None
        ),
    )


__all__ = [
    "FOURNISSEURS",
    "URL_LLAMA_DEFAUT",
    "VARIABLES_CLE",
    "FournisseurPydanticAI",
    "construire_fournisseur_llm",
]
