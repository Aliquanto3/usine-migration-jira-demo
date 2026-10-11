"""`FournisseurFactice` : fournisseur LLM scripté, déterministe et sans réseau (AD-13)."""

from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from pydantic import BaseModel, JsonValue

from usine.contrats.erreurs import UsineErreur
from usine.contrats.llm import (
    AppelOutil,
    MessageAgent,
    OutilAgent,
    ParametresAppel,
    ReponseAgentBrute,
    ReponseStructuree,
)


@dataclass(frozen=True)
class ReponseAgentScriptee:
    """Tour d'Agent scripté : appels d'outils demandés, puis texte final."""

    texte: str
    appels: tuple[AppelOutil, ...] = ()


@dataclass(frozen=True)
class AppelEnregistre:
    """Appel reçu par le fournisseur factice."""

    methode: str
    entree: str | tuple[MessageAgent, ...]
    parametres: ParametresAppel
    outils: tuple[str, ...] = ()


def _jetons(texte: str) -> int:
    return len(texte.split())


class FournisseurFactice:
    """Rejoue des réponses scriptées dans l'ordre et enregistre chaque appel dans `appels`."""

    def __init__(
        self,
        reponses_structurees: Iterable[BaseModel] = (),
        reponses_agent: Iterable[ReponseAgentScriptee] = (),
        version_modele: str = "factice:modele",
    ) -> None:
        self._structurees: deque[BaseModel] = deque(reponses_structurees)
        self._agent: deque[ReponseAgentScriptee] = deque(reponses_agent)
        self._version_modele = version_modele
        self.appels: list[AppelEnregistre] = []

    @property
    def version_modele(self) -> str:
        """Version de modèle annoncée."""
        return self._version_modele

    def generer_structure[T: BaseModel](
        self, prompt: str, schema: type[T], parametres: ParametresAppel
    ) -> ReponseStructuree[T]:
        """Renvoie la prochaine réponse structurée scriptée, qui doit être un `schema`."""
        self.appels.append(AppelEnregistre("generer_structure", prompt, parametres))
        if not self._structurees:
            raise UsineErreur("FournisseurFactice : plus de réponse structurée scriptée")
        sortie = self._structurees.popleft()
        if not isinstance(sortie, schema):
            raise UsineErreur(
                f"FournisseurFactice : réponse scriptée {type(sortie).__name__},"
                f" schéma demandé {schema.__name__}"
            )
        brut = sortie.model_dump_json()
        return ReponseStructuree[T](
            sortie=sortie,
            brut=brut,
            jetons_entree=_jetons(prompt),
            jetons_sortie=_jetons(brut),
            version_modele=self._version_modele,
        )

    def executer_agent(
        self,
        messages: Sequence[MessageAgent],
        outils: Sequence[OutilAgent],
        parametres: ParametresAppel,
    ) -> ReponseAgentBrute:
        """Joue le prochain tour scripté en n'appelant que les `outils` reçus."""
        recus = tuple(messages)
        self.appels.append(
            AppelEnregistre("executer_agent", recus, parametres, tuple(o.nom for o in outils))
        )
        if not self._agent:
            raise UsineErreur("FournisseurFactice : plus de réponse d'Agent scriptée")
        script = self._agent.popleft()
        par_nom = {outil.nom: outil for outil in outils}
        conversation = list(recus)
        if script.appels:
            conversation.append(
                MessageAgent(role="assistant", contenu="", appels_outils=script.appels)
            )
        for appel in script.appels:
            outil = par_nom.get(appel.nom_outil)
            if outil is None:
                raise UsineErreur(
                    f"FournisseurFactice : outil inconnu {appel.nom_outil!r}"
                    f" (reçus : {', '.join(par_nom) or 'aucun'})"
                )
            arguments: Mapping[str, JsonValue] = appel.arguments
            resultat = outil.executer(arguments)
            conversation.append(
                MessageAgent(role="outil", contenu=resultat, id_appel=appel.id_appel)
            )
        conversation.append(MessageAgent(role="assistant", contenu=script.texte))
        return ReponseAgentBrute(
            texte=script.texte,
            messages=tuple(conversation),
            jetons_entree=sum(_jetons(m.contenu) for m in recus),
            jetons_sortie=_jetons(script.texte),
            version_modele=self._version_modele,
        )
