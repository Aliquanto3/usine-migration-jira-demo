"""Écran Agent : libellés et mise en forme d'une réponse contrôlée (FR-39, FR-40)."""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Protocol

from usine.contrats.format import formater_date
from usine.contrats.llm import ReponseAgent, ReponseAgentEnregistree, StatutControle


class Session(Protocol):
    """Ce que l'écran utilise d'une `SessionAgent` (`ui/cli.session_agent`)."""

    @property
    def passage_id(self) -> str:
        """Passage consulté."""
        ...

    def repondre(self, question: str) -> ReponseAgent:
        """Réponse contrôlée à `question`."""
        ...

    def fermer(self) -> None:
        """Ferme les fournisseurs de la session."""
        ...


AUCUN_PASSAGE = "Aucun Passage publié : lancer la Chaîne pour que l'Agent puisse le consulter."

QUESTION_DEMO = "Quelle Entité risque de passer au rouge, et pourquoi ?"
"""Question de la démo, proposée dans le champ de saisie."""

LIBELLE_QUESTION = "Question à l'Agent"
LIBELLE_ENVOYER = "Poser la question"

LEGENDE = (
    "L'Agent ne lit que le dernier Passage publié, par des outils en lecture seule ; chaque"
    " chiffre et chaque ticket de sa réponse est contrôlé contre les résultats de ces outils."
)

MESSAGE_REPLI = (
    "En Mode repli, l'Agent ne s'adresse à aucun LLM : choisir une question enregistrée lors"
    " d'une répétition, sa réponse contrôlée est rejouée telle quelle."
)

LIBELLE_CHOIX = "Question enregistrée"
LIBELLE_REJOUER = "Rejouer la réponse"
REFUS_REPLI = "Mode repli : réponses enregistrées de l'Agent refusées"


def mention_repli(enregistree: ReponseAgentEnregistree) -> str:
    """Mention « Mode repli » d'une réponse rejouée : date d'enregistrement et Passage."""
    return (
        f"Mode repli : réponse enregistrée le {formater_date(enregistree.horodatage.date())}"
        f" sur le Passage {enregistree.passage_id}, rejouée sans LLM"
    )


LIBELLES_STATUT: Mapping[StatutControle, str] = MappingProxyType(
    {
        StatutControle.non_controle: "non contrôlée",
        StatutControle.conforme: "conforme : chiffres et tickets vérifiés",
        StatutControle.corrige: "corrigée",
        StatutControle.rejete: "rejetée par le contrôle",
    }
)
"""Libellé du statut de contrôle d'une réponse."""


def texte_statut(reponse: ReponseAgent) -> str:
    """Statut de contrôle de la réponse, en français."""
    return f"Contrôle : {LIBELLES_STATUT[reponse.statut_controle]}"


def texte_outils(reponse: ReponseAgent) -> str:
    """Outils appelés, dans l'ordre, ou mention explicite d'aucun appel."""
    if not reponse.outils_appeles:
        return "Outils appelés : aucun"
    return f"Outils appelés : {', '.join(reponse.outils_appeles)}"
